# Agentic Content Intelligence Engine
## Research Document & Implementation Plan

**Version**: 1.0
**Date**: December 2024
**Status**: Planning Phase

---

## Executive Summary

This document outlines the architecture and implementation plan for transforming the Podcast Studio from a simple keyword-based content aggregator into an **Agentic Content Intelligence Engine** - a multi-agent system that autonomously discovers, researches, verifies, and synthesizes content for podcast generation.

### Key Differentiators vs Competition

| Capability | NotebookLM | Wondercraft | Jellypod | **PodcastOS (Target)** |
|------------|------------|-------------|----------|------------------------|
| Content Sources | Manual upload | Manual input | 100+ file types | **50+ live sources** |
| Topic Discovery | None | None | None | **Autonomous agents** |
| Research Depth | Single-pass LLM | Basic | Basic | **Multi-agent deep research** |
| Fact Verification | None | None | None | **Cross-source verification** |
| Trend Detection | None | None | None | **Real-time velocity tracking** |
| Clustering | None | None | None | **Semantic (embedding-based)** |

---

## Part 1: Current State Analysis

### 1.1 Existing Aggregators

| File | Source | Method | Limitations |
|------|--------|--------|-------------|
| `reddit_aggregator.py` | Reddit | PRAW/JSON API | 10 hardcoded subreddits, rate limited |
| `news_aggregator.py` | Supabase | Database query | Depends on external pipeline |
| `uscis_aggregator.py` | USCIS RSS | feedparser | Single source, limited scope |
| `content_ranker.py` | Combined | Keyword matching | Brittle, misses semantic similarity |

### 1.2 Current Pipeline Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Reddit    │     │    News     │     │    USCIS    │
│  (10 subs)  │     │ (Supabase)  │     │   (RSS)     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                 ┌─────────────────┐
                 │ Keyword-Based   │
                 │ Topic Clusters  │
                 │ (10 categories) │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Single-Pass     │
                 │ Gemini Research │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Script Gen      │
                 └─────────────────┘
```

### 1.3 Identified Gaps

1. **Limited Sources**: Only 3 source types, 10 Reddit subs
2. **Dumb Clustering**: Keyword-based misses "visa processing delays" ≈ "USCIS backlogs"
3. **No Cross-Verification**: Single source claims treated as facts
4. **No Trend Detection**: Can't identify accelerating vs declining stories
5. **Single-Pass Research**: No iteration, no gap-filling
6. **No Human Stories**: Missing real examples and case studies
7. **No Counter-Arguments**: One-sided perspective

---

## Part 2: Target Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          AGENTIC CONTENT INTELLIGENCE ENGINE                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  LAYER 1: SOURCE CONNECTORS                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ Reddit  │ │ News    │ │ Hacker  │ │ YouTube │ │ Twitter │ │ Gov     │        │
│  │ (PRAW)  │ │ (APIs)  │ │ News    │ │ (Trans) │ │ (Nitter)│ │ (RSS)   │        │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │
│       │          │          │          │          │          │                   │
│  LAYER 2: UNIFIED CONTENT LAKE                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  Raw Content Store (Deduplicated, Timestamped, Source-Tagged)            │   │
│  │  - Embeddings computed on ingest                                          │   │
│  │  - Entity extraction (people, orgs, policies)                            │   │
│  │  - Sentiment scoring                                                      │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                           │
│  LAYER 3: TOPIC INTELLIGENCE                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  Semantic Clustering Engine                                               │   │
│  │  - HDBSCAN clustering on embeddings                                       │   │
│  │  - Cross-source correlation                                               │   │
│  │  - Trend velocity calculation                                             │   │
│  │  - Breaking news detection                                                │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                           │
│  LAYER 4: RESEARCH CREW (CrewAI)                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │  │ Fact     │ │ Context  │ │ Counter  │ │ Story    │ │ Verify   │        │   │
│  │  │ Finder   │ │ Builder  │ │ Argument │ │ Hunter   │ │ Agent    │        │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │
│  │                                                                           │   │
│  │  Orchestrated by CrewAI with:                                             │   │
│  │  - Tavily for web search                                                  │   │
│  │  - Perplexity for fact verification                                       │   │
│  │  - Exa.ai for semantic research                                           │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                           │
│  LAYER 5: EDITORIAL REVIEW                                                       │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  - Claim verification against multiple sources                            │   │
│  │  - Source credibility scoring                                             │   │
│  │  - Bias detection and balance check                                       │   │
│  │  - Gap analysis and filling                                               │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                              PODCAST GENERATION
```

