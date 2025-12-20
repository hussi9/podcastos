"""Source Manager for orchestrating multiple content sources."""

import asyncio
from datetime import datetime
from typing import Optional
import logging

from .base import BaseConnector
from .hackernews import HackerNewsConnector
from .newsdata import NewsDataConnector
from .youtube import YouTubeTranscriptConnector
from .rss import RSSConnector
from .reddit import RedditConnector
from ..models.content import RawContent, SourceConfig, ProfileSourceConfig


logger = logging.getLogger(__name__)


class SourceManager:
    """
    Manages and orchestrates multiple content source connectors.
    Handles concurrent fetching, deduplication, and ranking.
    """

    CONNECTOR_TYPES = {
        "reddit": RedditConnector,
        "hackernews": HackerNewsConnector,
        "newsdata": NewsDataConnector,
        "youtube": YouTubeTranscriptConnector,
        "rss": RSSConnector,
    }

    def __init__(self, profile_config: Optional[ProfileSourceConfig] = None):
        self.connectors: dict[str, BaseConnector] = {}
        self.last_fetch_all: Optional[datetime] = None
        self.total_items_fetched = 0

        if profile_config:
            self.load_profile(profile_config)

    def load_profile(self, profile_config: ProfileSourceConfig):
        """
        Load source configurations for a podcast profile.
        """
        self.connectors.clear()

        for source_config in profile_config.sources:
            try:
                self.add_source(source_config)
            except Exception as e:
                logger.error(f"Error loading source {source_config.id}: {e}")

        logger.info(f"Loaded {len(self.connectors)} sources for profile {profile_config.profile_id}")

    def add_source(self, config: SourceConfig):
        """
        Add a content source to the manager.
        """
        connector_class = self.CONNECTOR_TYPES.get(config.source_type)
        if not connector_class:
            raise ValueError(f"Unknown source type: {config.source_type}")

        connector = connector_class(config)
        self.connectors[config.id] = connector
        logger.info(f"Added source: {config.name} ({config.source_type})")

    def remove_source(self, source_id: str):
        """Remove a source by ID."""
        if source_id in self.connectors:
            del self.connectors[source_id]
            logger.info(f"Removed source: {source_id}")

    async def fetch_all(self, limit_per_source: int = 50) -> list[RawContent]:
        """
        Fetch content from all active sources concurrently.
        Returns deduplicated and ranked results.
        """
        all_items = []

        # Get active connectors
        active_connectors = [
            c for c in self.connectors.values() if c.config.is_active
        ]

        if not active_connectors:
            logger.warning("No active sources configured")
            return []

        # Fetch from all sources concurrently
        tasks = [
            connector.fetch_with_tracking(limit_per_source)
            for connector in active_connectors
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Fetch error: {result}")

        # Deduplicate
        deduplicated = self._deduplicate(all_items)

        # Compute content hashes
        for item in deduplicated:
            item.compute_hash()

        # Rank by weighted engagement
        ranked = self._rank_items(deduplicated)

        self.last_fetch_all = datetime.now()
        self.total_items_fetched += len(ranked)

        logger.info(f"Fetched {len(ranked)} unique items from {len(active_connectors)} sources")

        return ranked

    async def fetch_source(self, source_id: str, limit: int = 50) -> list[RawContent]:
        """
        Fetch from a specific source.
        """
        connector = self.connectors.get(source_id)
        if not connector:
            raise ValueError(f"Source not found: {source_id}")

        return await connector.fetch_with_tracking(limit)

    def _deduplicate(self, items: list[RawContent]) -> list[RawContent]:
        """
        Deduplicate items by URL and content similarity.
        """
        seen_urls = set()
        seen_titles = set()
        unique_items = []

        for item in items:
            # Skip if exact URL match
            if item.url and item.url in seen_urls:
                continue

            # Skip if very similar title (basic dedup)
            title_key = item.title.lower().strip()[:50]
            if title_key in seen_titles:
                continue

            if item.url:
                seen_urls.add(item.url)
            seen_titles.add(title_key)
            unique_items.append(item)

        return unique_items

    def _rank_items(self, items: list[RawContent]) -> list[RawContent]:
        """
        Rank items by weighted engagement and source priority.
        """
        def score(item: RawContent) -> float:
            # Get source priority
            connector = None
            for c in self.connectors.values():
                if c.source_type == item.source_type:
                    connector = c
                    break

            priority = connector.config.priority if connector else 5
            credibility = connector.config.credibility_score if connector else 0.5

            # Weighted score
            base_score = item.engagement_score
            weighted = (
                base_score * (priority / 10) * credibility
            )

            return weighted

        return sorted(items, key=score, reverse=True)

    def get_stats(self) -> dict:
        """
        Get statistics for all sources.
        """
        return {
            "total_sources": len(self.connectors),
            "active_sources": sum(1 for c in self.connectors.values() if c.config.is_active),
            "last_fetch_all": self.last_fetch_all.isoformat() if self.last_fetch_all else None,
            "total_items_fetched": self.total_items_fetched,
            "sources": {
                source_id: connector.get_stats()
                for source_id, connector in self.connectors.items()
            },
        }

    def get_source_health(self) -> dict[str, str]:
        """
        Get health status for each source.
        """
        health = {}
        for source_id, connector in self.connectors.items():
            if not connector.config.is_active:
                health[source_id] = "inactive"
            elif connector.config.last_error:
                health[source_id] = "error"
            elif connector.fetch_count == 0:
                health[source_id] = "pending"
            else:
                health[source_id] = "healthy"
        return health


# Factory functions for common podcast profiles
def create_tech_source_manager(profile_id: int) -> SourceManager:
    """Create a source manager for a tech-focused podcast."""
    config = ProfileSourceConfig.for_tech_podcast(profile_id)
    return SourceManager(config)


def create_finance_source_manager(profile_id: int) -> SourceManager:
    """Create a source manager for a finance-focused podcast."""
    config = ProfileSourceConfig.for_finance_podcast(profile_id)
    return SourceManager(config)


def create_immigration_source_manager(profile_id: int) -> SourceManager:
    """Create a source manager for an immigration-focused podcast."""
    config = ProfileSourceConfig.for_immigration_podcast(profile_id)
    return SourceManager(config)
