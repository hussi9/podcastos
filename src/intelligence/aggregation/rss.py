"""RSS/Atom feed connector."""

from datetime import datetime
from typing import Optional
import httpx
import feedparser
import logging
from email.utils import parsedate_to_datetime

from .base import BaseConnector
from ..models.content import RawContent, SourceConfig


logger = logging.getLogger(__name__)


class RSSConnector(BaseConnector):
    """
    Connector for RSS/Atom feeds.
    Uses feedparser library (free, no API key).
    """

    def __init__(self, config: Optional[SourceConfig] = None):
        if config is None:
            config = SourceConfig(
                id="rss",
                source_type="rss",
                name="RSS Feeds",
                config={"feeds": []},
                priority=6,
                credibility_score=0.75,
            )
        super().__init__(config)
        self.feeds = config.config.get("feeds", [])

    async def fetch(self, limit: int = 50) -> list[RawContent]:
        """Fetch items from all configured RSS feeds."""
        all_items = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for feed_url in self.feeds:
                try:
                    items = await self._fetch_feed(client, feed_url)
                    all_items.extend(items)
                except Exception as e:
                    logger.error(f"Error fetching RSS feed {feed_url}: {e}")

        # Sort by date (newest first)
        all_items.sort(key=lambda x: x.published_at, reverse=True)

        # Apply keyword filters
        filtered_items = [item for item in all_items if self.filter_by_keywords(item)]

        return filtered_items[:limit]

    async def _fetch_feed(self, client: httpx.AsyncClient, feed_url: str) -> list[RawContent]:
        """Fetch and parse a single RSS feed."""
        items = []

        try:
            # Fetch feed content
            response = await client.get(feed_url)
            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.text)

            if feed.bozo and feed.bozo_exception:
                logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")

            # Get feed title for source name
            feed_title = feed.feed.get("title", feed_url)

            # Parse entries
            for entry in feed.entries:
                try:
                    item = self._parse_entry(entry, feed_title, feed_url)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.debug(f"Error parsing RSS entry: {e}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching RSS feed {feed_url}: {e}")
        except Exception as e:
            logger.error(f"Error processing RSS feed {feed_url}: {e}")

        return items

    def _parse_entry(self, entry: dict, feed_title: str, feed_url: str) -> Optional[RawContent]:
        """Parse a feed entry into RawContent."""
        title = entry.get("title")
        if not title:
            return None

        # Parse publication date
        published_at = self._parse_date(entry)

        # Get content/description
        body = ""
        if "content" in entry:
            body = entry.content[0].get("value", "") if entry.content else ""
        elif "summary" in entry:
            body = entry.get("summary", "")
        elif "description" in entry:
            body = entry.get("description", "")

        # Strip HTML tags (basic)
        body = self._strip_html(body)

        # Get URL
        url = entry.get("link", entry.get("id"))

        return RawContent(
            id=RawContent.generate_id(url or title, "rss"),
            source_type="rss",
            source_name=feed_title,
            title=title,
            body=body,
            url=url,
            author=entry.get("author"),
            published_at=published_at,
        )

    def _parse_date(self, entry: dict) -> datetime:
        """Parse date from various RSS date formats."""
        date_fields = ["published", "updated", "created"]

        for field in date_fields:
            parsed = f"{field}_parsed"
            if parsed in entry and entry[parsed]:
                try:
                    time_tuple = entry[parsed]
                    return datetime(*time_tuple[:6])
                except Exception:
                    pass

            if field in entry:
                try:
                    return parsedate_to_datetime(entry[field])
                except Exception:
                    pass

        return datetime.now()

    def _strip_html(self, text: str) -> str:
        """Basic HTML tag stripping."""
        import re
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Decode common HTML entities
        clean = clean.replace("&nbsp;", " ")
        clean = clean.replace("&amp;", "&")
        clean = clean.replace("&lt;", "<")
        clean = clean.replace("&gt;", ">")
        clean = clean.replace("&quot;", '"')
        clean = clean.replace("&#39;", "'")
        # Clean up whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def add_feed(self, feed_url: str) -> bool:
        """
        Add a new feed URL to the configuration.
        Returns True if successful.
        """
        if feed_url in self.feeds:
            return True

        # Validate feed
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(feed_url)
                response.raise_for_status()
                feed = feedparser.parse(response.text)

                if feed.bozo and not feed.entries:
                    logger.error(f"Invalid RSS feed: {feed_url}")
                    return False

                self.feeds.append(feed_url)
                logger.info(f"Added RSS feed: {feed.feed.get('title', feed_url)}")
                return True

            except Exception as e:
                logger.error(f"Error validating RSS feed {feed_url}: {e}")
                return False
