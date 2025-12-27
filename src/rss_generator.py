"""
RSS feed generator for podcast distribution
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from jinja2 import Template
import logging

from .podcast_engine import EpisodeMetadata

logger = logging.getLogger(__name__)


RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
    xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
    xmlns:content="http://purl.org/rss/1.0/modules/content/"
    xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{{ podcast.title }}</title>
    <link>{{ podcast.website_url }}</link>
    <language>en-us</language>
    <copyright>{{ podcast.copyright }}</copyright>
    <itunes:author>{{ podcast.author }}</itunes:author>
    <description>{{ podcast.description }}</description>
    <itunes:summary>{{ podcast.description }}</itunes:summary>
    <itunes:owner>
      <itunes:name>{{ podcast.author }}</itunes:name>
      <itunes:email>{{ podcast.email }}</itunes:email>
    </itunes:owner>
    <itunes:image href="{{ podcast.image_url }}"/>
    <itunes:category text="{{ podcast.category }}">
      <itunes:category text="{{ podcast.subcategory }}"/>
    </itunes:category>
    <itunes:explicit>{{ podcast.explicit }}</itunes:explicit>
    <atom:link href="{{ podcast.feed_url }}" rel="self" type="application/rss+xml"/>
    {% for episode in episodes %}
    <item>
      <title>{{ episode.title }}</title>
      <itunes:title>{{ episode.title }}</itunes:title>
      <description><![CDATA[{{ episode.description }}]]></description>
      <itunes:summary>{{ episode.summary }}</itunes:summary>
      <enclosure url="{{ episode.audio_url }}" length="{{ episode.audio_size }}" type="audio/mpeg"/>
      <guid isPermaLink="false">{{ episode.guid }}</guid>
      <pubDate>{{ episode.pub_date }}</pubDate>
      <itunes:duration>{{ episode.duration }}</itunes:duration>
      <itunes:explicit>no</itunes:explicit>
      <itunes:episodeType>full</itunes:episodeType>
    </item>
    {% endfor %}
  </channel>
</rss>"""


class PodcastFeedConfig:
    """Configuration for the podcast feed"""

    def __init__(
        self,
        title: str = "Desi Daily",
        description: str = "Your daily dose of news and insights for the South Asian community in America",
        website_url: str = "https://desivibe.com/podcast",
        feed_url: str = "https://desivibe.com/podcast/feed.xml",
        author: str = "DesiVibe",
        email: str = "podcast@desivibe.com",
        image_url: str = "https://desivibe.com/podcast/cover.jpg",
        category: str = "News",
        subcategory: str = "Daily News",
        copyright: str = "2024 DesiVibe",
        explicit: str = "no",
        base_audio_url: str = "https://desivibe.com/podcast/episodes",
    ):
        self.title = title
        self.description = description
        self.website_url = website_url
        self.feed_url = feed_url
        self.author = author
        self.email = email
        self.image_url = image_url
        self.category = category
        self.subcategory = subcategory
        self.copyright = copyright
        self.explicit = explicit
        self.base_audio_url = base_audio_url


class RSSGenerator:
    """
    Generates RSS/Podcast feeds for distribution
    """

    def __init__(self, config: Optional[PodcastFeedConfig] = None):
        self.config = config or PodcastFeedConfig()
        self.template = Template(RSS_TEMPLATE)

    def generate_feed(
        self,
        episodes: list[EpisodeMetadata],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate RSS feed XML from episode list

        Args:
            episodes: List of episode metadata
            output_path: Optional path to save the feed

        Returns:
            RSS feed XML string
        """
        # Prepare episodes for template
        feed_episodes = []

        for ep in episodes:
            # Format duration as HH:MM:SS
            duration_seconds = ep.duration_seconds
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # Parse date for RSS format
            try:
                ep_date = datetime.fromisoformat(ep.date.replace("Z", "+00:00"))
            except (ValueError, AttributeError) as e:
                # Invalid date format or missing date - use current time
                import logging
                logging.getLogger(__name__).warning(f"Failed to parse episode date '{ep.date}': {e}")
                ep_date = datetime.now()

            # RFC 2822 date format for RSS
            pub_date = ep_date.strftime("%a, %d %b %Y %H:%M:%S +0000")

            # Audio URL
            audio_url = ep.audio_url or f"{self.config.base_audio_url}/{ep.episode_id}.mp3"

            # Estimate file size (rough: 1 minute = ~1MB at 128kbps)
            audio_size = ep.duration_seconds * 16000  # bytes

            feed_episodes.append({
                "title": ep.title,
                "description": ep.description,
                "summary": ep.description[:200] + "..." if len(ep.description) > 200 else ep.description,
                "audio_url": audio_url,
                "audio_size": audio_size,
                "guid": ep.episode_id,
                "pub_date": pub_date,
                "duration": duration_str,
            })

        # Render template
        feed_xml = self.template.render(
            podcast=self.config,
            episodes=feed_episodes,
        )

        # Save if path provided
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(feed_xml)
            logger.info(f"RSS feed saved: {output_path}")

        return feed_xml

    def validate_feed(self, feed_xml: str) -> dict:
        """Basic validation of RSS feed"""
        issues = []

        if '<?xml version="1.0"' not in feed_xml:
            issues.append("Missing XML declaration")

        if "<channel>" not in feed_xml:
            issues.append("Missing channel element")

        if "<item>" not in feed_xml:
            issues.append("No episodes in feed")

        item_count = feed_xml.count("<item>")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "episode_count": item_count,
        }
