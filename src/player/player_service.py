"""Player service for managing episode playback and interactions."""

import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime
import logging

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class SegmentInfo(BaseModel):
    """Information about a playable segment."""
    id: str
    title: str
    type: str  # intro, content, outro
    file_path: str
    file_url: Optional[str] = None
    start_time_seconds: float
    duration_seconds: float
    can_skip: bool = True
    can_deep_dive: bool = False


class EpisodeInfo(BaseModel):
    """Episode metadata for the player."""
    episode_id: str
    title: str
    description: Optional[str] = None
    total_duration_seconds: float
    generated_at: datetime
    segments: list[SegmentInfo] = Field(default_factory=list)
    combined_file_path: Optional[str] = None
    combined_file_url: Optional[str] = None


class PlaybackState(BaseModel):
    """Current playback state."""
    episode_id: str
    current_segment_index: int = 0
    current_time_seconds: float = 0.0
    is_playing: bool = False
    playback_rate: float = 1.0
    volume: float = 1.0


class DeepDiveRequest(BaseModel):
    """Request for deep dive on a topic."""
    episode_id: str
    segment_id: str
    question: Optional[str] = None


class DeepDiveResponse(BaseModel):
    """Response with deep dive content."""
    segment_id: str
    original_title: str
    deep_dive_text: str
    deep_dive_audio_url: Optional[str] = None
    sources: list[str] = Field(default_factory=list)


class PlayerService:
    """
    Service for interactive podcast playback.

    Features:
    - Load episodes from manifest files
    - Track playback state
    - Skip to specific segments
    - Generate deep-dive content on demand
    """

    def __init__(self, episodes_dir: str = "./output"):
        self.episodes_dir = Path(episodes_dir)
        self._episodes: dict[str, EpisodeInfo] = {}
        self._playback_states: dict[str, PlaybackState] = {}

    def load_episode(self, manifest_path: str) -> EpisodeInfo:
        """Load episode from manifest file."""
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        segments = []
        for seg in manifest.get("segments", []):
            segments.append(SegmentInfo(
                id=seg["id"],
                title=seg["title"],
                type=seg["type"],
                file_path=seg["file_path"],
                start_time_seconds=seg["start_time_seconds"],
                duration_seconds=seg["duration_seconds"],
                can_skip=seg["type"] == "content",
                can_deep_dive=seg["type"] == "content",
            ))

        episode = EpisodeInfo(
            episode_id=manifest["episode_id"],
            title=manifest["title"],
            total_duration_seconds=manifest["total_duration_seconds"],
            generated_at=datetime.fromisoformat(manifest["generated_at"]),
            segments=segments,
        )

        # Check for combined file
        combined_path = self.episodes_dir / f"{episode.episode_id}_complete.wav"
        if combined_path.exists():
            episode.combined_file_path = str(combined_path)

        self._episodes[episode.episode_id] = episode
        logger.info(f"Loaded episode: {episode.title} ({len(segments)} segments)")

        return episode

    def scan_episodes(self) -> list[EpisodeInfo]:
        """Scan episodes directory for available episodes."""
        episodes = []

        for manifest_file in self.episodes_dir.glob("*_manifest.json"):
            try:
                episode = self.load_episode(str(manifest_file))
                episodes.append(episode)
            except Exception as e:
                logger.error(f"Failed to load {manifest_file}: {e}")

        return episodes

    def get_episode(self, episode_id: str) -> Optional[EpisodeInfo]:
        """Get episode by ID."""
        return self._episodes.get(episode_id)

    def list_episodes(self) -> list[EpisodeInfo]:
        """List all loaded episodes."""
        return list(self._episodes.values())

    def get_playback_state(self, episode_id: str) -> PlaybackState:
        """Get or create playback state for an episode."""
        if episode_id not in self._playback_states:
            self._playback_states[episode_id] = PlaybackState(episode_id=episode_id)
        return self._playback_states[episode_id]

    def update_playback_state(
        self,
        episode_id: str,
        segment_index: Optional[int] = None,
        time_seconds: Optional[float] = None,
        is_playing: Optional[bool] = None,
        playback_rate: Optional[float] = None,
    ) -> PlaybackState:
        """Update playback state."""
        state = self.get_playback_state(episode_id)

        if segment_index is not None:
            state.current_segment_index = segment_index
        if time_seconds is not None:
            state.current_time_seconds = time_seconds
        if is_playing is not None:
            state.is_playing = is_playing
        if playback_rate is not None:
            state.playback_rate = playback_rate

        return state

    def skip_to_segment(self, episode_id: str, segment_index: int) -> PlaybackState:
        """Skip to a specific segment."""
        episode = self.get_episode(episode_id)
        if not episode:
            raise ValueError(f"Episode not found: {episode_id}")

        if segment_index < 0 or segment_index >= len(episode.segments):
            raise ValueError(f"Invalid segment index: {segment_index}")

        segment = episode.segments[segment_index]

        return self.update_playback_state(
            episode_id,
            segment_index=segment_index,
            time_seconds=segment.start_time_seconds,
        )

    def next_segment(self, episode_id: str) -> Optional[PlaybackState]:
        """Move to next segment."""
        state = self.get_playback_state(episode_id)
        episode = self.get_episode(episode_id)

        if not episode:
            return None

        next_index = state.current_segment_index + 1
        if next_index >= len(episode.segments):
            return None  # End of episode

        return self.skip_to_segment(episode_id, next_index)

    def previous_segment(self, episode_id: str) -> Optional[PlaybackState]:
        """Move to previous segment."""
        state = self.get_playback_state(episode_id)

        prev_index = state.current_segment_index - 1
        if prev_index < 0:
            return None  # Already at start

        return self.skip_to_segment(episode_id, prev_index)

    async def generate_deep_dive(
        self,
        request: DeepDiveRequest,
    ) -> DeepDiveResponse:
        """
        Generate deep-dive content for a segment.
        Uses Gemini to expand on the topic with more detail.
        """
        episode = self.get_episode(request.episode_id)
        if not episode:
            raise ValueError(f"Episode not found: {request.episode_id}")

        # Find segment
        segment = None
        for seg in episode.segments:
            if seg.id == request.segment_id:
                segment = seg
                break

        if not segment:
            raise ValueError(f"Segment not found: {request.segment_id}")

        # Generate deep dive using research engine
        from ..intelligence.research.research_orchestrator import quick_research

        question = request.question or f"Tell me more about {segment.title}"

        logger.info(f"Generating deep dive for: {segment.title}")

        research = await quick_research(
            f"{segment.title}: {question}",
            depth="standard",
        )

        return DeepDiveResponse(
            segment_id=segment.id,
            original_title=segment.title,
            deep_dive_text=research.get("summary", ""),
            sources=research.get("sources", []),
        )

    def get_segment_audio_path(self, episode_id: str, segment_id: str) -> Optional[str]:
        """Get the audio file path for a specific segment."""
        episode = self.get_episode(episode_id)
        if not episode:
            return None

        for segment in episode.segments:
            if segment.id == segment_id:
                return segment.file_path

        return None
