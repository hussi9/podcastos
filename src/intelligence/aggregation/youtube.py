"""YouTube transcript connector for video content."""

import re
from datetime import datetime
from typing import Optional
import logging

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from .base import BaseConnector
from ..models.content import RawContent, SourceConfig


logger = logging.getLogger(__name__)


class YouTubeTranscriptConnector(BaseConnector):
    """
    Connector for YouTube video transcripts.
    Uses youtube-transcript-api (free, no API key).

    Note: This connector needs video IDs/URLs provided.
    It doesn't discover videos - use for specific channels or search results.
    """

    def __init__(self, config: Optional[SourceConfig] = None):
        if config is None:
            config = SourceConfig(
                id="youtube",
                source_type="youtube",
                name="YouTube Transcripts",
                config={"video_ids": []},
                priority=7,
                credibility_score=0.7,
            )
        super().__init__(config)
        self.video_ids = config.config.get("video_ids", [])
        self.languages = config.config.get("languages", ["en"])

    async def fetch(self, limit: int = 50) -> list[RawContent]:
        """
        Fetch transcripts for configured video IDs.
        """
        items = []

        for video_id in self.video_ids[:limit]:
            try:
                item = await self.fetch_video(video_id)
                if item and self.filter_by_keywords(item):
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error fetching YouTube video {video_id}: {e}")

        return items

    async def fetch_video(self, video_id: str) -> Optional[RawContent]:
        """
        Fetch transcript for a single video.
        """
        # Extract video ID from URL if needed
        video_id = self._extract_video_id(video_id)

        try:
            # Get transcript
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try to get manual transcript first, then auto-generated
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(self.languages)
            except NoTranscriptFound:
                try:
                    transcript = transcript_list.find_generated_transcript(self.languages)
                except NoTranscriptFound:
                    # Try to get any available transcript
                    for t in transcript_list:
                        if t.language_code.startswith("en"):
                            transcript = t
                            break

            if not transcript:
                logger.debug(f"No transcript available for {video_id}")
                return None

            # Fetch the actual transcript text
            transcript_data = transcript.fetch()

            # Combine into body text
            body = " ".join([entry["text"] for entry in transcript_data])

            # Get duration
            total_duration = sum(entry.get("duration", 0) for entry in transcript_data)

            return RawContent(
                id=RawContent.generate_id(video_id, "youtube"),
                source_type="youtube",
                source_name="YouTube",
                title=f"YouTube Video: {video_id}",  # Would need YouTube API for actual title
                body=body,
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=datetime.now(),  # Would need YouTube API for actual date
            )

        except TranscriptsDisabled:
            logger.debug(f"Transcripts disabled for {video_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")
            return None

    def _extract_video_id(self, url_or_id: str) -> str:
        """Extract video ID from URL or return as-is if already an ID."""
        # Common YouTube URL patterns
        patterns = [
            r"(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})",
            r"(?:youtu\.be\/)([a-zA-Z0-9_-]{11})",
            r"(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})",
            r"(?:youtube\.com\/v\/)([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        # Assume it's already a video ID
        return url_or_id

    async def fetch_from_urls(self, urls: list[str]) -> list[RawContent]:
        """
        Convenience method to fetch from a list of URLs.
        """
        items = []
        for url in urls:
            try:
                item = await self.fetch_video(url)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug(f"Error fetching YouTube URL {url}: {e}")
        return items
