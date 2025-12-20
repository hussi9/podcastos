"""
Unified Content Engine - Generate Newsletter + Podcast from same research.

This is the core engine that powers the product:
1. User provides topic OR their own content
2. We research and enhance it
3. Output: Newsletter (email) + Podcast (audio)
4. Auto-distribute to email list + Spotify
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, Union
from pathlib import Path
import logging
import json

from pydantic import BaseModel, Field

from ..models.content import RawContent, TopicCluster
from ..models.research import EpisodeResearchBundle, VerifiedTopic
from ..clustering.clusterer import SemanticClusterer
from ..clustering.topic_namer import TopicNamer
from ..research.google_researcher import GoogleResearcher, ResearchDepth
from ..research.topic_verifier import TopicVerifier
from .script_generator import ScriptGenerator, PodcastScript
from .newsletter_generator import NewsletterGenerator, Newsletter
from ..audio.tts_generator import TTSGenerator, AudioEpisode
from ..audio.audio_stitcher import AudioStitcher


logger = logging.getLogger(__name__)


class ContentInput(BaseModel):
    """Input for content generation."""

    # Option 1: Topic to research
    topic: Optional[str] = None

    # Option 2: User's own content to enhance
    user_content: Optional[str] = None
    user_content_title: Optional[str] = None
    user_content_url: Optional[str] = None

    # Brand settings
    brand_name: str = "Your Brand"
    brand_voice: str = "professional but conversational"
    host_name: Optional[str] = None

    # Output preferences
    generate_newsletter: bool = True
    generate_podcast: bool = True

    # Target lengths
    newsletter_words: int = 800
    podcast_minutes: int = 6


class ContentOutput(BaseModel):
    """Output from content generation."""

    id: str
    generated_at: datetime = Field(default_factory=datetime.now)

    # Newsletter output
    newsletter: Optional[Newsletter] = None
    newsletter_html_path: Optional[str] = None
    newsletter_markdown_path: Optional[str] = None

    # Podcast output
    podcast_script: Optional[PodcastScript] = None
    podcast_audio: Optional[AudioEpisode] = None
    podcast_audio_path: Optional[str] = None
    podcast_rss_entry: Optional[dict] = None

    # Metadata
    topic: str = ""
    word_count: int = 0
    audio_duration_seconds: float = 0

    success: bool = True
    errors: list[str] = Field(default_factory=list)


class ContentEngine:
    """
    The unified content generation engine.

    Takes topic or user content → Outputs newsletter + podcast.
    """

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.researcher = GoogleResearcher()
        self.verifier = TopicVerifier()
        self.script_generator = ScriptGenerator()
        self.newsletter_generator = NewsletterGenerator()
        self.tts_generator = TTSGenerator(output_dir=str(self.output_dir))
        self.audio_stitcher = AudioStitcher(output_dir=str(self.output_dir))

    async def generate(self, input: ContentInput) -> ContentOutput:
        """
        Generate content from input.

        Workflow:
        1. Research the topic (or enhance user content)
        2. Generate newsletter
        3. Generate podcast script
        4. Generate audio
        5. Return all outputs
        """
        output_id = f"content-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        output = ContentOutput(id=output_id)

        try:
            # Step 1: Create or research content
            logger.info("Step 1: Researching content...")
            bundle = await self._research_content(input)
            output.topic = bundle.main_theme or input.topic or "Content Update"

            # Step 2: Generate newsletter (if requested)
            if input.generate_newsletter:
                logger.info("Step 2: Generating newsletter...")
                newsletter = await self.newsletter_generator.generate_newsletter(
                    bundle,
                    newsletter_name=input.brand_name,
                )
                output.newsletter = newsletter
                output.word_count = newsletter.total_word_count

                # Save newsletter files
                output.newsletter_html_path = await self._save_newsletter(
                    newsletter, output_id, "html"
                )
                output.newsletter_markdown_path = await self._save_newsletter(
                    newsletter, output_id, "md"
                )

            # Step 3: Generate podcast script (if requested)
            if input.generate_podcast:
                logger.info("Step 3: Generating podcast script...")
                script = await self.script_generator.generate_script(
                    bundle,
                    podcast_name=input.brand_name,
                )
                output.podcast_script = script

                # Step 4: Generate audio
                logger.info("Step 4: Generating audio...")
                audio_episode = await self.tts_generator.generate_episode_audio(script)

                # Stitch audio
                audio_path = self.audio_stitcher.stitch_episode(audio_episode)
                manifest_path = self.audio_stitcher.save_manifest(audio_episode)

                output.podcast_audio = audio_episode
                output.podcast_audio_path = audio_path
                output.audio_duration_seconds = audio_episode.total_duration_seconds

                # Generate RSS entry for Spotify
                output.podcast_rss_entry = self._generate_rss_entry(
                    script, audio_path, input.brand_name
                )

            logger.info(f"Content generation complete: {output_id}")
            return output

        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            output.success = False
            output.errors.append(str(e))
            return output

    async def _research_content(self, input: ContentInput) -> EpisodeResearchBundle:
        """Research and create content bundle."""

        if input.user_content:
            # User provided their own content - enhance it with research
            return await self._enhance_user_content(input)
        else:
            # Research from scratch based on topic
            return await self._research_topic(input)

    async def _research_topic(self, input: ContentInput) -> EpisodeResearchBundle:
        """Research a topic from scratch."""
        topic = input.topic or "Today's News"

        # Create a pseudo-cluster for the topic
        cluster = TopicCluster(
            id=f"topic-{datetime.now().strftime('%H%M%S')}",
            name=topic,
            summary=f"Research on: {topic}",
            category="general",
            contents=[],
            priority_score=10.0,
        )

        # Research it
        researched = await self.researcher.research_topic(
            cluster, depth=ResearchDepth.STANDARD
        )

        # Verify and enhance
        verified = await self.verifier.verify_topic(researched)

        # Create bundle
        bundle = EpisodeResearchBundle(
            id=f"bundle-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            profile_id=1,
            episode_date=datetime.now(),
            main_theme=topic,
            verified_topics=[verified] if verified else [],
        )

        return bundle

    async def _enhance_user_content(self, input: ContentInput) -> EpisodeResearchBundle:
        """Take user's content and enhance with research."""
        from ..models.research import ResearchedTopic, VerifiedFact

        # Create a researched topic from user content
        researched = ResearchedTopic(
            id=f"user-content-{datetime.now().strftime('%H%M%S')}",
            cluster_id="user-provided",
            headline=input.user_content_title or "Your Content",
            summary=input.user_content[:500] if input.user_content else "",
            category="user-content",
            background=input.user_content or "",
            current_situation="",
            implications="",
            verified_facts=[],
            expert_opinions=[],
            research_depth="user-provided",
        )

        # Optionally enhance with additional research
        if input.topic:
            # Add context research
            additional = await self.researcher._quick_research(
                input.topic,
                input.user_content[:300] if input.user_content else "",
            )
            researched.current_situation = additional.get("summary", "")

        # Create verified topic
        verified = VerifiedTopic(
            id=f"verified-user-{datetime.now().strftime('%H%M%S')}",
            researched_topic=researched,
            editorial_score=10.0,
            final_headline=input.user_content_title or input.topic or "Your Update",
            final_summary=input.user_content[:300] if input.user_content else "",
            suggested_tone="conversational",
            suggested_duration_seconds=input.podcast_minutes * 60 // 3,
        )

        bundle = EpisodeResearchBundle(
            id=f"bundle-user-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            profile_id=1,
            episode_date=datetime.now(),
            main_theme=input.user_content_title or input.topic or "Your Update",
            verified_topics=[verified],
        )

        return bundle

    async def _save_newsletter(
        self, newsletter: Newsletter, output_id: str, format: str
    ) -> str:
        """Save newsletter to file."""
        filename = f"{output_id}_newsletter.{format}"
        filepath = self.output_dir / filename

        if format == "html":
            content = newsletter.html_content
        elif format == "md":
            content = newsletter.markdown_content
        else:
            content = newsletter.plain_text

        with open(filepath, "w") as f:
            f.write(content or "")

        return str(filepath)

    def _generate_rss_entry(
        self, script: PodcastScript, audio_path: str, brand_name: str
    ) -> dict:
        """Generate RSS entry for podcast distribution."""
        return {
            "title": script.title,
            "description": script.description,
            "pubDate": script.episode_date.isoformat(),
            "duration": script.total_duration_seconds,
            "audio_url": audio_path,  # Will be replaced with hosted URL
            "guid": script.id,
            "author": brand_name,
        }


