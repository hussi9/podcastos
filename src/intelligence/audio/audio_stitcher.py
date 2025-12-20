"""Audio stitcher for combining segments into full episodes."""

import os
import wave
from pathlib import Path
from typing import Optional, Any
import logging
import json

from .tts_generator import AudioEpisode, AudioSegment


logger = logging.getLogger(__name__)


class AudioStitcher:
    """
    Combines audio segments into a complete episode.
    Uses Python's built-in wave module for concatenation (works on Python 3.13+).
    """

    # Audio parameters (must match TTS output)
    SAMPLE_RATE = 24000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit = 2 bytes

    def __init__(
        self,
        output_dir: str = "./audio_output",
        transition_ms: int = 500,  # Silence between segments
        intro_music_path: Optional[str] = None,
        outro_music_path: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.transition_ms = transition_ms
        self.intro_music_path = intro_music_path
        self.outro_music_path = outro_music_path

    def _create_silence(self, duration_ms: int) -> bytes:
        """Create silence as raw PCM bytes."""
        num_samples = int(self.SAMPLE_RATE * duration_ms / 1000)
        # 16-bit silence = 0 bytes
        return bytes(num_samples * self.SAMPLE_WIDTH)

    def _read_wav_data(self, file_path: str) -> bytes:
        """Read raw PCM data from a WAV file."""
        with wave.open(file_path, "rb") as wav:
            return wav.readframes(wav.getnframes())

    def stitch_episode(
        self,
        episode: AudioEpisode,
        output_filename: Optional[str] = None,
        include_music: bool = False,
    ) -> str:
        """
        Stitch all segments into a single audio file.
        Returns path to the combined file.
        """
        # Create silence for transitions
        silence = self._create_silence(self.transition_ms)

        # Collect all audio data
        all_audio = []

        # Add intro
        all_audio.append(self._read_wav_data(episode.intro.file_path))
        all_audio.append(silence)

        # Add content segments
        for i, segment in enumerate(episode.segments):
            all_audio.append(self._read_wav_data(segment.file_path))
            # Add transition between segments
            if i < len(episode.segments) - 1:
                all_audio.append(silence)

        # Add final transition and outro
        all_audio.append(silence)
        all_audio.append(self._read_wav_data(episode.outro.file_path))

        # Combine all data
        combined_data = b"".join(all_audio)

        # Export as WAV
        output_filename = output_filename or f"{episode.episode_id}_complete.wav"
        output_path = self.output_dir / output_filename

        with wave.open(str(output_path), "wb") as wav_out:
            wav_out.setnchannels(self.CHANNELS)
            wav_out.setsampwidth(self.SAMPLE_WIDTH)
            wav_out.setframerate(self.SAMPLE_RATE)
            wav_out.writeframes(combined_data)

        # Calculate duration
        total_duration = len(combined_data) / (self.SAMPLE_RATE * self.SAMPLE_WIDTH)

        episode.combined_file_path = str(output_path)
        episode.total_duration_seconds = total_duration

        logger.info(f"Stitched episode: {output_path} ({total_duration:.1f}s)")

        return str(output_path)

    def generate_segment_manifest(
        self,
        episode: AudioEpisode,
    ) -> dict:
        """
        Generate a manifest file for segment-based playback.
        This enables the interactive player to skip/seek to specific topics.
        """
        manifest = {
            "episode_id": episode.episode_id,
            "title": episode.title,
            "total_duration_seconds": episode.total_duration_seconds,
            "generated_at": episode.generated_at.isoformat(),
            "segments": [],
        }

        # Track cumulative offset
        offset = 0

        # Intro
        manifest["segments"].append({
            "id": episode.intro.segment_id,
            "title": "Introduction",
            "type": "intro",
            "file_path": episode.intro.file_path,
            "start_time_seconds": offset,
            "duration_seconds": episode.intro.duration_seconds,
        })
        offset += episode.intro.duration_seconds + (self.transition_ms / 1000)

        # Content segments
        for segment in episode.segments:
            manifest["segments"].append({
                "id": segment.segment_id,
                "title": segment.title,
                "type": "content",
                "file_path": segment.file_path,
                "start_time_seconds": offset,
                "duration_seconds": segment.duration_seconds,
            })
            offset += segment.duration_seconds + (self.transition_ms / 1000)

        # Outro
        manifest["segments"].append({
            "id": episode.outro.segment_id,
            "title": "Closing",
            "type": "outro",
            "file_path": episode.outro.file_path,
            "start_time_seconds": offset,
            "duration_seconds": episode.outro.duration_seconds,
        })

        return manifest

    def save_manifest(
        self,
        episode: AudioEpisode,
        output_filename: Optional[str] = None,
    ) -> str:
        """
        Save segment manifest to JSON file.
        """
        manifest = self.generate_segment_manifest(episode)

        output_filename = output_filename or f"{episode.episode_id}_manifest.json"
        output_path = self.output_dir / output_filename

        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Saved manifest: {output_path}")
        return str(output_path)

    def create_segment_playlist(
        self,
        episode: AudioEpisode,
    ) -> list[dict]:
        """
        Create a playlist for segment-based playback.
        Each entry has info needed for the player.
        """
        playlist = []

        all_segments = [
            (episode.intro, "intro"),
            *[(s, "content") for s in episode.segments],
            (episode.outro, "outro"),
        ]

        for segment, seg_type in all_segments:
            playlist.append({
                "id": segment.segment_id,
                "title": segment.title,
                "type": seg_type,
                "file_url": segment.file_path,  # Would be URL in production
                "duration_seconds": segment.duration_seconds,
                "can_skip": seg_type == "content",
            })

        return playlist


# Convenience function
def stitch_and_save(
    episode: AudioEpisode,
    output_dir: str = "./audio_output",
) -> tuple[str, str]:
    """
    Stitch episode and save manifest.
    Returns (audio_path, manifest_path).
    """
    stitcher = AudioStitcher(output_dir)

    audio_path = stitcher.stitch_episode(episode)
    manifest_path = stitcher.save_manifest(episode)

    return audio_path, manifest_path
