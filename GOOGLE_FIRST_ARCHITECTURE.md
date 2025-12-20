# Google-First Agentic Content Intelligence Engine
## Complete Architecture & Implementation Plan

**Version**: 2.0
**Date**: December 2024
**Philosophy**: Maximize Google/Gemini capabilities, add complementary tools only for specific gaps

---

## Executive Summary

This architecture leverages **every available Google/Gemini capability** as the primary stack, with strategic complementary tools only where Google has documented limitations.

### Google Stack (Primary)
| Capability | Google Tool | Use Case |
|------------|-------------|----------|
| LLM Reasoning | Gemini 2.5 Flash/Pro | Script generation, synthesis |
| Web Search | Google Search Grounding | Real-time facts, current events |
| Deep Research | Deep Research Agent | Comprehensive topic research |
| URL Reading | URL Context Tool | Read any webpage, PDF, document |
| Location Data | Google Maps Grounding | Location-relevant content |
| Code Execution | Code Execution Tool | Data processing, calculations |
| Structured Output | JSON Schema | Typed responses |
| Audio Generation | Gemini TTS / Google Cloud TTS | Podcast audio |

### Complementary Tools (Gap Coverage)
| Gap | Tool | Why Needed |
|-----|------|------------|
| Content Aggregation | Reddit, HN, NewsData APIs | Google doesn't aggregate social/news |
| Semantic Search Accuracy | Exa.ai | 94.9% vs Google's SEO bias |
| Ultra-Fast Current Events | Perplexity (optional) | 358ms vs Gemini's 22-90s |
| Local Embeddings | sentence-transformers | Offline clustering |

---

## Part 1: Complete Google Gemini Toolbox

### 1.1 Available Tools & Capabilities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GOOGLE GEMINI TOOLBOX (2025)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MODELS                                                                      │
│  ├── gemini-2.5-flash          Best price/performance, thinking             │
│  ├── gemini-2.5-pro            Most capable, complex reasoning              │
│  ├── gemini-3-pro-preview      Latest, most factual                         │
│  └── gemini-2.5-flash-preview-tts   Native audio generation                 │
│                                                                              │
│  GROUNDING TOOLS                                                             │
│  ├── google_search             Real-time web search with citations          │
│  ├── google_maps               250M+ places, location-aware responses       │
│  ├── url_context               Read URLs, PDFs, images (up to 20/request)   │
│  └── youtube_context           Video content via URL                        │
│                                                                              │
│  EXECUTION TOOLS                                                             │
│  ├── code_execution            Run Python for calculations/data             │
│  └── function_calling          Custom tool integration                      │
│                                                                              │
│  AGENTS                                                                      │
│  └── deep-research-*           Autonomous multi-step research agent         │
│                                                                              │
│  OUTPUT FORMATS                                                              │
│  ├── structured_output         JSON Schema / Pydantic compatible            │
│  ├── thinking                  Show reasoning steps                         │
│  └── grounding_metadata        Citations, sources, search queries           │
│                                                                              │
│  AUDIO                                                                       │
│  ├── Gemini Native Audio       Expressive, multi-speaker TTS                │
│  └── Google Cloud TTS          Neural2/Journey voices, 4M chars free        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Tool Pricing (December 2025)

| Tool | Pricing |
|------|---------|
| Gemini 2.5 Flash | $0.075/1M input, $0.30/1M output |
| Gemini 2.5 Pro | $1.25/1M input, $5.00/1M output |
| Google Search Grounding | $14/1K search queries |
| URL Context | Included in token pricing |
| Deep Research Agent | $2/1M input tokens |
| Google Cloud TTS (Neural2) | FREE up to 1M chars/month |
| Gemini Native TTS | $0.80/1M characters |

---

## Part 2: Architecture

