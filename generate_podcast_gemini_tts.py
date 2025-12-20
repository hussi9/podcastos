#!/usr/bin/env python3
"""
Generate podcast using Gemini 2.5 TTS with multi-speaker support.
This creates a natural-sounding podcast with two hosts discussing topics.
"""

import asyncio
import json
import os
import wave
import subprocess
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Voice assignments for our hosts
VOICES = {
    "Raj": "Orus",      # Male voice - warm, friendly
    "Priya": "Aoede",   # Female voice - expressive
}


def save_wav(filename: str, pcm_data: bytes, channels=1, rate=24000, sample_width=2):
    """Save PCM audio data as WAV file."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)


def convert_to_mp3(wav_path: str, mp3_path: str):
    """Convert WAV to MP3 using ffmpeg."""
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", wav_path,
            "-codec:a", "libmp3lame", "-qscale:a", "2",
            mp3_path
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e.stderr.decode()}")
        return False


async def generate_dialogue_script(content: str) -> str:
    """Use Gemini to generate a natural dialogue script from the content."""

    prompt = f"""You are writing a podcast script for "Desi Daily", a news podcast for South Asian immigrants in the USA.

Create a natural conversation between two hosts:
- Raj: Male host, came to US 12 years ago on H-1B, now green card holder in tech
- Priya: Female host, second-generation Indian-American

RULES:
1. Format EXACTLY as: "Raj: [dialogue]" or "Priya: [dialogue]" on separate lines
2. Make it sound like two smart friends having a real conversation
3. Include specific facts, statistics, and expert quotes from the content
4. Show genuine emotions - frustration, hope, surprise, empathy
5. DO NOT use forced slang like "yaar", "na?", "accha"
6. Group related topics together with clear transitions
7. Keep total dialogue under 8000 characters (about 10 minutes of audio)
8. Start with a warm greeting, end with a hopeful takeaway

Here is the content to discuss:

{content}

Write the complete dialogue script now:"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


async def generate_audio_from_dialogue(dialogue: str, output_path: str) -> bool:
    """Convert dialogue script to audio using Gemini 2.5 TTS."""

    print("Generating audio with Gemini 2.5 TTS...")
    print(f"Dialogue length: {len(dialogue)} characters")

    # Prepare the TTS prompt
    tts_prompt = f"""TTS the following podcast conversation between Raj and Priya:

{dialogue}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=tts_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker='Raj',
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=VOICES["Raj"],
                                    )
                                )
                            ),
                            types.SpeakerVoiceConfig(
                                speaker='Priya',
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=VOICES["Priya"],
                                    )
                                )
                            ),
                        ]
                    )
                )
            )
        )

        # Extract audio data
        audio_data = response.candidates[0].content.parts[0].inline_data.data

        # Save as WAV first
        wav_path = output_path.replace(".mp3", ".wav")
        save_wav(wav_path, audio_data)
        print(f"Saved WAV: {wav_path}")

        # Convert to MP3
        if convert_to_mp3(wav_path, output_path):
            print(f"Converted to MP3: {output_path}")
            # Remove WAV file
            os.remove(wav_path)
            return True
        else:
            print("MP3 conversion failed, keeping WAV file")
            return True

    except Exception as e:
        print(f"TTS generation error: {e}")
        return False


async def generate_full_podcast():
    """Full workflow: read content, generate dialogue, create audio."""

    print("=" * 60)
    print("DESI DAILY PODCAST GENERATOR")
    print("Using Gemini 2.5 TTS Multi-Speaker")
    print("=" * 60)

    # Read the content
    today = datetime.now().strftime("%Y%m%d")
    content_path = Path(f"output/notebooklm/desi-daily-{today}.txt")

    if not content_path.exists():
        print(f"Content file not found: {content_path}")
        print("Running export script first...")
        from export_for_notebooklm import export_topics_for_notebooklm
        await export_topics_for_notebooklm()

    with open(content_path, "r") as f:
        content = f.read()

    print(f"\n1. Loaded content: {len(content)} characters")

    # Generate dialogue script
    print("\n2. Generating dialogue script with Gemini...")
    dialogue = await generate_dialogue_script(content)

    # Save the script for reference
    script_path = Path(f"output/scripts/dd-{today}_gemini_dialogue.txt")
    script_path.parent.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w") as f:
        f.write(dialogue)
    print(f"   Saved dialogue script: {script_path}")
    print(f"   Dialogue length: {len(dialogue)} characters")

    # Generate audio
    print("\n3. Generating audio...")
    output_dir = Path("output/audio")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(output_dir / f"dd-{today}-gemini-tts.mp3")

    success = await generate_audio_from_dialogue(dialogue, output_path)

    if success:
        file_size = Path(output_path).stat().st_size / 1024 / 1024
        print(f"\n{'=' * 60}")
        print("PODCAST READY!")
        print(f"{'=' * 60}")
        print(f"File: {output_path}")
        print(f"Size: {file_size:.1f} MB")

        # Open the file
        subprocess.run(["open", output_path])

        return output_path
    else:
        print("\nFailed to generate podcast audio")
        return None


if __name__ == "__main__":
    asyncio.run(generate_full_podcast())
