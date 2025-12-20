"""Hacker News connector using Firebase API."""

import asyncio
from datetime import datetime
from typing import Optional
import httpx
import logging

from .base import BaseConnector
from ..models.content import RawContent, SourceConfig


logger = logging.getLogger(__name__)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsConnector(BaseConnector):
    """
    Connector for Hacker News using their official Firebase API.
    Free, no API key required.
    """

    def __init__(self, config: Optional[SourceConfig] = None):
        if config is None:
            config = SourceConfig(
                id="hackernews",
                source_type="hackernews",
                name="Hacker News",
                config={"endpoints": ["topstories", "beststories"]},
                priority=9,
                credibility_score=0.8,
            )
        super().__init__(config)
        self.endpoints = config.config.get("endpoints", ["topstories"])

    async def fetch(self, limit: int = 50) -> list[RawContent]:
        """Fetch top/best stories from Hacker News."""
        all_items = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for endpoint in self.endpoints:
                try:
                    items = await self._fetch_endpoint(client, endpoint, limit // len(self.endpoints))
                    all_items.extend(items)
                except Exception as e:
                    logger.error(f"Error fetching HN {endpoint}: {e}")

        # Deduplicate by ID
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_items.append(item)

        # Sort by engagement score
        unique_items.sort(key=lambda x: x.engagement_score, reverse=True)

        # Apply keyword filters
        filtered_items = [item for item in unique_items if self.filter_by_keywords(item)]

        return filtered_items[:limit]

    async def _fetch_endpoint(
        self, client: httpx.AsyncClient, endpoint: str, limit: int
    ) -> list[RawContent]:
        """Fetch stories from a specific endpoint."""
        # Get story IDs
        response = await client.get(f"{HN_API_BASE}/{endpoint}.json")
        response.raise_for_status()
        story_ids = response.json()[:limit * 2]  # Fetch extra for filtering

        # Fetch stories concurrently (batch of 10)
        items = []
        for i in range(0, len(story_ids), 10):
            batch = story_ids[i:i+10]
            tasks = [self._fetch_item(client, item_id) for item_id in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, RawContent):
                    items.append(result)
                elif isinstance(result, Exception):
                    logger.debug(f"Error fetching HN item: {result}")

            if len(items) >= limit:
                break

        return items[:limit]

    async def _fetch_item(self, client: httpx.AsyncClient, item_id: int) -> RawContent:
        """Fetch a single HN item."""
        response = await client.get(f"{HN_API_BASE}/item/{item_id}.json")
        response.raise_for_status()
        data = response.json()

        if not data or data.get("type") != "story":
            raise ValueError(f"Invalid item: {item_id}")

        # Skip dead/deleted items
        if data.get("dead") or data.get("deleted"):
            raise ValueError(f"Dead/deleted item: {item_id}")

        return RawContent(
            id=RawContent.generate_id(str(item_id), "hackernews"),
            source_type="hackernews",
            source_name="Hacker News",
            title=data.get("title", ""),
            body=data.get("text", ""),  # For Ask HN, Show HN posts
            url=data.get("url"),
            author=data.get("by"),
            published_at=datetime.fromtimestamp(data.get("time", 0)),
            score=data.get("score", 0),
            comments=data.get("descendants", 0),
        )

    async def fetch_comments(self, item_id: int, limit: int = 10) -> list[str]:
        """
        Fetch top comments for an item.
        Useful for getting community perspectives.
        """
        comments = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get item to find comment IDs
            response = await client.get(f"{HN_API_BASE}/item/{item_id}.json")
            response.raise_for_status()
            data = response.json()

            comment_ids = data.get("kids", [])[:limit]

            # Fetch comments
            for comment_id in comment_ids:
                try:
                    comment_response = await client.get(f"{HN_API_BASE}/item/{comment_id}.json")
                    comment_response.raise_for_status()
                    comment_data = comment_response.json()

                    if comment_data and not comment_data.get("deleted"):
                        text = comment_data.get("text", "")
                        if text:
                            comments.append(text)
                except Exception as e:
                    logger.debug(f"Error fetching comment {comment_id}: {e}")

        return comments