### 2.1 High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GOOGLE-FIRST CONTENT INTELLIGENCE PIPELINE                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STAGE 1: CONTENT AGGREGATION (Complementary - Google doesn't have this)    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │
│  │  │ Reddit  │ │ Hacker  │ │ NewsData│ │ YouTube │ │ Gov RSS │       │    │
│  │  │ (PRAW)  │ │ News    │ │ API     │ │ Trans   │ │ Feeds   │       │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  STAGE 2: SEMANTIC CLUSTERING (Local + Gemini)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  sentence-transformers (local) → HDBSCAN → Gemini names clusters   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  STAGE 3: INTELLIGENT RESEARCH (Google Tools)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                                                                      │    │
│  │  Route by topic complexity:                                          │    │
│  │                                                                      │    │
│  │  SIMPLE TOPICS ──────────────────────────────────────────────────── │    │
│  │  │                                                                   │    │
│  │  ▼  Gemini 2.5 Flash + Google Search + URL Context                  │    │
│  │     - Quick facts with citations                                     │    │
│  │     - Read source URLs for depth                                     │    │
│  │     - 5-15 seconds                                                   │    │
│  │                                                                      │    │
│  │  COMPLEX/BREAKING TOPICS ────────────────────────────────────────── │    │
│  │  │                                                                   │    │
│  │  ▼  Gemini Deep Research Agent                                      │    │
│  │     - Multi-step autonomous research                                 │    │
│  │     - Browses 100+ pages                                            │    │
│  │     - Comprehensive synthesis                                        │    │
│  │     - 5-20 minutes                                                   │    │
│  │                                                                      │    │
│  │  GAP: Counter-arguments & Accuracy ─────────────────────────────── │    │
│  │  │                                                                   │    │
│  │  ▼  Exa.ai Semantic Search (complementary)                          │    │
│  │     - 94.9% accuracy on research queries                            │    │
│  │     - Finds opposing viewpoints                                      │    │
│  │     - Overcomes Google's SEO bias                                    │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  STAGE 4: SYNTHESIS & VERIFICATION (Google)                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Gemini 2.5 Pro + Thinking Mode                                     │    │
│  │  - Synthesize all research                                          │    │
│  │  - Cross-verify claims                                              │    │
│  │  - Structured JSON output                                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  STAGE 5: SCRIPT GENERATION (Google)                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Gemini 2.5 Flash → Natural dialogue script                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  STAGE 6: AUDIO GENERATION (Google)                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Gemini Native TTS (multi-speaker) OR Google Cloud TTS              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Detailed Stage Breakdown

#### Stage 1: Content Aggregation

**Why complementary tools are needed**: Google doesn't provide APIs to aggregate content from Reddit, Hacker News, or news sources. This is our differentiator.

```python
# src/intelligence/aggregation/source_manager.py

from dataclasses import dataclass
from typing import Optional
import asyncio

@dataclass
class SourceConfig:
    """Configuration for a content source"""
    source_type: str  # reddit, hackernews, newsdata, youtube, rss
    name: str
    config: dict
    priority: int = 5
    is_active: bool = True


class SourceManager:
    """
    Manages all content sources.
    This is our KEY DIFFERENTIATOR - Google doesn't have this.
    """

    def __init__(self):
        self.connectors = {
            'reddit': RedditConnector(),
            'hackernews': HackerNewsConnector(),
            'newsdata': NewsDataConnector(),
            'youtube': YouTubeConnector(),
            'rss': RSSConnector(),
        }

    async def fetch_all(
        self,
        sources: list[SourceConfig]
    ) -> list[RawContent]:
        """Fetch content from all configured sources in parallel"""

        tasks = []
        for source in sources:
            if source.is_active:
                connector = self.connectors.get(source.source_type)
                if connector:
                    tasks.append(
                        connector.fetch(source.config)
                    )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_content = []
        for result in results:
            if isinstance(result, list):
                all_content.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Source fetch failed: {result}")

        return all_content
```

**Connectors to build:**

| Connector | API | Free Tier |
|-----------|-----|-----------|
| `RedditConnector` | PRAW + JSON fallback | 60 req/min |
| `HackerNewsConnector` | Firebase JSON | Unlimited |
| `NewsDataConnector` | newsdata.io | 200 req/day |
| `YouTubeConnector` | youtube-transcript-api | Varies |
| `RSSConnector` | feedparser | Unlimited |

---

#### Stage 2: Semantic Clustering

**Using local embeddings + Gemini for naming:**

```python
# src/intelligence/clustering/semantic_clusterer.py

from sentence_transformers import SentenceTransformer
import hdbscan
import numpy as np
from google import genai

class SemanticClusterer:
    """
    Cluster content semantically using local embeddings.
    Use Gemini only for naming clusters (cost-effective).
    """

    def __init__(self, gemini_client: genai.Client):
        # Local model - no API cost for embeddings
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.gemini = gemini_client

    async def cluster(
        self,
        contents: list[RawContent]
    ) -> list[TopicCluster]:
        """Cluster content by semantic similarity"""

        # 1. Compute embeddings locally (FREE)
        texts = [f"{c.title} {c.body[:500]}" for c in contents]
        embeddings = self.embedder.encode(texts)

        # 2. Cluster with HDBSCAN (auto-detects cluster count)
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=3,
            min_samples=2,
            metric='cosine',
            cluster_selection_method='eom'
        )
        labels = clusterer.fit_predict(embeddings)

        # 3. Build clusters
        clusters = {}
        for i, label in enumerate(labels):
            if label == -1:  # Noise
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(contents[i])

        # 4. Name clusters using Gemini (minimal tokens)
        topic_clusters = []
        for label, cluster_contents in clusters.items():
            name, summary = await self._name_cluster(cluster_contents)
            topic_clusters.append(TopicCluster(
                id=f"cluster-{label}",
                name=name,
                summary=summary,
                contents=cluster_contents,
                embedding_centroid=np.mean(
                    [embeddings[i] for i, l in enumerate(labels) if l == label],
                    axis=0
                ).tolist()
            ))

        return topic_clusters

    async def _name_cluster(
        self,
        contents: list[RawContent]
    ) -> tuple[str, str]:
        """Use Gemini to name a cluster (minimal tokens)"""

        # Sample titles for naming
        sample_titles = [c.title for c in contents[:5]]

        response = await self.gemini.models.generate_content_async(
            model="gemini-2.5-flash",
            contents=f"""Given these related article titles, provide:
1. A short topic name (3-5 words)
2. A one-sentence summary

Titles:
{chr(10).join(sample_titles)}

Respond as JSON: {{"name": "...", "summary": "..."}}""",
            config=GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        data = json.loads(response.text)
        return data["name"], data["summary"]
```

