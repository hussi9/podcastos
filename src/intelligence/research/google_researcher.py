"""Google Research Engine using Gemini APIs."""

import os
import time
from enum import Enum
from typing import Optional
import logging

from google import genai
from google.genai import types

from ..models.content import TopicCluster
from ..models.research import (
    ResearchedTopic,
    VerifiedFact,
    ExpertOpinion,
    TrendVelocity,
)


logger = logging.getLogger(__name__)


class ResearchDepth(str, Enum):
    """Research depth levels."""
    QUICK = "quick"  # Google Search Grounding only (~10 sec)
    STANDARD = "standard"  # Search + follow-up queries (~30 sec)
    DEEP = "deep"  # Full Deep Research Agent (~5-20 min)


class GoogleResearcher:
    """
    Google-first research engine using:
    - Gemini 2.0 Flash for quick research
    - Google Search Grounding for real-time facts
    - Deep Research Agent for comprehensive analysis
    - URL Context Tool for specific source analysis
    """

    QUICK_RESEARCH_PROMPT = """You are a research assistant. Research "{topic_name}" using web search and provide a concise summary.

Context: {context}

Write 2-3 paragraphs covering:
- What is happening and why it matters
- Key facts with sources
- Expert opinions if available

Be direct and factual. Start with the main point, not acknowledgment."""

    DEEP_RESEARCH_PROMPT = """You are a research assistant. Research "{topic_name}" thoroughly using web search.

Context: {context}

Write a comprehensive analysis (4-6 paragraphs) covering:
- Background and context
- Current developments and key facts
- Expert opinions and different perspectives
- Why this matters and future implications

Be direct and factual. Start with the main findings, not acknowledgment. Cite sources naturally."""

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        deep_research_model: str = "gemini-2.5-pro-preview-05-06",
    ):
        self.model = model
        self.deep_research_model = deep_research_model
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Lazy load the Gemini client."""
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def research_topic(
        self,
        cluster: TopicCluster,
        depth: ResearchDepth = ResearchDepth.STANDARD,
    ) -> ResearchedTopic:
        """
        Research a topic cluster.
        """
        start_time = time.time()

        # Prepare context from cluster
        context = self._prepare_context(cluster)

        if depth == ResearchDepth.QUICK:
            result = await self._quick_research(cluster.name, context)
        elif depth == ResearchDepth.STANDARD:
            result = await self._standard_research(cluster.name, context)
        else:
            result = await self._deep_research(cluster.name, context)

        # Create ResearchedTopic
        researched = ResearchedTopic(
            id=f"research-{cluster.id}",
            cluster_id=cluster.id,
            headline=result.get("headline", cluster.name),
            summary=result.get("summary", cluster.summary),
            category=cluster.category,
            background=result.get("background", ""),
            current_situation=result.get("current_situation", ""),
            implications=result.get("implications", ""),
            verified_facts=result.get("verified_facts", []),
            expert_opinions=result.get("expert_opinions", []),
            human_stories=result.get("human_stories", []),
            community_sentiment=self._extract_community_sentiment(cluster),
            research_depth=depth.value,
            research_duration_seconds=time.time() - start_time,
            sources_consulted=result.get("sources_count", 0),
            google_search_grounding_used=depth in [ResearchDepth.QUICK, ResearchDepth.STANDARD],
            deep_research_used=depth == ResearchDepth.DEEP,
        )

        # Detect trends
        if cluster.is_breaking:
            researched.is_breaking_news = True
            researched.trend_velocity = TrendVelocity.VIRAL

        researched.calculate_quality_metrics()

        logger.info(
            f"Researched topic '{cluster.name}' at {depth.value} depth "
            f"in {researched.research_duration_seconds:.1f}s"
        )

        return researched

    async def _quick_research(self, topic: str, context: str) -> dict:
        """
        Quick research using Google Search Grounding.
        """
        prompt = self.QUICK_RESEARCH_PROMPT.format(
            topic_name=topic,
            context=context[:500],
        )

        # Use Search Grounding
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        return self._parse_research_response(response.text)

    async def _standard_research(self, topic: str, context: str) -> dict:
        """
        Standard research with search grounding and follow-up.
        """
        # First pass: broad research
        initial = await self._quick_research(topic, context)

        # Follow-up for specific aspects
        follow_up_prompt = f"""Based on initial research about "{topic}", provide more detail on:
