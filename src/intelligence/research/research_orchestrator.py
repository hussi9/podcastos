"""Research Orchestrator - coordinates all research activities."""

import asyncio
from datetime import datetime
from typing import Optional
import logging

from .google_researcher import GoogleResearcher, ResearchDepth
from .exa_researcher import ExaResearcher
from ..models.content import TopicCluster
from ..models.research import (
    ResearchedTopic,
    VerifiedTopic,
    EpisodeResearchBundle,
)


logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """
    Orchestrates research across all sources:
    - Google Research (primary)
    - Exa.ai (counter-arguments)
    - URL Context (specific sources)

    Manages research depth based on topic priority.
    """

    def __init__(
        self,
        google_researcher: Optional[GoogleResearcher] = None,
        exa_researcher: Optional[ExaResearcher] = None,
    ):
        self.google = google_researcher or GoogleResearcher()
        self.exa = exa_researcher or ExaResearcher()

    async def research_cluster(
        self,
        cluster: TopicCluster,
        depth: Optional[ResearchDepth] = None,
        include_counter_arguments: bool = True,
    ) -> ResearchedTopic:
        """
        Research a single topic cluster.
        Automatically determines depth based on priority if not specified.
        """
        # Auto-determine depth
        if depth is None:
            depth = self._determine_depth(cluster)

        # Primary research with Google
        researched = await self.google.research_topic(cluster, depth)

        # Add counter-arguments from Exa (for balanced coverage)
        if include_counter_arguments and researched.verified_facts:
            try:
                main_claim = researched.verified_facts[0].claim if researched.verified_facts else cluster.name
                counter_args = await self.exa.find_counter_arguments(
                    cluster.name,
                    main_claim,
                    num_results=3,
                )
                researched.counter_arguments = counter_args
                researched.exa_search_used = True
            except Exception as e:
                logger.warning(f"Failed to get counter-arguments: {e}")

        return researched

    async def research_clusters(
        self,
        clusters: list[TopicCluster],
        max_concurrent: int = 3,
    ) -> list[ResearchedTopic]:
        """
        Research multiple clusters with controlled concurrency.
        """
        researched_topics = []

        # Process in batches
        for i in range(0, len(clusters), max_concurrent):
            batch = clusters[i:i + max_concurrent]

            tasks = [
                self.research_cluster(cluster)
                for cluster in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for j, result in enumerate(results):
                if isinstance(result, ResearchedTopic):
                    researched_topics.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Research error for cluster {batch[j].id}: {result}")

        logger.info(f"Researched {len(researched_topics)} topics")
        return researched_topics

    async def create_episode_bundle(
        self,
        clusters: list[TopicCluster],
        profile_id: int,
        max_topics: int = 5,
        target_duration_minutes: int = 15,
    ) -> EpisodeResearchBundle:
        """
        Create a complete research bundle for an episode.

        1. Prioritize clusters
        2. Research top clusters
        3. Verify and score topics
        4. Create bundle with proper ordering
        """
        # Sort clusters by priority
        sorted_clusters = sorted(
            clusters,
            key=lambda c: c.priority_score,
            reverse=True,
        )

        # Research top clusters
        top_clusters = sorted_clusters[:max_topics]
        researched_topics = await self.research_clusters(top_clusters)

        # Editorial verification
        verified_topics = []
        for i, topic in enumerate(researched_topics):
            verified = await self._verify_topic(topic, priority_rank=i)
            if verified.editorial_approved:
                verified_topics.append(verified)

        # Create bundle
        bundle = EpisodeResearchBundle(
            id=f"bundle-{profile_id}-{datetime.now().strftime('%Y%m%d%H%M')}",
            profile_id=profile_id,
            episode_date=datetime.now(),
            verified_topics=verified_topics,
        )

        # Determine main theme
        if verified_topics:
            bundle.main_theme = self._determine_main_theme(verified_topics)
            bundle.episode_summary = self._generate_episode_summary(verified_topics)

        bundle.calculate_episode_metrics()

        logger.info(
            f"Created episode bundle with {len(verified_topics)} topics, "
            f"theme: {bundle.main_theme}"
        )

        return bundle

    async def _verify_topic(
        self,
        topic: ResearchedTopic,
        priority_rank: int = 0,
    ) -> VerifiedTopic:
        """
        Verify a researched topic for editorial quality.
        """
        # Calculate editorial score
        score = self._calculate_editorial_score(topic)

        # Determine suggested tone
        if topic.is_breaking_news:
            tone = "urgent"
        elif topic.category in ["tech", "science"]:
            tone = "analytical"
        elif topic.category in ["culture", "community"]:
            tone = "conversational"
        else:
            tone = "informative"

        # Generate talking points
        talking_points = self._generate_talking_points(topic)

        # Estimate duration based on content
        duration = self._estimate_duration(topic)

        return VerifiedTopic(
            id=f"verified-{topic.id}",
            researched_topic=topic,
            editorial_approved=score >= 1.0,  # Lower threshold for now
            editorial_score=score,
            final_headline=topic.headline,
            final_summary=topic.summary,
            suggested_tone=tone,
            suggested_duration_seconds=duration,
            key_talking_points=talking_points,
            priority_rank=priority_rank,
        )

    def _determine_depth(self, cluster: TopicCluster) -> ResearchDepth:
        """
        Determine appropriate research depth based on cluster characteristics.
        """
        # Breaking news = quick (speed matters)
        if cluster.is_breaking:
            return ResearchDepth.QUICK

        # High priority = deep
        if cluster.priority_score >= 8:
            return ResearchDepth.DEEP

        # Multiple sources = standard
        if cluster.source_diversity >= 3:
            return ResearchDepth.STANDARD

        # Default
        return ResearchDepth.STANDARD

    def _calculate_editorial_score(self, topic: ResearchedTopic) -> float:
        """
        Calculate editorial quality score (0-10).
        """
        score = 0.0

        # Fact count (max 3 points)
        fact_points = min(3.0, len(topic.verified_facts) * 0.5)
        score += fact_points

        # Expert opinions (max 2 points)
        expert_points = min(2.0, len(topic.expert_opinions) * 0.5)
        score += expert_points

        # Counter-arguments (max 2 points for balance)
        if topic.counter_arguments:
            score += min(2.0, len(topic.counter_arguments) * 0.5)

        # Has summary (1 point)
        if topic.summary and len(topic.summary) > 50:
            score += 1.0

        # Has implications (1 point)
        if topic.implications and len(topic.implications) > 30:
            score += 1.0

        # Breaking/trending bonus (1 point)
        if topic.is_breaking_news:
            score += 1.0

        return min(10.0, score)

    def _generate_talking_points(self, topic: ResearchedTopic) -> list[str]:
        """
        Generate key talking points from research.
        """
        points = []

        # Start with key facts
        for fact in topic.verified_facts[:3]:
            points.append(fact.claim[:150])

        # Add counter-argument if available
        if topic.counter_arguments:
            points.append(f"However: {topic.counter_arguments[0].argument[:100]}")

        # Add implication
        if topic.implications:
            points.append(f"Why it matters: {topic.implications[:100]}")

        return points

    def _estimate_duration(self, topic: ResearchedTopic) -> int:
        """
        Estimate segment duration in seconds based on content.
        """
        # Base duration
        duration = 60

        # Add time for facts
        duration += len(topic.verified_facts) * 15

        # Add time for expert opinions
        duration += len(topic.expert_opinions) * 20

        # Add time for counter-arguments
        duration += len(topic.counter_arguments) * 15

        # Breaking news gets more time
        if topic.is_breaking_news:
            duration = int(duration * 1.3)

        # Cap at 5 minutes per topic
        return min(300, duration)

    def _determine_main_theme(self, topics: list[VerifiedTopic]) -> str:
        """
        Determine the main theme from verified topics.
        """
        from collections import Counter

        categories = [t.researched_topic.category for t in topics]
        most_common = Counter(categories).most_common(1)

        if most_common:
            category = most_common[0][0]
            return f"Today's {category.title()} News"

        return "Today's Top Stories"

    def _generate_episode_summary(self, topics: list[VerifiedTopic]) -> str:
        """
        Generate episode summary from topics.
        """
        if not topics:
            return ""

        headlines = [t.final_headline for t in topics[:3]]
        return f"In this episode: {'; '.join(headlines)}."


# Helper function for quick research
async def quick_research(topic: str) -> dict:
    """
    Quick research helper for ad-hoc queries.
    """
    researcher = GoogleResearcher()

    # Create a minimal cluster
    from ..models.content import RawContent

    content = RawContent(
        id="adhoc",
        source_type="manual",
        source_name="Manual",
        title=topic,
        body="",
        published_at=datetime.now(),
    )

    cluster = TopicCluster(
        id="adhoc",
        name=topic,
        summary="",
        contents=[content],
    )

    researched = await researcher.research_topic(cluster, ResearchDepth.QUICK)

    return {
        "headline": researched.headline,
        "summary": researched.summary,
        "facts": [f.claim for f in researched.verified_facts],
        "sources_count": researched.sources_consulted,
    }