---

#### Stage 3: Intelligent Research (Google-First)

**The core research engine using ALL Google tools:**

```python
# src/intelligence/research/google_research_engine.py

from google import genai
from google.genai.types import (
    GenerateContentConfig,
    GoogleSearch,
    Tool,
    UrlContext,
)
from typing import Optional
import asyncio


class GoogleResearchEngine:
    """
    Research engine using ALL Google capabilities:
    - Gemini 2.5 Flash/Pro for reasoning
    - Google Search for real-time facts
    - URL Context for reading sources
    - Deep Research Agent for comprehensive research
    """

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

        # Optional: Exa for counter-arguments (covers Google's SEO bias)
        self.exa = ExaClient(api_key=os.getenv("EXA_API_KEY")) if os.getenv("EXA_API_KEY") else None

    async def research_topic(
        self,
        topic: TopicCluster,
        depth: str = "auto"  # auto, quick, deep
    ) -> ResearchedTopic:
        """
        Research a topic using the appropriate Google tools.

        Routing logic:
        - Simple topics → Gemini + Google Search + URL Context
        - Complex/breaking → Deep Research Agent
        - All topics → Exa for counter-arguments (if available)
        """

        # Determine depth
        if depth == "auto":
            depth = self._determine_depth(topic)

        if depth == "deep":
            # Use Deep Research Agent for complex topics
            research = await self._deep_research(topic)
        else:
            # Use Gemini + Google Search + URL Context for quick research
            research = await self._quick_research(topic)

        # Add counter-arguments from Exa (if available)
        if self.exa:
            counter_args = await self._get_counter_arguments(topic)
            research.counter_arguments = counter_args

        return research

    def _determine_depth(self, topic: TopicCluster) -> str:
        """Determine if topic needs deep or quick research"""

        # Deep research for:
        # - Breaking news (< 6 hours old)
        # - High engagement (> 500 combined score)
        # - Complex topics (policy, legal, technical)

        is_breaking = any(
            (datetime.now() - c.published_at).total_seconds() < 6 * 3600
            for c in topic.contents
        )

        is_high_engagement = sum(
            c.score or 0 for c in topic.contents
        ) > 500

        complex_keywords = [
            'policy', 'regulation', 'law', 'court', 'ruling',
            'investigation', 'analysis', 'controversy'
        ]
        is_complex = any(
            kw in topic.name.lower() or kw in topic.summary.lower()
            for kw in complex_keywords
        )

        if is_breaking or is_high_engagement or is_complex:
            return "deep"
        return "quick"

    async def _quick_research(
        self,
        topic: TopicCluster
    ) -> ResearchedTopic:
        """
        Quick research using Gemini + Google Search + URL Context.
        Time: 5-15 seconds
        """

        # Collect URLs from aggregated content
        source_urls = [c.url for c in topic.contents[:10] if c.url]

        prompt = f"""
You are a research assistant for a daily podcast.

TOPIC: {topic.name}
SUMMARY: {topic.summary}

AGGREGATED CONTENT FROM COMMUNITY:
{self._format_contents(topic.contents[:5])}

RESEARCH OBJECTIVES:
1. Find specific facts with numbers, dates, and statistics
2. Identify the historical context (how we got here)
3. Explain the current situation in detail
4. Predict future implications
5. Find expert opinions or official statements
6. Identify practical advice for listeners
7. Note any controversies or debates

Use Google Search to find current information.
Read the source URLs for deeper context.

OUTPUT FORMAT (JSON):
{{
    "key_facts": [
        {{"fact": "...", "source": "...", "date": "..."}}
    ],
    "statistics": ["..."],
    "historical_context": "...",
    "current_situation": "...",
    "future_implications": "...",
    "expert_opinions": [
        {{"person": "...", "role": "...", "quote": "..."}}
    ],
    "practical_advice": ["..."],
    "sources_used": ["..."]
}}
"""

        # Combine Google Search + URL Context
        tools = [
            Tool(google_search=GoogleSearch()),
        ]

        # Add URL context for source URLs
        if source_urls:
            tools.append(Tool(url_context=UrlContext(urls=source_urls[:5])))

        response = await self.client.models.generate_content_async(
            model="gemini-2.5-flash",
            contents=prompt,
            config=GenerateContentConfig(
                tools=tools,
                response_mime_type="application/json",
                temperature=0.3,  # Lower for factual accuracy
            )
        )

        # Parse response
        data = json.loads(response.text)

        # Extract grounding metadata (citations)
        citations = []
        if hasattr(response, 'grounding_metadata'):
            for chunk in response.grounding_metadata.grounding_chunks:
                citations.append({
                    "title": chunk.web.title,
                    "url": chunk.web.uri
                })

        return ResearchedTopic(
            topic=topic,
            key_facts=[VerifiedFact(**f) for f in data.get("key_facts", [])],
            statistics=data.get("statistics", []),
            historical_context=data.get("historical_context", ""),
            current_situation=data.get("current_situation", ""),
            future_implications=data.get("future_implications", ""),
            expert_opinions=data.get("expert_opinions", []),
            practical_advice=data.get("practical_advice", []),
            citations=citations,
            research_method="quick",
            research_time_seconds=response.usage_metadata.total_time_ms / 1000
        )

    async def _deep_research(
        self,
        topic: TopicCluster
    ) -> ResearchedTopic:
        """
        Deep research using Gemini Deep Research Agent.
        Time: 5-20 minutes
        """

        prompt = f"""
Conduct comprehensive research on the following topic for a podcast episode.

TOPIC: {topic.name}

CONTEXT FROM COMMUNITY SOURCES:
{self._format_contents(topic.contents[:10])}

RESEARCH OBJECTIVES:
1. Verify claims from community sources against authoritative sources
2. Find the complete historical timeline of this issue
3. Gather specific statistics, numbers, and data points
4. Collect expert opinions from officials, lawyers, analysts
5. Document all sides of any debate (pro, con, nuanced)
6. Find real human stories and case studies
7. Compile actionable advice for affected individuals
8. Identify what's likely to happen next

DELIVERABLE:
A comprehensive research report (2000-3000 words) with:
- Executive summary
- Key facts with citations
- Historical context
- Current situation analysis
- Multiple perspectives
- Real examples
- Practical recommendations
- Sources bibliography

This will be used to create a 5-7 minute podcast segment, so prioritize
the most important and interesting information.
"""

        # Start deep research (runs in background)
        interaction = await self.client.interactions.create_async(
            agent="deep-research-pro-preview-12-2025",
            contents=prompt,
            background=True,
            store=True,
            config={
                "agent_config": {
                    "thinking_config": {
                        "include_thoughts": True
                    }
                }
            }
        )

        # Poll for completion (max 20 minutes)
        start_time = datetime.now()
        max_wait = 20 * 60  # 20 minutes

        while not interaction.done:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > max_wait:
                logger.warning(f"Deep research timeout for {topic.name}")
                break

            await asyncio.sleep(30)  # Check every 30 seconds
            interaction = await self.client.interactions.get_async(
                interaction.id
            )

            # Log progress
            if interaction.thoughts:
                logger.info(f"Research progress: {interaction.thoughts[-1]}")

        # Parse the research report
        return self._parse_deep_research(interaction.result, topic)

    async def _get_counter_arguments(
        self,
        topic: TopicCluster
    ) -> list[str]:
        """
        Use Exa.ai to find counter-arguments.
        This covers Google's limitation of SEO bias toward popular opinions.
        """

        if not self.exa:
            return []

        try:
            # Search for opposing viewpoints
            results = await self.exa.search_async(
                query=f"criticism problems concerns issues with {topic.name}",
                num_results=10,
                type="keyword",  # Better for finding opposition
                use_autoprompt=True
            )

            counter_args = []
            for result in results.results:
                if result.text:
                    counter_args.append(result.text[:500])

            return counter_args[:5]

        except Exception as e:
            logger.warning(f"Exa search failed: {e}")
            return []

    def _format_contents(self, contents: list[RawContent]) -> str:
        """Format content for prompt"""
        formatted = []
        for c in contents:
            formatted.append(f"""
Source: {c.source_name} ({c.source_type})
Title: {c.title}
Content: {c.body[:300]}...
URL: {c.url}
Engagement: {c.score or 'N/A'} upvotes, {c.comments or 'N/A'} comments
""")
        return "\n---\n".join(formatted)

    def _parse_deep_research(
        self,
        result: str,
        topic: TopicCluster
    ) -> ResearchedTopic:
        """Parse deep research report into structured format"""

        # Use Gemini to extract structured data from the report
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""
Extract structured data from this research report.

REPORT:
{result}

OUTPUT FORMAT (JSON):
{{
    "key_facts": [{{"fact": "...", "source": "...", "date": "..."}}],
    "statistics": ["..."],
    "historical_context": "...",
    "current_situation": "...",
    "future_implications": "...",
    "expert_opinions": [{{"person": "...", "role": "...", "quote": "..."}}],
    "arguments_for": ["..."],
    "arguments_against": ["..."],
    "real_stories": ["..."],
    "practical_advice": ["..."],
    "sources": ["..."]
}}
""",
            config=GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        data = json.loads(response.text)

        return ResearchedTopic(
            topic=topic,
            key_facts=[VerifiedFact(**f) for f in data.get("key_facts", [])],
            statistics=data.get("statistics", []),
            historical_context=data.get("historical_context", ""),
            current_situation=data.get("current_situation", ""),
            future_implications=data.get("future_implications", ""),
            expert_opinions=data.get("expert_opinions", []),
            arguments_for=data.get("arguments_for", []),
            arguments_against=data.get("arguments_against", []),
            real_stories=data.get("real_stories", []),
            practical_advice=data.get("practical_advice", []),
            citations=data.get("sources", []),
            research_method="deep",
            full_report=result
        )
```