### 2.2 Component Details

#### Layer 1: Source Connectors

Each source connector implements a common interface:

```python
class SourceConnector(ABC):
    """Base class for all content sources"""

    @abstractmethod
    async def fetch(self, config: SourceConfig) -> list[RawContent]:
        """Fetch content from source"""
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """Return source type identifier"""
        pass
```

**Planned Connectors:**

| Connector | API/Method | Rate Limits | Priority |
|-----------|------------|-------------|----------|
| `RedditConnector` | PRAW + JSON fallback | 60/min | P0 |
| `HackerNewsConnector` | Firebase JSON API | Unlimited | P0 |
| `NewsDataConnector` | NewsData.io API | 200/day free | P0 |
| `YouTubeConnector` | youtube-transcript-api | Varies | P1 |
| `RSSConnector` | feedparser | Unlimited | P0 |
| `TavilyConnector` | Tavily Search API | 1000/month free | P0 |
| `TwitterConnector` | Nitter scraping | Rate limited | P2 |
| `CrawlerConnector` | Crawl4AI | Self-hosted | P1 |

#### Layer 2: Unified Content Lake

```python
class RawContent(BaseModel):
    """Unified content model for all sources"""

    id: str                          # Unique ID (hash of url+source)
    source_type: str                 # reddit, hackernews, news, etc.
    source_name: str                 # r/technology, TechCrunch, etc.

    # Content
    title: str
    body: str
    url: str
    author: Optional[str]

    # Metadata
    published_at: datetime
    fetched_at: datetime

    # Engagement (if available)
    score: Optional[int]
    comments: Optional[int]
    shares: Optional[int]

    # Computed on ingest
    embedding: Optional[list[float]]  # 384-dim sentence-transformer
    entities: list[str]               # Extracted entities
    sentiment: float                  # -1 to 1

    # Deduplication
    content_hash: str                 # For dedup
    is_duplicate: bool = False
    canonical_id: Optional[str]       # Points to original if duplicate
```

#### Layer 3: Topic Intelligence

**Semantic Clustering:**

```python
class SemanticClusterer:
    """Cluster content by semantic similarity, not keywords"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.embedder = SentenceTransformer(model_name)

    async def cluster(self, contents: list[RawContent]) -> list[TopicCluster]:
        # 1. Compute embeddings (if not cached)
        embeddings = self._get_embeddings(contents)

        # 2. Cluster with HDBSCAN (auto-determines cluster count)
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=3,
            min_samples=2,
            metric='cosine',
            cluster_selection_method='eom'
        )
        labels = clusterer.fit_predict(embeddings)

        # 3. Build topic clusters
        clusters = self._build_clusters(contents, labels)

        # 4. Name clusters using LLM
        for cluster in clusters:
            cluster.name = await self._generate_cluster_name(cluster)
            cluster.summary = await self._generate_summary(cluster)

        return clusters
```

**Cross-Source Correlation:**

```python
class SourceCorrelator:
    """Identify same story across different sources"""

    async def correlate(self, cluster: TopicCluster) -> CorrelatedTopic:
        # Count sources
        source_types = set(c.source_type for c in cluster.contents)

        # Calculate confidence based on source diversity
        correlation_score = 0.0

        if "reddit" in source_types:
            correlation_score += 1.0  # Community signal
        if "news" in source_types:
            correlation_score += 1.5  # Media coverage
        if "gov" in source_types:
            correlation_score += 2.0  # Official source
        if len(source_types) >= 3:
            correlation_score *= 1.5  # Multi-source bonus

        # Extract common claims
        common_claims = await self._extract_common_claims(cluster)

        return CorrelatedTopic(
            cluster=cluster,
            correlation_score=correlation_score,
            source_count=len(source_types),
            common_claims=common_claims,
            verified_facts=[]  # Filled by research crew
        )
```

**Trend Velocity:**

