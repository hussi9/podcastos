"""
AI-powered podcast script generator using Google Gemini
"""

from datetime import datetime
from typing import Optional
import google.generativeai as genai
from pydantic import BaseModel
import logging
import json
import re

from ..aggregators.content_ranker import PodcastTopic

logger = logging.getLogger(__name__)


class DialogueLine(BaseModel):
    """A single line of dialogue in the podcast"""

    speaker: str  # "raj" or "priya"
    text: str
    emotion: Optional[str] = None  # For TTS guidance: excited, concerned, thoughtful, etc.


class PodcastSegment(BaseModel):
    """A segment of the podcast covering one topic"""

    topic_id: str
    topic_title: str
    duration_estimate: int  # seconds
    dialogue: list[DialogueLine]


class PodcastScript(BaseModel):
    """Complete podcast script"""

    episode_id: str
    episode_title: str
    episode_date: str
    duration_estimate: int  # total seconds
    intro: list[DialogueLine]
    segments: list[PodcastSegment]
    outro: list[DialogueLine]

    def to_ssml_blocks(self) -> list[dict]:
        """Convert script to blocks for TTS processing"""
        blocks = []

        # Intro
        for line in self.intro:
            blocks.append({
                "speaker": line.speaker,
                "text": line.text,
                "section": "intro",
            })

        # Segments
        for segment in self.segments:
            for line in segment.dialogue:
                blocks.append({
                    "speaker": line.speaker,
                    "text": line.text,
                    "section": segment.topic_id,
                })

        # Outro
        for line in self.outro:
            blocks.append({
                "speaker": line.speaker,
                "text": line.text,
                "section": "outro",
            })

        return blocks