---

#### Stage 4: Synthesis & Verification

```python
# src/intelligence/synthesis/synthesizer.py

class ResearchSynthesizer:
    """
    Synthesize and verify research using Gemini with thinking mode.
    """

    def __init__(self, client: genai.Client):
        self.client = client

    async def synthesize(
        self,
        researched_topics: list[ResearchedTopic]
    ) -> list[VerifiedTopic]:
        """
        Synthesize research and cross-verify claims.
        Uses Gemini 2.5 Pro with thinking for complex reasoning.
        """

        verified_topics = []

        for topic in researched_topics:
            # Use thinking mode for verification
            response = await self.client.models.generate_content_async(
                model="gemini-2.5-pro",
                contents=f"""
You are a senior editor verifying research for a podcast.

TOPIC: {topic.topic.name}

RESEARCH FINDINGS:
Key Facts: {json.dumps([f.dict() for f in topic.key_facts])}
Statistics: {topic.statistics}
Expert Opinions: {topic.expert_opinions}

VERIFICATION TASKS:
1. Cross-check facts against each other for consistency
2. Flag any claims that seem exaggerated or unverified
3. Identify gaps in the research
4. Ensure balanced perspective (both sides represented)
5. Rate overall confidence in the research

Think through this carefully, then provide:

{{
    "verified_facts": [...],
    "flagged_claims": [...],
    "gaps_identified": [...],
    "balance_score": 0.0-1.0,
    "confidence_score": 0.0-1.0,
    "editorial_notes": "..."
}}
""",
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    thinking_config={"thinking_budget_tokens": 2000}
                )
            )

            verification = json.loads(response.text)

            verified_topics.append(VerifiedTopic(
                research=topic,
                verified_facts=verification["verified_facts"],
                flagged_claims=verification["flagged_claims"],
                gaps=verification["gaps_identified"],
                balance_score=verification["balance_score"],
                confidence_score=verification["confidence_score"],
                editorial_notes=verification["editorial_notes"]
            ))

        return verified_topics
```

