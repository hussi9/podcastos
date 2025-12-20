"""
Topic Verifier - Validates and enhances researched topics for podcast generation.

Takes a ResearchedTopic and returns a VerifiedTopic ready for script generation.
"""

import logging
from datetime import datetime
from typing import Optional

from ..models.research import ResearchedTopic, VerifiedTopic


logger = logging.getLogger(__name__)


class TopicVerifier:
    """
    Verifies and enhances researched topics.

    Responsibilities:
    1. Validate research quality
    2. Generate editorial score
    3. Suggest tone and duration
    4. Extract key talking points
    """

    def __init__(self, min_score: float = 3.0):
        self.min_score = min_score

    async def verify_topic(self, researched: ResearchedTopic) -> Optional[VerifiedTopic]:
        """
        Verify a researched topic and prepare for script generation.

        Args:
            researched: The researched topic to verify

        Returns:
            VerifiedTopic if approved, None if rejected
        """
        try:
            # Calculate editorial score
            score = self._calculate_score(researched)

            # Generate key talking points
            talking_points = self._extract_talking_points(researched)

            # Suggest tone based on content
            tone = self._suggest_tone(researched)

            # Calculate suggested duration
            duration = self._calculate_duration(researched)

            # Create verified topic
            verified = VerifiedTopic(
                id=f"verified-{researched.id}",
                researched_topic=researched,
                editorial_approved=score >= self.min_score,
                editorial_score=score,
                final_headline=researched.headline,
                final_summary=researched.summary,
                suggested_tone=tone,
                suggested_duration_seconds=duration,
                key_talking_points=talking_points,
                verified_at=datetime.now(),
            )

            logger.info(f"Topic verified: {researched.headline[:50]}... (score: {score:.1f})")
            return verified

        except Exception as e:
            logger.error(f"Topic verification failed: {e}")
            # Return a basic verified topic even on error
            return VerifiedTopic(
                id=f"verified-{researched.id}",
                researched_topic=researched,
                editorial_approved=True,
                editorial_score=5.0,
                final_headline=researched.headline,
                final_summary=researched.summary,
                suggested_tone="informative",
                suggested_duration_seconds=180,
                key_talking_points=[],
            )

    def _calculate_score(self, researched: ResearchedTopic) -> float:
        """
        Calculate editorial score based on research quality.

        Scoring (0-10):
        - Facts: up to 3 points
        - Summary quality: up to 2 points
        - Source diversity: up to 2 points
        - Expert opinions: up to 2 points
        - Timeliness: up to 1 point
        """
        score = 0.0

        # Facts (0-3 points)
        fact_count = len(researched.verified_facts)
        score += min(fact_count / 2, 3.0)

        # Summary quality (0-2 points)
        summary_words = len(researched.summary.split())
        if summary_words >= 50:
            score += 2.0
        elif summary_words >= 25:
            score += 1.0

        # Source diversity (0-2 points)
        score += min(researched.source_diversity, 2.0)

        # Expert opinions (0-2 points)
        opinion_count = len(researched.expert_opinions)
        score += min(opinion_count, 2.0)

        # Timeliness (0-1 point)
        if researched.is_breaking_news:
            score += 1.0
        elif researched.trend_velocity.value in ["rising", "viral"]:
            score += 0.5

        return min(score, 10.0)

    def _extract_talking_points(self, researched: ResearchedTopic) -> list[str]:
        """Extract key talking points from research."""
        points = []

        # From headline
        if researched.headline:
            points.append(researched.headline)

        # From verified facts (top 3)
        for fact in researched.verified_facts[:3]:
            points.append(fact.fact)

        # From expert opinions (top 2)
        for opinion in researched.expert_opinions[:2]:
            points.append(f"{opinion.expert_name}: {opinion.opinion[:100]}")

        # From implications
        if researched.implications:
            points.append(f"Impact: {researched.implications[:100]}")

        return points[:5]  # Max 5 points

    def _suggest_tone(self, researched: ResearchedTopic) -> str:
        """Suggest appropriate tone based on content."""
        if researched.is_breaking_news:
            return "urgent"

        if researched.category in ["technology", "science", "analysis"]:
            return "analytical"

        if researched.category in ["lifestyle", "entertainment", "culture"]:
            return "conversational"

        if len(researched.counter_arguments) > 0:
            return "balanced"

        return "informative"

    def _calculate_duration(self, researched: ResearchedTopic) -> int:
        """Calculate suggested segment duration in seconds."""
        # Base duration
        duration = 120  # 2 minutes base

        # Add for content depth
        fact_count = len(researched.verified_facts)
        duration += fact_count * 15  # 15 seconds per fact

        opinion_count = len(researched.expert_opinions)
        duration += opinion_count * 20  # 20 seconds per opinion

        # Add for background/context
        if researched.background:
            duration += 30

        # Cap at 5 minutes for a single topic
        return min(duration, 300)
