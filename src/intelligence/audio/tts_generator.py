"""TTS Generator using Gemini Native TTS."""

import os
import asyncio
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from ..synthesis.script_generator import PodcastScript, ScriptSegment


logger = logging.getLogger(__name__)


class AudioSegment(BaseModel):
    """Generated audio segment."""

    id: str
    segment_id: str
    title: str

    # Audio file info
    file_path: str
    duration_seconds: float = 0.0
    file_size_bytes: int = 0

    # Metadata
    sample_rate: int = 24000
    format: str = "wav"

    # Generation info
    generated_at: datetime = Field(default_factory=datetime.now)
    voice_used: str = "Kore"


class AudioEpisode(BaseModel):
    """Complete audio episode with segments."""

    id: str
    episode_id: str
    title: str

    # Audio segments
    intro: AudioSegment
    segments: list[AudioSegment] = Field(default_factory=list)
    outro: AudioSegment

    # Combined file (if stitched)
    combined_file_path: Optional[str] = None
    total_duration_seconds: float = 0.0

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.now)

    def calculate_duration(self):
        """Calculate total duration."""
        all_segments = [self.intro] + self.segments + [self.outro]
        self.total_duration_seconds = sum(s.duration_seconds for s in all_segments)


class TTSGenerator:
    """
    Text-to-Speech generator using Gemini Native TTS.

    Features:
    - Per-segment audio generation
    - Multiple voice options
    - Emotional expression support
    - Segment metadata for interactive playback
    """

    # Available Gemini TTS voices
    VOICES = {
        "Kore": "Clear, professional female voice",
        "Charon": "Deep, authoritative male voice",
        "Fenrir": "Energetic male voice",
        "Aoede": "Warm, conversational female voice",
        "Puck": "Friendly, casual voice",
    }

    DEFAULT_VOICE = "Kore"

    def __init__(
        self,
        output_dir: str = "./audio_output",
        voice: str = None,
        model: str = "gemini-2.5-flash-preview-tts",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.voice = voice or self.DEFAULT_VOICE
        self.model = model
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        """Lazy load the Gemini client."""
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def generate_episode_audio(
        self,
        script: PodcastScript,
        voice: Optional[str] = None,
    ) -> AudioEpisode:
        """
        Generate audio for a complete podcast script.
        Each segment is generated separately for interactive playback.
        """
        voice = voice or self.voice

        episode_dir = self.output_dir / script.id
        episode_dir.mkdir(exist_ok=True)

        # Generate intro
        logger.info("Generating intro audio...")
        intro_audio = await self._generate_segment_audio(
            script.intro, episode_dir, voice
        )

        # Generate content segments
        segment_audios = []
        for i, segment in enumerate(script.segments):
            logger.info(f"Generating segment {i+1}/{len(script.segments)}: {segment.title[:30]}...")
            audio = await self._generate_segment_audio(segment, episode_dir, voice)
            segment_audios.append(audio)

        # Generate outro
        logger.info("Generating outro audio...")
        outro_audio = await self._generate_segment_audio(
            script.outro, episode_dir, voice
        )

        # Create episode
        episode = AudioEpisode(
            id=f"audio-{script.id}",
            episode_id=script.id,
            title=script.title,
            intro=intro_audio,
            segments=segment_audios,
            outro=outro_audio,
        )
        episode.calculate_duration()

        logger.info(
            f"Generated audio episode: {len(segment_audios)} segments, "
            f"~{episode.total_duration_seconds / 60:.1f} minutes"
        )

        return episode

    async def _generate_segment_audio(
        self,
        segment: ScriptSegment,
        output_dir: Path,
        voice: str,
    ) -> AudioSegment:
        """Generate audio for a single script segment."""
        # Use SSML if available, otherwise plain text
        text = segment.ssml_script or segment.host_script

        # Generate audio (raw PCM data)
        audio_data = await self._synthesize_speech(text, voice)

        # Save to file as proper WAV
        file_name = f"{segment.sequence:02d}_{segment.id}.wav"
        file_path = output_dir / file_name

        # Write proper WAV file with header
        # Gemini TTS returns L16 (16-bit linear PCM) at 24kHz mono
        with wave.open(str(file_path), "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes per sample
            wav_file.setframerate(24000)  # 24kHz sample rate
            wav_file.writeframes(audio_data)

        # Calculate duration from PCM data
        # PCM: sample_rate * channels * bytes_per_sample
        pcm_size = len(audio_data)
        duration = pcm_size / (24000 * 2)  # 24kHz, 16-bit mono

        # Get actual file size (includes WAV header)
        file_size = file_path.stat().st_size

        return AudioSegment(
            id=f"audio-{segment.id}",
            segment_id=segment.id,
            title=segment.title,
            file_path=str(file_path),
            duration_seconds=duration,
            file_size_bytes=file_size,
            voice_used=voice,
        )

    async def _synthesize_speech(self, text: str, voice: str) -> bytes:
        """
        Synthesize speech using Gemini TTS.
        Returns raw PCM audio data (L16, 24kHz, mono).
        """
        # Configure speech generation
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice,
                    ),
                ),
            ),
        )

        # Generate audio
        response = self.client.models.generate_content(
            model=self.model,
            contents=text,
            config=config,
        )

        # Extract audio data - it's already raw bytes, not base64
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("audio"):
                # Data is raw PCM bytes (L16 = 16-bit linear, 24kHz)
                return part.inline_data.data

        raise ValueError("No audio data in response")

    async def generate_segment_only(
        self,
        text: str,
        segment_id: str,
        voice: Optional[str] = None,
    ) -> AudioSegment:
        """
        Generate audio for a single piece of text.
        Useful for regenerating individual segments.
        """
        voice = voice or self.voice

        audio_data = await self._synthesize_speech(text, voice)

        file_path = self.output_dir / f"{segment_id}.wav"

        # Write proper WAV file
        with wave.open(str(file_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(audio_data)

        pcm_size = len(audio_data)
        duration = pcm_size / (24000 * 2)
        file_size = file_path.stat().st_size

        return AudioSegment(
            id=f"audio-{segment_id}",
            segment_id=segment_id,
            title="Generated Segment",
            file_path=str(file_path),
            duration_seconds=duration,
            file_size_bytes=file_size,
            voice_used=voice,
        )

    def list_voices(self) -> dict[str, str]:
        """List available voices."""
        return self.VOICES.copy()


class DialogueTTSGenerator(TTSGenerator):
    """
    Extended TTS generator for dialogue-style podcasts.
    Supports multiple voices for host and co-host.
    """

    def __init__(
        self,
        output_dir: str = "./audio_output",
        host_voice: str = "Kore",
        co_host_voice: str = "Charon",
    ):
        super().__init__(output_dir, host_voice)
        self.host_voice = host_voice
        self.co_host_voice = co_host_voice

    async def generate_dialogue_segment(
        self,
        host_text: str,
        co_host_text: Optional[str],
        segment_id: str,
    ) -> list[AudioSegment]:
        """
        Generate audio for a dialogue segment.
        Returns list of audio parts (host, then co-host if present).
        """
        parts = []

        # Host audio
        host_audio = await self.generate_segment_only(
            host_text,
            f"{segment_id}_host",
            self.host_voice,
        )
        parts.append(host_audio)

        # Co-host audio if present
        if co_host_text:
            co_host_audio = await self.generate_segment_only(
                co_host_text,
                f"{segment_id}_cohost",
                self.co_host_voice,
            )
            parts.append(co_host_audio)

        return parts