---

#### Stage 5: Script Generation

```python
# src/intelligence/generation/script_generator.py

class EnhancedScriptGenerator:
    """
    Generate podcast scripts using verified research.
    Uses Gemini 2.5 Flash for speed.
    """

    def __init__(self, client: genai.Client):
        self.client = client

    async def generate_script(
        self,
        verified_topics: list[VerifiedTopic],
        hosts: list[Host],
        target_duration_minutes: int = 12
    ) -> PodcastScript:
        """Generate natural dialogue script from verified research"""

        prompt = f"""
You are writing a script for a daily podcast with two hosts.

HOSTS:
{self._format_hosts(hosts)}

VERIFIED TOPICS TO COVER:
{self._format_topics(verified_topics)}

TARGET DURATION: {target_duration_minutes} minutes

SCRIPT REQUIREMENTS:
1. Natural conversational dialogue (not robotic)
2. Hosts should have distinct voices and perspectives
3. Include specific facts with attributions
4. Add moments of humor, surprise, or insight
5. Include practical takeaways for listeners
6. Smooth transitions between topics
7. Engaging intro and memorable outro

OUTPUT FORMAT (JSON):
{{
    "title": "Episode title",
    "description": "Episode description for RSS",
    "segments": [
        {{
            "type": "intro|topic|outro",
            "topic_id": "...",
            "duration_estimate_seconds": 60,
            "dialogue": [
                {{
                    "speaker": "host_name",
                    "text": "What they say",
                    "emotion": "neutral|excited|concerned|thoughtful|humorous"
                }}
            ]
        }}
    ],
    "total_duration_estimate_seconds": ...
}}
"""

        response = await self.client.models.generate_content_async(
            model="gemini-2.5-flash",
            contents=prompt,
            config=GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,  # Higher for creativity
                max_output_tokens=8000
            )
        )

        return PodcastScript.parse_raw(response.text)
```