```python
class TrendDetector:
    """Detect trending and breaking stories"""

    async def calculate_velocity(
        self,
        topic: str,
        window_hours: int = 24
    ) -> TrendVelocity:
        # Get mention counts per hour
        hourly_counts = await self._get_hourly_mentions(topic, window_hours)

        # Calculate velocity (rate of change)
        if len(hourly_counts) < 2:
            return TrendVelocity(velocity=0, status="stable")

        recent = np.mean(hourly_counts[-3:])  # Last 3 hours
        earlier = np.mean(hourly_counts[-12:-3])  # 3-12 hours ago

        velocity = (recent - earlier) / max(earlier, 1)

        if velocity > 2.0:
            status = "breaking"
        elif velocity > 0.5:
            status = "accelerating"
        elif velocity < -0.5:
            status = "declining"
        else:
            status = "stable"

        return TrendVelocity(
            velocity=velocity,
            status=status,
            mentions_last_hour=hourly_counts[-1],
            mentions_last_24h=sum(hourly_counts)
        )
```

#### Layer 4: Research Crew (CrewAI)

**Agent Definitions:**

```python
from crewai import Agent, Task, Crew, Process

class ResearchCrew:
    """Multi-agent research team using CrewAI"""

    def __init__(self, llm_model: str = "gemini/gemini-2.0-flash"):
        self.llm = llm_model
        self._create_agents()

    def _create_agents(self):
        self.fact_finder = Agent(
            role="Fact Researcher",
            goal="Find specific facts, statistics, dates, and citations",
            backstory="""You are an investigative journalist obsessed with
            accuracy. You never report vague claims - only specific,
            verifiable facts with sources.""",
            tools=[TavilySearchTool(), PerplexityTool(), WebScraperTool()],
            llm=self.llm,
            verbose=True
        )

        self.context_builder = Agent(
            role="Context Specialist",
            goal="Build historical context and explain implications",
            backstory="""You are a historian and policy analyst who helps
            people understand how we got here and what comes next. You
            connect dots across time.""",
            tools=[TavilySearchTool(), WikipediaTool()],
            llm=self.llm
        )

        self.devil_advocate = Agent(
            role="Counter-Argument Finder",
            goal="Find opposing viewpoints and nuanced perspectives",
            backstory="""You are a debate champion who sees all sides of
            every issue. You believe every story has multiple valid
            perspectives that deserve to be heard.""",
            tools=[RedditSearchTool(), TwitterSearchTool(), TavilySearchTool()],
            llm=self.llm
        )

        self.story_hunter = Agent(
            role="Human Story Finder",
            goal="Find real examples, case studies, and human interest angles",
            backstory="""You are a feature writer who knows that data alone
            doesn't move people - stories do. You find the human face
            behind every statistic.""",
            tools=[RedditSearchTool(), NewsSearchTool()],
            llm=self.llm
        )

        self.fact_checker = Agent(
            role="Editorial Reviewer",
            goal="Verify claims and ensure balanced, accurate coverage",
            backstory="""You are a senior editor with zero tolerance for
            errors. You cross-check every claim against multiple sources
            and flag anything that can't be verified.""",
            tools=[PerplexityTool(), FactCheckTool()],
            llm=self.llm
        )

    async def research_topic(self, topic: CorrelatedTopic) -> ResearchedTopic:
        """Run full research crew on a topic"""

        # Define tasks
        fact_task = Task(
            description=f"""Research facts about: {topic.name}

            Find:
            - Specific statistics with numbers and dates
            - Official policy names and numbers
            - Key dates and deadlines
            - Quotes from officials or experts

            Return structured JSON with sources.""",
            agent=self.fact_finder,
            expected_output="JSON with key_facts, statistics, sources"
        )

        context_task = Task(
            description=f"""Build context for: {topic.name}

            Explain:
            - How did we get here? (historical context)
            - What exactly is happening now?
            - What does this mean for the future?

            Provide a narrative arc.""",
            agent=self.context_builder,
            expected_output="JSON with historical_context, current_situation, future_implications"
        )

        counter_task = Task(
            description=f"""Find opposing views on: {topic.name}

            Research:
            - Arguments in favor
            - Arguments against
            - Nuanced middle-ground perspectives
            - Common misconceptions

            Be fair to all sides.""",
            agent=self.devil_advocate,
            expected_output="JSON with arguments_for, arguments_against, nuanced_take"
        )

        story_task = Task(
            description=f"""Find human stories about: {topic.name}

            Look for:
            - Real examples from Reddit or news
            - Case studies
            - Personal experiences
            - Practical advice from real people

            Make it relatable.""",
            agent=self.story_hunter,
            expected_output="JSON with real_stories, case_studies, practical_advice"
        )

        # Create crew and run
        crew = Crew(
            agents=[
                self.fact_finder,
                self.context_builder,
                self.devil_advocate,
                self.story_hunter
            ],
            tasks=[fact_task, context_task, counter_task, story_task],
            process=Process.parallel,  # Run in parallel
            verbose=True
        )

        results = await crew.kickoff_async()

        # Fact check the combined results
        verify_task = Task(
            description=f"""Verify the following research:

            {results}

            Cross-check key claims against multiple sources.
            Flag any unverified or potentially inaccurate statements.
            Rate source credibility.
            Ensure balanced perspective.""",
            agent=self.fact_checker,
            expected_output="JSON with verified_facts, flagged_claims, credibility_scores"
        )

        verification = await Crew(
            agents=[self.fact_checker],
            tasks=[verify_task]
        ).kickoff_async()

        return self._combine_results(results, verification)
```

