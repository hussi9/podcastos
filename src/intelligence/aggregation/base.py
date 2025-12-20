"""Base connector class for content sources."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import logging

from ..models.content import RawContent, SourceConfig


logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """
    Abstract base class for content source connectors.
    All connectors must implement the fetch method.
    """

    def __init__(self, config: SourceConfig):
        self.config = config
        self.last_fetch: Optional[datetime] = None
        self.fetch_count = 0
        self.error_count = 0

    @property
    def source_type(self) -> str:
        return self.config.source_type

    @property
    def source_name(self) -> str:
        return self.config.name

    @abstractmethod
    async def fetch(self, limit: int = 50) -> list[RawContent]:
        """
        Fetch content from the source.

        Args:
            limit: Maximum number of items to fetch

        Returns:
            List of RawContent items
        """
        pass

    async def fetch_with_tracking(self, limit: int = 50) -> list[RawContent]:
        """
        Fetch with error tracking and metrics.
        """
        try:
            logger.info(f"Fetching from {self.source_name} (limit={limit})")
            results = await self.fetch(limit)
            self.last_fetch = datetime.now()
            self.fetch_count += 1
            logger.info(f"Fetched {len(results)} items from {self.source_name}")
            return results
        except Exception as e:
            self.error_count += 1
            self.config.last_error = str(e)
            logger.error(f"Error fetching from {self.source_name}: {e}")
            return []

    def filter_by_keywords(self, content: RawContent) -> bool:
        """
        Check if content passes keyword filters.
        """
        text = f"{content.title} {content.body}".lower()

        # Check exclusions first
        for keyword in self.config.keywords_exclude:
            if keyword.lower() in text:
                return False

        # If no include keywords, everything passes
        if not self.config.keywords_include:
            return True

        # Check inclusions
        for keyword in self.config.keywords_include:
            if keyword.lower() in text:
                return True

        return False

    def should_fetch(self) -> bool:
        """
        Check if enough time has passed since last fetch.
        """
        if not self.config.is_active:
            return False

        if not self.last_fetch:
            return True

        elapsed = (datetime.now() - self.last_fetch).total_seconds() / 60
        return elapsed >= self.config.fetch_interval_minutes

    def get_stats(self) -> dict:
        """
        Get connector statistics.
        """
        return {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "is_active": self.config.is_active,
            "last_fetch": self.last_fetch.isoformat() if self.last_fetch else None,
            "fetch_count": self.fetch_count,
            "error_count": self.error_count,
            "last_error": self.config.last_error,
        }