---

#### Stage 6: Audio Generation

```python
# src/intelligence/audio/google_tts.py

class GoogleTTSEngine:
    """
    Audio generation using Google's TTS options:
    1. Gemini Native TTS (multi-speaker, expressive)
    2. Google Cloud TTS (cost-effective, reliable)
    """

    def __init__(
        self,
        client: genai.Client,
        use_gemini_native: bool = True  # Use Gemini's native TTS
    ):
        self.client = client
        self.use_gemini_native = use_gemini_native

        if not use_gemini_native:
            from google.cloud import texttospeech
            self.cloud_tts = texttospeech.TextToSpeechClient()

    async def generate_audio(
        self,
        script: PodcastScript,
        hosts: dict[str, HostVoiceConfig]
    ) -> AudioOutput:
        """Generate audio for the entire script"""

        if self.use_gemini_native:
            return await self._generate_gemini_native(script, hosts)
        else:
            return await self._generate_cloud_tts(script, hosts)

    async def _generate_gemini_native(
        self,
        script: PodcastScript,
        hosts: dict[str, HostVoiceConfig]
    ) -> AudioOutput:
        """
        Use Gemini Native TTS for expressive, multi-speaker audio.
        Supports emotion tags and natural conversation.
        """

        segments = []

        for segment in script.segments:
            # Build SSML-like prompt for Gemini TTS
            dialogue_text = ""
            for line in segment.dialogue:
                host_config = hosts[line.speaker]
                dialogue_text += f"""
<speaker voice="{host_config.voice_name}" emotion="{line.emotion}">
{line.text}
</speaker>
"""

            response = await self.client.models.generate_content_async(
                model="gemini-2.5-flash-preview-tts",
                contents=dialogue_text,
                config=GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config={
                        "multi_speaker_config": {
                            "speaker_voice_configs": [
                                {
                                    "speaker_id": name,
                                    "voice_config": {"voice_name": config.voice_name}
                                }
                                for name, config in hosts.items()
                            ]
                        }
                    }
                )
            )

            # Save audio segment
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            segment_path = f"output/segments/{segment.topic_id}.wav"

            with open(segment_path, "wb") as f:
                f.write(audio_data)

            segments.append(AudioSegment(
                segment_id=segment.topic_id,
                path=segment_path,
                duration_seconds=segment.duration_estimate_seconds
            ))

        # Combine segments
        final_audio = self._combine_segments(segments)

        return AudioOutput(
            segments=segments,
            final_audio_path=final_audio
        )
```

---

## Part 3: Data Models

```python
# src/intelligence/models/content.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class RawContent(BaseModel):
    """Unified content from any source"""
    id: str
    source_type: str  # reddit, hackernews, newsdata, youtube, rss
    source_name: str
    title: str
    body: str
    url: Optional[str]
    author: Optional[str]
    published_at: datetime
    fetched_at: datetime
    score: Optional[int] = None
    comments: Optional[int] = None


class TopicCluster(BaseModel):
    """Semantically clustered content"""
    id: str
    name: str
    summary: str
    contents: list[RawContent]
    embedding_centroid: list[float]
    is_breaking: bool = False
    complexity_score: float = 0.5


class VerifiedFact(BaseModel):
    """A verified fact with source"""
    fact: str
    source: str
    date: Optional[str] = None
    confidence: float = 0.8


class ResearchedTopic(BaseModel):
    """Fully researched topic"""
    topic: TopicCluster
    key_facts: list[VerifiedFact]
    statistics: list[str]
    historical_context: str
    current_situation: str
    future_implications: str
    expert_opinions: list[dict]
    arguments_for: list[str] = []
    arguments_against: list[str] = []
    counter_arguments: list[str] = []
    real_stories: list[str] = []
    practical_advice: list[str]
    citations: list[dict]
    research_method: str  # quick or deep
    research_time_seconds: Optional[float] = None
    full_report: Optional[str] = None


class VerifiedTopic(BaseModel):
    """Editorially verified topic"""
    research: ResearchedTopic
    verified_facts: list[VerifiedFact]
    flagged_claims: list[str]
    gaps: list[str]
    balance_score: float
    confidence_score: float
    editorial_notes: str
```

---

## Part 4: Complete Pipeline Orchestration

