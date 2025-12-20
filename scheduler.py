"""
Scheduled podcast generation
Can be run as a standalone service or via cron/systemd
"""

import asyncio
import os
from datetime import datetime
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from src.podcast_engine import create_engine_from_env, PodcastEngine
from src.rss_generator import RSSGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


async def generate_daily_episode(engine: PodcastEngine, rss_generator: RSSGenerator):
    """Generate the daily podcast episode"""
    logger.info("🎙️  Starting daily episode generation...")

    try:
        # Generate episode
        metadata = await engine.generate_episode(
            target_date=datetime.now(),
            topic_count=5,
            target_duration_minutes=12,
            generate_audio=True,
        )

        logger.info(f"✅ Episode generated: {metadata.episode_id}")
        logger.info(f"   Title: {metadata.title}")
        logger.info(f"   Duration: {metadata.duration_seconds // 60} minutes")

        # Update RSS feed
        episodes = engine.list_episodes()
        feed_path = os.path.join(engine.output_dir, "feed.xml")
        rss_generator.generate_feed(episodes, feed_path)
        logger.info(f"✅ RSS feed updated: {feed_path}")

        # Optional: Upload to storage (S3, etc.)
        # await upload_episode(metadata)

        return metadata

    except Exception as e:
        logger.error(f"❌ Episode generation failed: {e}")
        raise


async def run_once():
    """Run a single episode generation (for testing or manual triggers)"""
    logger.info("Running one-time episode generation...")

    engine = await create_engine_from_env()
    rss_generator = RSSGenerator()

    await generate_daily_episode(engine, rss_generator)


async def run_scheduler():
    """Run the scheduled podcast generator"""
    logger.info("Starting scheduled podcast generator...")

    engine = await create_engine_from_env()
    rss_generator = RSSGenerator()

    # Get schedule from environment
    generation_hour = int(os.getenv("GENERATION_HOUR", "6"))
    timezone = os.getenv("TIMEZONE", "America/New_York")

    scheduler = AsyncIOScheduler(timezone=timezone)

    # Schedule daily generation
    scheduler.add_job(
        generate_daily_episode,
        CronTrigger(hour=generation_hour, minute=0),
        args=[engine, rss_generator],
        id="daily_episode",
        name="Daily Episode Generation",
        replace_existing=True,
    )

    logger.info(f"📅 Scheduled daily generation at {generation_hour}:00 {timezone}")

    scheduler.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Desi Podcast Generator Scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't start scheduler)",
    )
    parser.add_argument(
        "--enhanced",
        action="store_true",
        help="Use enhanced mode with deep research (Gemini + Google Search)",
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="Generate script only (no audio)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview today's content without generating",
    )
    parser.add_argument(
        "--notebooklm",
        action="store_true",
        help="Export for Google NotebookLM (use their Audio Overview feature)",
    )

    args = parser.parse_args()

    if args.preview:
        async def preview():
            engine = await create_engine_from_env()
            preview_data = await engine.get_content_preview()

            print("\n📋 Today's Content Preview")
            print("=" * 50)
            print(f"Date: {preview_data['date']}")
            print(f"Topics found: {preview_data['topic_count']}")
            print()

            for i, topic in enumerate(preview_data["topics"], 1):
                flags = []
                if topic.get("is_breaking"):
                    flags.append("🔴 BREAKING")
                if topic.get("is_trending"):
                    flags.append("📈 TRENDING")
                flag_str = " ".join(flags)

                print(f"{i}. {topic['title']} {flag_str}")
                print(f"   Category: {topic['category']}")
                print(f"   Score: {topic['score']:.1f}")
                print(f"   Sources: {', '.join(topic['sources'])}")
                if topic.get("key_points"):
                    print("   Key points:")
                    for point in topic["key_points"]:
                        print(f"     • {point[:80]}...")
                print()

        asyncio.run(preview())

    elif args.notebooklm:
        # Export for NotebookLM
        async def export_notebooklm():
            from export_for_notebooklm import export_topics_for_notebooklm

            logger.info("📓 Exporting topics for Google NotebookLM...")
            output_path = await export_topics_for_notebooklm()

            # Open NotebookLM in browser
            import subprocess
            subprocess.run(["open", "https://notebooklm.google.com"])

            # Open the output folder
            import os
            output_dir = os.path.dirname(output_path)
            subprocess.run(["open", output_dir])

            print("\n" + "=" * 60)
            print("📓 NotebookLM WORKFLOW")
            print("=" * 60)
            print("1. NotebookLM is open in your browser")
            print("2. The export folder is open in Finder")
            print(f"3. Upload: {output_path}")
            print("4. Click 'Audio Overview' → 'Deep Dive'")
            print("5. Wait ~2-3 minutes for podcast generation")
            print("6. Download the MP3 and save to output/notebooklm/")
            print("=" * 60)

        asyncio.run(export_notebooklm())

    elif args.once:
        if args.enhanced:
            # Enhanced mode with deep research
            async def run_enhanced():
                logger.info("🔬 Running ENHANCED mode with deep research...")
                engine = await create_engine_from_env()
                rss_generator = RSSGenerator()

                metadata = await engine.generate_enhanced_episode(
                    target_date=datetime.now(),
                    topic_count=5,
                    target_duration_minutes=15,
                    generate_audio=not args.script_only,
                )

                print(f"\n✅ Enhanced episode generated: {metadata.episode_id}")
                print(f"   Title: {metadata.title}")
                print(f"   Duration: {metadata.duration_seconds // 60} minutes")
                print(f"   Topics: {len(metadata.topics)}")

                if not args.script_only:
                    # Update RSS feed
                    episodes = engine.list_episodes()
                    feed_path = os.path.join(engine.output_dir, "feed.xml")
                    rss_generator.generate_feed(episodes, feed_path)
                    print(f"✅ RSS feed updated: {feed_path}")

            asyncio.run(run_enhanced())

        elif args.script_only:
            async def script_only():
                engine = await create_engine_from_env()
                script = await engine.generate_script_only()
                print(f"\n✅ Script generated: {script.episode_id}")
                print(f"   Title: {script.episode_title}")
                print(f"   Segments: {len(script.segments)}")

            asyncio.run(script_only())
        else:
            asyncio.run(run_once())

    else:
        asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