class ScriptGenerator:
    """
    Generates conversational podcast scripts using Google Gemini
    """

    # System prompt for script generation
    SYSTEM_PROMPT = """You are a podcast script writer for "{podcast_name}", a daily news and discussion
podcast.

You write natural, conversational dialogue between two hosts:
- RAJ: A pragmatic tech professional who immigrated 10 years ago. He focuses on practical advice,
  facts, and actionable insights. He has deep knowledge about visas, careers, and corporate America.
  His tone is warm but direct.
- PRIYA: An empathetic second-generation Indian-American community organizer. She brings cultural
  context, emotional intelligence, and community perspectives. She shares relatable stories and
  focuses on the human side of issues.

Guidelines:
1. Write natural, conversational dialogue - not formal or scripted sounding
2. Include back-and-forth discussion, not just alternating monologues
3. Add brief reactions, acknowledgments ("That's a great point", "Exactly", "Hmm, interesting")
4. Include personal anecdotes or "I heard from a friend" stories to make it relatable
5. Provide practical advice and actionable takeaways
6. Be sensitive to immigrant experiences - acknowledge struggles without being negative
7. Use some Hindi/Gujarati/Tamil words occasionally (yaar, accha, basically) but keep it accessible
8. Keep each speaker's turn to 2-4 sentences for natural flow
9. Total script should be conversational and engaging, not dry news reading

Output format: Return ONLY valid JSON with this structure:
{{
  "intro": [{{"speaker": "raj" or "priya", "text": "..."}}],
  "segments": [
    {{
      "topic_id": "...",
      "topic_title": "...",
      "dialogue": [{{"speaker": "raj" or "priya", "text": "..."}}]
    }}
  ],
  "outro": [{{"speaker": "raj" or "priya", "text": "..."}}]
}}"""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name

    async def generate_script(
        self,
        topics: list[PodcastTopic],
        episode_date: Optional[datetime] = None,
        target_duration_minutes: int = 12,
        podcast_name: str = "Podcast",
    ) -> PodcastScript:
        """Generate a complete podcast script from topics"""

        if not episode_date:
            episode_date = datetime.now()

        date_str = episode_date.strftime("%B %d, %Y")
        day_of_week = episode_date.strftime("%A")

        # Build the prompt with topic information
        logger.info(f"Generating script for {len(topics)} topics")
        for i, t in enumerate(topics):
            logger.info(f"  Topic {i+1}: {t.title} ({t.category})")
        topics_info = self._format_topics_for_prompt(topics)
        logger.debug(f"Topics formatted for prompt:\n{topics_info[:500]}...")

        # Format system prompt with podcast name
        system_prompt = self.SYSTEM_PROMPT.format(podcast_name=podcast_name)

        prompt = f"""{system_prompt}

---

Generate a podcast script for {podcast_name} - {day_of_week}, {date_str}

Target duration: {target_duration_minutes} minutes (aim for ~{target_duration_minutes * 150} words total)

TODAY'S TOPICS:
{topics_info}

Create an engaging podcast episode covering these topics. Include:
1. A warm intro welcoming listeners and previewing what's coming
2. A segment for each topic with natural discussion between Raj and Priya
3. A friendly outro encouraging listeners to share and tune in tomorrow

Remember to:
- Start with the most important/breaking news
- Add practical advice where relevant
- Include community perspectives
- Make transitions between topics smooth
- Keep the energy upbeat but respectful of serious topics

CRITICAL: Return ONLY valid JSON with this EXACT structure (no other keys allowed):
{{
  "intro": [{{"speaker": "raj", "text": "..."}}, {{"speaker": "priya", "text": "..."}}],
  "segments": [
    {{
      "topic_id": "topic_1",
      "topic_title": "Topic Title Here",
      "dialogue": [{{"speaker": "raj", "text": "..."}}, {{"speaker": "priya", "text": "..."}}]
    }}
  ],
  "outro": [{{"speaker": "raj", "text": "..."}}, {{"speaker": "priya", "text": "..."}}]
}}

Speaker must be lowercase "raj" or "priya". Return ONLY the JSON, no markdown code blocks."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.8,
                    top_p=0.9,
                    max_output_tokens=8000,
                ),
            )

            # Parse the response
            logger.info(f"Raw Gemini response length: {len(response.text)} chars")
            logger.debug(f"Raw response (first 500 chars): {response.text[:500]}")
            script_data = self._parse_response(response.text)
            logger.info(f"Parsed script_data keys: {script_data.keys()}")
            logger.info(f"Intro lines: {len(script_data.get('intro', []))}")
            logger.info(f"Segments: {len(script_data.get('segments', []))}")

            # Build the PodcastScript object
            episode_id = f"dd-{episode_date.strftime('%Y%m%d')}"
            episode_title = self._generate_episode_title(topics, episode_date, podcast_name)

            # Parse intro
            intro_lines = [
                DialogueLine(speaker=line["speaker"], text=line["text"])
                for line in script_data.get("intro", [])
            ]

            # Parse segments
            segments = []
            for seg_data in script_data.get("segments", []):
                dialogue = [
                    DialogueLine(speaker=line["speaker"], text=line["text"])
                    for line in seg_data.get("dialogue", [])
                ]
                segment = PodcastSegment(
                    topic_id=seg_data.get("topic_id", "unknown"),
                    topic_title=seg_data.get("topic_title", "Discussion"),
                    duration_estimate=len(dialogue) * 15,  # ~15 sec per exchange
                    dialogue=dialogue,
                )
                segments.append(segment)

            # Parse outro
            outro_lines = [
                DialogueLine(speaker=line["speaker"], text=line["text"])
                for line in script_data.get("outro", [])
            ]

            # Calculate total duration
            total_words = sum(
                len(line.text.split())
                for line in intro_lines + outro_lines
            )
            for seg in segments:
                total_words += sum(len(line.text.split()) for line in seg.dialogue)

            # Estimate ~150 words per minute for conversational speech
            duration_estimate = (total_words / 150) * 60

            script = PodcastScript(
                episode_id=episode_id,
                episode_title=episode_title,
                episode_date=episode_date.isoformat(),
                duration_estimate=int(duration_estimate),
                intro=intro_lines,
                segments=segments,
                outro=outro_lines,
            )

            logger.info(
                f"Generated script: {episode_title}, "
                f"~{int(duration_estimate/60)} minutes, "
                f"{len(segments)} segments"
            )

            return script

        except Exception as e:
            logger.error(f"Script generation failed: {e}")
            import traceback
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            # Return a fallback script
            logger.info("Generating fallback script...")
            return self._generate_fallback_script(topics, episode_date, podcast_name)

    def _format_topics_for_prompt(self, topics: list[PodcastTopic]) -> str:
        """Format topics into a readable string for the prompt"""
        lines = []

        for i, topic in enumerate(topics, 1):
            status = []
            if topic.is_breaking:
                status.append("BREAKING")
            if topic.is_trending:
                status.append("TRENDING")
            status_str = f" [{', '.join(status)}]" if status else ""

            lines.append(f"\n## Topic {i}: {topic.title}{status_str}")
            lines.append(f"Category: {topic.category}")
            lines.append(f"Sources: {', '.join(topic.sources)}")

            if topic.key_points:
                lines.append("Key points:")
                for point in topic.key_points[:4]:
                    lines.append(f"  - {point}")

            if topic.community_sentiment:
                lines.append(f"Community sentiment: {topic.community_sentiment}")

        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> dict:
        """Parse the Gemini response into structured data"""
        # Clean up the response
        text = response_text.strip()
        logger.info(f"Parsing response, original length: {len(text)}")

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
            logger.info("Removed ```json prefix")
        elif text.startswith("```"):
            text = text[3:]
            logger.info("Removed ``` prefix")
        if text.endswith("```"):
            text = text[:-3]
            logger.info("Removed ``` suffix")

        text = text.strip()
        logger.info(f"Cleaned text length: {len(text)}")
        logger.info(f"First 200 chars: {text[:200]}")

        try:
            result = json.loads(text)
            logger.info(f"JSON parse SUCCESS! Keys: {result.keys()}")
            # Normalize the response structure if Gemini used alternative format
            return self._normalize_script_structure(result)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            logger.warning(f"Error at position {e.pos}: {text[max(0, e.pos-50):e.pos+50]}")
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                logger.info(f"Found JSON match, length: {len(json_match.group())}")
                try:
                    result = json.loads(json_match.group())
                    logger.info(f"Regex JSON parse SUCCESS! Keys: {result.keys()}")
                    return self._normalize_script_structure(result)
                except Exception as e2:
                    logger.error(f"Regex JSON parse also failed: {e2}")

            # Return empty structure if parsing fails
            logger.error("Failed to parse script response - returning empty structure")
            return {"intro": [], "segments": [], "outro": []}

    def _normalize_script_structure(self, data: dict) -> dict:
        """Normalize different response formats from Gemini to expected structure"""
        # If already in expected format, return as-is
        if "intro" in data and "outro" in data and isinstance(data.get("segments"), list):
            if data["segments"] and "dialogue" in data["segments"][0]:
                logger.info("Response already in expected format")
                return data

        logger.info("Normalizing alternative response format...")

        normalized = {"intro": [], "segments": [], "outro": []}

        # Handle alternative format where everything is in "segments" with different keys
        segments = data.get("segments", [])

        for seg in segments:
            # Determine segment type
            seg_title = seg.get("segmentTitle", seg.get("topic_title", "")).lower()

            # Extract dialogue lines (could be "script", "dialogue", or "lines")
            lines = seg.get("script", seg.get("dialogue", seg.get("lines", [])))

            # Normalize speaker names to lowercase
            normalized_lines = []
            for line in lines:
                speaker = line.get("speaker", "").lower()
                text = line.get("text", line.get("content", ""))
                if speaker in ["raj", "priya"] and text:
                    normalized_lines.append({"speaker": speaker, "text": text})

            # Categorize segment
            if "intro" in seg_title:
                normalized["intro"].extend(normalized_lines)
            elif "outro" in seg_title or "closing" in seg_title or "goodbye" in seg_title:
                normalized["outro"].extend(normalized_lines)
            else:
                # Regular topic segment
                normalized["segments"].append({
                    "topic_id": seg.get("topic_id", f"topic_{len(normalized['segments'])+1}"),
                    "topic_title": seg.get("segmentTitle", seg.get("topic_title", "Discussion")),
                    "dialogue": normalized_lines
                })

        logger.info(f"Normalized: {len(normalized['intro'])} intro lines, "
                   f"{len(normalized['segments'])} segments, "
                   f"{len(normalized['outro'])} outro lines")

        return normalized

    def _generate_episode_title(
        self, topics: list[PodcastTopic], episode_date: datetime, podcast_name: str = "Podcast"
    ) -> str:
        """Generate an episode title"""
        date_str = episode_date.strftime("%b %d")

        # Find the most important topic
        breaking = [t for t in topics if t.is_breaking]
        if breaking:
            main_topic = breaking[0].title
        elif topics:
            main_topic = topics[0].title
        else:
            main_topic = "Daily Update"

        return f"{main_topic} | {podcast_name} - {date_str}"

    def _generate_fallback_script(
        self, topics: list[PodcastTopic], episode_date: datetime, podcast_name: str = "Podcast"
    ) -> PodcastScript:
        """Generate a basic fallback script if AI generation fails"""
        date_str = episode_date.strftime("%B %d, %Y")

        intro = [
            DialogueLine(
                speaker="raj",
                text=f"Good morning everyone! Welcome to {podcast_name} for {date_str}. I'm Raj."
            ),
            DialogueLine(
                speaker="priya",
                text="And I'm Priya! We've got some interesting topics to cover today."
            ),
        ]

        segments = []
        for topic in topics[:3]:
            segment = PodcastSegment(
                topic_id=topic.id,
                topic_title=topic.title,
                duration_estimate=120,
                dialogue=[
                    DialogueLine(
                        speaker="raj",
                        text=f"Let's talk about {topic.title}. {topic.summary}"
                    ),
                    DialogueLine(
                        speaker="priya",
                        text="That's really interesting. I've been seeing a lot of discussion about this in the community."
                    ),
                    DialogueLine(
                        speaker="raj",
                        text="Absolutely. For our listeners dealing with this, my advice would be to stay informed and reach out to professionals if needed."
                    ),
                ],
            )
            segments.append(segment)

        outro = [
            DialogueLine(
                speaker="priya",
                text=f"That's all for today's episode! Thanks for listening to {podcast_name}."
            ),
            DialogueLine(
                speaker="raj",
                text="Don't forget to share this with friends and family. We'll be back tomorrow with more updates. Take care!"
            ),
        ]

        return PodcastScript(
            episode_id=f"dd-{episode_date.strftime('%Y%m%d')}",
            episode_title=f"Daily Update | {podcast_name} - {episode_date.strftime('%b %d')}",
            episode_date=episode_date.isoformat(),
            duration_estimate=600,
            intro=intro,
            segments=segments,
            outro=outro,
        )

    async def regenerate_segment(
        self, topic: PodcastTopic, context: str = ""
    ) -> PodcastSegment:
        """Regenerate a single segment with more detail"""
        prompt = f"""Generate a detailed podcast segment for the topic: {topic.title}

Context from the episode: {context}

Topic details:
{self._format_topics_for_prompt([topic])}

Create an engaging 3-4 minute segment with natural dialogue between Raj and Priya.
Include practical advice and community perspectives.

Return ONLY JSON:
{{
  "topic_id": "{topic.id}",
  "topic_title": "{topic.title}",
  "dialogue": [{{"speaker": "raj" or "priya", "text": "..."}}]
}}"""

        try:
            response = self.model.generate_content(prompt)
            data = self._parse_response(response.text)

            dialogue = [
                DialogueLine(speaker=line["speaker"], text=line["text"])
                for line in data.get("dialogue", [])
            ]

            return PodcastSegment(
                topic_id=data.get("topic_id", topic.id),
                topic_title=data.get("topic_title", topic.title),
                duration_estimate=len(dialogue) * 15,
                dialogue=dialogue,
            )

        except Exception as e:
            logger.error(f"Segment regeneration failed: {e}")
            return PodcastSegment(
                topic_id=topic.id,
                topic_title=topic.title,
                duration_estimate=120,
                dialogue=[
                    DialogueLine(speaker="raj", text=f"Let's discuss {topic.title}."),
                    DialogueLine(speaker="priya", text="This is an important topic for our community."),
                ],
            )