```python
# src/intelligence/pipeline.py

class GoogleFirstPipeline:
    """
    Complete podcast generation pipeline using Google-first approach.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config

        # Initialize Google client
        self.gemini = genai.Client(api_key=config.gemini_api_key)

        # Initialize components
        self.source_manager = SourceManager()
        self.clusterer = SemanticClusterer(self.gemini)
        self.researcher = GoogleResearchEngine(config.gemini_api_key)
        self.synthesizer = ResearchSynthesizer(self.gemini)
        self.script_generator = EnhancedScriptGenerator(self.gemini)
        self.tts_engine = GoogleTTSEngine(self.gemini)

    async def generate_episode(
        self,
        profile: PodcastProfile,
        target_date: datetime = None
    ) -> Episode:
        """
        Generate a complete podcast episode.

        Pipeline stages:
        1. Aggregate content from all sources
        2. Cluster semantically
        3. Research each topic (quick or deep)
        4. Verify and synthesize
        5. Generate script
        6. Generate audio
        """

        target_date = target_date or datetime.now()
        logger.info(f"Generating episode for {profile.name} - {target_date.date()}")

        # Stage 1: Aggregate
        logger.info("Stage 1: Aggregating content...")
        raw_contents = await self.source_manager.fetch_all(profile.sources)
        logger.info(f"Aggregated {len(raw_contents)} items from {len(profile.sources)} sources")

        # Stage 2: Cluster
        logger.info("Stage 2: Semantic clustering...")
        clusters = await self.clusterer.cluster(raw_contents)
        logger.info(f"Created {len(clusters)} topic clusters")

        # Select top clusters by engagement
        top_clusters = sorted(
            clusters,
            key=lambda c: sum(x.score or 0 for x in c.contents),
            reverse=True
        )[:profile.topic_count]

        # Stage 3: Research
        logger.info("Stage 3: Researching topics...")
        researched_topics = []
        for cluster in top_clusters:
            logger.info(f"Researching: {cluster.name}")
            researched = await self.researcher.research_topic(cluster)
            researched_topics.append(researched)
            logger.info(f"  Method: {researched.research_method}, "
                       f"Facts: {len(researched.key_facts)}")

        # Stage 4: Verify & Synthesize
        logger.info("Stage 4: Verifying and synthesizing...")
        verified_topics = await self.synthesizer.synthesize(researched_topics)

        avg_confidence = sum(t.confidence_score for t in verified_topics) / len(verified_topics)
        logger.info(f"Average confidence score: {avg_confidence:.2f}")

        # Stage 5: Generate Script
        logger.info("Stage 5: Generating script...")
        script = await self.script_generator.generate_script(
            verified_topics,
            profile.hosts,
            profile.target_duration_minutes
        )
        logger.info(f"Script generated: {script.title}")

        # Stage 6: Generate Audio
        logger.info("Stage 6: Generating audio...")
        audio = await self.tts_engine.generate_audio(
            script,
            {h.name: h.voice_config for h in profile.hosts}
        )
        logger.info(f"Audio generated: {audio.final_audio_path}")

        # Create episode
        episode = Episode(
            profile_id=profile.id,
            episode_id=f"{profile.slug}-{target_date.strftime('%Y%m%d')}",
            title=script.title,
            description=script.description,
            date=target_date,
            topics_covered=[t.research.topic.name for t in verified_topics],
            script=script.json(),
            audio_path=audio.final_audio_path,
            duration_seconds=audio.total_duration_seconds,
            research_metadata={
                "topics_researched": len(verified_topics),
                "deep_research_count": sum(1 for t in researched_topics if t.research_method == "deep"),
                "average_confidence": avg_confidence,
                "sources_used": list(set(
                    c["url"] for t in verified_topics
                    for c in t.research.citations
                ))
            }
        )

        return episode
```

---

## Part 5: Environment Variables

```bash
# .env

# ===== GOOGLE (Primary) =====
GEMINI_API_KEY=your_gemini_api_key

# Google Cloud (for Cloud TTS if not using Gemini Native)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_TTS_API_KEY=your_google_tts_key  # Optional, for API key auth

# ===== COMPLEMENTARY TOOLS =====
# Exa.ai - For counter-arguments (covers Google's SEO bias)
EXA_API_KEY=your_exa_api_key  # Optional, 1000 free/month

# Content Aggregation
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
NEWSDATA_API_KEY=your_newsdata_key  # 200 free/day

# ===== OPTIONAL FALLBACKS =====
# Only if you want additional search options
PERPLEXITY_API_KEY=your_perplexity_key  # Optional, for ultra-fast search
TAVILY_API_KEY=your_tavily_key  # Optional, for fact verification

# ===== SETTINGS =====
TTS_PROVIDER=gemini_native  # gemini_native or google_cloud
RESEARCH_DEPTH=auto  # auto, quick, or deep
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Local embedding model
```

---

## Part 6: File Structure

