"""Content aggregation connectors for multiple sources."""

from .base import BaseConnector
from .hackernews import HackerNewsConnector
from .newsdata import NewsDataConnector
from .youtube import YouTubeTranscriptConnector
from .rss import RSSConnector
from .reddit import RedditConnector
from .source_manager import SourceManager

__all__ = [
    "BaseConnector",
    "HackerNewsConnector",
    "NewsDataConnector",
    "YouTubeTranscriptConnector",
    "RSSConnector",
    "RedditConnector",
    "SourceManager",
]