#### Layer 5: Editorial Review

```python
class EditorialReview:
    """Final quality gate before script generation"""

    async def review(self, researched_topic: ResearchedTopic) -> ReviewedTopic:
        # 1. Claim verification
        verified_claims = []
        flagged_claims = []

        for claim in researched_topic.all_claims:
            verification = await self._verify_claim(claim)
            if verification.confidence > 0.8:
                verified_claims.append(claim)
            else:
                flagged_claims.append((claim, verification.reason))

        # 2. Source credibility
        source_scores = {}
        for source in researched_topic.sources:
            source_scores[source] = await self._score_credibility(source)

        # 3. Balance check
        balance_score = self._check_balance(researched_topic)
        if balance_score < 0.6:
            # Add more counter-arguments
            additional = await self._find_missing_perspectives(researched_topic)
            researched_topic.counter_arguments.extend(additional)

        # 4. Gap analysis
        gaps = await self._identify_gaps(researched_topic)
        if gaps:
            filled = await self._fill_gaps(gaps)
            researched_topic = self._merge(researched_topic, filled)

        return ReviewedTopic(
            topic=researched_topic,
            verified_claims=verified_claims,
            flagged_claims=flagged_claims,
            source_credibility=source_scores,
            balance_score=balance_score,
            review_passed=len(flagged_claims) == 0 and balance_score >= 0.6
        )
```

---

## Part 3: Data Models

### 3.1 Source Configuration

```python
class SourceConfig(BaseModel):
    """Configuration for a content source"""

    id: str
    source_type: str  # reddit, hackernews, news_api, rss, youtube, twitter
    name: str         # Display name

    # Type-specific config
    config: dict      # subreddit name, API key, RSS url, etc.

    # Filtering
    categories: list[str] = []
    keywords_include: list[str] = []
    keywords_exclude: list[str] = []

    # Weighting
    priority: int = 5           # 1-10
    credibility_score: float = 0.7  # 0-1

    # Rate limiting
    fetch_interval_minutes: int = 60
    max_items_per_fetch: int = 50

    # Status
    is_active: bool = True
    last_fetched: Optional[datetime] = None
    last_error: Optional[str] = None


class ProfileSourceConfig(BaseModel):
    """Sources configured for a specific podcast profile"""

    profile_id: int
    sources: list[SourceConfig]

    # Default source templates by category
    @classmethod
    def for_tech_podcast(cls, profile_id: int) -> "ProfileSourceConfig":
        return cls(
            profile_id=profile_id,
            sources=[
                SourceConfig(
                    id="reddit-tech",
                    source_type="reddit",
                    name="Tech Subreddits",
                    config={
                        "subreddits": [
                            "technology", "programming", "webdev",
                            "MachineLearning", "artificial", "cscareerquestions",
                            "startups", "SaaS", "devops"
                        ]
                    },
                    priority=8,
                    credibility_score=0.6
                ),
                SourceConfig(
                    id="hackernews",
                    source_type="hackernews",
                    name="Hacker News",
                    config={"endpoints": ["topstories", "beststories"]},
                    priority=9,
                    credibility_score=0.8
                ),
                SourceConfig(
                    id="tech-news",
                    source_type="news_api",
                    name="Tech News",
                    config={
                        "categories": ["technology"],
                        "domains": ["techcrunch.com", "theverge.com", "arstechnica.com"]
                    },
                    priority=8,
                    credibility_score=0.85
                ),
            ]
        )
```