```
src/
├── intelligence/                  # NEW: Agentic layer
│   ├── __init__.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── content.py            # RawContent, TopicCluster
│   │   ├── research.py           # ResearchedTopic, VerifiedTopic
│   │   └── script.py             # PodcastScript, Dialogue
│   │
│   ├── aggregation/
│   │   ├── __init__.py
│   │   ├── source_manager.py     # Orchestrates all sources
│   │   ├── reddit_connector.py
│   │   ├── hackernews_connector.py
│   │   ├── newsdata_connector.py
│   │   ├── youtube_connector.py
│   │   └── rss_connector.py
│   │
│   ├── clustering/
│   │   ├── __init__.py
│   │   ├── semantic_clusterer.py  # Local embeddings + HDBSCAN
│   │   └── trend_detector.py      # Velocity detection
│   │
│   ├── research/
│   │   ├── __init__.py
│   │   ├── google_research_engine.py  # Main research (Google tools)
│   │   └── exa_complement.py          # Exa for counter-arguments
│   │
│   ├── synthesis/
│   │   ├── __init__.py
│   │   └── synthesizer.py         # Verification + synthesis
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   └── script_generator.py    # Dialogue generation
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── google_tts.py          # Gemini Native + Cloud TTS
│   │   └── audio_mixer.py         # Segment combining
│   │
│   └── pipeline.py                # Complete orchestration
│
├── aggregators/                   # EXISTING (will be migrated)
├── generators/                    # EXISTING (will be migrated)
└── tts/                          # EXISTING (will be migrated)
```

---

## Part 7: Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

| Day | Task | Files |
|-----|------|-------|
| 1 | Update dependencies | `requirements.txt` |
| 1 | Create models | `models/*.py` |
| 2 | Build HackerNews connector | `aggregation/hackernews_connector.py` |
| 2 | Build NewsData connector | `aggregation/newsdata_connector.py` |
| 3 | Build YouTube connector | `aggregation/youtube_connector.py` |
| 3 | Build source manager | `aggregation/source_manager.py` |
| 4 | Build semantic clusterer | `clustering/semantic_clusterer.py` |
| 5 | Integration tests | `tests/test_aggregation.py` |

### Phase 2: Google Research Engine (Week 2)

| Day | Task | Files |
|-----|------|-------|
| 1 | Quick research (Gemini + Search) | `research/google_research_engine.py` |
| 2 | Deep research (Interactions API) | `research/google_research_engine.py` |
| 3 | Exa integration | `research/exa_complement.py` |
| 4 | Synthesizer | `synthesis/synthesizer.py` |
| 5 | Research tests | `tests/test_research.py` |

### Phase 3: Generation & Audio (Week 3)

| Day | Task | Files |
|-----|------|-------|
| 1 | Script generator | `generation/script_generator.py` |
| 2 | Gemini Native TTS | `audio/google_tts.py` |
| 3 | Audio mixer | `audio/audio_mixer.py` |
| 4 | Pipeline orchestration | `pipeline.py` |
| 5 | End-to-end tests | `tests/test_pipeline.py` |

### Phase 4: Integration (Week 4)

| Day | Task | Files |
|-----|------|-------|
| 1 | Connect to webapp | Update `webapp/` |
| 2 | Profile-based sources | Update DB models |
| 3 | Migrate existing code | Deprecate old aggregators |
| 4 | Documentation | Update README |
| 5 | Production testing | Full episode generation |

---

## Part 8: Cost Estimates

### Per Episode (12 minutes, 5 topics)

| Component | Usage | Cost |
|-----------|-------|------|
| Source aggregation | API calls | ~$0 (free tiers) |
| Semantic clustering | Local | $0 |
| Quick research (3 topics) | ~10K tokens + 3 searches | ~$0.05 |
| Deep research (2 topics) | ~50K tokens | ~$0.10 |
| Exa counter-args | 5 searches | ~$0.02 |
| Synthesis | ~5K tokens | ~$0.01 |
| Script generation | ~10K tokens | ~$0.01 |
| Gemini TTS (12 min) | ~15K chars | ~$0.01 |
| **Total per episode** | | **~$0.20** |

### Monthly (30 episodes)

| Item | Cost |
|------|------|
| Episode generation | ~$6 |
| Buffer/retries | ~$4 |
| **Monthly total** | **~$10** |

---

## Summary: Google Tools Used

| Google Tool | How We Use It |
|-------------|---------------|
| **Gemini 2.5 Flash** | Cluster naming, script generation, quick research |
| **Gemini 2.5 Pro** | Synthesis, verification (with thinking) |
| **Google Search Grounding** | Real-time facts, current events |
| **URL Context** | Read source URLs, PDFs |
| **Deep Research Agent** | Comprehensive research for complex topics |
| **Structured Output** | JSON responses, Pydantic compatibility |
| **Thinking Mode** | Verification reasoning |
| **Gemini Native TTS** | Multi-speaker podcast audio |
| **Google Cloud TTS** | Fallback, cost-effective audio |

## Complementary Tools (Gap Coverage)

| Tool | Gap Covered | Why Needed |
|------|-------------|------------|
| **Exa.ai** | Counter-arguments | 94.9% accuracy, overcomes Google's SEO bias |
| **Reddit/HN/News APIs** | Content aggregation | Google doesn't have social/news aggregation |
| **sentence-transformers** | Local embeddings | Cost-free clustering |

---

Ready to implement?
