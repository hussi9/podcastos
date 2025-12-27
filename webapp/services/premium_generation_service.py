"""
Premium Generation Service - Complete Implementation
Integrates: Gemini Deep Research + Nano Banana Pro + Multi-Source + Audio

This is the COMPLETE production implementation combining all components.
"""

import os
import sys
import asyncio
import threading
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from webapp.models import GenerationJob, PodcastProfile, Episode, Newsletter
from src.intelligence.research.gemini_deep_research import GeminiDeepResearch
from src.intelligence.synthesis.newsletter_generator_thinking import GeminiThinkingNewsletterGenerator
import logging

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
_genai_client = None
_tts_client = None


# Store for running jobs with thread safety
import threading
_RUNNING_JOBS = {}
_JOBS_LOCK = threading.Lock()


class GeminiNotConfiguredError(Exception):
    """Raised when Gemini API is not properly configured."""
    pass


class PremiumGenerationService:
    """
    Complete production-ready generation service
    
    Features:
    - Gemini Deep Research
    - Nano Banana Pro newsletters
    - Google Cloud TTS
    - Complete error handling
    - Progress tracking
    - Database persistence
    """
    
    def __init__(self, db_session_factory):
        self.Session = db_session_factory
        self.gemini_client = None
        self.tts_client = None
        self.tts_available = False
        
        # Validate and initialize Gemini API
        self._init_gemini()
        
        # Initialize Google Cloud TTS if available (optional)
        self._init_tts()
    
    def _init_gemini(self):
        """Initialize Gemini client with validation."""
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            raise GeminiNotConfiguredError(
                "GEMINI_API_KEY environment variable is not set. "
                "Please set it to use the Premium Generation Service.\n"
                "Get your API key at: https://makersuite.google.com/app/apikey"
            )
        
        if len(api_key) < 20:
            raise GeminiNotConfiguredError(
                "GEMINI_API_KEY appears to be invalid (too short). "
                "Please check your API key configuration."
            )
        
        try:
            from google import genai
            self.gemini_client = genai.Client(api_key=api_key)
            logger.info("✅ Gemini API client initialized successfully")
        except ImportError:
            raise GeminiNotConfiguredError(
                "google-genai package is not installed. "
                "Run: pip install google-genai"
            )
        except Exception as e:
            raise GeminiNotConfiguredError(
                f"Failed to initialize Gemini client: {e}"
            )
    
    def _init_tts(self):
        """Initialize Google Cloud TTS (optional)."""
        try:
            from google.cloud import texttospeech
            self.tts_client = texttospeech.TextToSpeechClient()
            self.tts_available = True
            logger.info("✅ Google Cloud TTS initialized successfully")
        except ImportError:
            self.tts_available = False
            logger.warning(
                "⚠️  google-cloud-texttospeech not installed. "
                "Audio generation will be disabled. "
                "Install with: pip install google-cloud-texttospeech"
            )
        except Exception as e:
            self.tts_available = False
            error_msg = str(e)
            if "credentials" in error_msg.lower():
                logger.warning(
                    "⚠️  Google Cloud TTS credentials not configured. "
                    "Set GOOGLE_APPLICATION_CREDENTIALS or run: "
                    "gcloud auth application-default login"
                )
            else:
                logger.warning(f"⚠️  Google Cloud TTS initialization failed: {e}")
            self.tts_client = None
    
    def start_generation_job(self, profile_id: int, options: dict) -> str:
        """
        Start complete podcast generation
        
        Args:
            profile_id: Podcast profile ID
            options: Generation options (topic, etc.)
        
        Returns:
            job_id: Unique job identifier
        """
        db = self.Session()
        try:
            # Verify profile exists
            profile = db.query(PodcastProfile).get(profile_id)
            if not profile:
                raise ValueError(f"Profile {profile_id} not found")
            
            # Create job record
            job_id = f"job-{uuid.uuid4().hex[:8]}"
            job = GenerationJob(
                profile_id=profile_id,
                job_id=job_id,
                target_date=datetime.now(),
                status='pending',
                current_stage='initializing',
                progress_percent=0,
                stages_completed=[],
                stages_pending=[
                    'research',
                    'synthesis',
                    'script',
                    'audio',
                    'newsletter'
                ],
            )
            db.add(job)
            db.commit()
            
            # Spawn async worker thread
            thread = threading.Thread(
                target=self._run_complete_generation,
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
    
    def _run_complete_generation(self, job_id: str, profile_id: int, options: dict):
        """
        Main generation loop (runs in background thread)
        """
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(
                self._async_generation_pipeline(job_id, profile_id, options)
            )
        except Exception as e:
            self._update_job_error(job_id, str(e))
        finally:
            loop.close()
    
    async def _async_generation_pipeline(self, job_id: str, profile_id: int, options: dict):
        """
        Complete async generation pipeline
        """
        db = self.Session()
        
        try:
            # Get profile
            profile = db.query(PodcastProfile).get(profile_id)
            topic = options.get('topic', 'Latest updates')
            
            # ===== STAGE 1: DEEP RESEARCH =====
            self._update_job_stage(job_id, 'research', 20)
            
            print(f"🔍 [{job_id}] Starting Gemini Deep Research...")
            researcher = GeminiDeepResearch()
            
            research_results = await researcher.research_topic(
                topic=topic,
                context=None,
                max_iterations=5
            )
            
            print(f"✅ [{job_id}] Research complete: {len(research_results.get('sources', []))} sources")
            
            # ===== STAGE 2: SYNTHESIS (Nano Banana Pro) =====
            self._update_job_stage(job_id, 'synthesis', 40)
            
            print(f"🍌 [{job_id}] Synthesizing with Nano Banana Pro...")
            
            synthesis_response = await self.gemini_client.aio.models.generate_content(
                model="gemini-2.0-flash-thinking-exp",
                contents=f"""Synthesize this research about '{topic}'.
                
Research Summary:
{research_results.get('summary', '')}

Key Facts:
{chr(10).join(f"- {fact}" for fact in research_results.get('key_facts', [])[:15])}

Think deeply and create a comprehensive 3-paragraph synthesis for podcast production."""
            )
            
            synthesis = synthesis_response.text
            print(f"✅ [{job_id}] Synthesis complete")
            
            # ===== STAGE 3: SCRIPT GENERATION =====
            self._update_job_stage(job_id, 'script', 60)
            
            print(f"✍️  [{job_id}] Generating script with Gemini...")
            
            script_response = await self.gemini_client.aio.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=f"""Create a professional 20-minute podcast script about: {topic}

Research Synthesis:
{synthesis}

Format as multi-host dialogue between:
- Host A (analytical, asks probing questions)
- Host B (explanatory, provides insights)

Include:
1. Engaging intro (2 min)
2. Main discussion (15 min) - 3-4 key topics
3. Takeaways & outro (3 min)

Make it conversational, informative, and engaging."""
            )
            
            script = script_response.text
            print(f"✅ [{job_id}] Script generated ({len(script)} characters)")
            
            # ===== STAGE 4: AUDIO (Optional) =====
            self._update_job_stage(job_id, 'audio', 75)
            
            audio_path = None
            if self.tts_available:
                print(f"🎙️  [{job_id}] Generating audio...")
                try:
                    audio_path = await self._generate_audio(script, job_id)
                    print(f"✅ [{job_id}] Audio generated: {audio_path}")
                except Exception as e:
                    print(f"⚠️  [{job_id}] Audio generation failed: {e}")
            else:
                print(f"ℹ️  [{job_id}] Skipping audio (TTS not configured)")
            
            # ===== STAGE 5: NEWSLETTER (Nano Banana Pro) =====
            self._update_job_stage(job_id, 'newsletter', 90)
            
            print(f"📰 [{job_id}] Generating premium newsletter...")
            
            # Prepare research bundle
            research_bundle = {
                "topics": [{
                    "title": topic,
                    "summary": synthesis,
                    "key_facts": research_results.get('key_facts', [])[:10],
                    "sources": research_results.get('sources', [])[:5]
                }]
            }
            
            profile_settings = {
                "name": profile.name,
                "target_audience": profile.target_audience or "General audience",
                "tone": profile.tone or "Conversational and analytical"
            }
            
            newsletter_gen = GeminiThinkingNewsletterGenerator()
            newsletter_data = await newsletter_gen.generate_newsletter(
                research_bundle=research_bundle,
                profile_settings=profile_settings
            )
            
            print(f"✅ [{job_id}] Newsletter generated")
            
            # ===== SAVE TO DATABASE =====
            self._update_job_stage(job_id, 'finalizing', 95)
            
            # Create episode
            episode = Episode(
                profile_id=profile_id,
                title=newsletter_data['title'],
                subtitle=newsletter_data.get('subtitle', ''),
                description=synthesis[:500],
                script_content=script,
                audio_file_path=audio_path,
                status='completed',
                generated_at=datetime.utcnow()
            )
            db.add(episode)
            db.flush()
            
            # Create newsletter
            newsletter = Newsletter(
                episode_id=episode.id,
                title=newsletter_data['title'],
                subtitle=newsletter_data.get('subtitle', ''),
                content_markdown=newsletter_data['content_markdown'],
                content_html=newsletter_data['content_html'],
                sent_at=None  # Not sent yet
            )
            db.add(newsletter)
            db.commit()
            
            # ===== COMPLETE =====
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            job.status = 'completed'
            job.progress_percent = 100
            job.completed_at = datetime.utcnow()
            job.result_data = {
                'episode_id': episode.id,
                'newsletter_id': newsletter.id,
                'research_sources': len(research_results.get('sources', [])),
                'script_length': len(script),
                'audio_generated': audio_path is not None
            }
            db.commit()
            
            print(f"🎉 [{job_id}] Generation complete!")
            print(f"   Episode ID: {episode.id}")
            print(f"   Newsletter ID: {newsletter.id}")
            
        except Exception as e:
            print(f"❌ [{job_id}] Error: {e}")
            raise
        finally:
            db.close()
    
    async def _generate_audio(self, script: str, job_id: str, hosts: list = None) -> str:
        """
        Generate audio using Google Cloud TTS with multi-host support.
        
        Args:
            script: The script text (may contain host markers like [Host A] or [Raj])
            job_id: Job identifier for file naming
            hosts: Optional list of host configs with voice settings
            
        Returns:
            Path to the generated audio file
        """
        from google.cloud import texttospeech
        import re
        
        # Default host voice configurations
        default_hosts = {
            'host_a': {'name': 'en-US-Neural2-D', 'pitch': 0, 'rate': 1.0},  # Male voice
            'host_b': {'name': 'en-US-Neural2-F', 'pitch': 0, 'rate': 1.0},  # Female voice
            'raj': {'name': 'en-US-Neural2-D', 'pitch': -2, 'rate': 0.95},    # Raj - deeper male
            'priya': {'name': 'en-US-Neural2-F', 'pitch': 2, 'rate': 1.05},   # Priya - higher female
            'narrator': {'name': 'en-US-Neural2-A', 'pitch': 0, 'rate': 1.0}, # Neutral narrator
        }
        
        # Parse script into segments by host
        segments = self._parse_script_by_host(script)
        
        if not segments:
            # Fallback: treat entire script as single segment
            segments = [{'host': 'narrator', 'text': script[:5000]}]
        
        output_dir = Path("output/audio")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        audio_segments = []
        
        for i, segment in enumerate(segments):
            host_key = segment['host'].lower().replace(' ', '_')
            host_config = default_hosts.get(host_key, default_hosts['narrator'])
            
            # Skip empty segments
            if not segment['text'].strip():
                continue
            
            # Limit text length per segment
            text = segment['text'][:3000]
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name=host_config['name']
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                pitch=host_config.get('pitch', 0),
                speaking_rate=host_config.get('rate', 1.0)
            )
            
            try:
                response = self.tts_client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
                
                # Save segment
                segment_path = output_dir / f"segment_{job_id}_{i:03d}.mp3"
                with open(segment_path, "wb") as f:
                    f.write(response.audio_content)
                
                audio_segments.append(str(segment_path))
                logger.info(f"Generated audio segment {i+1}/{len(segments)} for {segment['host']}")
                
            except Exception as e:
                logger.warning(f"Failed to generate segment {i}: {e}")
                continue
        
        # Combine segments into final audio
        if audio_segments:
            final_path = await self._combine_audio_segments(audio_segments, job_id, output_dir)
            
            # Cleanup segment files
            for seg_path in audio_segments:
                try:
                    Path(seg_path).unlink()
                except Exception:
                    pass
            
            return final_path
        else:
            # Fallback: single audio generation
            logger.warning("No segments generated, using fallback")
            return await self._generate_simple_audio(script[:5000], job_id, output_dir)
    
    def _parse_script_by_host(self, script: str) -> list:
        """
        Parse script into segments by host speaker.
        
        Supports formats:
        - [Host A]: text
        - [Raj]: text
        - **Host A:** text
        - RAJ: text
        """
        import re
        
        # Pattern to match host markers
        patterns = [
            r'\[([^\]]+)\]:\s*',           # [Host A]: 
            r'\*\*([^*]+):\*\*\s*',         # **Host A:**
            r'^([A-Z][A-Za-z]+):\s*',       # RAJ: or Raj:
        ]
        
        segments = []
        current_host = 'narrator'
        current_text = []
        
        for line in script.split('\n'):
            matched = False
            
            for pattern in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    # Save previous segment
                    if current_text:
                        segments.append({
                            'host': current_host,
                            'text': ' '.join(current_text)
                        })
                        current_text = []
                    
                    # Start new segment
                    current_host = match.group(1).strip()
                    remaining = re.sub(pattern, '', line.strip())
                    if remaining:
                        current_text.append(remaining)
                    matched = True
                    break
            
            if not matched and line.strip():
                current_text.append(line.strip())
        
        # Add final segment
        if current_text:
            segments.append({
                'host': current_host,
                'text': ' '.join(current_text)
            })
        
        return segments
    
    async def _combine_audio_segments(self, segment_paths: list, job_id: str, output_dir: Path) -> str:
        """Combine multiple audio segments into one file using pydub."""
        try:
            from pydub import AudioSegment
            
            combined = AudioSegment.empty()
            
            for path in segment_paths:
                segment = AudioSegment.from_mp3(path)
                # Add small pause between segments
                combined += segment + AudioSegment.silent(duration=300)
            
            final_path = output_dir / f"episode_{job_id}.mp3"
            combined.export(str(final_path), format="mp3")
            
            return str(final_path)
            
        except ImportError:
            logger.warning("pydub not available, using first segment only")
            # Fallback: just use the first segment
            if segment_paths:
                import shutil
                final_path = output_dir / f"episode_{job_id}.mp3"
                shutil.copy(segment_paths[0], final_path)
                return str(final_path)
            raise
    
    async def _generate_simple_audio(self, text: str, job_id: str, output_dir: Path) -> str:
        """Generate simple single-voice audio as fallback."""
        from google.cloud import texttospeech
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Neural2-A"
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        response = self.tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        audio_path = output_dir / f"episode_{job_id}.mp3"
        with open(audio_path, "wb") as f:
            f.write(response.audio_content)
        
        return str(audio_path)
    
    def _update_job_stage(self, job_id: str, stage: str, progress: int):
        """Update job progress"""
        db = self.Session()
        try:
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job:
                job.current_stage = stage
                job.progress_percent = progress
                if stage not in job.stages_completed:
                    job.stages_completed.append(stage)
                db.commit()
        finally:
            db.close()
    
    def _update_job_error(self, job_id: str, error: str):
        """Update job with error"""
        db = self.Session()
        try:
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job:
                job.status = 'failed'
                job.error_message = error
                job.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status"""
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
                'error': job.error_message,
                'result': job.result_data
            }
        finally:
            db.close()
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job"""
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
