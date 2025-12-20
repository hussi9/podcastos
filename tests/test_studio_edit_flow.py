"""
Functional Test for Studio Edit Flow
Simulates:
1. Job reaches Review State
2. User submits EDITED script via JSON payload to /approve
3. Verify Script file is updated on disk
4. Verify Audio Generation uses updated content (conceptually)
5. Verify Final Episode metadata matches triggers
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

# MOCK EXTERNAL DEPENDENCIES
sys.modules['google.generativeai'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['elevenlabs'] = MagicMock()
sys.modules['praw'] = MagicMock()
sys.modules['pydub'] = MagicMock()

from webapp.app import app
from webapp.models import init_db, get_session, PodcastProfile, GenerationJob, Episode
from webapp.services.generation_service import GenerationService

# Setup Test Client
client = app.test_client()

async def mock_generate_script_only(*args, **kwargs):
    from src.generators import PodcastScript, PodcastSegment, DialogueLine
    return PodcastScript(
        episode_id="edit-test-1",
        episode_title="Original Title",
        episode_date=datetime.now().isoformat(),
        duration_estimate=120,
        intro=[DialogueLine(speaker="Raj", text="Original Intro")],
        segments=[
            PodcastSegment(
                topic_id="topic-1",
                topic_title="Original Topic",
                duration_estimate=60,
                dialogue=[DialogueLine(speaker="Priya", text="Original Dialogue")]
            )
        ],
        outro=[DialogueLine(speaker="Raj", text="Original Outro")]
    )

def run_test():
    print("--- Starting Studio Edit Flow Test ---")
    
    # 1. Setup
    db_path = "test_edit.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Configure app to use test db
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['TESTING'] = True
    
    # Init DB
    # We must configure the app to use our test DB path
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.abspath(db_path)}'
    
    # Init DB tables
    with app.app_context():
        from webapp.models import Base
        from webapp.app import init_db as app_init_db
        # We need to actuly Create Tables because app.init_db just yields session
        engine = app_init_db() 
        Base.metadata.create_all(bind=engine)

    # Now Service uses the SAME engine/session factory as the App Context?
    # No, we manually instantiated GenerationService(Session).
    # Ideally they should share.
    # Let's just point GenerationService to use the same engine.
    
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    test_engine = create_engine(f'sqlite:///{os.path.abspath(db_path)}')
    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    
    gen_service = GenerationService(TestSession)
    
    # Patch the global gen_service in app.py to rely on OUR service instance (or just same DB)
    # The app code uses `gen_service` imported from `services.generation_service`.
    # We can't easily replace that module-level variable in `app.py` from here without some hack.
    # Hack:
    import webapp.app
    webapp.app.gen_service.Session = TestSession # Force it to use our DB
    
    # Create Profile
    db = TestSession()
    profile = PodcastProfile(name="Editor Pod", topic_count=1, target_duration_minutes=5)
    db.add(profile)
    db.commit()
    profile_id = profile.id
    db.close()
    
    # 2. Start Job (Mocked)
    # We must patch src.podcast_engine.PodcastEngine at the SOURCE where generation_service imports it
    # AND patch webapp.app.gen_service.resume_generation_job later.
    
    # IMPORTANT: The background thread running inside 'start_generation_job' needs to use the same DB.
    # Since we replaced Session on the service instance, it should Work.
    
    with patch('src.podcast_engine.PodcastEngine') as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.generate_script_only.side_effect = mock_generate_script_only
        mock_instance.scripts_dir = Path("/tmp")
        mock_instance.episodes_dir = Path("/tmp")
        
        # We also need to patch where GenerationService imports PodcastEngine (src.podcast_engine)
        # The patch above does that if imports are correct.
        
        print("Starting Job...")
        job_id = gen_service.start_generation_job(profile_id, {'editorial_review': True})
        
        # Wait for pause
        print("Waiting for pause...")
        for _ in range(10):
            time.sleep(0.5)
            db = TestSession()
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job and job.status == 'waiting_for_review':
                break
            db.close()
            
        if job.status != 'waiting_for_review':
            print("FAIL: Job did not pause")
            return

                # We need to hack app.py's get_db to return our TestSession
        
        original_get_db = app.view_functions['job_approve'].__globals__['get_db']
        
        def mock_get_db():
            return TestSession()
            
        # PATCH Path object in app.py to redirect file operations to /tmp ?? Too risky/hard.
        # Better: Patch the specific logic block or path variable?
        # Let's just create the file where the APP expects it.
        
        real_output_dir = Path(webapp.app.__file__).parent.parent / 'output' / 'scripts'
        real_output_dir.mkdir(parents=True, exist_ok=True)
        real_script_path = real_output_dir / "edit-test-1.json"
        
        # Write initial file there instead of /tmp
        with open(real_script_path, "w") as f:
            json.dump({
                "episode_id": "edit-test-1",
                "episode_title": "Original Title",
                "segments": [{"topic_title": "Original Topic", "duration_estimate": 60}]
            }, f)

        try: 
            with patch('webapp.app.get_db', side_effect=mock_get_db):
                with patch('webapp.app.gen_service.resume_generation_job') as mock_resume:
                    response = client.post(f'/jobs/{job_id}/approve', json={
                        'episode_title': "EDITED TITLE",
                        'intro': [{'speaker': 'Raj', 'text': 'New Intro'}],
                        'segments': [
                            {'topic_title': "EDITED TOPIC", 'topic_id': 'topic-1', 'dialogue': []}
                        ],
                        'outro': []
                    })
                    
                    if response.status_code != 302 and response.status_code != 200:
                        print(f"FAIL: API request failed {response.status_code}")
                        print(response.text)
                        return

                    print("API request successful.")
                    
                    # 4. Verify File Update
                    with open(real_script_path, "r") as f:
                        updated_data = json.load(f)
                    
                    print(f"File Title: {updated_data.get('episode_title')}")
                    
                    if updated_data.get('episode_title') == "EDITED TITLE":
                        print("SUCCESS: Script file was updated with new title.")
                    else:
                        print(f"FAIL: Script file not updated. Got: {updated_data.get('episode_title')}")
                        
                    if updated_data['segments'][0]['topic_title'] == "EDITED TOPIC":
                        print("SUCCESS: Segment title updated.")
                    else:
                        # Print what we got
                        print(f"FAIL: Segment title not updated. Got: {updated_data['segments'][0].get('topic_title')}")
                        
                    # 5. Verify Resume called
                    if mock_resume.called:
                        print("SUCCESS: resume_generation_job was triggered.")
                    else:
                        print("FAIL: resume_generation_job was NOT triggered.")
        finally:
            # Cleanup real file
            if real_script_path.exists():
                os.remove(real_script_path)

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    run_test()