### 3.2 Topic Models

```python
class TopicCluster(BaseModel):
    """A cluster of related content items"""

    id: str
    name: str                    # Generated by LLM
    summary: str                 # 2-3 sentence summary
    category: str                # immigration, tech, career, etc.

    # Content
    contents: list[RawContent]

    # Metrics
    total_engagement: int        # Sum of scores/comments
    source_diversity: int        # Number of unique sources
    time_span_hours: float       # Oldest to newest

    # Clustering metadata
    centroid: list[float]        # Cluster centroid embedding
    coherence_score: float       # How tight is the cluster


class CorrelatedTopic(BaseModel):
    """Topic with cross-source correlation analysis"""

    cluster: TopicCluster

    # Correlation
    correlation_score: float     # Confidence based on source diversity
    common_claims: list[str]     # Claims appearing in multiple sources

    # Trend analysis
    trend_velocity: TrendVelocity
    is_breaking: bool
    is_trending: bool

    # For research
    research_priority: int       # 1-10, based on score + trend


class ResearchedTopic(BaseModel):
    """Fully researched topic ready for script generation"""

    topic: CorrelatedTopic

    # Facts & Statistics
    key_facts: list[VerifiedFact]
    statistics: list[Statistic]

    # Context
    historical_context: str
    current_situation: str
    future_implications: str

    # Perspectives
    expert_opinions: list[ExpertOpinion]
    arguments_for: list[str]
    arguments_against: list[str]
    nuanced_take: str

    # Human interest
    real_stories: list[HumanStory]
    practical_advice: list[str]

    # Quality
    verification_status: str     # verified, partially_verified, unverified
    source_credibility_avg: float
    balance_score: float
```

---

## Part 4: API Integrations

### 4.1 Tavily Search

```python
class TavilySearchTool:
    """Tavily API integration for agentic search"""

    def __init__(self, api_key: str):
        from tavily import TavilyClient
        self.client = TavilyClient(api_key)

    async def search(
        self,
        query: str,
        search_depth: str = "advanced",  # basic or advanced
        max_results: int = 10,
        include_domains: list[str] = None,
        exclude_domains: list[str] = None
    ) -> list[SearchResult]:
        """
        Search the web for relevant content.

        Pricing:
        - 1000 free searches/month
        - $0.01 per search after
        """
        response = self.client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains
        )

        return [
            SearchResult(
                title=r["title"],
                url=r["url"],
                content=r["content"],
                score=r.get("score", 0)
            )
            for r in response["results"]
        ]

    async def search_context(
        self,
        query: str,
        max_tokens: int = 4000
    ) -> str:
        """Get search results optimized for LLM context"""
        response = self.client.get_search_context(
            query=query,
            max_tokens=max_tokens
        )
        return response
```

### 4.2 NewsData.io

```python
class NewsDataConnector:
    """NewsData.io API integration"""

    BASE_URL = "https://newsdata.io/api/1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_news(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,  # business, technology, etc.
        country: str = "us",
        language: str = "en",
        domain: Optional[list[str]] = None,
        timeframe: int = 24  # hours
    ) -> list[RawContent]:
        """
        Fetch news articles.

        Pricing:
        - Free: 200 requests/day
        - Basic ($49/mo): 3000 requests/day

        Categories: business, entertainment, environment, food,
                   health, politics, science, sports, technology,
                   top, tourism, world
        """
        async with httpx.AsyncClient() as client:
            params = {
                "apikey": self.api_key,
                "country": country,
                "language": language,
                "timeframe": timeframe
            }

            if query:
                params["q"] = query
            if category:
                params["category"] = category
            if domain:
                params["domain"] = ",".join(domain)

            response = await client.get(
                f"{self.BASE_URL}/latest",
                params=params
            )

            data = response.json()

            return [
                RawContent(
                    id=self._generate_id(article["link"]),
                    source_type="news",
                    source_name=article.get("source_name", "Unknown"),
                    title=article["title"],
                    body=article.get("description", "") or article.get("content", ""),
                    url=article["link"],
                    author=article.get("creator", [None])[0],
                    published_at=self._parse_date(article["pubDate"]),
                    fetched_at=datetime.now()
                )
                for article in data.get("results", [])
            ]
```

