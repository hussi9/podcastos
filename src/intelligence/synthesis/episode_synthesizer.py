"""Episode Synthesizer - orchestrates the complete pipeline."""

import asyncio
from datetime import datetime
from typing import Optional
import logging

from ..aggregation.source_manager import SourceManager
from ..clustering.clusterer import SemanticClusterer
from ..clustering.topic_namer import TopicNamer
from ..research.research_orchestrator import ResearchOrchestrator
from .script_generator import ScriptGenerator, PodcastScript
from ..models.content import ProfileSourceConfig


logger = logging.getLogger(__name__)


class EpisodeResult:
    """Result of episode synthesis."""

    def __init__(
        self,
        script: PodcastScript,
        stats: dict,
        errors: list[str] = None,
    ):
        self.script = script
        self.stats = stats
        self.errors = errors or []
        self.success = len(self.errors) == 0


class EpisodeSynthesizer:
    """
    Complete episode synthesis pipeline:

    1. Aggregate content from sources
    2. Cluster semantically
    3. Name clusters with LLM
    4. Research top clusters
    5. Generate script

    This is the main entry point for podcast generation.
    """

    def __init__(
        self,
        source_manager: Optional[SourceManager] = None,
        clusterer: Optional[SemanticClusterer] = None,
        topic_namer: Optional[TopicNamer] = None,
        research_orchestrator: Optional[ResearchOrchestrator] = None,
        script_generator: Optional[ScriptGenerator] = None,
    ):
        self.source_manager = source_manager
        self.clusterer = clusterer or SemanticClusterer()
        self.topic_namer = topic_namer or TopicNamer()
        self.research_orchestrator = research_orchestrator or ResearchOrchestrator()
        self.script_generator = script_generator or ScriptGenerator()

    async def synthesize_episode(
        self,
        profile_id: int,
        profile_config: Optional[ProfileSourceConfig] = None,
        podcast_name: str = "Your Daily Podcast",
        max_topics: int = 5,
        target_duration_minutes: int = 15,
    ) -> EpisodeResult:
        """
        Synthesize a complete podcast episode.

        Returns EpisodeResult with script and stats.
        """
        stats = {
            "started_at": datetime.now().isoformat(),
            "profile_id": profile_id,
            "stages": {},
        }
        errors = []

        try:
            # Stage 1: Content Aggregation
            logger.info("Stage 1: Aggregating content...")
            stage_start = datetime.now()

            if profile_config:
                self.source_manager = SourceManager(profile_config)
            elif not self.source_manager:
                # Default to tech podcast
                self.source_manager = SourceManager(
                    ProfileSourceConfig.for_tech_podcast(profile_id)
                )

            contents = await self.source_manager.fetch_all(limit_per_source=50)

            stats["stages"]["aggregation"] = {
                "duration_seconds": (datetime.now() - stage_start).total_seconds(),
                "items_fetched": len(contents),
                "sources_used": len(self.source_manager.connectors),
            }

            if not contents:
                errors.append("No content fetched from sources")
                return EpisodeResult(None, stats, errors)

            # Stage 2: Semantic Clustering
            logger.info("Stage 2: Clustering content...")
            stage_start = datetime.now()

            clusters = self.clusterer.cluster_contents(contents)

            # Merge similar clusters
            clusters = self.clusterer.merge_similar_clusters(clusters)

            stats["stages"]["clustering"] = {
                "duration_seconds": (datetime.now() - stage_start).total_seconds(),
                "clusters_created": len(clusters),
            }

            if not clusters:
                errors.append("No clusters created from content")
                return EpisodeResult(None, stats, errors)

            # Stage 3: Topic Naming
            logger.info("Stage 3: Naming topics...")
            stage_start = datetime.now()

            named_clusters = await self.topic_namer.name_clusters(clusters[:max_topics * 2])

            stats["stages"]["naming"] = {
                "duration_seconds": (datetime.now() - stage_start).total_seconds(),
                "topics_named": len(named_clusters),
            }

            # Stage 4: Research
            logger.info("Stage 4: Researching topics...")
            stage_start = datetime.now()

            bundle = await self.research_orchestrator.create_episode_bundle(
                clusters=named_clusters,
                profile_id=profile_id,
                max_topics=max_topics,
            )

            stats["stages"]["research"] = {
                "duration_seconds": (datetime.now() - stage_start).total_seconds(),
                "topics_researched": len(bundle.verified_topics),
                "total_facts": bundle.total_facts_verified,
                "sources_consulted": bundle.total_sources_consulted,
            }

            if not bundle.verified_topics:
                errors.append("No topics passed verification")
                return EpisodeResult(None, stats, errors)

            # Stage 5: Script Generation
            logger.info("Stage 5: Generating script...")
            stage_start = datetime.now()

            script = await self.script_generator.generate_script(
                bundle=bundle,
                podcast_name=podcast_name,
            )

            stats["stages"]["script_generation"] = {
                "duration_seconds": (datetime.now() - stage_start).total_seconds(),
                "segments_generated": len(script.segments),
                "total_words": script.word_count,
                "estimated_duration_seconds": script.total_duration_seconds,
            }

            # Final stats
            stats["completed_at"] = datetime.now().isoformat()
            stats["total_duration_seconds"] = sum(
                s["duration_seconds"] for s in stats["stages"].values()
            )

            logger.info(
                f"Episode synthesis complete: {len(script.segments)} segments, "
                f"{script.word_count} words, "
                f"~{script.total_duration_seconds // 60} minutes, "
                f"in {stats['total_duration_seconds']:.1f}s"
            )

            return EpisodeResult(script, stats, errors)

        except Exception as e:
            logger.error(f"Episode synthesis failed: {e}")
            errors.append(str(e))
            stats["error"] = str(e)
            stats["completed_at"] = datetime.now().isoformat()
            return EpisodeResult(None, stats, errors)

    async def synthesize_quick(
        self,
        profile_id: int,
        podcast_name: str = "Quick Update",
        max_topics: int = 3,
    ) -> EpisodeResult:
        """
        Quick episode synthesis with minimal research.
        Good for breaking news or rapid updates.
        """
        from ..research.google_researcher import ResearchDepth

        # Override research depth to quick
        original_determine_depth = self.research_orchestrator._determine_depth

        def quick_depth(cluster):
            return ResearchDepth.QUICK

        self.research_orchestrator._determine_depth = quick_depth

        try:
            result = await self.synthesize_episode(
                profile_id=profile_id,
                podcast_name=podcast_name,
                max_topics=max_topics,
            )
        finally:
            # Restore original method
            self.research_orchestrator._determine_depth = original_determine_depth

        return result


# Convenience function for direct usage
async def create_episode(
    profile_type: str = "tech",
    podcast_name: str = "Your Daily Podcast",
    max_topics: int = 5,
) -> EpisodeResult:
    """
    Create an episode with a preset profile type.

    profile_type: "tech", "finance", or "immigration"
    """
    profile_id = 1

    if profile_type == "tech":
        config = ProfileSourceConfig.for_tech_podcast(profile_id)
    elif profile_type == "finance":
        config = ProfileSourceConfig.for_finance_podcast(profile_id)
    elif profile_type == "immigration":
        config = ProfileSourceConfig.for_immigration_podcast(profile_id)
    else:
        raise ValueError(f"Unknown profile type: {profile_type}")

    synthesizer = EpisodeSynthesizer()

    return await synthesizer.synthesize_episode(
        profile_id=profile_id,
        profile_config=config,
        podcast_name=podcast_name,
        max_topics=max_topics,
    )
