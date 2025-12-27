"""
Enhanced AI-powered podcast script generator with deep research integration.
Creates natural, fact-rich conversations.
"""

from datetime import datetime
from typing import Optional
import google.generativeai as genai
from pydantic import BaseModel
import logging
import json
import re

from ..research.topic_researcher import TopicResearch

logger = logging.getLogger(__name__)


class DialogueLine(BaseModel):
    """A single line of dialogue in the podcast"""
    speaker: str  # "raj" or "priya"
    text: str
    emotion: Optional[str] = None


class PodcastSegment(BaseModel):
    """A segment of the podcast covering one topic"""
    topic_id: str
    topic_title: str
    duration_estimate: int
    dialogue: list[DialogueLine]


class PodcastScript(BaseModel):
    """Complete podcast script"""
    episode_id: str
    episode_title: str
    episode_date: str
    duration_estimate: int
    intro: list[DialogueLine]
    segments: list[PodcastSegment]
    outro: list[DialogueLine]

    def to_ssml_blocks(self) -> list[dict]:
        """Convert script to blocks for TTS processing"""
        blocks = []
        for line in self.intro:
            blocks.append({"speaker": line.speaker, "text": line.text, "section": "intro"})
        for segment in self.segments:
            for line in segment.dialogue:
                blocks.append({"speaker": line.speaker, "text": line.text, "section": segment.topic_id})
        for line in self.outro:
            blocks.append({"speaker": line.speaker, "text": line.text, "section": "outro"})
        return blocks


