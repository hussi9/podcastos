"""
Functional Test for PodcastOS Workflow
Simulates:
1. Creating a Podcast Profile
2. Starting a Generation Job with 'Studio Mode' (Human Review)
3. Verifying Job Pauses
4. Resuming Job (Approving)
5. Verifying Completion and Data Integrity (Segments, Audio paths)
"""

import sys
import os
import asyncio
import threading
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

# MOCK EXTERNAL DEPENDENCIES BEFORE IMPORTING ENGINE
from unittest.mock import MagicMock
sys.modules['google.generativeai'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['elevenlabs'] = MagicMock()
sys.modules['praw'] = MagicMock()
sys.modules['pydub'] = MagicMock() # Mock P yd ub for AudioMixer

from webapp.models import init_db, get_session, PodcastProfile, GenerationJob, Episode, Segment
from webapp.services.generation_service import GenerationService
from src.podcast_engine import PodcastEngine # Explicit import

# Mock the expensive components to avoid real API calls
from unittest.mock import MagicMock, patch

async def mock_generate_script_only(*args, **kwargs):
    from src.generators import PodcastScript, PodcastSegment, DialogueLine
    print("[MOCK] Generating Script...")
    return PodcastScript(
        episode_id="test-ep-1",
        episode_title="Test Episode",
        episode_date=datetime.now().isoformat(),
        duration_estimate=120,
        intro=[DialogueLine(speaker="Raj", text="Hello world")],
        segments=[
            PodcastSegment(
                topic_id="topic-1",
                topic_title="Test Topic 1",
                duration_estimate=60,
                dialogue=[DialogueLine(speaker="Priya", text="Topic discussion")]
            )
        ],
        outro=[DialogueLine(speaker="Raj", text="Goodbye")]
    )

async def mock_generate_episode_audio(*args, **kwargs):
    print("[MOCK] Generating Audio...")
    # Return dummy AudioSegments
    # We need to mock the object structure correctly
    mock_seg1 = MagicMock()
    mock_seg1.audio_path = "/tmp/test_intro.mp3"
    mock_seg1.duration_ms = 1000
    mock_seg1.section = "intro"
    
    mock_seg2 = MagicMock()
    mock_seg2.audio_path = "/tmp/test_topic.mp3"
    mock_seg2.duration_ms = 2000
    mock_seg2.section = "topic-1"
    
    mock_seg3 = MagicMock()
    mock_seg3.audio_path = "/tmp/test_outro.mp3"
    mock_seg3.duration_ms = 1000
    mock_seg3.section = "outro"

    return [mock_seg1, mock_seg2, mock_seg3]

async def mock_combine_segments(*args, **kwargs):
    print("[MOCK] Combining Segments...")
    return {"intro": "/tmp/test_intro.mp3", "topic-1": "/tmp/test_topic.mp3", "outro": "/tmp/test_outro.mp3"}

def run_test():
    print("--- Starting Functional Test ---")
    
    # 1. Setup DB
    db_path = "test_studio.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    engine = init_db(db_path)
    Session = lambda: get_session(engine)
    gen_service = GenerationService(Session)
    
    db = Session()
    try:
        # 2. Create Profile
        profile = PodcastProfile(name="Test Pod", topic_count=1, target_duration_minutes=5)
        db.add(profile)
        db.commit()
        profile_id = profile.id
        print(f"Created Profile ID: {profile_id}")
        
        # 3. Start Job with Studio Mode
        print("Starting Job with Studio Mode...")
        options = {
            'topic_count': 1,
            'duration': 5,
            'editorial_review': True, # <--- ENABLING STUDIO MODE
            'deep_research': False
        }
        
        # MOCKING THE ENGINE
        # We patch the source class directly
        with patch('src.podcast_engine.PodcastEngine') as MockEngine:
            # Configure Mock
            mock_instance = MockEngine.return_value
            mock_instance.generate_script_only.side_effect = mock_generate_script_only
            mock_instance.tts.generate_episode_audio.side_effect = mock_generate_episode_audio
            mock_instance.tts.combine_segments_by_section.side_effect = mock_combine_segments
            
            async def mock_combine_audio(*args, **kwargs):
                return "/tmp/full_episode.mp3"
            mock_instance.tts.combine_audio_segments.side_effect = mock_combine_audio
            mock_instance.scripts_dir = Path("/tmp")
            mock_instance.episodes_dir = Path("/tmp")
            
            # Start Job
            job_id = gen_service.start_generation_job(profile_id, options)
            print(f"Job started: {job_id}")
            
            # Wait for pause
            print("Waiting for job to reach review state...")
            max_retries = 10
            while max_retries > 0:
                time.sleep(1)
                job = db.query(GenerationJob).filter_by(job_id=job_id).first()
                if job.status == 'waiting_for_review':
                    print("SUCCESS: Job paused at 'waiting_for_review'")
                    break
                max_retries -= 1
            
            if job.status != 'waiting_for_review':
                print(f"FAILURE: Job did not pause. Status: {job.status}")
                return

            # Verify Stage Details
            print(f"Stage Info: {job.stage_details}")
            
            # 4. Resume Job (Approve)
            print("Resuming Job (Simulating Approval)...")
            
            # Need to create a fake script file because resume logic reads it
            with open(f"/tmp/test-ep-1.json", "w") as f:
                import json
                script_json = {
                    "episode_id": "test-ep-1",
                    "episode_title": "Test Episode",
                    "episode_date": datetime.now().isoformat(),
                    "duration_estimate": 120,
                    "intro": [{"speaker": "Raj", "text": "Hello"}],
                    "segments": [{"topic_id": "topic-1", "topic_title": "Test Topic 1", "duration_estimate": 60, "dialogue": []}],
                    "outro": [{"speaker": "Raj", "text": "Bye"}]
                }
                json.dump(script_json, f)

            # We need to patch the engine creation inside resume_generation_job as well
            # Since it imports create_engine_from_env inside the thread
            # We can't easily patch inside a thread from here without complex mocking
            # So we rely on the fact that it calls _finish_audio_generation which mocks engine calls?
            # No, resume_generation_job creates a NEW engine instance.
            
            # We patch the source function
            # And since it's an async function being called, we need the return value to be awaitable
            async def mock_create_engine_async():
                return mock_instance

            with patch('src.podcast_engine.create_engine_from_env', side_effect=mock_create_engine_async):
                 gen_service.resume_generation_job(job_id)
                 
                 # Wait for completion
                 print("Waiting for job completion...")
                 max_retries = 10
                 while max_retries > 0:
                     time.sleep(1)
                     db.expire_all() # Refresh
                     job = db.query(GenerationJob).filter_by(job_id=job_id).first()
                     if job.status == 'completed':
                         print("SUCCESS: Job completed")
                         break
                     if job.status == 'failed':
                         print(f"FAILURE: Job failed with error: {job.error_message}")
                         break
                     max_retries -= 1
            
            if job.status != 'completed':
                print(f"FAILURE: Job did not complete. Status: {job.status}")
                return

            # 5. Verify Data Integrity
            episode = db.query(Episode).filter_by(episode_id="test-ep-1").first()
            if not episode:
                print("FAILURE: Episode record not found")
                return
            
            print(f"Episode Created: {episode.title} (ID: {episode.id})")
            
            segments = db.query(Segment).filter_by(episode_id=episode.id).all()
            print(f"Segments found: {len(segments)}")
            for s in segments:
                print(f" - [{s.sequence_index}] {s.content_type}: {s.title}")
            
            if len(segments) == 3:
                print("SUCCESS: All segments created (Intro + Topic + Outro)")
            else:
                print(f"FAILURE: Expected 3 segments, found {len(segments)}")

    except Exception as e:
        print(f"TEST EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        if os.path.exists(db_path):
             os.remove(db_path)

if __name__ == "__main__":
    run_test()
