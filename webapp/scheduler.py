"""
Podcast Generation Scheduler.
Uses APScheduler to run podcast generation at scheduled times.
"""

import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from webapp.models import PodcastProfile, GenerationJob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('podcast_scheduler')

# Global scheduler instance
scheduler = None
_scheduler_lock = threading.Lock()


def get_scheduler():
    """Get or create the global scheduler instance."""
    global scheduler
    with _scheduler_lock:
        if scheduler is None:
            scheduler = BackgroundScheduler(
                timezone='UTC',
                job_defaults={
                    'coalesce': True,  # Combine missed runs into one
                    'max_instances': 1,  # Only one instance per job
                    'misfire_grace_time': 3600,  # 1 hour grace period
                }
            )
        return scheduler


def init_scheduler(db_path: str = None):
    """Initialize and start the scheduler with all active profiles."""
    if db_path is None:
        db_path = Path(__file__).parent / 'podcast_studio.db'

    sched = get_scheduler()

    # Don't start if already running
    if sched.running:
        logger.info("Scheduler already running")
        return sched

    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)

    # Load all profiles with scheduling enabled
    db = Session()
    try:
        profiles = db.query(PodcastProfile).filter_by(
            is_active=True,
            schedule_enabled=True
        ).all()

        for profile in profiles:
            add_profile_job(profile)

        logger.info(f"Loaded {len(profiles)} scheduled profiles")
    finally:
        db.close()

    # Start the scheduler
    sched.start()
    logger.info("Scheduler started")

    return sched


def add_profile_job(profile: PodcastProfile):
    """Add or update a scheduled job for a profile."""
    sched = get_scheduler()
    job_id = f"profile_{profile.id}_generation"

    # Remove existing job if any
    if sched.get_job(job_id):
        sched.remove_job(job_id)
        logger.info(f"Removed existing job for profile {profile.id}")

    if not profile.schedule_enabled:
        logger.info(f"Scheduling disabled for profile {profile.id}")
        return

    # Build cron trigger from profile settings
    # Convert day names to cron day_of_week format
    day_map = {
        'mon': 'mon', 'tue': 'tue', 'wed': 'wed', 'thu': 'thu',
        'fri': 'fri', 'sat': 'sat', 'sun': 'sun'
    }

    days = profile.schedule_days or ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    day_of_week = ','.join([day_map.get(d.lower(), d) for d in days])

    trigger = CronTrigger(
        hour=profile.schedule_hour or 6,
        minute=profile.schedule_minute or 0,
        day_of_week=day_of_week,
        timezone=profile.timezone or 'America/New_York'
    )

    sched.add_job(
        run_scheduled_generation,
        trigger=trigger,
        id=job_id,
        args=[profile.id],
        name=f"Generate {profile.name}",
        replace_existing=True,
    )

    logger.info(f"Scheduled job for profile {profile.id} ({profile.name}) at {profile.schedule_hour}:{profile.schedule_minute:02d} on {day_of_week}")


def remove_profile_job(profile_id: int):
    """Remove a scheduled job for a profile."""
    sched = get_scheduler()
    job_id = f"profile_{profile_id}_generation"

    if sched.get_job(job_id):
        sched.remove_job(job_id)
        logger.info(f"Removed scheduled job for profile {profile_id}")


def run_scheduled_generation(profile_id: int):
    """Run a scheduled podcast generation."""
    import asyncio
    from webapp.app import run_generation_pipeline, Session

    logger.info(f"Starting scheduled generation for profile {profile_id}")

    db = Session()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if not profile:
            logger.error(f"Profile {profile_id} not found")
            return

        if not profile.is_active:
            logger.info(f"Profile {profile_id} is not active, skipping")
            return

        # Create a generation job
        job_id = f"scheduled-{uuid.uuid4().hex[:8]}"
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

        # Update last scheduled run
        profile.last_scheduled_run = datetime.utcnow()
        db.commit()

        logger.info(f"Created job {job_id} for profile {profile_id}")

        # Get generation options from profile
        options = {
            'topic_count': profile.topic_count,
            'duration': profile.target_duration_minutes,
            'deep_research': True,
            'use_continuity': True,
            'tts_model': profile.tts_model or 'gemini-2.5-flash-preview-tts',
        }

    finally:
        db.close()

    # Run the generation pipeline in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(run_generation_pipeline(job_id, profile_id, options))
        logger.info(f"Completed scheduled generation for profile {profile_id}")
    except Exception as e:
        logger.error(f"Scheduled generation failed for profile {profile_id}: {e}")
        # Update job status
        db = Session()
        try:
            job = db.query(GenerationJob).filter_by(job_id=job_id).first()
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    finally:
        loop.close()


def get_scheduled_jobs():
    """Get list of all scheduled jobs."""
    sched = get_scheduler()
    jobs = []

    for job in sched.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger),
        })

    return jobs


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")


# Convenience function to update a profile's schedule
def update_profile_schedule(profile_id: int, db_path: str = None):
    """Update the schedule for a specific profile."""
    if db_path is None:
        db_path = Path(__file__).parent / 'podcast_studio.db'

    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)

    db = Session()
    try:
        profile = db.query(PodcastProfile).get(profile_id)
        if profile:
            if profile.schedule_enabled:
                add_profile_job(profile)
            else:
                remove_profile_job(profile_id)
    finally:
        db.close()


if __name__ == '__main__':
    # Test the scheduler
    print("Testing scheduler...")

    init_scheduler()

    jobs = get_scheduled_jobs()
    print(f"Scheduled jobs: {len(jobs)}")
    for job in jobs:
        print(f"  - {job['name']}: next run at {job['next_run']}")

    print("\nScheduler is running. Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_scheduler()
        print("Scheduler stopped.")
