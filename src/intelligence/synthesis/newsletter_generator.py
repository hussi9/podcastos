"""Newsletter generator - converts research into written newsletter format."""

import os
from datetime import datetime
from typing import Optional
import logging

from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from ..models.research import VerifiedTopic, EpisodeResearchBundle


logger = logging.getLogger(__name__)


class NewsletterSection(BaseModel):
    """A single section of a newsletter."""

    id: str
    topic_id: str
    sequence: int = 0

    # Content
    headline: str
    subheadline: Optional[str] = None
    body: str  # Main content in markdown
    key_takeaway: Optional[str] = None

    # Metadata
    word_count: int = 0
    sources: list[str] = Field(default_factory=list)


class Newsletter(BaseModel):
    """Complete newsletter issue."""

    id: str
    profile_id: int
    issue_date: datetime

    # Newsletter metadata
    title: str
    subtitle: str
    preview_text: str  # Email preview

    # Content
    intro: str
    sections: list[NewsletterSection] = Field(default_factory=list)
    outro: str

    # Formatting
    html_content: Optional[str] = None
    markdown_content: Optional[str] = None
    plain_text: Optional[str] = None

    # Stats
    total_word_count: int = 0
    reading_time_minutes: int = 0

    generated_at: datetime = Field(default_factory=datetime.now)

    def calculate_stats(self):
        """Calculate newsletter stats."""
        words = len(self.intro.split()) + len(self.outro.split())
        for section in self.sections:
            words += len(section.body.split())
            section.word_count = len(section.body.split())

        self.total_word_count = words
        self.reading_time_minutes = max(1, words // 200)  # ~200 wpm reading


class NewsletterGenerator:
    """
    Generates written newsletters from researched topics.
    Complements the podcast script generator - same research, different format.
    """

    SECTION_PROMPT = """Write a deep-dive newsletter section about this topic.
    
    CONTEXT:
    Newsletter Name: {newsletter_name}
    Target Audience: {audience}
    Tone: {tone}
    
    TOPIC: {headline}
    SUMMARY: {summary}
    
    KEY FACTS FROM RESEARCH:
    {facts}
    
    EXPERT OPINIONS:
    {opinions}
    
    INSTRUCTIONS:
    Write a compelling, journalistic narrative about this topic. Do NOT just list facts. weave them into a story.
    
    STRUCTURE:
    1. The Hook: Start with why this matters NOW.
    2. The Analysis: Explain the "what" and the "why". Use the facts to support your analysis.
    3. The Expert View: Integrate the expert opinions naturally (e.g., "As TechCrunch notes...", "Experts suggest...").
    4. The Takeaway: Conclude with what the reader should do or think about this.
    
    STYLE GUIDELINES:
    - Write like a top-tier Substack writer (e.g., Ben Thompson, Casey Newton).
    - Be opinionated but grounded in facts.
    - Use short, punchy paragraphs.
    - Use bolding for emphasis, but don't overdo it.
    - NO generic transitions ("Let's dive in", "In conclusion").
    - If facts are missing, acknowledge the uncertainty rather than making things up.
    
    Length: ~{words} words.
    Format: Markdown. No H1/H2 headers (this is a section). Use ### for sub-points if needed.
    """
    
    INTRO_PROMPT = """Write a shorter, punchier Editor's Note for this newsletter.
    
    CONTEXT:
    Newsletter: {title}
    Date: {date}
    Theme: {theme}
    Audience: {audience}
    Tone: {tone}
    
    TOPICS IN THIS ISSUE:
    {topics_preview}
    
    INSTRUCTIONS:
    Write a personal, "Letter from the Editor" style intro.
    - Connect the themes if possible.
    - If there's a major headline, lead with that.
    - Be warm, welcoming, but get to the point.
    - ~100 words max.
    """
    
    OUTRO_PROMPT = """Write a brief sign-off.
    
    Newsletter: {title}
    Tone: {tone}
    
    INSTRUCTIONS:
    - Thank the reader.
    - Encourage them to listen to the podcast version for more depth.
    - Ask a thought-provoking question related to the topics.
    - ~50 words.
    """

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def generate_newsletter(
        self,
        bundle: EpisodeResearchBundle,
        newsletter_name: str = "Your Newsletter",
        audience: str = "General Audience",
        tone: str = "Professional and engaging",
    ) -> Newsletter:
        """Generate a complete newsletter from research bundle."""

        # Generate intro
        intro = await self._generate_intro(bundle, newsletter_name, audience, tone)

        # Generate sections
        sections = []
        for i, topic in enumerate(bundle.verified_topics):
            section = await self._generate_section(topic, i, newsletter_name, audience, tone)
            sections.append(section)

        # Generate outro
        outro = await self._generate_outro(bundle, newsletter_name, tone)

        # Create newsletter
        newsletter = Newsletter(
            id=f"newsletter-{bundle.id}",
            profile_id=bundle.profile_id,
            issue_date=bundle.episode_date,
            title=f"{newsletter_name}: {bundle.main_theme or 'This Week'}",
            subtitle=bundle.main_theme or "Your Weekly Update",
            preview_text=self._create_preview(sections),
            intro=intro,
            sections=sections,
            outro=outro,
        )

        newsletter.calculate_stats()

        # Generate formatted versions
        newsletter.markdown_content = self._to_markdown(newsletter)
        newsletter.html_content = self._to_html(newsletter)
        newsletter.plain_text = self._to_plain_text(newsletter)

        logger.info(
            f"Generated newsletter with {len(sections)} sections, "
            f"{newsletter.total_word_count} words, ~{newsletter.reading_time_minutes} min read"
        )

        return newsletter

    async def _generate_section(
        self,
        topic: VerifiedTopic,
        sequence: int,
        newsletter_name: str,
        audience: str,
        tone: str,
    ) -> NewsletterSection:
        """Generate a single newsletter section."""
        research = topic.researched_topic

        # Format facts
        facts = "\n".join([
            f"- {fact.claim} (Source: {fact.source_url})"
            for fact in research.verified_facts[:8] 
        ]) or "No specific facts available"

        # Format opinions
        opinions = "\n".join([
            f"- {op.expert_name}: \"{op.quote}\""
            for op in research.expert_opinions[:5]
        ]) or "None available"

        # Target ~150 words per section
        target_words = 250

        prompt = self.SECTION_PROMPT.format(
            newsletter_name=newsletter_name,
            audience=audience,
            tone=tone,
            headline=topic.final_headline,
            summary=topic.final_summary,
            facts=facts,
            opinions=opinions,
            words=target_words,
        )

        body = await self._generate(prompt)

        # Collect sources
        sources = [f.source_url for f in research.verified_facts if f.source_url]

        return NewsletterSection(
            id=f"section-{topic.id}",
            topic_id=topic.id,
            sequence=sequence,
            headline=topic.final_headline,
            body=body,
            sources=list(set(sources))[:3],
        )

    async def _generate_intro(
        self,
        bundle: EpisodeResearchBundle,
        newsletter_name: str,
        audience: str,
        tone: str,
    ) -> str:
        """Generate newsletter intro."""
        topics_preview = "\n".join([
            f"- {t.final_headline}"
            for t in bundle.verified_topics[:5]
        ])

        prompt = self.INTRO_PROMPT.format(
            title=newsletter_name,
            date=bundle.episode_date.strftime("%B %d, %Y"),
            theme=bundle.main_theme or "This Week's Top Stories",
            audience=audience,
            tone=tone,
            topics_preview=topics_preview,
        )

        return await self._generate(prompt)

    async def _generate_outro(
        self,
        bundle: EpisodeResearchBundle,
        newsletter_name: str,
        tone: str,
    ) -> str:
        """Generate newsletter outro."""
        topics_summary = ", ".join([
            t.final_headline[:40]
            for t in bundle.verified_topics[:3]
        ])

        prompt = self.OUTRO_PROMPT.format(
            title=newsletter_name,
            topics_summary=topics_summary,
            tone=tone,
        )

        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> str:
        """Generate content from Gemini."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=800,
            ),
        )
        return response.text.strip()

    def _create_preview(self, sections: list[NewsletterSection]) -> str:
        """Create email preview text."""
        if sections:
            return f"{sections[0].headline}: {sections[0].body[:100]}..."
        return "Your weekly update is here"

    def _to_markdown(self, newsletter: Newsletter) -> str:
        """Convert newsletter to markdown."""
        lines = [
            f"# {newsletter.title}",
            f"*{newsletter.subtitle}*",
            "",
            newsletter.intro,
            "",
            "---",
            "",
        ]

        for section in newsletter.sections:
            lines.extend([
                f"## {section.headline}",
                "",
                section.body,
                "",
            ])
            if section.sources:
                lines.append(f"*Sources: {', '.join(section.sources[:2])}*")
            lines.extend(["", "---", ""])

        lines.extend([
            newsletter.outro,
            "",
            f"---",
            f"*{newsletter.reading_time_minutes} min read · {newsletter.total_word_count} words*",
        ])

        return "\n".join(lines)

    def _to_html(self, newsletter: Newsletter) -> str:
        """Convert newsletter to HTML email."""
        # Simple HTML template
        sections_html = ""
        for section in newsletter.sections:
            sections_html += f"""
            <div style="margin-bottom: 30px;">
                <h2 style="color: #1a1a2e; font-size: 20px; margin-bottom: 10px;">{section.headline}</h2>
                <div style="color: #333; line-height: 1.6;">{self._md_to_html(section.body)}</div>
            </div>
            <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9;">
    <div style="background: white; padding: 30px; border-radius: 10px;">
        <h1 style="color: #1a1a2e; font-size: 28px; margin-bottom: 5px;">{newsletter.title}</h1>
        <p style="color: #666; font-size: 16px; margin-bottom: 20px;">{newsletter.subtitle}</p>

        <div style="color: #333; line-height: 1.6; margin-bottom: 25px;">
            {self._md_to_html(newsletter.intro)}
        </div>

        <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">

        {sections_html}

        <div style="color: #333; line-height: 1.6;">
            {self._md_to_html(newsletter.outro)}
        </div>

        <p style="color: #999; font-size: 12px; margin-top: 30px; text-align: center;">
            {newsletter.reading_time_minutes} min read · {newsletter.total_word_count} words
        </p>
    </div>
</body>
</html>
"""

    def _md_to_html(self, md: str) -> str:
        """Simple markdown to HTML conversion."""
        import re
        html = md
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        # Bullet points
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html)
        # Paragraphs
        html = re.sub(r'\n\n', '</p><p>', html)
        html = f'<p>{html}</p>'
        return html

    def _to_plain_text(self, newsletter: Newsletter) -> str:
        """Convert newsletter to plain text."""
        import re

        lines = [
            newsletter.title.upper(),
            newsletter.subtitle,
            "=" * 50,
            "",
            newsletter.intro,
            "",
            "-" * 50,
            "",
        ]

        for section in newsletter.sections:
            # Remove markdown formatting
            body = re.sub(r'\*\*(.+?)\*\*', r'\1', section.body)
            body = re.sub(r'\*(.+?)\*', r'\1', body)

            lines.extend([
                section.headline.upper(),
                "",
                body,
                "",
                "-" * 50,
                "",
            ])

        lines.extend([
            newsletter.outro,
            "",
            f"Reading time: {newsletter.reading_time_minutes} min",
        ])

        return "\n".join(lines)
