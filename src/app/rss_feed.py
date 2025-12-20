"""
RSS Feed Generator for PodcastOS.

Generates podcast RSS feeds compatible with:
- Spotify for Podcasters
- Apple Podcasts
- Google Podcasts
- Other podcast platforms

The RSS feed follows the iTunes/Spotify podcast specification.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from pydantic import BaseModel
import hashlib


class PodcastChannel(BaseModel):
    """Podcast channel/show information."""
    title: str
    description: str
    author: str = "PodcastOS"
    email: str = "podcast@podcastos.com"
    website: str = "https://podcastos.com"
    image_url: Optional[str] = None
    category: str = "Technology"
    language: str = "en"
    explicit: bool = False


class PodcastEpisode(BaseModel):
    """Individual podcast episode."""
    id: str
    title: str
    description: str
    audio_url: str
    audio_file_size: int  # bytes
    duration_seconds: int
    published_at: datetime
    image_url: Optional[str] = None
    episode_number: Optional[int] = None
    season_number: Optional[int] = None


class RSSFeed(BaseModel):
    """Complete RSS feed data."""
    feed_url: str
    channel: PodcastChannel
    episodes: List[PodcastEpisode] = []


class RSSFeedGenerator:
    """
    Generate podcast RSS feeds for distribution platforms.

    Usage:
        generator = RSSFeedGenerator(output_dir="./output/rss")
        feed = generator.create_feed(channel_info)
        generator.add_episode(feed_id, episode)
        rss_xml = generator.generate_xml(feed_id)
    """

    def __init__(self, output_dir: str = "./output/rss", base_url: str = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.feeds_file = self.output_dir / "feeds.json"
        self.base_url = base_url or os.getenv("BASE_URL", "http://127.0.0.1:8080")

        # Ensure feeds file exists
        if not self.feeds_file.exists():
            self._save_feeds({})

    def _load_feeds(self) -> dict:
        """Load all feeds from storage."""
        if self.feeds_file.exists():
            with open(self.feeds_file, "r") as f:
                return json.load(f)
        return {}

    def _save_feeds(self, feeds: dict):
        """Save feeds to storage."""
        with open(self.feeds_file, "w") as f:
            json.dump(feeds, f, indent=2, default=str)

    def create_feed(self, channel: PodcastChannel) -> str:
        """
        Create a new podcast feed.

        Returns:
            Feed ID
        """
        # Generate unique feed ID from title
        feed_id = hashlib.md5(channel.title.encode()).hexdigest()[:8]

        feeds = self._load_feeds()

        feeds[feed_id] = {
            "channel": channel.model_dump(),
            "episodes": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self._save_feeds(feeds)

        # Generate initial RSS file
        self._generate_rss_file(feed_id)

        return feed_id

    def get_feed(self, feed_id: str) -> Optional[dict]:
        """Get feed by ID."""
        feeds = self._load_feeds()
        return feeds.get(feed_id)

    def list_feeds(self) -> List[dict]:
        """List all feeds."""
        feeds = self._load_feeds()
        return [
            {"id": fid, **data}
            for fid, data in feeds.items()
        ]

    def add_episode(
        self,
        feed_id: str,
        episode: PodcastEpisode,
    ) -> bool:
        """
        Add an episode to a feed.

        Returns:
            True if successful
        """
        feeds = self._load_feeds()

        if feed_id not in feeds:
            return False

        feeds[feed_id]["episodes"].append(episode.model_dump())
        feeds[feed_id]["updated_at"] = datetime.now().isoformat()

        self._save_feeds(feeds)

        # Regenerate RSS file
        self._generate_rss_file(feed_id)

        return True

    def add_episode_from_generation(
        self,
        feed_id: str,
        audio_path: str,
        title: str,
        description: str,
        duration_seconds: int,
    ) -> Optional[PodcastEpisode]:
        """
        Add episode from a generated podcast file.

        Args:
            feed_id: The feed to add to
            audio_path: Path to the audio file
            title: Episode title
            description: Episode description
            duration_seconds: Episode duration

        Returns:
            The created episode
        """
        feeds = self._load_feeds()

        if feed_id not in feeds:
            return None

        # Get file size
        audio_file = Path(audio_path)
        if not audio_file.exists():
            return None

        file_size = audio_file.stat().st_size

        # Create episode
        episode_num = len(feeds[feed_id]["episodes"]) + 1
        episode_id = f"ep{episode_num}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Build audio URL
        audio_filename = audio_file.name
        audio_url = f"{self.base_url}/files/{audio_filename}"

        episode = PodcastEpisode(
            id=episode_id,
            title=title,
            description=description,
            audio_url=audio_url,
            audio_file_size=file_size,
            duration_seconds=duration_seconds,
            published_at=datetime.now(),
            episode_number=episode_num,
        )

        self.add_episode(feed_id, episode)

        return episode

    def _generate_rss_file(self, feed_id: str) -> str:
        """
        Generate RSS XML file for a feed.

        Returns:
            Path to the generated RSS file
        """
        feeds = self._load_feeds()
        feed_data = feeds.get(feed_id)

        if not feed_data:
            raise ValueError(f"Feed not found: {feed_id}")

        channel = feed_data["channel"]
        episodes = feed_data["episodes"]

        # Create RSS structure
        rss = Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

        channel_elem = SubElement(rss, "channel")

        # Channel metadata
        SubElement(channel_elem, "title").text = channel["title"]
        SubElement(channel_elem, "description").text = channel["description"]
        SubElement(channel_elem, "language").text = channel.get("language", "en")
        SubElement(channel_elem, "link").text = channel.get("website", self.base_url)

        # iTunes specific tags
        SubElement(channel_elem, "itunes:author").text = channel.get("author", "PodcastOS")
        SubElement(channel_elem, "itunes:summary").text = channel["description"]
        SubElement(channel_elem, "itunes:explicit").text = "yes" if channel.get("explicit") else "no"

        # Category
        category = SubElement(channel_elem, "itunes:category")
        category.set("text", channel.get("category", "Technology"))

        # Owner info
        owner = SubElement(channel_elem, "itunes:owner")
        SubElement(owner, "itunes:name").text = channel.get("author", "PodcastOS")
        SubElement(owner, "itunes:email").text = channel.get("email", "podcast@podcastos.com")

        # Image
        if channel.get("image_url"):
            image = SubElement(channel_elem, "itunes:image")
            image.set("href", channel["image_url"])

        # Atom self-link
        atom_link = SubElement(channel_elem, "atom:link")
        atom_link.set("href", f"{self.base_url}/rss/{feed_id}.xml")
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")

        # Episodes
        for ep in reversed(episodes):  # Newest first
            item = SubElement(channel_elem, "item")

            SubElement(item, "title").text = ep["title"]
            SubElement(item, "description").text = ep["description"]
            SubElement(item, "guid").text = ep["id"]

            # Pub date
            if isinstance(ep["published_at"], str):
                pub_date = datetime.fromisoformat(ep["published_at"].replace("Z", "+00:00"))
            else:
                pub_date = ep["published_at"]
            SubElement(item, "pubDate").text = pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000")

            # Enclosure (audio file)
            enclosure = SubElement(item, "enclosure")
            enclosure.set("url", ep["audio_url"])
            enclosure.set("length", str(ep["audio_file_size"]))
            enclosure.set("type", "audio/wav")  # or audio/mpeg for mp3

            # iTunes tags
            SubElement(item, "itunes:summary").text = ep["description"]
            SubElement(item, "itunes:explicit").text = "no"

            # Duration in HH:MM:SS format
            duration = ep["duration_seconds"]
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            if hours:
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes}:{seconds:02d}"
            SubElement(item, "itunes:duration").text = duration_str

            # Episode number
            if ep.get("episode_number"):
                SubElement(item, "itunes:episode").text = str(ep["episode_number"])

            if ep.get("season_number"):
                SubElement(item, "itunes:season").text = str(ep["season_number"])

        # Pretty print XML
        xml_str = minidom.parseString(tostring(rss)).toprettyxml(indent="  ")
        # Remove extra blank lines
        xml_str = "\n".join([line for line in xml_str.split("\n") if line.strip()])

        # Save to file
        rss_path = self.output_dir / f"{feed_id}.xml"
        with open(rss_path, "w") as f:
            f.write(xml_str)

        return str(rss_path)

    def get_rss_url(self, feed_id: str) -> str:
        """Get the public URL for a feed's RSS."""
        return f"{self.base_url}/rss/{feed_id}.xml"

    def get_rss_xml(self, feed_id: str) -> Optional[str]:
        """Get the RSS XML content for a feed."""
        rss_path = self.output_dir / f"{feed_id}.xml"
        if rss_path.exists():
            with open(rss_path, "r") as f:
                return f.read()
        return None


# Quick-start function for common use case
def create_podcast_feed(
    title: str,
    description: str,
    author: str = "PodcastOS",
) -> str:
    """
    Quick function to create a new podcast feed.

    Returns:
        Feed ID
    """
    generator = RSSFeedGenerator()
    channel = PodcastChannel(
        title=title,
        description=description,
        author=author,
    )
    return generator.create_feed(channel)


def add_episode_to_feed(
    feed_id: str,
    audio_path: str,
    title: str,
    description: str,
    duration_seconds: int,
) -> Optional[PodcastEpisode]:
    """
    Quick function to add an episode to a feed.

    Returns:
        The created episode
    """
    generator = RSSFeedGenerator()
    return generator.add_episode_from_generation(
        feed_id=feed_id,
        audio_path=audio_path,
        title=title,
        description=description,
        duration_seconds=duration_seconds,
    )


def get_feed_url(feed_id: str) -> str:
    """Get the RSS URL for a feed."""
    generator = RSSFeedGenerator()
    return generator.get_rss_url(feed_id)
