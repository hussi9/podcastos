"""Script generator using Gemini for podcast script synthesis."""

import os
from datetime import datetime
from typing import Optional
import logging

from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from ..models.research import VerifiedTopic, EpisodeResearchBundle


logger = logging.getLogger(__name__)


class ScriptSegment(BaseModel):
    """A single segment of a podcast script."""

    id: str
    topic_id: str
    sequence: int = 0

    # Content
    title: str
    host_script: str = Field(..., description="Main host speaking content")
    co_host_script: Optional[str] = None  # For dialogue format

    # Metadata
    tone: str = "informative"
    estimated_duration_seconds: int = 120

    # Sources for transparency
    sources: list[str] = Field(default_factory=list)

    # Audio generation ready
    ssml_script: Optional[str] = None  # SSML formatted for TTS


class PodcastScript(BaseModel):
    """Complete podcast episode script."""

    id: str
    profile_id: int
    episode_date: datetime

    # Episode metadata
    title: str
    description: str
    main_theme: str

    # Segments
    intro: ScriptSegment
    segments: list[ScriptSegment] = Field(default_factory=list)
    outro: ScriptSegment

    # Totals
    total_duration_seconds: int = 0
    word_count: int = 0

    # Generation metadata
    generated_at: datetime = Field(default_factory=datetime.now)

    def calculate_totals(self):
        """Calculate total duration and word count."""
        all_segments = [self.intro] + self.segments + [self.outro]

        self.total_duration_seconds = sum(s.estimated_duration_seconds for s in all_segments)

        total_words = 0
        for seg in all_segments:
            total_words += len(seg.host_script.split())
            if seg.co_host_script:
                total_words += len(seg.co_host_script.split())
        self.word_count = total_words


