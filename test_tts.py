"""Debug TTS generation."""

import os
import base64
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

# Check API key
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
print(f"API Key found: {bool(api_key)}")

# Create client
client = genai.Client(api_key=api_key)

# Test text
text = "Hello, welcome to Tech Daily. Today we're covering some fascinating news about AI and technology."

# First, try the official TTS approach from Gemini docs
print("\nAttempting TTS generation...")

try:
    # Using gemini-2.5-flash-preview-tts model
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

    print(f"Response type: {type(response)}")
    print(f"Candidates: {len(response.candidates)}")

    if response.candidates:
        content = response.candidates[0].content
        print(f"Parts: {len(content.parts)}")

        for i, part in enumerate(content.parts):
            print(f"\nPart {i}:")
            print(f"  Type: {type(part)}")
            if hasattr(part, 'inline_data'):
                print(f"  Has inline_data: {part.inline_data is not None}")
                if part.inline_data:
                    print(f"  MIME type: {part.inline_data.mime_type}")
                    print(f"  Data length: {len(part.inline_data.data) if part.inline_data.data else 0}")

                    # Try to decode and save
                    audio_data = base64.b64decode(part.inline_data.data)
                    print(f"  Decoded length: {len(audio_data)} bytes")

                    with open("test_output.wav", "wb") as f:
                        f.write(audio_data)
                    print(f"  Saved to test_output.wav")
            elif hasattr(part, 'text'):
                print(f"  Text: {part.text[:100]}...")

except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Also try alternate model
print("\n\nTrying alternate model gemini-2.0-flash...")
try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"Generate speech audio for: {text}",
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

    print(f"Response candidates: {len(response.candidates)}")
    if response.candidates:
        for i, part in enumerate(response.candidates[0].content.parts):
            if hasattr(part, 'inline_data') and part.inline_data:
                audio_data = base64.b64decode(part.inline_data.data)
                print(f"Got audio: {len(audio_data)} bytes")
                with open("test_output2.wav", "wb") as f:
                    f.write(audio_data)
                print("Saved to test_output2.wav")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