class PodcastRSSGenerator:
    """
    Generate RSS feed for podcast distribution to Spotify/Apple.

    Users submit this RSS URL to Spotify for Podcasters, Apple Podcasts Connect, etc.
    """

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)

    def generate_feed(
        self,
        podcast_name: str,
        podcast_description: str,
        author: str,
        email: str,
        episodes: list[dict],
        base_url: str = "https://yoursite.com/podcasts",
        cover_image_url: Optional[str] = None,
    ) -> str:
        """Generate a complete RSS feed for podcast distribution."""

        items = ""
        for ep in episodes:
            items += f"""
        <item>
            <title>{ep['title']}</title>
            <description><![CDATA[{ep.get('description', '')}]]></description>
            <pubDate>{ep['pubDate']}</pubDate>
            <enclosure url="{base_url}/{ep['audio_url']}" length="0" type="audio/mpeg"/>
            <guid isPermaLink="false">{ep['guid']}</guid>
            <itunes:duration>{int(ep.get('duration', 0))}</itunes:duration>
            <itunes:author>{author}</itunes:author>
            <itunes:explicit>false</itunes:explicit>
        </item>"""

        feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
    xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
    xmlns:content="http://purl.org/rss/1.0/modules/content/"
    xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
        <title>{podcast_name}</title>
        <description><![CDATA[{podcast_description}]]></description>
        <link>{base_url}</link>
        <language>en-us</language>
        <copyright>© {datetime.now().year} {author}</copyright>
        <itunes:author>{author}</itunes:author>
        <itunes:owner>
            <itunes:name>{author}</itunes:name>
            <itunes:email>{email}</itunes:email>
        </itunes:owner>
        <itunes:image href="{cover_image_url or base_url + '/cover.jpg'}"/>
        <itunes:category text="Technology"/>
        <itunes:explicit>false</itunes:explicit>
        <atom:link href="{base_url}/feed.xml" rel="self" type="application/rss+xml"/>
        {items}
    </channel>
</rss>"""

        return feed

    def save_feed(self, feed_content: str, filename: str = "podcast_feed.xml") -> str:
        """Save RSS feed to file."""
        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            f.write(feed_content)
        return str(filepath)


# Convenience function for quick generation
async def generate_content(
    topic: str = None,
    user_content: str = None,
    brand_name: str = "Your Brand",
    output_dir: str = "./output",
) -> ContentOutput:
    """
    Quick content generation.

    Example:
        # From topic
        result = await generate_content(topic="AI trends 2025", brand_name="Tech Weekly")

        # From user content
        result = await generate_content(
            user_content="Your blog post content here...",
            brand_name="My Newsletter"
        )
    """
    engine = ContentEngine(output_dir)

    input = ContentInput(
        topic=topic,
        user_content=user_content,
        brand_name=brand_name,
    )

    return await engine.generate(input)
