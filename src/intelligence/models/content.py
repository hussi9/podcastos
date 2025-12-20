"""
Content models for the intelligence pipeline.
Unified data structures for content from any source.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import hashlib


class RawContent(BaseModel):
    """
    Unified content model for all sources.
    Every piece of content (Reddit post, news article, HN story, etc.)
    gets normalized to this format.
    """

    id: str = Field(..., description="Unique ID (hash of url+source)")
    source_type: str = Field(..., description="reddit, hackernews, newsdata, youtube, rss")
    source_name: str = Field(..., description="r/technology, TechCrunch, Hacker News, etc.")

    # Core content
    title: str
    body: str = ""
    url: Optional[str] = None
    author: Optional[str] = None

    # Timestamps
    published_at: datetime
    fetched_at: datetime = Field(default_factory=datetime.now)

    # Engagement metrics (if available)
    score: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None

    # Computed fields (filled during processing)
    embedding: Optional[list[float]] = None
    entities: list[str] = Field(default_factory=list)
    sentiment: Optional[float] = None  # -1 to 1
    categories: list[str] = Field(default_factory=list)

    # Deduplication
    content_hash: Optional[str] = None
    is_duplicate: bool = False
    canonical_id: Optional[str] = None

    def compute_hash(self) -> str:
        """Compute content hash for deduplication."""
        content = f"{self.title.lower().strip()}{self.body[:500].lower().strip()}"
        self.content_hash = hashlib.md5(content.encode()).hexdigest()
        return self.content_hash

    @property
    def engagement_score(self) -> float:
        """Calculate engagement score."""
        score = self.score or 0
        comments = self.comments or 0
        return score + (comments * 2)

    @classmethod
    def generate_id(cls, url: str, source_type: str) -> str:
        """Generate unique ID from URL and source."""
        content = f"{source_type}:{url}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class TopicCluster(BaseModel):
    """
    A cluster of semantically related content items.
    Created by the semantic clustering engine.
    """

    id: str
    name: str = Field(..., description="LLM-generated topic name")
    summary: str = Field(..., description="2-3 sentence summary")
    category: str = Field(default="general", description="Topic category")

    # Clustered content
    contents: list[RawContent] = Field(default_factory=list)

    # Cluster metrics
    total_engagement: int = 0
    source_diversity: int = 0  # Number of unique source types
    content_count: int = 0
    time_span_hours: float = 0.0

    # Clustering metadata
    embedding_centroid: Optional[list[float]] = None
    coherence_score: float = 0.0

    # Trend indicators
    is_breaking: bool = False
    is_trending: bool = False
    trend_velocity: float = 0.0

    # Research priority (1-10)
    priority_score: float = 5.0

    def calculate_metrics(self):
        """Calculate cluster metrics from contents."""
        if not self.contents:
            return

        self.content_count = len(self.contents)
        self.total_engagement = sum(c.engagement_score for c in self.contents)
        self.source_diversity = len(set(c.source_type for c in self.contents))

        # Time span
        times = [c.published_at for c in self.contents]
        if len(times) >= 2:
            self.time_span_hours = (max(times) - min(times)).total_seconds() / 3600

        # Priority score based on engagement and diversity
        self.priority_score = min(10, (
            (self.total_engagement / 100) +
            (self.source_diversity * 2) +
            (5 if self.is_breaking else 0) +
            (3 if self.is_trending else 0)
        ))


class SourceConfig(BaseModel):
    """Configuration for a content source."""

    id: str
    source_type: str = Field(..., description="reddit, hackernews, newsdata, youtube, rss")
    name: str = Field(..., description="Display name")

    # Type-specific configuration
    config: dict = Field(default_factory=dict)

    # Filtering
    categories: list[str] = Field(default_factory=list)
    keywords_include: list[str] = Field(default_factory=list)
    keywords_exclude: list[str] = Field(default_factory=list)

    # Weighting
    priority: int = Field(default=5, ge=1, le=10)
    credibility_score: float = Field(default=0.7, ge=0.0, le=1.0)

    # Rate limiting
    fetch_interval_minutes: int = 60
    max_items_per_fetch: int = 50

    # Status
    is_active: bool = True
    last_fetched: Optional[datetime] = None
    last_error: Optional[str] = None


class ProfileSourceConfig(BaseModel):
    """
    Collection of sources configured for a podcast profile.
    Includes factory methods for common configurations.
    """

    profile_id: int
    sources: list[SourceConfig] = Field(default_factory=list)

    @classmethod
    def for_tech_podcast(cls, profile_id: int) -> "ProfileSourceConfig":
        """Pre-built configuration for a tech-focused podcast."""
        return cls(
            profile_id=profile_id,
            sources=[
                SourceConfig(
                    id="reddit-tech",
                    source_type="reddit",
                    name="Tech Subreddits",
                    config={
                        "subreddits": [
                            "technology", "programming", "webdev", "devops",
                            "MachineLearning", "artificial", "LocalLLaMA",
                            "cscareerquestions", "ExperiencedDevs",
                            "startups", "SaaS", "indiehackers",
                        ]
                    },
                    priority=8,
                    credibility_score=0.6,
                ),
                SourceConfig(
                    id="hackernews",
                    source_type="hackernews",
                    name="Hacker News",
                    config={"endpoints": ["topstories", "beststories"]},
                    priority=9,
                    credibility_score=0.8,
                ),
                SourceConfig(
                    id="tech-news",
                    source_type="newsdata",
                    name="Tech News",
                    config={
                        "categories": ["technology", "science"],
                        "domains": ["techcrunch.com", "theverge.com", "arstechnica.com"],
                    },
                    priority=8,
                    credibility_score=0.85,
                ),
            ],
        )

    @classmethod
    def for_finance_podcast(cls, profile_id: int) -> "ProfileSourceConfig":
        """Pre-built configuration for a finance-focused podcast."""
        return cls(
            profile_id=profile_id,
            sources=[
                SourceConfig(
                    id="reddit-finance",
                    source_type="reddit",
                    name="Finance Subreddits",
                    config={
                        "subreddits": [
                            "personalfinance", "investing", "stocks", "options",
                            "financialindependence", "fatFIRE", "Bogleheads",
                            "CryptoCurrency", "Bitcoin", "wallstreetbets",
                            "realestateinvesting", "smallbusiness",
                        ]
                    },
                    priority=8,
                    credibility_score=0.6,
                ),
                SourceConfig(
                    id="finance-news",
                    source_type="newsdata",
                    name="Finance News",
                    config={
                        "categories": ["business"],
                        "domains": ["bloomberg.com", "wsj.com", "reuters.com"],
                    },
                    priority=9,
                    credibility_score=0.9,
                ),
            ],
        )

    @classmethod
    def for_immigration_podcast(cls, profile_id: int) -> "ProfileSourceConfig":
        """Pre-built configuration for an immigration-focused podcast."""
        return cls(
            profile_id=profile_id,
            sources=[
                SourceConfig(
                    id="reddit-immigration",
                    source_type="reddit",
                    name="Immigration Subreddits",
                    config={
                        "subreddits": [
                            "immigration", "USCIS", "h1b", "greencard",
                            "f1visa", "ABCDesis", "ImmigrationCanada",
                        ]
                    },
                    priority=9,
                    credibility_score=0.7,
                ),
                SourceConfig(
                    id="uscis-rss",
                    source_type="rss",
                    name="USCIS Official",
                    config={
                        "feeds": [
                            "https://www.uscis.gov/news/news-releases/feed",
                        ]
                    },
                    priority=10,
                    credibility_score=1.0,
                ),
                SourceConfig(
                    id="immigration-news",
                    source_type="newsdata",
                    name="Immigration News",
                    config={
                        "q": "immigration visa green card USCIS",
                        "categories": ["politics", "world"],
                    },
                    priority=8,
                    credibility_score=0.8,
                ),
            ],
        )
