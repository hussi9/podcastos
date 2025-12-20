"""
Deep topic researcher using Gemini with Google Search grounding.
Adds facts, nuances, historical context, and future implications to topics.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import google.generativeai as genai

logger = logging.getLogger(__name__)


class ResearchedFact(BaseModel):
    """A specific fact or data point"""
    fact: str
    source: Optional[str] = None
    date: Optional[str] = None


class ExpertOpinion(BaseModel):
    """An expert or official opinion on the topic"""
    person: str
    role: str
    quote: str
    context: Optional[str] = None


class TopicResearch(BaseModel):
    """Deep research on a single topic"""
    topic_title: str

    # Core facts and numbers
    key_facts: list[ResearchedFact]
    statistics: list[str]

    # Context
    historical_context: str  # What happened before, how we got here
    current_situation: str   # What's happening now in detail
    future_implications: str # What this means going forward

    # Perspectives
    expert_opinions: list[ExpertOpinion]
    community_reactions: list[str]  # Real reactions from Reddit/social

    # For natural conversation
    common_misconceptions: list[str]
    practical_advice: list[str]
    related_stories: list[str]  # Real examples, case studies

    # Debate points (for back-and-forth)
    arguments_for: list[str]
    arguments_against: list[str]
    nuanced_take: str


class TopicResearcher:
    """
    Uses Gemini with Google Search to deeply research podcast topics.
    Adds facts, context, and nuance for richer conversations.
    """

    RESEARCH_PROMPT = """You are a research assistant for a podcast about South Asian immigrants in the USA.
Your job is to deeply research a topic and provide SPECIFIC, FACTUAL information.

IMPORTANT GUIDELINES:
1. Use REAL facts, numbers, dates - not vague statements
2. Include SPECIFIC statistics (e.g., "processing time increased from 6 to 18 months")
3. Reference REAL policies, laws, and their actual names
4. Include REAL quotes from officials, lawyers, or community members if available
5. Provide HISTORICAL CONTEXT - what led to this situation
6. Give FUTURE IMPLICATIONS - what this means going forward
7. Include REAL community reactions and concerns
8. Note any COMMON MISCONCEPTIONS people have
9. Provide PRACTICAL, ACTIONABLE advice

Research this topic thoroughly using current information:

TOPIC: {topic_title}

EXISTING INFORMATION:
{existing_info}

CATEGORY: {category}

Provide comprehensive research in this JSON format:
{{
  "topic_title": "{topic_title}",
  "key_facts": [
    {{"fact": "Specific fact with numbers/dates", "source": "Source name", "date": "When"}},
  ],
  "statistics": [
    "Specific statistic with numbers",
  ],
  "historical_context": "2-3 paragraphs on how we got here, what changed, key dates",
  "current_situation": "2-3 paragraphs on exactly what's happening now, who's affected, specific details",
  "future_implications": "2-3 paragraphs on what this means, predictions, timeline",
  "expert_opinions": [
    {{"person": "Name", "role": "Immigration Attorney/USCIS Official/etc", "quote": "Actual or paraphrased quote", "context": "When/where said"}}
  ],
  "community_reactions": [
    "Real concern or reaction from the community",
  ],
  "common_misconceptions": [
    "Something people often get wrong about this",
  ],
  "practical_advice": [
    "Specific actionable advice for listeners",
  ],
  "related_stories": [
    "Real example or case study illustrating this issue",
  ],
  "arguments_for": [
    "Argument supporting this policy/change",
  ],
  "arguments_against": [
    "Argument against this policy/change",
  ],
  "nuanced_take": "A balanced, thoughtful perspective that acknowledges complexity"
}}

Return ONLY valid JSON, no markdown."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)

        # Use standard model - Gemini 2.0 has recent training data
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name

    async def research_topic(self, topic) -> TopicResearch:
        """
        Deeply research a single topic using Gemini + Google Search.
        """
        logger.info(f"Researching topic: {topic.title}")

        # Format existing info from aggregators
        existing_info = self._format_existing_info(topic)

        prompt = self.RESEARCH_PROMPT.format(
            topic_title=topic.title,
            existing_info=existing_info,
            category=topic.category,
        )

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Lower temp for factual accuracy
                    top_p=0.9,
                    max_output_tokens=4000,
                ),
            )

            # Parse response
            research_data = self._parse_response(response.text)

            research = TopicResearch(
                topic_title=topic.title,
                key_facts=[ResearchedFact(**f) for f in research_data.get("key_facts", [])],
                statistics=research_data.get("statistics", []),
                historical_context=research_data.get("historical_context", ""),
                current_situation=research_data.get("current_situation", ""),
                future_implications=research_data.get("future_implications", ""),
                expert_opinions=[ExpertOpinion(**o) for o in research_data.get("expert_opinions", [])],
                community_reactions=research_data.get("community_reactions", []),
                common_misconceptions=research_data.get("common_misconceptions", []),
                practical_advice=research_data.get("practical_advice", []),
                related_stories=research_data.get("related_stories", []),
                arguments_for=research_data.get("arguments_for", []),
                arguments_against=research_data.get("arguments_against", []),
                nuanced_take=research_data.get("nuanced_take", ""),
            )

            logger.info(f"Research complete: {len(research.key_facts)} facts, "
                       f"{len(research.expert_opinions)} expert opinions")

            return research

        except Exception as e:
            logger.error(f"Research failed for {topic.title}: {e}")
            # Return minimal research
            return TopicResearch(
                topic_title=topic.title,
                key_facts=[],
                statistics=[],
                historical_context="",
                current_situation=topic.summary or "",
                future_implications="",
                expert_opinions=[],
                community_reactions=topic.key_points or [],
                common_misconceptions=[],
                practical_advice=[],
                related_stories=[],
                arguments_for=[],
                arguments_against=[],
                nuanced_take="",
            )

    async def research_all_topics(self, topics: list) -> list[TopicResearch]:
        """Research all topics in parallel"""
        logger.info(f"Starting deep research on {len(topics)} topics...")

        tasks = [self.research_topic(topic) for topic in topics]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        researched = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Research failed for topic {i}: {result}")
            else:
                researched.append(result)

        logger.info(f"Completed research on {len(researched)} topics")
        return researched

    def _format_existing_info(self, topic) -> str:
        """Format existing topic info for the research prompt"""
        lines = []

        if topic.summary:
            lines.append(f"Summary: {topic.summary}")

        if topic.key_points:
            lines.append("Key points from aggregation:")
            for point in topic.key_points:
                lines.append(f"  - {point}")

        if topic.sources:
            lines.append(f"Sources: {', '.join(topic.sources)}")

        if topic.community_sentiment:
            lines.append(f"Community sentiment: {topic.community_sentiment}")

        return "\n".join(lines) if lines else "No existing information"

    def _parse_response(self, response_text: str) -> dict:
        """Parse Gemini response to JSON"""
        import json
        import re

        text = response_text.strip()

        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass

            logger.error("Failed to parse research response")
            return {}