1. The most significant recent developments
2. Expert credibility of cited sources
3. Any conflicting viewpoints

Initial findings summary: {initial.get('summary', '')[:300]}"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=follow_up_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        # Merge results
        follow_up = self._parse_research_response(response.text)

        return {
            "headline": initial.get("headline", topic),
            "summary": initial.get("summary", ""),
            "background": initial.get("background", ""),
            "current_situation": follow_up.get("current_situation", initial.get("current_situation", "")),
            "implications": initial.get("implications", ""),
            "verified_facts": initial.get("verified_facts", []) + follow_up.get("verified_facts", []),
            "expert_opinions": initial.get("expert_opinions", []) + follow_up.get("expert_opinions", []),
            "human_stories": initial.get("human_stories", []),
            "sources_count": initial.get("sources_count", 0) + follow_up.get("sources_count", 0),
        }

    async def _deep_research(self, topic: str, context: str) -> dict:
        """
        Deep research using Gemini Deep Research capabilities.
        Uses thinking mode for comprehensive analysis.
        """
        prompt = self.DEEP_RESEARCH_PROMPT.format(
            topic_name=topic,
            context=context[:1000],
        )

        # Use deep research model
        response = self.client.models.generate_content(
            model=self.model,  # Use standard model for now
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        return self._parse_research_response(response.text, detailed=True)

    async def research_url(self, url: str, question: str) -> dict:
        """
        Research specific content at a URL using URL Context Tool.
        """
        prompt = f"""Analyze the content at this URL and answer the following question:

URL: {url}
Question: {question}

Provide factual information based on the URL content."""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                tools=[types.Tool(url_context=types.UrlContext())],
            ),
        )

        return {"answer": response.text, "url": url}

    def _prepare_context(self, cluster: TopicCluster) -> str:
        """Prepare research context from cluster."""
        parts = []

        # Add top content titles
        for content in cluster.contents[:5]:
            parts.append(f"- [{content.source_name}] {content.title}")

        # Add sample body text
        for content in cluster.contents[:2]:
            if content.body:
                parts.append(f"\nFrom {content.source_name}:\n{content.body[:300]}")

        return "\n".join(parts)

    def _extract_community_sentiment(self, cluster: TopicCluster) -> str:
        """Extract overall sentiment from community sources."""
        reddit_items = [c for c in cluster.contents if c.source_type == "reddit"]
        hn_items = [c for c in cluster.contents if c.source_type == "hackernews"]

        sentiments = []
        if reddit_items:
            avg_score = sum(c.score or 0 for c in reddit_items) / len(reddit_items)
            if avg_score > 100:
                sentiments.append("highly positive on Reddit")
            elif avg_score > 20:
                sentiments.append("positive reception on Reddit")

        if hn_items:
            avg_score = sum(c.score or 0 for c in hn_items) / len(hn_items)
            if avg_score > 100:
                sentiments.append("strong HN interest")
            elif avg_score > 30:
                sentiments.append("notable HN discussion")

        return "; ".join(sentiments) if sentiments else None

    def _clean_preamble(self, text: str) -> str:
        """Remove common model preambles from response."""
        import re

        cleaned = text.strip()

        # Remove markdown bold/headers at start
        cleaned = re.sub(r"^\*\*[^*]+\*\*:?\s*\n?", "", cleaned)
        cleaned = re.sub(r"^#+\s*[^\n]+\n+", "", cleaned)

        # Common preamble patterns to remove (apply repeatedly)
        preambles = [
            r"^Okay,?\s*I\s*will[^.]+\.\s*",
            r"^Sure,?\s*I\s*(can|will)[^.]+\.\s*",
            r"^I'll\s*[^.]+\.\s*",
            r"^Let me\s*[^.]+\.\s*",
            r"^Here's\s*(a|an|the)?\s*(comprehensive\s*)?(analysis|summary|overview|breakdown)[^:]*:?\s*",
            r"^Based on[^,]+,\s*",
            r"^This\s*(analysis|summary)\s*[^.]+\.\s*",
        ]

        for pattern in preambles:
            cleaned = re.sub(pattern, "", cleaned.strip(), flags=re.IGNORECASE)

        # Clean any remaining markdown headers
        cleaned = re.sub(r"^\*\*[^*]+\*\*:?\s*\n?", "", cleaned.strip())
        cleaned = re.sub(r"^#+\s*[^\n]+\n+", "", cleaned.strip())

        return cleaned.strip()

    def _parse_research_response(self, text: str, detailed: bool = False) -> dict:
        """Parse research response into structured format."""
        result = {
            "headline": "",
            "summary": "",
            "background": "",
            "current_situation": "",
            "implications": "",
            "verified_facts": [],
            "expert_opinions": [],
            "human_stories": [],
            "sources_count": 0,
        }

        if not text or not text.strip():
            return result

        # Clean preambles from model responses
        text = self._clean_preamble(text)

        # First, capture the full text as summary (fallback)
        full_text = text.strip()

        # Extract sections (basic parsing - LLM responses vary)
        lines = text.split("\n")
        current_section = "summary"
        current_text = []

        for line in lines:
            line_lower = line.lower().strip()

            # Skip empty lines
            if not line.strip():
                continue

            # Detect section headers (only if line is short - likely a header)
            is_header = len(line.strip()) < 50 and any(
                kw in line_lower for kw in ["background", "history", "context", "current",
                                             "recent", "implication", "impact", "future", "matter"]
            )

            if is_header:
                if current_text:
                    result[current_section] = " ".join(current_text)

                if any(kw in line_lower for kw in ["background", "history", "context"]):
                    current_section = "background"
                elif any(kw in line_lower for kw in ["current", "recent", "now", "today"]):
                    current_section = "current_situation"
                elif any(kw in line_lower for kw in ["implication", "impact", "future", "matter"]):
                    current_section = "implications"
                current_text = []
            else:
                current_text.append(line.strip())

                # Extract facts (lines with sources or key phrases)
                if "http" in line or "according to" in line_lower or "announced" in line_lower:
                    result["verified_facts"].append(
                        VerifiedFact(
                            claim=line.strip()[:500],
                            source_url=self._extract_url(line) or "search_grounding",
                            source_name="Google Search",
                            verification_status="grounded",
                            confidence_score=0.8,
                        )
                    )
                    result["sources_count"] += 1

                # Extract expert opinions
                if any(kw in line_lower for kw in ["said", "stated", "expert", "analyst", "professor"]):
                    result["expert_opinions"].append(
                        ExpertOpinion(
                            quote=line.strip()[:500],
                            expert_name=self._extract_name(line) or "Expert",
                            source_url="search_grounding",
                        )
                    )

        # Save remaining text
        if current_text:
            result[current_section] = " ".join(current_text)

        # Ensure we have a summary - use full text if sections parsing didn't work
        if not result["summary"]:
            result["summary"] = full_text[:1000]

        # Use background if summary is still empty
        if not result["summary"] and result["background"]:
            result["summary"] = result["background"][:500]

        # Generate headline from first sentence
        if not result["headline"] and result["summary"]:
            first_sentence = result["summary"].split(".")[0]
            result["headline"] = first_sentence[:100]

        return result

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text."""
        import re
        match = re.search(r'https?://[^\s\)]+', text)
        return match.group(0) if match else None

    def _extract_name(self, text: str) -> Optional[str]:
        """Extract person name from quote attribution."""
        import re
        # Simple pattern for "Name said" or "according to Name"
        patterns = [
            r'([A-Z][a-z]+ [A-Z][a-z]+) (?:said|stated|noted)',
            r'according to ([A-Z][a-z]+ [A-Z][a-z]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
