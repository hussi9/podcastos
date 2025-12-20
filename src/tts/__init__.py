"""Text-to-Speech modules"""

from .elevenlabs_tts import ElevenLabsTTS
from .google_tts import GoogleTTS

__all__ = ["ElevenLabsTTS", "GoogleTTS"]