### 4.3 Hacker News

```python
class HackerNewsConnector:
    """Hacker News Firebase API integration"""

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    async def fetch_stories(
        self,
        story_type: str = "topstories",  # topstories, newstories, beststories
        limit: int = 30
    ) -> list[RawContent]:
        """
        Fetch stories from Hacker News.

        Pricing: FREE (no rate limits)
        """
        async with httpx.AsyncClient() as client:
            # Get story IDs
            response = await client.get(f"{self.BASE_URL}/{story_type}.json")
            story_ids = response.json()[:limit]

            # Fetch each story
            stories = []
            for story_id in story_ids:
                story_response = await client.get(
                    f"{self.BASE_URL}/item/{story_id}.json"
                )
                story = story_response.json()

                if story and story.get("type") == "story":
                    stories.append(RawContent(
                        id=f"hn-{story_id}",
                        source_type="hackernews",
                        source_name="Hacker News",
                        title=story.get("title", ""),
                        body=story.get("text", ""),  # For Ask HN posts
                        url=story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        author=story.get("by"),
                        published_at=datetime.fromtimestamp(story.get("time", 0)),
                        fetched_at=datetime.now(),
                        score=story.get("score", 0),
                        comments=story.get("descendants", 0)
                    ))

            return stories
```

### 4.4 YouTube Transcripts

```python
class YouTubeConnector:
    """YouTube transcript fetching"""

    def __init__(self):
        from youtube_transcript_api import YouTubeTranscriptApi
        self.api = YouTubeTranscriptApi

    async def fetch_transcript(
        self,
        video_id: str,
        languages: list[str] = ["en"]
    ) -> RawContent:
        """
        Fetch transcript from a YouTube video.

        Pricing: FREE (but may be rate limited)
        """
        try:
            transcript = self.api.get_transcript(video_id, languages=languages)

            # Combine transcript segments
            full_text = " ".join([segment["text"] for segment in transcript])

            return RawContent(
                id=f"yt-{video_id}",
                source_type="youtube",
                source_name="YouTube",
                title="",  # Need separate API call for title
                body=full_text,
                url=f"https://youtube.com/watch?v={video_id}",
                published_at=datetime.now(),  # Approximate
                fetched_at=datetime.now()
            )
        except Exception as e:
            logger.error(f"Failed to fetch transcript for {video_id}: {e}")
            return None

    async def fetch_channel_videos(
        self,
        channel_id: str,
        max_videos: int = 10
    ) -> list[RawContent]:
        """Fetch transcripts from recent channel videos"""
        # Would need YouTube Data API for this
        # For now, return empty
        return []
```

---

## Part 5: Implementation Plan

### Phase 1: Foundation (Week 1)

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Install dependencies | Updated requirements.txt, verified installs |
| 1 | Create source config models | `src/intelligence/models/sources.py` |
| 2 | Build HackerNews connector | `src/aggregators/hackernews_aggregator.py` |
| 2 | Build NewsData connector | `src/aggregators/newsdata_aggregator.py` |
| 3 | Build YouTube connector | `src/aggregators/youtube_aggregator.py` |
| 3 | Build Tavily connector | `src/aggregators/tavily_aggregator.py` |
| 4 | Create unified content model | `src/intelligence/models/content.py` |
| 4 | Build source manager | `src/intelligence/source_manager.py` |
| 5 | Expand Reddit to 20+ subs | Update `reddit_aggregator.py` |
| 5 | Integration testing | Test all connectors end-to-end |

### Phase 2: Semantic Intelligence (Week 2)

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Set up sentence-transformers | Embedding pipeline |
| 1 | Build embedding cache | Redis/SQLite cache for embeddings |
| 2 | Implement HDBSCAN clustering | `src/intelligence/clustering.py` |
| 2 | Build cluster naming (LLM) | Auto-generate topic names |
| 3 | Implement cross-source correlation | `src/intelligence/correlator.py` |
| 3 | Build trend velocity detection | `src/intelligence/trend_detector.py` |
| 4 | Create topic intelligence pipeline | `src/intelligence/topic_intelligence.py` |
| 5 | Replace keyword-based ranker | Update `content_ranker.py` |
| 5 | Integration testing | Verify clustering quality |

