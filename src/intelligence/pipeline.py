"""
Main Pipeline - Complete episode generation from start to finish.

Usage:
    python -m src.intelligence.pipeline --profile tech --name "Tech Daily"
    python -m src.intelligence.pipeline --profile finance --quick
"""

import asyncio
import argparse
import logging
import json
from datetime import datetime
from pathlib import Path

from .models.content import ProfileSourceConfig
from .synthesis.episode_synthesizer import EpisodeSynthesizer, EpisodeResult
from .audio.tts_generator import TTSGenerator
from .audio.audio_stitcher import AudioStitcher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_pipeline(
    profile_type: str = "tech",
    podcast_name: str = "Your Daily Podcast",
    max_topics: int = 5,
    quick_mode: bool = False,
    generate_audio: bool = True,
    output_dir: str = "./output",
) -> dict:
    """
    Run the complete podcast generation pipeline.

    Returns dict with paths and stats.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = {
        "started_at": datetime.now().isoformat(),
        "profile_type": profile_type,
        "podcast_name": podcast_name,
    }

    # Create profile config
    profile_id = 1
    if profile_type == "tech":
        config = ProfileSourceConfig.for_tech_podcast(profile_id)
    elif profile_type == "finance":
        config = ProfileSourceConfig.for_finance_podcast(profile_id)
    elif profile_type == "immigration":
        config = ProfileSourceConfig.for_immigration_podcast(profile_id)
    else:
        raise ValueError(f"Unknown profile type: {profile_type}")

    logger.info(f"Starting pipeline for {profile_type} podcast: {podcast_name}")

    # Initialize synthesizer
    synthesizer = EpisodeSynthesizer()

    # Run synthesis
    if quick_mode:
        episode_result = await synthesizer.synthesize_quick(
            profile_id=profile_id,
            podcast_name=podcast_name,
            max_topics=max_topics,
        )
    else:
        episode_result = await synthesizer.synthesize_episode(
            profile_id=profile_id,
            profile_config=config,
            podcast_name=podcast_name,
            max_topics=max_topics,
        )

    if not episode_result.success:
        logger.error(f"Pipeline failed: {episode_result.errors}")
        results["success"] = False
        results["errors"] = episode_result.errors
        return results

    script = episode_result.script
    results["synthesis_stats"] = episode_result.stats

    # Save script
    script_path = output_path / f"{script.id}_script.json"
    with open(script_path, "w") as f:
        json.dump(script.model_dump(mode="json"), f, indent=2, default=str)
    results["script_path"] = str(script_path)

    logger.info(f"Script saved: {script_path}")

    # Generate audio if requested
    if generate_audio:
        logger.info("Generating audio...")

        tts = TTSGenerator(output_dir=str(output_path))
        audio_episode = await tts.generate_episode_audio(script)

        # Stitch and save manifest
        stitcher = AudioStitcher(output_dir=str(output_path))
        audio_path = stitcher.stitch_episode(audio_episode)
        manifest_path = stitcher.save_manifest(audio_episode)

        results["audio_path"] = audio_path
        results["manifest_path"] = manifest_path
        results["audio_duration_seconds"] = audio_episode.total_duration_seconds

        logger.info(f"Audio saved: {audio_path}")

    results["success"] = True
    results["completed_at"] = datetime.now().isoformat()

    # Print summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Profile: {profile_type}")
    print(f"Podcast: {podcast_name}")
    print(f"Topics: {len(script.segments)}")
    print(f"Words: {script.word_count}")
    print(f"Duration: ~{script.total_duration_seconds // 60:.0f} minutes")
    if generate_audio:
        print(f"Audio: {results['audio_path']}")
    print(f"Script: {results['script_path']}")
    print("=" * 60 + "\n")

    return results


async def test_aggregation_only(profile_type: str = "tech", limit: int = 20):
    """Test content aggregation without full pipeline."""
    from .aggregation.source_manager import (
        create_tech_source_manager,
        create_finance_source_manager,
        create_immigration_source_manager,
    )

    if profile_type == "tech":
        manager = create_tech_source_manager(1)
    elif profile_type == "finance":
        manager = create_finance_source_manager(1)
    else:
        manager = create_immigration_source_manager(1)

    logger.info(f"Testing aggregation for {profile_type}...")
    contents = await manager.fetch_all(limit_per_source=limit)

    print(f"\nFetched {len(contents)} items:")
    for i, content in enumerate(contents[:10], 1):
        print(f"{i}. [{content.source_name}] {content.title[:60]}...")

    return contents


async def test_clustering_only(contents: list):
    """Test semantic clustering."""
    from .clustering.clusterer import SemanticClusterer
    from .clustering.topic_namer import TopicNamer

    clusterer = SemanticClusterer()
    namer = TopicNamer()

    logger.info("Testing clustering...")
    clusters = clusterer.cluster_contents(contents)

    print(f"\nCreated {len(clusters)} clusters:")
    for cluster in clusters[:5]:
        print(f"- {cluster.name[:50]} ({len(cluster.contents)} items, score: {cluster.priority_score:.1f})")

    logger.info("Testing topic naming...")
    named = await namer.name_clusters(clusters[:3])

    print("\nNamed clusters:")
    for cluster in named:
        print(f"- {cluster.name}: {cluster.summary[:80]}...")

    return clusters


async def test_research_only(topic: str):
    """Test research on a specific topic."""
    from .research.research_orchestrator import quick_research

    logger.info(f"Testing research for: {topic}")
    result = await quick_research(topic)

    print(f"\nResearch Results for: {topic}")
    print(f"Headline: {result['headline']}")
    print(f"Summary: {result['summary'][:200]}...")
    print(f"Facts: {len(result['facts'])}")
    print(f"Sources: {result['sources_count']}")

    return result


def main():
    parser = argparse.ArgumentParser(description="PodcastOS Intelligence Pipeline")
    parser.add_argument(
        "--profile",
        choices=["tech", "finance", "immigration"],
        default="tech",
        help="Podcast profile type",
    )
    parser.add_argument(
        "--name",
        default="Your Daily Podcast",
        help="Podcast name",
    )
    parser.add_argument(
        "--topics",
        type=int,
        default=5,
        help="Maximum number of topics",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode (faster, less research)",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Skip audio generation",
    )
    parser.add_argument(
        "--output",
        default="./output",
        help="Output directory",
    )
    parser.add_argument(
        "--test",
        choices=["aggregation", "clustering", "research"],
        help="Run specific test instead of full pipeline",
    )
    parser.add_argument(
        "--research-topic",
        help="Topic to research (used with --test research)",
    )

    args = parser.parse_args()

    if args.test == "aggregation":
        asyncio.run(test_aggregation_only(args.profile))
    elif args.test == "clustering":
        contents = asyncio.run(test_aggregation_only(args.profile))
        asyncio.run(test_clustering_only(contents))
    elif args.test == "research":
        topic = args.research_topic or "AI regulation 2024"
        asyncio.run(test_research_only(topic))
    else:
        asyncio.run(
            run_pipeline(
                profile_type=args.profile,
                podcast_name=args.name,
                max_topics=args.topics,
                quick_mode=args.quick,
                generate_audio=not args.no_audio,
                output_dir=args.output,
            )
        )


if __name__ == "__main__":
    main()