class EnhancedScriptGenerator:
    """
    Generates natural, fact-rich podcast scripts using deep research.
    """

    SYSTEM_PROMPT = '''You are writing a podcast script for "{podcast_name}" - a news podcast.
Write like TWO INTELLIGENT FRIENDS having a genuine, thoughtful conversation about news that affects their community.

THE HOSTS:
- RAJ (he/him): Immigrated 12 years ago on H-1B, now green card holder. Works in tech at a FAANG company.
  He's been through the immigration system and knows it intimately. He provides facts, analysis, and practical advice.
  He can get genuinely frustrated with systemic issues. Analytical but warm.

- PRIYA (she/her): Second-generation, parents came in the 80s. Community organizer, very empathetic.
  She brings human stories, emotional perspective, and asks probing questions. Sometimes plays devil's advocate.
  Optimistic but realistic. Good at connecting issues to broader community impact.

CONVERSATION STYLE - CRITICAL:
1. NATURAL FLOW - Real back-and-forth, not alternating monologues
2. SPECIFIC FACTS - "Processing time went from 6 to 18 months" NOT "times increased"
3. REAL REFERENCES - Actual policy names, specific dates, real numbers
4. GENUINE REACTIONS - Surprise, frustration, hope, concern
5. THOUGHTFUL DISAGREEMENT - "I see it differently because..."
6. PERSONAL CONNECTION - "When I went through this..." or "A friend of mine..."
7. NATURAL INTERRUPTIONS - "Wait, hold on—" or "Sorry to cut you off but—"
8. EMOTIONAL DEPTH - Show real feeling, not just information delivery

IMPORTANT - DO NOT:
- Use forced cultural slang like "yaar", "na?", "accha" repeatedly
- Make every sentence a question
- Use generic filler phrases
- Sound like reading a script

DO:
- Sound like two smart friends who genuinely care about these issues
- Show real emotions: frustration, hope, surprise, empathy
- Use natural pauses and moments of reflection
- Reference specific numbers, dates, and expert names
- Connect topics to real human impact

EMOTIONAL MOMENTS TO INCLUDE:
- Genuine frustration: "This is what's so frustrating about this whole system..."
- Empathy: "I can only imagine how stressful that must be for people waiting..."
- Hope: "But here's the thing that gives me some hope..."
- Concern: "What really worries me about this is..."
- Surprise: "Wait, seriously?" or "I had no idea it was that bad"
- Validation: "That's exactly what I was thinking"

GOOD DIALOGUE EXAMPLE:
RAJ: "I saw the latest USCIS data and honestly, it's worse than I thought."
PRIYA: "How bad are we talking?"
RAJ: "Premium processing—which people pay almost three thousand dollars for—is now taking 45 days on average. It's supposed to be 15."
PRIYA: "That's... that's triple the time. And they're not adjusting the fee?"
RAJ: "Not a cent. And the thing that really gets me is there's no recourse. Immigration lawyers are saying you just have to wait."
PRIYA: "So people are paying premium prices for standard service. That feels almost predatory."
RAJ: "It does. And the human cost—people missing job start dates, families in limbo..."

{continuity_context}

OUTPUT FORMAT:
Return ONLY valid JSON:
{{
  "intro": [{{"speaker": "raj", "text": "..."}}, {{"speaker": "priya", "text": "..."}}],
  "segments": [
    {{
      "topic_id": "topic_1",
      "topic_title": "Actual Topic Title",
      "dialogue": [{{"speaker": "raj", "text": "..."}}, {{"speaker": "priya", "text": "..."}}]
    }}
  ],
  "outro": [{{"speaker": "raj", "text": "..."}}, {{"speaker": "priya", "text": "..."}}]
}}

Speaker must be lowercase "raj" or "priya". Make each segment 8-12 dialogue exchanges for depth.'''

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name

    async def generate_script(
        self,
        researched_topics: list[TopicResearch],
        episode_date: Optional[datetime] = None,
        target_duration_minutes: int = 15,
        continuity_context: str = "",
        podcast_name: str = "Desi Daily",
    ) -> PodcastScript:
        """Generate a podcast script from deeply researched topics"""

        if not episode_date:
            episode_date = datetime.now()

        date_str = episode_date.strftime("%B %d, %Y")
        day_of_week = episode_date.strftime("%A")

        # Build rich prompt with all research
        research_content = self._format_research_for_prompt(researched_topics)

        # Format system prompt with continuity context and podcast name
        system_prompt = self.SYSTEM_PROMPT.format(
            podcast_name=podcast_name,
            continuity_context=continuity_context if continuity_context else ""
        )

        prompt = f'''{system_prompt}

---

Generate a podcast script for {podcast_name} - {day_of_week}, {date_str}

Target duration: {target_duration_minutes} minutes (longer, more in-depth segments)
Number of topics: {len(researched_topics)}

DEEPLY RESEARCHED TOPICS WITH FACTS:
{research_content}

INSTRUCTIONS:
1. Start with a natural, warm intro - not "welcome to our show" style
2. For EACH topic, create a deep 8-12 exchange conversation using the specific facts provided
3. Include the statistics, expert quotes, and historical context in natural dialogue
4. Have Raj and Priya sometimes disagree or challenge each other
5. End each segment with practical advice
6. Transition naturally between topics
7. End with a conversational outro

Use ALL the facts, numbers, and expert opinions provided. Don't be vague - be specific!

Return ONLY the JSON, no markdown code blocks.'''

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.9,  # Higher for more natural variation
                    top_p=0.95,
                    max_output_tokens=12000,  # More tokens for longer content
                ),
            )

            logger.info(f"Raw response length: {len(response.text)} chars")
            script_data = self._parse_response(response.text)

            # Build script object
            episode_id = f"dd-{episode_date.strftime('%Y%m%d')}"
            episode_title = self._generate_episode_title(researched_topics, episode_date, podcast_name)

            intro_lines = [
                DialogueLine(speaker=line["speaker"].lower(), text=line["text"])
                for line in script_data.get("intro", [])
            ]

            segments = []
            for seg_data in script_data.get("segments", []):
                dialogue = [
                    DialogueLine(speaker=line["speaker"].lower(), text=line["text"])
                    for line in seg_data.get("dialogue", [])
                ]
                segment = PodcastSegment(
                    topic_id=seg_data.get("topic_id", "unknown"),
                    topic_title=seg_data.get("topic_title", "Discussion"),
                    duration_estimate=len(dialogue) * 12,  # ~12 sec per exchange
                    dialogue=dialogue,
                )
                segments.append(segment)

            outro_lines = [
                DialogueLine(speaker=line["speaker"].lower(), text=line["text"])
                for line in script_data.get("outro", [])
            ]

            # Calculate duration
            total_words = sum(len(line.text.split()) for line in intro_lines + outro_lines)
            for seg in segments:
                total_words += sum(len(line.text.split()) for line in seg.dialogue)
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

            logger.info(f"Generated script: {episode_title}, ~{int(duration_estimate/60)} minutes, {len(segments)} segments")
            return script

        except Exception as e:
            logger.error(f"Script generation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _format_research_for_prompt(self, researched_topics: list[TopicResearch]) -> str:
        """Format all research into a rich prompt"""
        sections = []

        for i, research in enumerate(researched_topics, 1):
            lines = [f"\n{'='*60}"]
            lines.append(f"TOPIC {i}: {research.topic_title}")
            lines.append(f"{'='*60}")

            # Key facts with sources
            if research.key_facts:
                lines.append("\n📊 KEY FACTS (use these specific numbers!):")
                for fact in research.key_facts:
                    source = f" (Source: {fact.source})" if fact.source else ""
                    lines.append(f"  • {fact.fact}{source}")

            # Statistics
            if research.statistics:
                lines.append("\n📈 STATISTICS:")
                for stat in research.statistics:
                    lines.append(f"  • {stat}")

            # Historical context
            if research.historical_context:
                lines.append(f"\n📜 HISTORICAL CONTEXT:\n{research.historical_context}")

            # Current situation
            if research.current_situation:
                lines.append(f"\n🔥 CURRENT SITUATION:\n{research.current_situation}")

            # Future implications
            if research.future_implications:
                lines.append(f"\n🔮 FUTURE IMPLICATIONS:\n{research.future_implications}")

            # Expert opinions
            if research.expert_opinions:
                lines.append("\n👤 EXPERT OPINIONS (quote these!):")
                for opinion in research.expert_opinions:
                    lines.append(f'  • {opinion.person} ({opinion.role}): "{opinion.quote}"')

            # Community reactions
            if research.community_reactions:
                lines.append("\n💬 COMMUNITY REACTIONS:")
                for reaction in research.community_reactions:
                    lines.append(f"  • {reaction}")

            # Common misconceptions
            if research.common_misconceptions:
                lines.append("\n❌ COMMON MISCONCEPTIONS (address these!):")
                for misconception in research.common_misconceptions:
                    lines.append(f"  • {misconception}")

            # Practical advice
            if research.practical_advice:
                lines.append("\n✅ PRACTICAL ADVICE (share with listeners!):")
                for advice in research.practical_advice:
                    lines.append(f"  • {advice}")

            # Related stories
            if research.related_stories:
                lines.append("\n📖 RELATED STORIES/EXAMPLES:")
                for story in research.related_stories:
                    lines.append(f"  • {story}")

            # Debate points
            if research.arguments_for or research.arguments_against:
                lines.append("\n⚖️ DEBATE POINTS:")
                if research.arguments_for:
                    lines.append("  FOR:")
                    for arg in research.arguments_for:
                        lines.append(f"    • {arg}")
                if research.arguments_against:
                    lines.append("  AGAINST:")
                    for arg in research.arguments_against:
                        lines.append(f"    • {arg}")

            # Nuanced take
            if research.nuanced_take:
                lines.append(f"\n🎯 NUANCED PERSPECTIVE:\n{research.nuanced_take}")

            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    def _parse_response(self, response_text: str) -> dict:
        """Parse Gemini response"""
        text = response_text.strip()

        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning("Secondary JSON parse also failed")
            logger.error("Failed to parse script response")
            return {"intro": [], "segments": [], "outro": []}

    def _generate_episode_title(self, researched_topics: list[TopicResearch], episode_date: datetime, podcast_name: str = "Podcast") -> str:
        """Generate episode title from top topic"""
        date_str = episode_date.strftime("%b %d")
        if researched_topics:
            main_topic = researched_topics[0].topic_title
            # Shorten if too long
            if len(main_topic) > 40:
                main_topic = main_topic[:37] + "..."
            return f"{main_topic} | {podcast_name} - {date_str}"
        return f"Daily Update | {podcast_name} - {date_str}"