### Phase 3: Agentic Research (Week 3)

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Install CrewAI | Verified installation |
| 1 | Create agent tools (Tavily, etc.) | `src/intelligence/tools/` |
| 2 | Define research agents | `src/intelligence/agents/` |
| 2 | Build Fact Finder agent | With Tavily + Perplexity |
| 3 | Build Context Builder agent | With search tools |
| 3 | Build Counter-Argument agent | With Reddit/Twitter search |
| 4 | Build Story Hunter agent | With community sources |
| 4 | Build Fact Checker agent | With verification tools |
| 5 | Create research crew orchestration | `src/intelligence/research_crew.py` |
| 5 | Test multi-agent research | Verify output quality |

### Phase 4: Integration (Week 4)

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Build editorial review pipeline | `src/intelligence/editorial_review.py` |
| 2 | Create agentic pipeline orchestrator | `src/intelligence/pipeline.py` |
| 3 | Integrate with PodcastEngine | Update `podcast_engine.py` |
| 3 | Update webapp for source config | New UI for source management |
| 4 | Add profile-based source templates | Pre-built source configs |
| 5 | End-to-end testing | Full pipeline test |
| 5 | Documentation | Update README, API docs |

---

## Part 6: File Structure

```
src/
├── aggregators/                    # EXISTING - Content fetchers
│   ├── __init__.py
│   ├── reddit_aggregator.py       # UPDATED - 20+ subs
│   ├── news_aggregator.py         # EXISTING
│   ├── uscis_aggregator.py        # EXISTING
│   ├── hackernews_aggregator.py   # NEW
│   ├── newsdata_aggregator.py     # NEW
│   ├── youtube_aggregator.py      # NEW
│   ├── tavily_aggregator.py       # NEW
│   ├── rss_aggregator.py          # NEW - Generic RSS
│   └── twitter_aggregator.py      # NEW - Nitter-based
│
├── intelligence/                   # NEW - Agentic layer
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── sources.py             # SourceConfig, ProfileSourceConfig
│   │   ├── content.py             # RawContent, TopicCluster
│   │   └── research.py            # ResearchedTopic, VerifiedFact
│   │
│   ├── source_manager.py          # Orchestrates all sources
│   ├── content_lake.py            # Unified storage + dedup
│   ├── embedder.py                # Sentence transformer wrapper
│   ├── clustering.py              # HDBSCAN semantic clustering
│   ├── correlator.py              # Cross-source correlation
│   ├── trend_detector.py          # Velocity & breaking detection
│   ├── topic_intelligence.py      # Combined topic analysis
│   │
│   ├── agents/                    # CrewAI agents
│   │   ├── __init__.py
│   │   ├── fact_finder.py
│   │   ├── context_builder.py
│   │   ├── devil_advocate.py
│   │   ├── story_hunter.py
│   │   └── fact_checker.py
│   │
│   ├── tools/                     # Agent tools
│   │   ├── __init__.py
│   │   ├── tavily_tool.py
│   │   ├── perplexity_tool.py
│   │   ├── reddit_search_tool.py
│   │   └── web_scraper_tool.py
│   │
│   ├── research_crew.py           # CrewAI orchestration
│   ├── editorial_review.py        # Quality gate
│   └── pipeline.py                # Full agentic pipeline
│
├── generators/                     # EXISTING
├── tts/                           # EXISTING
├── research/                      # EXISTING - Will be deprecated
└── podcast_engine.py              # UPDATED - Use new pipeline
```

---

## Part 7: Environment Variables

```bash
# === EXISTING ===
GEMINI_API_KEY=your_gemini_key
ELEVENLABS_API_KEY=your_elevenlabs_key
GOOGLE_TTS_API_KEY=your_google_tts_key
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_key

# === NEW: Content Intelligence ===
# Search APIs
TAVILY_API_KEY=your_tavily_key           # 1000 free/month
NEWSDATA_API_KEY=your_newsdata_key       # 200 free/day
PERPLEXITY_API_KEY=your_perplexity_key   # Optional, paid

# Optional enhancements
EXA_API_KEY=your_exa_key                 # Optional, 1000 free/month
FIRECRAWL_API_KEY=your_firecrawl_key     # Optional, for anti-bot sites

# Embedding model (optional - defaults to local)
OPENAI_API_KEY=your_openai_key           # For OpenAI embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2         # Default: local model

# CrewAI settings
CREWAI_LLM=gemini/gemini-2.0-flash       # LLM for agents
CREWAI_VERBOSE=true                       # Debug logging
```

