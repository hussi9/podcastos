"""
Generation Service
Handles the orchestration of the podcast generation pipeline.
Currently wraps the legacy threaded implementation but is designed to receive
future upgrades to Celery/Redis without breaking the interface.
"""

import threading
import uuid
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from webapp.models import GenerationJob, PodcastProfile

# Store for running jobs (in-memory for now, would be Redis in prod)
# Mapping: job_id -> Thread
_RUNNING_JOBS = {}


class GenerationService:
    def __init__(self, db_session_factory):
        self.Session = db_session_factory

    def start_generation_job(self, profile_id: int, options: dict) -> str:
        """
        Creates a new generation job record and spawns the background worker.
        Returns the new job_id.
        """
        db = self.Session()
        try:
            # 1. verify profile
            profile = db.query(PodcastProfile).get(profile_id)
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")

            # 2. create job record
            job_id = f"job-{uuid.uuid4().hex[:8]}"
            job = GenerationJob(
                profile_id=profile_id,
                job_id=job_id,
                target_date=datetime.now(),
                status='pending',
                current_stage='initializing',
                progress_percent=0,
                stages_completed=[],
                stages_pending=['content_gathering', 'research', 'scripting', 'review', 'audio'],
            )
            db.add(job)
            db.commit()

            # 3. spawn worker (This is the fragile part we will eventually replace with Celery)
            thread = threading.Thread(
                target=self._run_generation_async,
                args=(job_id, profile_id, options),
                daemon=True
            )
            thread.start()
            _RUNNING_JOBS[job_id] = thread

            return job_id
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def cancel_job(self, job_id: str) -> bool:
        """
        Marks a job as cancelled.
        Note: With threads, we can't easily 'kill' the thread, but we can set the flag.
        """
        db = self.Session()
        try:
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job and job.status in ['pending', 'running']:
                job.status = 'cancelled'
                job.error_message = 'Cancelled by user'
                job.completed_at = datetime.utcnow()
                db.commit()
                return True
            return False
        finally:
            db.close()

    def get_job_status(self, job_id: str) -> dict:
        """Returns the full status dict for a job."""
        db = self.Session()
        try:
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if not job:
                return None
            
            return {
                'job_id': job.job_id,
                'status': job.status,
                'current_stage': job.current_stage,
                'progress': job.progress_percent,
                'stages_completed': job.stages_completed or [],
                'stages_pending': job.stages_pending or [],
                'stage_details': job.stage_details or {},
                'error': job.error_message,
                'episode_id': job.episode_id,
            }
        finally:
            db.close()

    # --- Internal Workers ---

    def _run_generation_async(self, job_id: str, profile_id: int, options: dict):
        """Standard wrapper to run the asyncio pipeline in a synchronous thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_pipeline_logic(job_id, profile_id, options))
        except Exception as e:
            self._handle_job_failure(job_id, str(e))
        finally:
            loop.close()
            if job_id in _RUNNING_JOBS:
                del _RUNNING_JOBS[job_id]

    async def _run_pipeline_logic(self, job_id: str, profile_id: int, options: dict):
        """
        The actual business logic for the pipeline.
        """
        from dotenv import load_dotenv
        import os
        from pathlib import Path
        from webapp.models import GenerationJob, PodcastProfile, Host, Episode, TopicHistory
        from webapp.utils.logger import get_logger
        
        logger = get_logger("GenerationService")
        load_dotenv()
        
        # localized Db session
        db = self.Session()

        def update_job(**kwargs):
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job and job.status != 'cancelled':
                for key, value in kwargs.items():
                    if key == 'stage_completed':
                        completed = list(job.stages_completed or [])
                        if value not in completed:
                            completed.append(value)
                        job.stages_completed = completed
                        
                        pending = list(job.stages_pending or [])
                        if value in pending:
                            pending.remove(value)
                        job.stages_pending = pending
                    
                    elif hasattr(job, key):
                        setattr(job, key, value)
                db.commit()

        try:
            # START
            update_job(status='running', current_stage='initializing', progress_percent=5)
            
            profile = db.query(PodcastProfile).get(profile_id)
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")

            # Fetch job for target_date
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if not job:
                 raise ValueError("Job record missing")

            # Initialize PodcastEngine
            from src.podcast_engine import PodcastEngine
            
            # Determine TTS config
            tts_provider = "google"
            if "elevenlabs" in options.get('tts_model', '').lower():
                tts_provider = "elevenlabs"
                
            engine = PodcastEngine(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                google_tts_api_key=os.getenv("GOOGLE_TTS_API_KEY"),
                elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
                tts_provider=tts_provider,
                voice_raj=None, # Use defaults for now, or fetch from profile.hosts
                voice_priya=None,
                output_dir="output"
            )
            
            update_job(current_stage='generating', progress_percent=20)
            
            if options.get('deep_research'):
                update_job(stage_details={'info': "Running deep research workflow..."})
                # Check if we are resuming or starting fresh
                # For now, just generate script only
                script = await engine.generate_script_only(
                    target_date=job.target_date,
                    topic_count=options.get('topic_count', 5),
                    target_duration_minutes=options.get('duration', 12),
                )
            else:
                update_job(stage_details={'info': "Running standard workflow..."})
                script = await engine.generate_script_only(
                    target_date=job.target_date,
                    topic_count=options.get('topic_count', 5),
                    target_duration_minutes=options.get('duration', 12),
                )

            # --- CHECK FOR STUDIO MODE ---
            if options.get('editorial_review'):
                update_job(
                    status='waiting_for_review',
                    current_stage='review', 
                    progress_percent=60,
                    stage_details={'info': f"Script generated. Waiting for review. Script ID: {script.episode_id}"}
                )
                return  # <--- STOP HERE

            # If no review needed, proceed immediately to audio
            update_job(current_stage='generating_audio', progress_percent=70)
            
            await self._finish_audio_generation(job_id, profile_id, options, engine, script.episode_id)

        except Exception as e:
            import traceback
            traceback.print_exc()
            db.rollback()
            raise e
        finally:
            db.close()

    async def _finish_audio_generation(self, job_id, profile_id, options, engine, episode_id):
        """Helper to finish audio generation after script is ready"""
        from webapp.models import GenerationJob, PodcastProfile, Episode, Segment, TopicHistory
        
        # localized Db session
        db = self.Session()
        
        def update_job(**kwargs):
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job:
                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)
                db.commit()

        try:
            update_job(current_stage='generating_audio', progress_percent=70)
            
            # 1. Generate Audio from script
            # We assume script is already saved on disk by generate_script_only
            # We need to load it to get metadata for saving later
            script_path = engine.scripts_dir / f"{episode_id}.json"
            
            # Load script
            import json
            from src.generators import PodcastScript
            
            with open(script_path, "r") as f:
                script_data = json.load(f)
            script = PodcastScript(**script_data)
            
            # Now generate audio
            audio_segments = await engine.tts.generate_episode_audio(
                script_blocks=script.to_ssml_blocks(),
                episode_id=episode_id
            )
            
            update_job(current_stage='mixing_audio', progress_percent=85)

            # 2. Mix Audio
            from src.audio.mixer import AudioMixer
            mixer = AudioMixer(assets_dir="assets")
            segment_paths = [seg.audio_path for seg in audio_segments] if audio_segments else []
            
            # Map segments for metadata
            segments_map = {}
            if audio_segments and hasattr(engine.tts, 'combine_segments_by_section'):
                 segments_map = await engine.tts.combine_segments_by_section(audio_segments, episode_id)

            mixed_path = None
            if segment_paths:
                mixed_path = mixer.mix_episode(
                    speech_segments=segment_paths,
                    output_path=str(engine.episodes_dir / f"{episode_id}.mp3"),
                    bg_music='random',
                    ducking_volume=-10
                )
            
            final_audio_path = mixed_path
            if not final_audio_path and audio_segments:
                # Fallback
                 final_audio_path = await engine.tts.combine_audio_segments(
                    segments=audio_segments,
                    output_filename=f"{episode_id}.mp3",
                )

            update_job(current_stage='saving', progress_percent=95)

            # 3. Create Metadata Objects (recreating logic from PodcastEngine.generate_episode)
            from src.podcast_engine import EpisodeMetadata, SegmentMetadata
            
            # Re-calculate segment durations
            segment_durations = {}
            if audio_segments:
                 for seg in audio_segments:
                    sec = seg.section or "unknown"
                    segment_durations[sec] = segment_durations.get(sec, 0.0) + (seg.duration_ms / 1000.0)

            # Build SegmentMetadata list
            segment_list = []
            
            # Intro
            if "intro" in segments_map:
                segment_list.append(SegmentMetadata(
                    sequence=0,
                    topic_id="intro",
                    title="Introduction",
                    audio_path=segments_map["intro"],
                    duration_seconds=segment_durations.get("intro", 0.0)
                ))

            # Segments
            for i, seg in enumerate(script.segments):
                if seg.topic_id in segments_map:
                    segment_list.append(SegmentMetadata(
                        sequence=len(segment_list),
                        topic_id=seg.topic_id,
                        title=seg.topic_title,
                        audio_path=segments_map[seg.topic_id],
                        duration_seconds=segment_durations.get(seg.topic_id, seg.duration_estimate)
                    ))
            
            # Outro
            if "outro" in segments_map:
                segment_list.append(SegmentMetadata(
                    sequence=len(segment_list),
                    topic_id="outro",
                    title="Closing",
                    audio_path=segments_map["outro"],
                    duration_seconds=segment_durations.get("outro", 0.0)
                ))

            # 4. Save to Database
            
            # Save Episode RECORD
            episode = Episode(
                profile_id=profile_id,
                episode_id=episode_id,
                title=script.episode_title,
                date=datetime.fromisoformat(script.episode_date),
                script=open(script_path).read(),
                audio_path=str(final_audio_path) if final_audio_path else None,
                duration_seconds=int(script.duration_estimate),
                summary=f"Generated episode covering {len(script.segments)} topics.",
                status='published',
                # topics_covered is a list of strings
                topics_covered=[seg.topic_title for seg in script.segments]
            )
            db.add(episode)
            db.commit() # Commit to get ID
            
            # Save Segments 
            if segment_list:
                for seg in segment_list:
                    ctype = 'topic'
                    if seg.topic_id == 'intro': ctype = 'intro'
                    elif seg.topic_id == 'outro': ctype = 'outro'
                    
                    segment_entry = Segment(
                        episode_id=episode.id,
                        sequence_index=seg.sequence,
                        topic_id=seg.topic_id,
                        title=seg.title,
                        content_type=ctype,
                        audio_path=seg.audio_path,
                        duration_seconds=seg.duration_seconds
                    )
                    db.add(segment_entry)
                db.commit()
            
            # Save Topic History
            for seg in script.segments:
                topic_history = TopicHistory(
                    episode_id=episode.id,
                    title=seg.topic_title,
                    category="General",
                )
                db.add(topic_history)
            db.commit()

            update_job(
                status='completed',
                current_stage='complete',
                progress_percent=100,
                episode_id=episode.id,
                completed_at=datetime.utcnow()
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            update_job(status='failed', error_message=str(e))
            raise e
        finally:
            db.close()

    def resume_generation_job(self, job_id: str):
        """
        Resumes a job that was in 'active review' state.
        Spawns a new thread to finish the audio generation.
        """
        db = self.Session()
        try:
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if not job or job.status != 'waiting_for_review':
                raise ValueError("Job not in correct state to resume")
                
            # Parse stage_details to get script_id/episode_id
            # We stored "Script ID: {script.episode_id}" in info
            import re
            info = job.stage_details.get('info', '')
            match = re.search(r"Script ID: ([\w-]+)", info)
            if not match:
                raise ValueError("Could not find episode ID in job details")
            
            episode_id = match.group(1)
            profile_id = job.profile_id
            
            # We don't have the original options dict easily, but we can infer or mock defaults
            # (In a real app, store options in JSON column on Job)
            options = {'topic_count': 5, 'duration': 12, 'editorial_review': False} 
            
            # Setup engine 
            import os
            from src.podcast_engine import create_engine_from_env
            # We can't await here, so we have to do it inside the thread
            
            def run_resume():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    engine = loop.run_until_complete(create_engine_from_env())
                    loop.run_until_complete(self._finish_audio_generation(job_id, profile_id, options, engine, episode_id))
                finally:
                    loop.close()
            
            thread = threading.Thread(target=run_resume, daemon=True)
            thread.start()
            
            job.status = 'resumed'
            db.commit()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e
        finally:
            db.close()
            db.close()

    def _handle_job_failure(self, job_id, error_msg):
        db = self.Session()
        try:
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job:
                job.status = 'failed'
                job.error_message = error_msg
                job.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
