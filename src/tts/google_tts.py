"""
Google Cloud Text-to-Speech integration for podcast audio generation
A cost-effective alternative to ElevenLabs

Supports both API key and Service Account authentication.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import logging
import base64
import httpx

logger = logging.getLogger(__name__)


def _create_jwt(service_account_info: dict) -> str:
    """Create a JWT for service account authentication"""
    import hashlib
    import hmac

    # JWT Header
    header = {"alg": "RS256", "typ": "JWT"}

    # JWT Payload
    now = int(time.time())
    payload = {
        "iss": service_account_info["client_email"],
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,  # 1 hour
    }

    # Encode header and payload
    def b64_encode(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    header_b64 = b64_encode(header)
    payload_b64 = b64_encode(payload)
    unsigned = f"{header_b64}.{payload_b64}"

    # Sign with private key
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend

    private_key_pem = service_account_info["private_key"].encode()
    private_key = serialization.load_pem_private_key(
        private_key_pem, password=None, backend=default_backend()
    )

    signature = private_key.sign(unsigned.encode(), padding.PKCS1v15(), hashes.SHA256())
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    return f"{unsigned}.{signature_b64}"


async def _get_access_token_from_service_account(service_account_info: dict) -> Optional[str]:
    """Get an access token using service account credentials"""
    try:
        jwt = _create_jwt(service_account_info)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": jwt,
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            else:
                logger.error(f"Failed to get access token: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"Error getting access token: {e}")

    return None


class GoogleVoiceConfig(BaseModel):
    """Configuration for a Google TTS voice"""

    name: str  # e.g., "en-US-Journey-D"
    language_code: str  # e.g., "en-US"
    ssml_gender: str  # "MALE" or "FEMALE"
    speaking_rate: float = 1.0
    pitch: float = 0.0


class AudioSegment(BaseModel):
    """A generated audio segment"""

    speaker: str
    text: str
    section: Optional[str] = "unknown"
    audio_path: str
    duration_ms: int


class GoogleTTS:
    """
    Google Cloud Text-to-Speech client for generating podcast audio

    Uses the REST API directly to avoid heavy SDK dependencies.
    Supports both API key and service account authentication.
    """

    BASE_URL = "https://texttospeech.googleapis.com/v1"

    # Recommended voices for podcast-style content
    # Using Neural2 voices which are high quality and support all features
    DEFAULT_VOICES = {
        "raj": GoogleVoiceConfig(
            name="en-US-Neural2-D",  # Male, natural
            language_code="en-US",
            ssml_gender="MALE",
            speaking_rate=1.0,
            pitch=-2.0,  # Slightly deeper
        ),
        "priya": GoogleVoiceConfig(
            name="en-US-Neural2-F",  # Female, natural
            language_code="en-US",
            ssml_gender="FEMALE",
            speaking_rate=1.0,
            pitch=1.0,  # Slightly higher
        ),
    }

    # Alternative Indian English voices
    INDIAN_VOICES = {
        "raj": GoogleVoiceConfig(
            name="en-IN-Neural2-B",  # Indian English Male
            language_code="en-IN",
            ssml_gender="MALE",
            speaking_rate=0.95,
            pitch=-1.0,
        ),
        "priya": GoogleVoiceConfig(
            name="en-IN-Neural2-A",  # Indian English Female
            language_code="en-IN",
            ssml_gender="FEMALE",
            speaking_rate=0.95,
            pitch=1.0,
        ),
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        credentials_path: Optional[str] = None,
        service_account_info: Optional[dict] = None,
        use_indian_accent: bool = False,
        output_dir: str = "output/audio",
    ):
        """
        Initialize Google TTS client.

        Args:
            api_key: Google Cloud API key (simpler setup)
            credentials_path: Path to service account JSON file
            service_account_info: Service account dict (alternative to file)
            use_indian_accent: Use Indian English voices instead of US English
            output_dir: Directory for audio output
        """
        self.api_key = api_key
        self.credentials_path = credentials_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load service account from file if path provided
        self.service_account_info = service_account_info
        if credentials_path and not service_account_info:
            try:
                with open(credentials_path, "r") as f:
                    self.service_account_info = json.load(f)
                logger.info(f"Loaded service account from {credentials_path}")
            except Exception as e:
                logger.error(f"Failed to load service account: {e}")

        # Select voice set
        self.voices = self.INDIAN_VOICES if use_indian_accent else self.DEFAULT_VOICES

        # Token caching for service account auth
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0

    async def _get_auth_headers(self) -> dict:
        """Get authentication headers for API requests"""
        if self.api_key:
            return {}  # API key is passed as query param

        # Service account authentication
        if self.service_account_info:
            # Check if token is expired (refresh 5 min early)
            if not self.access_token or time.time() > self.token_expiry - 300:
                self.access_token = await _get_access_token_from_service_account(
                    self.service_account_info
                )
                self.token_expiry = time.time() + 3600  # 1 hour

            if self.access_token:
                return {"Authorization": f"Bearer {self.access_token}"}

        return {}

    def _get_auth_params(self) -> dict:
        """Get authentication query parameters"""
        if self.api_key:
            return {"key": self.api_key}
        return {}  # Service account uses headers, not params

    async def generate_speech(
        self,
        text: str,
        speaker: str,
        output_filename: Optional[str] = None,
        audio_encoding: str = "MP3",
    ) -> Optional[bytes]:
        """
        Generate speech for a single text segment.

        Args:
            text: Text to synthesize
            speaker: Speaker name ("raj" or "priya")
            output_filename: Optional filename to save audio
            audio_encoding: Audio format (MP3, LINEAR16, OGG_OPUS)

        Returns:
            Audio bytes if successful, None otherwise
        """
        voice_config = self.voices.get(speaker.lower())
        if not voice_config:
            logger.error(f"Unknown speaker: {speaker}")
            return None

        url = f"{self.BASE_URL}/text:synthesize"

        # Build request payload
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": voice_config.language_code,
                "name": voice_config.name,
                "ssmlGender": voice_config.ssml_gender,
            },
            "audioConfig": {
                "audioEncoding": audio_encoding,
                "speakingRate": voice_config.speaking_rate,
                "pitch": voice_config.pitch,
                "effectsProfileId": ["headphone-class-device"],  # Optimize for headphones
            },
        }

        headers = await self._get_auth_headers()
        headers["Content-Type"] = "application/json"
        params = self._get_auth_params()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    params=params,
                    timeout=60.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    # Audio is returned as base64-encoded string
                    audio_content = base64.b64decode(data["audioContent"])

                    # Save to file if filename provided
                    if output_filename:
                        output_path = self.output_dir / output_filename
                        with open(output_path, "wb") as f:
                            f.write(audio_content)
                        logger.info(f"Saved audio: {output_path}")

                    return audio_content
                else:
                    error_msg = response.text
                    logger.error(f"TTS request failed: {response.status_code} - {error_msg}")
                    return None

        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            return None

    async def generate_speech_ssml(
        self,
        ssml: str,
        speaker: str,
        output_filename: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Generate speech from SSML markup for more control.

        SSML allows adding pauses, emphasis, etc:
        <speak>
            Hello <break time="500ms"/> world!
            <emphasis level="strong">Important</emphasis>
        </speak>
        """
        voice_config = self.voices.get(speaker.lower())
        if not voice_config:
            return None

        url = f"{self.BASE_URL}/text:synthesize"

        payload = {
            "input": {"ssml": ssml},
            "voice": {
                "languageCode": voice_config.language_code,
                "name": voice_config.name,
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": voice_config.speaking_rate,
                "pitch": voice_config.pitch,
            },
        }

        params = self._get_auth_params()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    params=params,
                    timeout=60.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    audio_content = base64.b64decode(data["audioContent"])

                    if output_filename:
                        output_path = self.output_dir / output_filename
                        with open(output_path, "wb") as f:
                            f.write(audio_content)

                    return audio_content

        except Exception as e:
            logger.error(f"SSML TTS error: {e}")

        return None

    async def generate_episode_audio(
        self,
        script_blocks: list[dict],
        episode_id: str,
        parallel_requests: int = 5,  # Google allows more parallelism
    ) -> list[AudioSegment]:
        """
        Generate audio for all blocks in a podcast script.

        Args:
            script_blocks: List of {speaker, text, section} dicts
            episode_id: Unique episode identifier
            parallel_requests: Number of concurrent API calls

        Returns:
            List of AudioSegment objects with paths to generated audio
        """
        audio_segments = []

        # Create episode directory
        episode_dir = self.output_dir / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)

        # Process in parallel with semaphore
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
                        section=section,
                        audio_path=str(episode_dir / filename),
                        duration_ms=duration_ms,
                    )
                return None

        # Generate all segments
        tasks = [process_block(i, block) for i, block in enumerate(script_blocks)]
        results = await asyncio.gather(*tasks)

        audio_segments = [r for r in results if r is not None]
        logger.info(f"Generated {len(audio_segments)} audio segments for {episode_id}")

        return audio_segments

    async def combine_audio_segments(
        self,
        segments: list[AudioSegment],
        output_filename: str,
    ) -> Optional[str]:
        """Combine audio segments into a single episode file"""
        try:
            from pydub import AudioSegment as PydubSegment

            combined = PydubSegment.empty()
            pause = PydubSegment.silent(duration=400)  # 400ms pause between speakers

            for i, segment in enumerate(segments):
                try:
                    audio = PydubSegment.from_mp3(segment.audio_path)
                    combined += audio

                    if i < len(segments) - 1:
                        combined += pause

                except Exception as e:
                    logger.warning(f"Failed to add segment: {e}")

            output_path = self.output_dir / output_filename
            combined.export(output_path, format="mp3", bitrate="192k")

            logger.info(f"Combined episode: {output_path} ({len(combined)/1000:.1f}s)")
            return str(output_path)

        except ImportError:
            logger.error("pydub not installed")
            return None
        except Exception as e:
            logger.error(f"Failed to combine audio: {e}")
            return None

    async def combine_segments_by_section(
        self,
        segments: list[AudioSegment],
        episode_id: str,
    ) -> dict[str, str]:
        """
        Combine audio segments into separate files per section.
        Returns dict mapping section_id -> file_path
        """
        from collections import defaultdict
        
        # Group segments
        grouped = defaultdict(list)
        for seg in segments:
            # Clean section id to be safe filename
            safe_section = "".join(c for c in (seg.section or "unknown") if c.isalnum() or c in ('_', '-'))
            grouped[safe_section].append(seg)
            
        results = {}
        
        # Combine each group
        for section, group_segments in grouped.items():
            # Ensure unique filenames for sections with same name but different order? 
            # In PodcastScript, topic_ids should be unique segments.
            # But just in case, intro and outro are unique.
            filename = f"{episode_id}_{section}.mp3"
            path = await self.combine_audio_segments(group_segments, filename)
            if path:
                results[section] = path
                
        return results

    async def list_available_voices(self, language_code: str = "en") -> list[dict]:
        """List available voices for a language"""
        url = f"{self.BASE_URL}/voices"
        params = self._get_auth_params()
        params["languageCode"] = language_code

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    voices = []
                    for voice in data.get("voices", []):
                        voices.append({
                            "name": voice["name"],
                            "language_codes": voice["languageCodes"],
                            "gender": voice["ssmlGender"],
                            "natural_sample_rate": voice.get("naturalSampleRateHertz"),
                        })
                    return voices

        except Exception as e:
            logger.error(f"Error listing voices: {e}")

        return []

    def get_cost_estimate(self, character_count: int) -> dict:
        """
        Estimate cost for generating audio.

        Google TTS Pricing (as of 2024):
        - Standard voices: Free up to 4M chars/month, then $4/1M chars
        - WaveNet voices: Free up to 1M chars/month, then $16/1M chars
        - Neural2 voices: Free up to 1M chars/month, then $16/1M chars
        - Journey voices: $30/1M chars (no free tier)
        """
        return {
            "characters": character_count,
            "standard_cost": max(0, (character_count - 4_000_000) / 1_000_000 * 4),
            "wavenet_cost": max(0, (character_count - 1_000_000) / 1_000_000 * 16),
            "neural2_cost": max(0, (character_count - 1_000_000) / 1_000_000 * 16),
            "journey_cost": character_count / 1_000_000 * 30,
            "note": "Journey voices have the best quality but cost more",
        }