---

## Part 8: Cost Estimates

### Monthly Costs (Production)

| Service | Free Tier | Usage Estimate | Monthly Cost |
|---------|-----------|----------------|--------------|
| **Tavily** | 1000 searches | ~500 searches/day | $50-100 |
| **NewsData.io** | 200/day | Sufficient | $0 |
| **Gemini** | Limited | ~100K tokens/day | $20-40 |
| **Perplexity** | None | ~200 verifications | $10 |
| **Sentence Transformers** | Free (local) | - | $0 |
| **CrewAI** | Free (OSS) | - | $0 |
| **Total** | - | - | **$80-150/mo** |

### Cost Optimization Strategies

1. **Cache aggressively**: Embeddings, search results, research
2. **Batch searches**: Combine related queries
3. **Use free tiers first**: NewsData, Tavily free tier
4. **Local embeddings**: sentence-transformers runs locally
5. **Fallback chain**: Tavily → Perplexity → Gemini search

---

## Part 9: Success Metrics

### Quality Metrics

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Source diversity | 3 types | 8+ types | Count unique source_type |
| Topics per episode | 5 | 5-7 | Count clusters |
| Facts per topic | ~3 | 8-10 | Count verified facts |
| Cross-source verification | 0% | 70%+ | Claims with 2+ sources |
| Counter-arguments | 0 | 2+ per topic | Count opposing views |
| Human stories | 0 | 1+ per episode | Count real examples |

### Performance Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Content fetch time | <30s | Time all sources |
| Clustering time | <10s | Time HDBSCAN |
| Research per topic | <60s | Time crew execution |
| Full pipeline | <5 min | End-to-end time |

---

## Part 10: Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits | Content gaps | Multi-source fallback, caching |
| LLM hallucinations | Bad facts | Cross-source verification, fact-checker agent |
| Clustering noise | Poor topics | Tune HDBSCAN params, manual review |
| Cost overruns | Budget | Usage monitoring, tier alerts |
| Source goes down | Missing content | Multiple sources per category |
| CrewAI complexity | Dev time | Start simple, add agents incrementally |

---

## Appendix A: Quick Start Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Test individual connectors
python -m src.aggregators.hackernews_aggregator
python -m src.aggregators.newsdata_aggregator

# Run semantic clustering test
python -m src.intelligence.clustering --test

# Run research crew test
python -m src.intelligence.research_crew --topic "H1B visa delays"

# Run full pipeline
python -m src.intelligence.pipeline --profile-id 1
```

---

## Appendix B: CrewAI Agent Prompts

### Fact Finder Prompt

```
You are an investigative journalist obsessed with accuracy.

Your job is to find SPECIFIC, VERIFIABLE facts about the given topic.

REQUIREMENTS:
1. Every fact must have a source
2. Include specific numbers, dates, percentages
3. Quote officials or experts when possible
4. Distinguish between confirmed facts and claims
5. Note when information is uncertain or disputed

OUTPUT FORMAT:
{
  "key_facts": [
    {"fact": "...", "source": "...", "date": "...", "confidence": 0.9}
  ],
  "statistics": [...],
  "expert_quotes": [...],
  "uncertain_claims": [...]
}
```

### Context Builder Prompt

```
You are a historian and policy analyst who helps people understand context.

Your job is to explain:
1. How did we get here? (historical background)
2. What exactly is happening now? (current situation)
3. What does this mean for the future? (implications)

REQUIREMENTS:
1. Provide a clear narrative arc
2. Include key dates and events
3. Explain cause and effect
4. Make it accessible to non-experts
5. Be balanced and factual

OUTPUT FORMAT:
{
  "historical_context": "2-3 paragraphs...",
  "current_situation": "2-3 paragraphs...",
  "future_implications": "2-3 paragraphs...",
  "key_dates": [...]
}
```

---

## Next Steps

1. **Review this document** with stakeholders
2. **Prioritize** which connectors to build first
3. **Set up API keys** for Tavily, NewsData
4. **Begin Phase 1** implementation
5. **Test incrementally** - don't wait for full build

---

*Document version: 1.0*
*Last updated: December 2024*
