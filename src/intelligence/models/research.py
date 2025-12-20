"""
Research models for the intelligence pipeline.
Represents researched, verified, and synthesized content.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TrendVelocity(str, Enum):
    """How fast a topic is trending."""
    STABLE = "stable"
    RISING = "rising"
    VIRAL = "viral"
    DECLINING = "declining"


class VerifiedFact(BaseModel):
    """
    A single verified fact from research.
    Includes source attribution and confidence.
    """

    claim: str = Field(..., description="The factual claim")
    source_url: str = Field(..., description="Primary source URL")
    source_name: str = Field(..., description="Source name (e.g., 'Reuters', 'Official USCIS')")
    source_type: str = Field(default="news", description="news, official, academic, community")

    # Verification
    verification_status: str = Field(default="unverified", description="verified, disputed, unverified")
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    corroborating_sources: list[str] = Field(default_factory=list)

    # Context
    context: Optional[str] = None
    date_of_fact: Optional[datetime] = None

    # For citations in script
    citation_text: Optional[str] = None


class ExpertOpinion(BaseModel):
    """
    An expert opinion or quote found during research.
    """

    quote: str = Field(..., description="The expert's statement")
    expert_name: str = Field(..., description="Name of the expert")
    expert_title: Optional[str] = None
    expert_affiliation: Optional[str] = None
    source_url: str
    date: Optional[datetime] = None

    # Perspective
    stance: str = Field(default="neutral", description="pro, con, neutral")
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)


class CounterArgument(BaseModel):
    """
    A counter-argument or alternative perspective.
    Sourced via Exa.ai to overcome Google's SEO bias.
    """

    argument: str = Field(..., description="The counter-argument")
    source_url: str
    source_name: str
    source_credibility: float = Field(default=0.5, ge=0.0, le=1.0)

    # Context
    context: Optional[str] = None
    expert_backing: Optional[str] = None


class ResearchedTopic(BaseModel):
    """
    A fully researched topic ready for script generation.
    Contains all facts, opinions, and counter-arguments.
    """

    id: str
    cluster_id: str = Field(..., description="Original TopicCluster ID")

    # Core content
    headline: str = Field(..., description="Compelling headline for the topic")
    summary: str = Field(..., description="2-3 paragraph executive summary")
    category: str = Field(default="general")

    # Deep research results
    background: str = Field(default="", description="Historical context and background")
    current_situation: str = Field(default="", description="What's happening now")
    implications: str = Field(default="", description="Why this matters, future impact")

    # Verified content
    verified_facts: list[VerifiedFact] = Field(default_factory=list)
    expert_opinions: list[ExpertOpinion] = Field(default_factory=list)
    counter_arguments: list[CounterArgument] = Field(default_factory=list)

    # Human stories (from Reddit, HN comments, etc.)
    human_stories: list[str] = Field(default_factory=list)
    community_sentiment: Optional[str] = None

    # Trending info
    trend_velocity: TrendVelocity = TrendVelocity.STABLE
    is_breaking_news: bool = False

    # Research metadata
    research_depth: str = Field(default="quick", description="quick, standard, deep")
    research_duration_seconds: float = 0.0
    sources_consulted: int = 0
    google_search_grounding_used: bool = False
    deep_research_used: bool = False
    exa_search_used: bool = False

    # Timestamps
    researched_at: datetime = Field(default_factory=datetime.now)

    # Quality metrics
    fact_density: float = 0.0  # Facts per 100 words
    source_diversity: int = 0  # Unique source types
    balance_score: float = 0.0  # Pro vs Con balance (0.5 = balanced)

    def calculate_quality_metrics(self):
        """Calculate quality metrics from research content."""
        # Fact density
        total_words = len(self.summary.split()) + len(self.background.split())
        if total_words > 0:
            self.fact_density = (len(self.verified_facts) / total_words) * 100

        # Source diversity
        source_types = set()
        for fact in self.verified_facts:
            source_types.add(fact.source_type)
        self.source_diversity = len(source_types)

        # Balance score
        pro_count = sum(1 for o in self.expert_opinions if o.stance == "pro")
        con_count = sum(1 for o in self.expert_opinions if o.stance == "con")
        total_opinions = pro_count + con_count
        if total_opinions > 0:
            self.balance_score = min(pro_count, con_count) / total_opinions
        else:
            self.balance_score = 0.5  # Neutral if no opinions


class VerifiedTopic(BaseModel):
    """
    A topic that has passed editorial review.
    Ready for script generation.
    """

    id: str
    researched_topic: ResearchedTopic

    # Editorial review
    editorial_approved: bool = False
    editorial_notes: Optional[str] = None
    editorial_score: float = Field(default=0.0, ge=0.0, le=10.0)

    # Final headline (may be edited)
    final_headline: str
    final_summary: str

    # Script generation hints
    suggested_tone: str = Field(default="informative", description="informative, conversational, urgent, analytical")
    suggested_duration_seconds: int = Field(default=180, description="Target segment duration")
    key_talking_points: list[str] = Field(default_factory=list)

    # Ordering
    priority_rank: int = Field(default=0, description="Order in the episode")

    # Timestamps
    verified_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_researched_topic(
        cls,
        researched_topic: ResearchedTopic,
        editorial_score: float = 7.0,
        priority_rank: int = 0,
    ) -> "VerifiedTopic":
        """Create a verified topic from a researched topic."""
        return cls(
            id=f"verified-{researched_topic.id}",
            researched_topic=researched_topic,
            editorial_approved=True,
            editorial_score=editorial_score,
            final_headline=researched_topic.headline,
            final_summary=researched_topic.summary,
            suggested_tone="urgent" if researched_topic.is_breaking_news else "informative",
            suggested_duration_seconds=180 if researched_topic.research_depth == "quick" else 300,
            key_talking_points=[f.claim for f in researched_topic.verified_facts[:5]],
            priority_rank=priority_rank,
        )


class EpisodeResearchBundle(BaseModel):
    """
    Complete research bundle for a single episode.
    Contains all verified topics ready for script generation.
    """

    id: str
    profile_id: int
    episode_date: datetime

    # Topics for this episode
    verified_topics: list[VerifiedTopic] = Field(default_factory=list)

    # Episode-level metadata
    main_theme: Optional[str] = None
    episode_summary: Optional[str] = None

    # Research stats
    total_sources_consulted: int = 0
    total_facts_verified: int = 0
    total_research_time_seconds: float = 0.0

    # Quality
    average_topic_score: float = 0.0
    overall_balance_score: float = 0.0

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    ready_for_script: bool = False

    def calculate_episode_metrics(self):
        """Calculate episode-level metrics."""
        if not self.verified_topics:
            return

        # Aggregate stats
        self.total_sources_consulted = sum(
            t.researched_topic.sources_consulted for t in self.verified_topics
        )
        self.total_facts_verified = sum(
            len(t.researched_topic.verified_facts) for t in self.verified_topics
        )
        self.total_research_time_seconds = sum(
            t.researched_topic.research_duration_seconds for t in self.verified_topics
        )

        # Quality metrics
        scores = [t.editorial_score for t in self.verified_topics]
        self.average_topic_score = sum(scores) / len(scores)

        balance_scores = [t.researched_topic.balance_score for t in self.verified_topics]
        self.overall_balance_score = sum(balance_scores) / len(balance_scores)

        # Ready check
        self.ready_for_script = all(t.editorial_approved for t in self.verified_topics)