class ScriptGenerator:
    """
    Generates podcast scripts from researched topics.
    Uses Gemini for natural, conversational script generation.
    """

    SEGMENT_PROMPT = """You are writing a podcast script that sounds EXACTLY like a real human host talking naturally.

Topic: {headline}
Summary: {summary}
Tone: {tone}

Key facts:
{facts}

Expert opinions:
{opinions}

Counter-arguments:
{counter_args}

CRITICAL REQUIREMENTS FOR HUMAN-LIKE DELIVERY:

1. **Sound like a REAL PERSON talking** - not reading. Use contractions (I'm, you're, that's, it's, don't, won't).
2. **Natural speech patterns** - Include occasional "you know", "I mean", "honestly", "look", "here's the thing"
3. **Show genuine emotion** - React to the news! "This is actually pretty wild...", "I have to say, this surprised me..."
4. **Rhetorical questions** - "But wait, what does this actually mean for us?", "Sound familiar?"
5. **Varied pacing** - Short punchy sentences. Then longer, more flowing ones that build the narrative.
6. **Personal perspective** - "The way I see it...", "What strikes me here is..."
7. **Acknowledge complexity** - "Now, it's not all black and white here...", "There's nuance to this..."
8. **Natural transitions** - "Okay, so here's where it gets interesting...", "But here's the kicker..."
9. **Conversational asides** - "(and trust me, I had to read that twice)", "(which, by the way, is kind of a big deal)"

LENGTH: ~{words} words ({duration} seconds when spoken naturally)

Write the script as if you're a knowledgeable friend explaining this over coffee. NO stage directions. NO "[Host Name]". Just pure, natural speech.

Start directly with engaging content - no "Welcome back" or segment announcements."""

    INTRO_PROMPT = """Write a podcast intro that sounds like a REAL HUMAN host - warm, natural, and genuine.

Show: {title}
Date: {date}
Today's Theme: {theme}

Stories coming up:
{topics_preview}

REQUIREMENTS:
- Sound like you're greeting a friend, not reading a script
- Be genuinely excited but not fake or over-the-top
- Tease the stories naturally - make people curious
- Use contractions and natural speech
- About 60-80 words

NO stage directions. NO "[Host Name]". NO cheesy radio voice. Just be real.

Example tone: "Hey, so glad you're here. We've got some really interesting stuff today..."

Start directly - no "Welcome to [show name]" formulas."""

    OUTRO_PROMPT = """Write a natural, human podcast outro. You just finished discussing: {topics_summary}

Show: {title}

REQUIREMENTS:
- Sound like a real person wrapping up a conversation
- Quick, genuine recap of why this mattered
- Thank listeners naturally (not formally)
- Simple call to action - don't be pushy
- About 40-60 words

NO stage directions. NO fake enthusiasm. Be real and warm.

Example tone: "Alright, that's what I've got for you today. If any of this was useful..."

Start directly with the wrap-up."""

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
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

    async def generate_script(
        self,
        bundle: EpisodeResearchBundle,
        podcast_name: str = "Your Daily Podcast",
    ) -> PodcastScript:
        """
        Generate a complete podcast script from research bundle.
        """
        # Generate intro
        intro = await self._generate_intro(bundle, podcast_name)

        # Generate segments for each topic
        segments = []
        for i, topic in enumerate(bundle.verified_topics):
            segment = await self._generate_segment(topic, i)
            segments.append(segment)

        # Generate outro
        outro = await self._generate_outro(bundle, podcast_name)

        # Create script
        script = PodcastScript(
            id=f"script-{bundle.id}",
            profile_id=bundle.profile_id,
            episode_date=bundle.episode_date,
            title=f"{podcast_name}: {bundle.main_theme or 'Todays Episode'}",
            description=bundle.episode_summary or "",
            main_theme=bundle.main_theme or "Todays Stories",
            intro=intro,
            segments=segments,
            outro=outro,
        )

        script.calculate_totals()

        logger.info(
            f"Generated script with {len(segments)} segments, "
            f"{script.word_count} words, ~{script.total_duration_seconds // 60} min"
        )

        return script

    async def _generate_segment(
        self,
        topic: VerifiedTopic,
        sequence: int,
    ) -> ScriptSegment:
        """Generate script for a single topic segment."""
        research = topic.researched_topic

        # Format facts
        facts = "\n".join([
            f"- {fact.claim} (Source: {fact.source_name})"
            for fact in research.verified_facts[:5]
        ])

        # Format opinions
        opinions = "\n".join([
            f"- {op.expert_name}: \"{op.quote[:150]}...\""
            for op in research.expert_opinions[:3]
        ]) or "None available"

        # Format counter-arguments
        counter_args = "\n".join([
            f"- {ca.argument[:150]} (Source: {ca.source_name})"
            for ca in research.counter_arguments[:2]
        ]) or "None"

        # Estimate word count from duration
        target_duration = topic.suggested_duration_seconds
        target_words = target_duration * 2.5  # ~150 words per minute

        prompt = self.SEGMENT_PROMPT.format(
            headline=topic.final_headline,
            summary=topic.final_summary,
            tone=topic.suggested_tone,
            facts=facts,
            opinions=opinions,
            counter_args=counter_args,
            duration=target_duration,
            words=int(target_words),
        )

        script_text = await self._generate(prompt)

        # Collect sources
        sources = [f.source_url for f in research.verified_facts if f.source_url]
        sources.extend([o.source_url for o in research.expert_opinions])

        return ScriptSegment(
            id=f"segment-{topic.id}",
            topic_id=topic.id,
            sequence=sequence,
            title=topic.final_headline,
            host_script=script_text,
            tone=topic.suggested_tone,
            estimated_duration_seconds=target_duration,
            sources=list(set(sources))[:5],  # Dedupe, limit to 5
        )

    async def _generate_intro(
        self,
        bundle: EpisodeResearchBundle,
        podcast_name: str,
    ) -> ScriptSegment:
        """Generate episode intro."""
        topics_preview = "\n".join([
            f"- {t.final_headline}"
            for t in bundle.verified_topics[:4]
        ])

        prompt = self.INTRO_PROMPT.format(
            title=podcast_name,
            date=bundle.episode_date.strftime("%B %d, %Y"),
            theme=bundle.main_theme or "Today's Top Stories",
            topics_preview=topics_preview,
        )

        script_text = await self._generate(prompt)

        return ScriptSegment(
            id=f"intro-{bundle.id}",
            topic_id="intro",
            sequence=-1,
            title="Introduction",
            host_script=script_text,
            tone="welcoming",
            estimated_duration_seconds=30,
        )

    async def _generate_outro(
        self,
        bundle: EpisodeResearchBundle,
        podcast_name: str,
    ) -> ScriptSegment:
        """Generate episode outro."""
        topics_summary = ", ".join([
            t.final_headline[:50]
            for t in bundle.verified_topics[:3]
        ])

        prompt = self.OUTRO_PROMPT.format(
            title=podcast_name,
            topics_summary=topics_summary,
        )

        script_text = await self._generate(prompt)

        return ScriptSegment(
            id=f"outro-{bundle.id}",
            topic_id="outro",
            sequence=999,
            title="Closing",
            host_script=script_text,
            tone="friendly",
            estimated_duration_seconds=20,
        )

    async def _generate(self, prompt: str) -> str:
        """Generate content from Gemini."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.85,  # Higher for more natural, varied speech
                max_output_tokens=1200,
            ),
        )
        return response.text.strip()

    def convert_to_ssml(self, segment: ScriptSegment) -> str:
        """
        Convert script to SSML for better TTS rendering.
        """
        text = segment.host_script

        # Wrap in speak tags
        ssml = ['<speak>']

        # Split into sentences for natural pauses
        sentences = text.replace('...', '<break time="500ms"/>').split('. ')

        for sentence in sentences:
            if sentence.strip():
                # Add emphasis to key phrases
                sentence = self._add_emphasis(sentence)
                ssml.append(f'<s>{sentence.strip()}.</s>')

        ssml.append('</speak>')

        segment.ssml_script = '\n'.join(ssml)
        return segment.ssml_script

    def _add_emphasis(self, text: str) -> str:
        """Add SSML emphasis to important phrases."""
        import re

        # Emphasize quoted text
        text = re.sub(
            r'"([^"]+)"',
            r'<emphasis level="moderate">"\1"</emphasis>',
            text
        )

        # Emphasize numbers/statistics
        text = re.sub(
            r'(\d+(?:\.\d+)?%)',
            r'<emphasis level="strong">\1</emphasis>',
            text
        )

        return text
