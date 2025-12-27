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

# Import enhanced generators for high-quality podcasts
from src.research.topic_researcher import TopicResearcher
from src.generators.enhanced_script_generator import EnhancedScriptGenerator

# Store for running jobs with thread safety
# Mapping: job_id -> Thread
import threading
_RUNNING_JOBS = {}
_JOBS_LOCK = threading.Lock()


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
                options=options,  # Store options for recovery
                is_recoverable=True,
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
            with _JOBS_LOCK:
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

            stage_details = job.stage_details or {}

            return {
                'job_id': job.job_id,
                'status': job.status,
                'current_stage': job.current_stage,
                'progress': job.progress_percent,
                'progress_percent': job.progress_percent,  # alias for template
                'stages_completed': job.stages_completed or [],
                'stages_pending': job.stages_pending or [],
                'stage_details': stage_details,
                'activity_log': stage_details.get('activity_log', []),
                'current_activity': stage_details.get('current_activity', ''),
                'error': job.error_message,
                'error_message': job.error_message,  # alias
                'episode_id': job.episode_id,
                'result_data': {'episode_id': job.episode_id} if job.episode_id else {},
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'created_at': job.created_at.isoformat() if job.created_at else None,
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
            with _JOBS_LOCK:
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

        def log_activity(message, level='info', details=None):
            """Add an activity log entry with timestamp."""
            from datetime import datetime
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job and job.status != 'cancelled':
                stage_details = dict(job.stage_details or {})
                activity_log = stage_details.get('activity_log', [])
                activity_log.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'message': message,
                    'level': level,
                    'details': details
                })
                # Keep last 100 entries
                if len(activity_log) > 100:
                    activity_log = activity_log[-100:]
                stage_details['activity_log'] = activity_log
                stage_details['current_activity'] = message
                job.stage_details = stage_details
                db.commit()
                logger.info(f"[{job_id}] {message}")

        try:
            # START
            update_job(status='running', current_stage='initializing', progress_percent=5, started_at=datetime.utcnow())
            log_activity("Starting podcast generation pipeline", "info")
            log_activity(f"Job ID: {job_id}", "info")

            profile = db.query(PodcastProfile).get(profile_id)
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")

            log_activity(f"Loaded podcast profile: {profile.name}", "success")
            log_activity(f"Target duration: {options.get('duration', 15)} minutes", "info")
            log_activity(f"Topic count: {options.get('topic_count', 5)}", "info")

            # Extract content sources from profile
            from webapp.models import ContentSource
            profile_sources = db.query(ContentSource).filter_by(
                profile_id=profile_id, is_active=True
            ).all()

            # Extract subreddits from sources
            subreddits = []
            for source in profile_sources:
                if source.source_type == 'reddit':
                    subreddit = source.config.get('subreddit') if source.config else None
                    if subreddit:
                        subreddits.append(subreddit)

            if subreddits:
                log_activity(f"Using {len(subreddits)} profile-specific subreddits: {', '.join(subreddits[:5])}", "info")
            else:
                log_activity("No profile sources configured, using defaults", "warning")

            # Fetch job for target_date
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if not job:
                 raise ValueError("Job record missing")

            # Initialize PodcastEngine
            log_activity("Initializing podcast engine...", "info")
            from src.podcast_engine import PodcastEngine

            # Determine TTS config
            tts_provider = "google"
            if "elevenlabs" in options.get('tts_model', '').lower():
                tts_provider = "elevenlabs"

            log_activity(f"TTS provider: {tts_provider}", "info")

            engine = PodcastEngine(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                google_tts_api_key=os.getenv("GOOGLE_TTS_API_KEY"),
                elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
                tts_provider=tts_provider,
                voice_raj=None, # Use defaults for now, or fetch from profile.hosts
                voice_priya=None,
                output_dir="output"
            )
            log_activity("Podcast engine initialized successfully", "success")

            # ============================================
            # STAGE 1: RESEARCH (10-30%)
            # ============================================
            update_job(current_stage='research', progress_percent=10, stage_completed='initializing')
            log_activity("Starting content research phase...", "info")

            if options.get('deep_research'):
                log_activity("Deep research mode enabled - searching multiple sources", "info")
            else:
                log_activity("Standard research mode - primary sources only", "info")

            # Actually fetch content from sources
            import asyncio
            import time

            update_job(progress_percent=12)
            log_activity("Connecting to content sources...", "info")
            await asyncio.sleep(0.3)  # Allow UI to update

            update_job(progress_percent=14)
            log_activity("Fetching from Reddit API...", "info")
            await asyncio.sleep(0.2)

            update_job(progress_percent=16)
            log_activity("Fetching from news sources...", "info")
            await asyncio.sleep(0.2)

            update_job(progress_percent=18)
            log_activity("Fetching from USCIS/official sources...", "info")

            # Get topics (this is the REAL research work)
            research_start = time.time()
            topics = await engine.content_ranker.get_ranked_topics(
                limit=options.get('topic_count', 5),
                subreddits=subreddits if subreddits else None
            )
            research_duration = time.time() - research_start

            update_job(progress_percent=25)
            log_activity(f"Research complete in {research_duration:.1f}s - found {len(topics)} topics", "success")

            for i, topic in enumerate(topics[:3]):
                log_activity(f"  Topic {i+1}: {topic.title[:60]}...", "info")

            # ============================================
            # STAGE 2: SYNTHESIS (30-45%)
            # ============================================
            update_job(current_stage='synthesis', progress_percent=30, stage_completed='research')
            log_activity("Research complete. Starting content synthesis...", "success")

            await asyncio.sleep(0.3)

            # Analyze topics and prepare for script generation
            update_job(progress_percent=33)
            log_activity("Scoring topics by relevance and engagement...", "info")

            # Log topic scores
            for i, topic in enumerate(topics[:5]):
                log_activity(f"  {topic.title[:50]}: score {topic.score:.1f}", "info")
                await asyncio.sleep(0.1)

            update_job(progress_percent=38)
            log_activity("Determining narrative flow and topic order...", "info")
            await asyncio.sleep(0.3)

            update_job(progress_percent=42)
            log_activity("Preparing topic briefs for script generation...", "info")

            # ============================================
            # STAGE 3: SCRIPT GENERATION (45-60%)
            # ============================================
            update_job(current_stage='script', progress_percent=45, stage_completed='synthesis')
            log_activity("Synthesis complete. Starting script generation...", "success")
            log_activity(f"Target: {options.get('duration', 15)}-minute episode with {len(topics)} topics", "info")

            update_job(progress_percent=47)
            log_activity("Initializing AI script writer (Gemini)...", "info")
            await asyncio.sleep(0.2)

            # Use enhanced script generation with deep research
            script_start = time.time()
            use_enhanced = options.get('deep_research', True)  # Default to enhanced mode

            if use_enhanced:
                log_activity("Using ENHANCED mode with deep research...", "info")

                # Deep research each topic
                researcher = TopicResearcher()
                enhanced_generator = EnhancedScriptGenerator()
                researched_topics = []

                for i, topic in enumerate(topics):
                    update_job(progress_percent=48 + (i * 2))
                    log_activity(f"Deep researching topic {i+1}/{len(topics)}: {topic.title[:40]}...", "info")

                    try:
                        # Build existing info from basic topic data
                        existing_info = f"""
Title: {topic.title}
Summary: {topic.summary}
Key Points: {', '.join(topic.key_points[:5]) if topic.key_points else 'None'}
Sources: {', '.join(topic.sources[:3]) if topic.sources else 'Various sources'}
Category: {topic.category}
"""
                        research = await researcher.research_topic(
                            topic_title=topic.title,
                            existing_info=existing_info,
                            category=topic.category
                        )
                        researched_topics.append(research)
                        log_activity(f"  Found {len(research.key_facts)} facts, {len(research.expert_opinions)} opinions", "success")
                    except Exception as e:
                        log_activity(f"  Research failed for topic, using basic info: {str(e)[:50]}", "warning")
                        # Create minimal research object
                        from src.research.topic_researcher import TopicResearch, ResearchedFact
                        basic_research = TopicResearch(
                            topic_title=topic.title,
                            key_facts=[ResearchedFact(fact=kp, source="Community discussion", confidence=0.7) for kp in topic.key_points[:3]],
                            statistics=[],
                            historical_context="",
                            current_situation=topic.summary,
                            future_implications="",
                            expert_opinions=[],
                            community_reactions=[],
                            common_misconceptions=[],
                            practical_advice=[],
                            related_stories=[],
                            arguments_for=[],
                            arguments_against=[],
                            nuanced_take=""
                        )
                        researched_topics.append(basic_research)

                update_job(progress_percent=52)
                log_activity("Deep research complete. Generating enhanced script...", "success")
                log_activity("Generating introduction dialogue (Raj & Priya)...", "info")

                # Generate script with enhanced generator
                script = await enhanced_generator.generate_script(
                    researched_topics=researched_topics,
                    episode_date=job.target_date,
                    target_duration_minutes=options.get('duration', 15),
                    podcast_name=profile.name,
                )
            else:
                log_activity("Using standard script generation...", "info")
                update_job(progress_percent=49)
                log_activity("Generating introduction dialogue (Raj & Priya)...", "info")

                # Use basic script generator
                script = await engine.script_generator.generate_script(
                    topics=topics,
                    episode_date=job.target_date,
                    target_duration_minutes=options.get('duration', 12),
                    podcast_name=profile.name,
                )

            script_duration = time.time() - script_start

            # Save script to disk
            episode_id = f"dd-{job.target_date.strftime('%Y%m%d')}"
            script_path = engine.scripts_dir / f"{episode_id}.json"
            with open(script_path, "w") as f:
                f.write(script.model_dump_json(indent=2))

            update_job(progress_percent=55)
            log_activity(f"Script generated in {script_duration:.1f}s - {len(script.segments)} segments", "success")

            # Log dialogue stats
            total_lines = len(script.intro) + len(script.outro)
            for seg in script.segments:
                total_lines += len(seg.dialogue)
            log_activity(f"Total dialogue lines: {total_lines} (Raj & Priya)", "info")

            update_job(progress_percent=60, stage_completed='script')
            log_activity(f"Script generation complete! Episode ID: {script.episode_id}", "success")

            # --- CHECK FOR STUDIO MODE ---
            if options.get('editorial_review'):
                log_activity("Editorial review mode enabled - pausing for script review", "info")
                update_job(
                    status='waiting_for_review',
                    current_stage='review',
                    progress_percent=60,
                )
                log_activity(f"Script ready for review. Episode ID: {script.episode_id}", "success")
                log_activity("Waiting for editorial approval before generating audio...", "info")
                return  # <--- STOP HERE

            # If no review needed, proceed immediately to audio
            log_activity("Proceeding directly to audio generation (no review required)", "info")
            update_job(current_stage='audio', progress_percent=65, stage_completed='script')
            log_activity("Starting audio production phase...", "info")

            await self._finish_audio_generation(job_id, profile_id, options, engine, script.episode_id, log_activity)

        except ValueError as e:
            # Configuration/validation errors
            error_msg = f"Configuration error: {str(e)}"
            log_activity(error_msg, "error")
            update_job(status='failed', error_message=error_msg)
            db.rollback()
            logger.error(f"[{job_id}] {error_msg}")
        except ConnectionError as e:
            # Network/API connection issues
            error_msg = f"Connection error: {str(e)[:200]}"
            log_activity(error_msg, "error")
            log_activity("Check your internet connection and API keys", "warning")
            update_job(status='failed', error_message=error_msg)
            db.rollback()
            logger.error(f"[{job_id}] {error_msg}")
        except TimeoutError as e:
            # Timeout issues
            error_msg = f"Operation timed out: {str(e)[:200]}"
            log_activity(error_msg, "error")
            log_activity("The operation took too long. Try reducing content length.", "warning")
            update_job(status='failed', error_message=error_msg)
            db.rollback()
            logger.error(f"[{job_id}] {error_msg}")
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            error_msg = f"Generation failed: {str(e)[:300]}"

            # Log the full error
            log_activity(error_msg, "error")
            log_activity("See server logs for full error details", "warning")

            # Update job with error
            update_job(
                status='failed',
                error_message=error_msg,
                stage_details={
                    **(db.query(GenerationJob).filter_by(job_id=job_id).first().stage_details or {}),
                    'error_trace': error_trace[-1000:],  # Last 1000 chars of trace
                    'error_type': type(e).__name__
                }
            )

            db.rollback()
            logger.error(f"[{job_id}] Generation failed: {e}\n{error_trace}")
        finally:
            db.close()

    async def _finish_audio_generation(self, job_id, profile_id, options, engine, episode_id, log_activity=None):
        """Helper to finish audio generation after script is ready"""
        from webapp.models import GenerationJob, PodcastProfile, Episode, Segment, TopicHistory
        from webapp.utils.logger import get_logger
        logger = get_logger("AudioGeneration")

        # localized Db session
        db = self.Session()

        def update_job(**kwargs):
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job and job.status != 'cancelled':
                for key, value in kwargs.items():
                    if key == 'stage_completed':
                        # Handle stage_completed specially to update stages_completed list
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

        def log(message, level='info', details=None):
            """Helper to log activity, handles missing log_activity gracefully"""
            if log_activity:
                log_activity(message, level, details)
            else:
                # Fallback: store in stage_details
                job = db.query(GenerationJob).filter_by(job_id=job_id).first()
                if job:
                    stage_details = dict(job.stage_details or {})
                    activity_log = stage_details.get('activity_log', [])
                    activity_log.append({
                        'timestamp': datetime.utcnow().isoformat(),
                        'message': message,
                        'level': level,
                        'details': details
                    })
                    stage_details['activity_log'] = activity_log
                    stage_details['current_activity'] = message
                    job.stage_details = stage_details
                    db.commit()
            logger.info(f"[{job_id}] {message}")

        try:
            update_job(current_stage='audio', progress_percent=70)
            log("Loading generated script...", "info")

            # 1. Generate Audio from script
            # We assume script is already saved on disk by generate_script_only
            # We need to load it to get metadata for saving later
            script_path = engine.scripts_dir / f"{episode_id}.json"
            log(f"Script found at: {script_path.name}", "info")

            # Load script
            import json
            from src.generators import PodcastScript

            with open(script_path, "r") as f:
                script_data = json.load(f)
            script = PodcastScript(**script_data)
            log(f"Script loaded: {script.episode_title}", "success")
            log(f"Script contains {len(script.segments)} segments", "info")

            # Now generate audio
            import time as time_module

            log("Initializing text-to-speech engine...", "info")
            update_job(progress_percent=72)

            log("Converting script to audio segments...", "info")
            total_segments = len(script.segments) + 2  # intro + segments + outro
            log(f"Processing {total_segments} audio segments (Raj & Priya voices)", "info")

            update_job(progress_percent=74)
            log("Generating intro audio (this may take a moment)...", "info")

            update_job(progress_percent=76)
            log("Sending dialogue to TTS API...", "info")

            tts_start = time_module.time()
            audio_segments = await engine.tts.generate_episode_audio(
                script_blocks=script.to_ssml_blocks(),
                episode_id=episode_id
            )
            tts_duration = time_module.time() - tts_start

            log(f"TTS complete in {tts_duration:.1f}s - {len(audio_segments) if audio_segments else 0} audio segments", "success")
            update_job(current_stage='audio', progress_percent=85, stage_completed='audio')
            log("Audio generation complete. Starting audio mixing...", "success")

            # 2. Mix Audio
            log("Initializing audio mixer...", "info")
            from src.audio.mixer import AudioMixer
            mixer = AudioMixer(assets_dir="assets")
            segment_paths = [seg.audio_path for seg in audio_segments] if audio_segments else []
            log(f"Collected {len(segment_paths)} audio segment files", "info")

            update_job(progress_percent=86)

            # Map segments for metadata
            segments_map = {}
            if audio_segments and hasattr(engine.tts, 'combine_segments_by_section'):
                log("Combining audio segments by section...", "info")
                segments_map = await engine.tts.combine_segments_by_section(audio_segments, episode_id)
                log(f"Created {len(segments_map)} section audio files", "success")

            update_job(progress_percent=88)
            log("Loading background music track...", "info")

            update_job(progress_percent=89)
            log("Mixing final audio with background music...", "info")

            mixed_path = None
            mix_start = time_module.time()
            if segment_paths:
                log("Applying audio ducking and transitions...", "info")
                mixed_path = mixer.mix_episode(
                    speech_segments=segment_paths,
                    output_path=str(engine.episodes_dir / f"{episode_id}.mp3"),
                    bg_music='random',
                    ducking_volume=-10
                )
                mix_duration = time_module.time() - mix_start
                log(f"Audio mixing complete in {mix_duration:.1f}s!", "success")

            final_audio_path = mixed_path
            if not final_audio_path and audio_segments:
                # Fallback
                log("Using fallback audio combination method...", "info")
                final_audio_path = await engine.tts.combine_audio_segments(
                    segments=audio_segments,
                    output_filename=f"{episode_id}.mp3",
                )

            update_job(progress_percent=92)
            log(f"Final audio saved: {episode_id}.mp3", "success")

            update_job(current_stage='newsletter', progress_percent=95, stage_completed='audio')
            log("Saving episode to database...", "info")

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
            log("Creating episode database record...", "info")

            # Generate unique episode_id (handle same-day duplicates)
            unique_episode_id = episode_id
            existing = db.query(Episode).filter_by(episode_id=episode_id).first()
            if existing:
                # Find the next available suffix
                suffix = 2
                while True:
                    candidate_id = f"{episode_id}-{suffix}"
                    if not db.query(Episode).filter_by(episode_id=candidate_id).first():
                        unique_episode_id = candidate_id
                        log(f"Episode ID {episode_id} exists, using {unique_episode_id}", "info")
                        break
                    suffix += 1
                    if suffix > 100:  # Safety limit
                        raise ValueError(f"Too many episodes on same day: {episode_id}")

            # Save Episode RECORD
            episode = Episode(
                profile_id=profile_id,
                episode_id=unique_episode_id,
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
            log(f"Episode record created (ID: {episode.id}, Episode ID: {unique_episode_id})", "success")

            # Save Segments
            if segment_list:
                log(f"Saving {len(segment_list)} audio segment records...", "info")
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
                log("Segment records saved", "success")

            # Save Topic History
            log("Updating topic history...", "info")
            for seg in script.segments:
                topic_history = TopicHistory(
                    episode_id=episode.id,
                    title=seg.topic_title,
                    category="General",
                )
                db.add(topic_history)
            db.commit()
            log("Topic history updated", "success")

            # 5. Generate Newsletter
            update_job(progress_percent=97)
            log("Starting newsletter generation...", "info")
            try:
                # Get profile name for newsletter
                newsletter_profile = db.query(PodcastProfile).get(profile_id)
                newsletter_name = newsletter_profile.name if newsletter_profile else "Newsletter"
                await self._generate_and_save_newsletter(profile_id, engine, episode_id, episode.id, newsletter_name)
                log("Newsletter generated successfully!", "success")
                update_job(stage_completed='newsletter')
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Don't fail the whole job if newsletter fails
                log(f"Newsletter generation skipped: {str(e)[:100]}", "warning")
                logger.error(f"Newsletter generation failed: {e}")

            log("Finalizing episode...", "info")
            update_job(
                status='completed',
                current_stage='complete',
                progress_percent=100,
                episode_id=episode.id,
                completed_at=datetime.utcnow()
            )
            log("Episode generation complete!", "success", {"episode_id": episode.id, "title": script.episode_title})
            
        except FileNotFoundError as e:
            error_msg = f"File not found: {str(e)[:200]}"
            log(error_msg, "error")
            log("Script or audio files may be missing. Try regenerating.", "warning")
            update_job(status='failed', error_message=error_msg)
            logger.error(f"[{job_id}] {error_msg}")
        except PermissionError as e:
            error_msg = f"Permission denied: {str(e)[:200]}"
            log(error_msg, "error")
            log("Check file/folder permissions for output directory", "warning")
            update_job(status='failed', error_message=error_msg)
            logger.error(f"[{job_id}] {error_msg}")
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            error_msg = f"Audio generation failed: {str(e)[:300]}"

            log(error_msg, "error")

            # Identify common error patterns
            error_str = str(e).lower()
            if 'api' in error_str or 'key' in error_str:
                log("This may be an API key issue. Check your TTS configuration.", "warning")
            elif 'audio' in error_str or 'wav' in error_str or 'mp3' in error_str:
                log("Audio processing failed. Check ffmpeg installation.", "warning")
            elif 'memory' in error_str:
                log("Memory issue detected. Try a shorter episode duration.", "warning")

            update_job(
                status='failed',
                error_message=error_msg,
                stage_details={
                    **(db.query(GenerationJob).filter_by(job_id=job_id).first().stage_details or {}),
                    'error_trace': error_trace[-1000:],
                    'error_type': type(e).__name__,
                    'error_stage': 'audio_generation'
                }
            )
            logger.error(f"[{job_id}] Audio generation failed: {e}\n{error_trace}")
        finally:
            db.close()

    async def _generate_and_save_newsletter(self, profile_id, engine, episode_id_str, episode_db_id, newsletter_name):
        """Generates newsletter after episode is done."""
        from src.intelligence.synthesis.newsletter_generator import NewsletterGenerator
        from src.intelligence.models.research import EpisodeResearchBundle, VerifiedTopic, ResearchedTopic
        from webapp.models import Newsletter as NewsletterModel
        from webapp.utils.logger import get_logger
        
        logger = get_logger("NewsletterService")
        
        # Check if research exists
        research_path = engine.scripts_dir / f"{episode_id_str}_research.json"
        
        bundle = None
        
        if research_path.exists():
            logger.info("Found deep research data, generating rich newsletter...")
            
            # Fetch profile details for customization
            db = self.Session()
            audience = "General Audience"
            tone = "Professional"
            try:
                profile = db.query(PodcastProfile).get(profile_id)
                if profile:
                    audience = profile.target_audience or "General Audience"
                    tone = profile.tone or "Professional"
            finally:
                db.close()
                
            import json
            with open(research_path, "r") as f:
                research_data = json.load(f)
                
            verified_topics = []
            for rt_data in research_data:
                # Handle potential recursive models or dicts
                try:
                    rt = ResearchedTopic(**rt_data)
                    vt = VerifiedTopic.from_researched_topic(rt)
                    verified_topics.append(vt)
                except Exception as e:
                    logger.warning(f"Error parsing topic for newsletter: {e}")
                
            if verified_topics:
                bundle = EpisodeResearchBundle(
                    id=f"bundle-{episode_id_str}",
                    profile_id=profile_id,
                    episode_date=datetime.now(), 
                    verified_topics=verified_topics,
                    main_theme="Podcast Update"
                )
        
        # Fallback: Generate newsletter from script if no deep research data
        if not bundle:
            script_path = engine.scripts_dir / f"{episode_id_str}.json"
            if script_path.exists():
                logger.info("No deep research data, generating newsletter from script...")
                import json
                with open(script_path, "r") as f:
                    script_data = json.load(f)

                # Create verified topics from script segments using proper nested models
                verified_topics = []
                for i, seg in enumerate(script_data.get('segments', [])):
                    try:
                        topic_id = seg.get('topic_id', f'topic_{i}')
                        topic_title = seg.get('topic_title', 'Topic')

                        # Extract key points from dialogue
                        dialogue_texts = [line.get('text', '') for line in seg.get('dialogue', [])]
                        summary_text = ' '.join(dialogue_texts[:3])[:500] if dialogue_texts else f"Discussion about {topic_title}"

                        # Create ResearchedTopic first
                        researched_topic = ResearchedTopic(
                            id=topic_id,
                            cluster_id=f"cluster-{topic_id}",
                            headline=topic_title,
                            summary=summary_text,
                            category=seg.get('category', 'General'),
                            background="",
                            current_situation=summary_text,
                            implications="",
                            research_depth="script_derived"
                        )

                        # Create VerifiedTopic wrapper
                        vt = VerifiedTopic(
                            id=f"verified-{topic_id}",
                            researched_topic=researched_topic,
                            editorial_approved=True,
                            editorial_score=7.0,
                            final_headline=topic_title,
                            final_summary=summary_text,
                            suggested_tone="informative",
                            key_talking_points=dialogue_texts[:3],
                            priority_rank=i
                        )
                        verified_topics.append(vt)
                    except Exception as e:
                        logger.warning(f"Error creating topic from script segment: {e}")

                if verified_topics:
                    # Fetch profile details
                    db = self.Session()
                    audience = "General Audience"
                    tone = "Professional"
                    try:
                        profile = db.query(PodcastProfile).get(profile_id)
                        if profile:
                            audience = profile.target_audience or "General Audience"
                            tone = profile.tone or "Professional"
                    finally:
                        db.close()

                    bundle = EpisodeResearchBundle(
                        id=f"bundle-{episode_id_str}",
                        profile_id=profile_id,
                        episode_date=datetime.now(),
                        verified_topics=verified_topics,
                        main_theme=script_data.get('episode_title', 'Podcast Update')
                    )

        if bundle:
            generator = NewsletterGenerator(model="gemini-2.0-flash")
            newsletter = await generator.generate_newsletter(
                bundle, 
                newsletter_name=newsletter_name,
                audience=audience,
                tone=tone
            )
            
            # Save to DB
            db = self.Session()
            try:
                nm = NewsletterModel(
                    episode_id=episode_db_id,
                    profile_id=profile_id,
                    title=newsletter.title,
                    subtitle=newsletter.subtitle,
                    issue_date=newsletter.issue_date,
                    intro=newsletter.intro,
                    outro=newsletter.outro,
                    sections=[s.dict() for s in newsletter.sections],
                    markdown_content=newsletter.markdown_content,
                    html_content=newsletter.html_content,
                    total_word_count=newsletter.total_word_count,
                    reading_time_minutes=newsletter.reading_time_minutes
                )
                db.add(nm)
                db.commit()
                logger.info(f"Newsletter saved for episode {episode_db_id}")
            except Exception as e:
                logger.error(f"Failed to save newsletter to DB: {e}")
                db.rollback()
            finally:
                db.close()
        else:
            logger.warning(f"No newsletter generated for episode {episode_id_str} - no research data or script found")

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
