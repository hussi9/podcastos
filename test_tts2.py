"""Debug TTS generation - proper handling."""

import os
import wave
import struct
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

text = "Hello, welcome to Tech Daily. Today we're covering some fascinating news about AI and technology. This is a test of the text to speech system."

print("Generating TTS...")

response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=text,
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Kore",
                ),
            ),
        ),
    ),
)

part = response.candidates[0].content.parts[0]
inline_data = part.inline_data

print(f"MIME type: {inline_data.mime_type}")
print(f"Raw data type: {type(inline_data.data)}")
print(f"Raw data length: {len(inline_data.data)}")

# The data might already be raw bytes, not base64
data = inline_data.data

# Check if it's bytes or string
if isinstance(data, str):
    print("Data is string, checking first 50 chars:", repr(data[:50]))
    # Try base64 decode
    import base64
    try:
        decoded = base64.b64decode(data)
        print(f"Base64 decoded length: {len(decoded)}")
        data = decoded
    except:
        print("Not valid base64")
else:
    print("Data is already bytes")

# Write raw PCM to WAV file
# L16 = Linear 16-bit, rate=24000
print(f"\nFinal audio data: {len(data)} bytes")
print(f"Duration estimate: {len(data) / (24000 * 2):.2f} seconds")

# Write as proper WAV
with wave.open("test_output_proper.wav", "wb") as wav_file:
    wav_file.setnchannels(1)  # Mono
    wav_file.setsampwidth(2)  # 16-bit = 2 bytes
    wav_file.setframerate(24000)  # 24kHz
    wav_file.writeframes(data)

print(f"Saved to test_output_proper.wav")

# Get file size
import os
size = os.path.getsize("test_output_proper.wav")
print(f"File size: {size} bytes")
