"""
ElevenLabs Text-to-Speech integration for podcast audio generation
"""

import asyncio
import io
import os
from pathlib import Path
from typing import Optional
import httpx
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class VoiceConfig(BaseModel):
    """Configuration for a voice"""

    voice_id: str
    name: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


class AudioSegment(BaseModel):
    """A generated audio segment"""

    speaker: str
    text: str
    audio_path: str
    duration_ms: int


class ElevenLabsTTS:
    """
    ElevenLabs Text-to-Speech client for generating podcast audio
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    # Default voices (can be overridden)
    DEFAULT_VOICES = {
        "raj": VoiceConfig(
            voice_id="pNInz6obpgDQGcFmaJgB",  # Adam - deep, warm male voice
            name="Adam",
            stability=0.5,
            similarity_boost=0.75,
        ),
        "priya": VoiceConfig(
            voice_id="EXAVITQu4vr4xnSDxMaL",  # Bella - warm female voice
            name="Bella",
            stability=0.5,
            similarity_boost=0.8,
        ),
    }

    def __init__(
        self,
        api_key: str,
        voice_raj: Optional[str] = None,
        voice_priya: Optional[str] = None,
        output_dir: str = "output/audio",
    ):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Configure voices
        self.voices = self.DEFAULT_VOICES.copy()
        if voice_raj:
            self.voices["raj"].voice_id = voice_raj
        if voice_priya:
            self.voices["priya"].voice_id = voice_priya

    async def generate_speech(
        self,
        text: str,
        speaker: str,
        output_filename: Optional[str] = None,
        model_id: str = "eleven_multilingual_v2",
    ) -> Optional[bytes]:
        """Generate speech for a single text segment"""

        voice_config = self.voices.get(speaker.lower())
        if not voice_config:
            logger.error(f"Unknown speaker: {speaker}")
            return None

        url = f"{self.BASE_URL}/text-to-speech/{voice_config.voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": voice_config.stability,
                "similarity_boost": voice_config.similarity_boost,
                "style": voice_config.style,
                "use_speaker_boost": voice_config.use_speaker_boost,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=60.0,
                )

                if response.status_code == 200:
                    audio_data = response.content

                    # Save to file if filename provided
                    if output_filename:
                        output_path = self.output_dir / output_filename
                        with open(output_path, "wb") as f:
                            f.write(audio_data)
                        logger.info(f"Saved audio: {output_path}")

                    return audio_data
                else:
                    logger.error(
                        f"TTS request failed: {response.status_code} - {response.text}"
                    )
                    return None

        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return None

    async def generate_episode_audio(
        self,
        script_blocks: list[dict],
        episode_id: str,
        parallel_requests: int = 3,
    ) -> list[AudioSegment]:
        """
        Generate audio for all blocks in a podcast script
        Uses parallel requests for efficiency
        """
        audio_segments = []

        # Create episode directory
        episode_dir = self.output_dir / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)

        # Process in batches to avoid rate limits
        semaphore = asyncio.Semaphore(parallel_requests)

        async def process_block(index: int, block: dict) -> Optional[AudioSegment]:
            async with semaphore:
                speaker = block.get("speaker", "raj")
                text = block.get("text", "")
                section = block.get("section", "segment")

                if not text:
                    return None

                filename = f"{index:03d}_{section}_{speaker}.mp3"
                audio_data = await self.generate_speech(
                    text=text,
                    speaker=speaker,
                    output_filename=f"{episode_id}/{filename}",
                )

                if audio_data:
                    # Estimate duration (~150 words per minute)
                    word_count = len(text.split())
                    duration_ms = int((word_count / 150) * 60 * 1000)

                    return AudioSegment(
                        speaker=speaker,
                        text=text,
                        audio_path=str(episode_dir / filename),
                        duration_ms=duration_ms,
                    )
                return None

        # Generate all audio segments
        tasks = [
            process_block(i, block) for i, block in enumerate(script_blocks)
        ]
        results = await asyncio.gather(*tasks)

        audio_segments = [r for r in results if r is not None]
        logger.info(f"Generated {len(audio_segments)} audio segments for {episode_id}")

        return audio_segments

    async def combine_audio_segments(
        self,
        segments: list[AudioSegment],
        output_filename: str,
        add_music: bool = False,
    ) -> Optional[str]:
        """
        Combine audio segments into a single episode file
        Requires pydub for audio processing
        """
        try:
            from pydub import AudioSegment as PydubSegment

            combined = PydubSegment.empty()

            # Add a brief pause between segments
            pause = PydubSegment.silent(duration=300)  # 300ms pause

            for i, segment in enumerate(segments):
                try:
                    audio = PydubSegment.from_mp3(segment.audio_path)
                    combined += audio

                    # Add pause after each segment (except last)
                    if i < len(segments) - 1:
                        combined += pause

                except Exception as e:
                    logger.warning(f"Failed to add segment {segment.audio_path}: {e}")

            # Export combined audio
            output_path = self.output_dir / output_filename
            combined.export(output_path, format="mp3", bitrate="192k")

            logger.info(
                f"Combined episode saved: {output_path} "
                f"({len(combined) / 1000:.1f} seconds)"
            )

            return str(output_path)

        except ImportError:
            logger.error("pydub not installed. Cannot combine audio segments.")
            return None
        except Exception as e:
            logger.error(f"Failed to combine audio: {e}")
            return None

    async def get_available_voices(self) -> list[dict]:
        """Get list of available voices from ElevenLabs"""
        url = f"{self.BASE_URL}/voices"

        headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    voices = [
                        {
                            "voice_id": v["voice_id"],
                            "name": v["name"],
                            "category": v.get("category", "unknown"),
                            "labels": v.get("labels", {}),
                        }
                        for v in data.get("voices", [])
                    ]
                    return voices
                else:
                    logger.error(f"Failed to fetch voices: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Error fetching voices: {e}")
            return []

    async def get_usage_stats(self) -> Optional[dict]:
        """Get current usage statistics"""
        url = f"{self.BASE_URL}/user/subscription"

        headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "character_count": data.get("character_count", 0),
                        "character_limit": data.get("character_limit", 0),
                        "tier": data.get("tier", "unknown"),
                    }
                return None

        except Exception as e:
            logger.error(f"Error fetching usage: {e}")
            return None
