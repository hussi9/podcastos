"""Generate audio from existing podcast script JSON."""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from src.intelligence.synthesis.script_generator import PodcastScript, ScriptSegment
from src.intelligence.audio.tts_generator import TTSGenerator
from src.intelligence.audio.audio_stitcher import AudioStitcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def generate_audio_from_script(script_path: str, output_dir: str = "./output"):
    """Generate audio from a saved podcast script JSON."""

    # Load script
    logger.info(f"Loading script from {script_path}")
    with open(script_path, "r") as f:
        script_data = json.load(f)

    # Parse dates back
    script_data["episode_date"] = datetime.fromisoformat(script_data["episode_date"])
    script_data["generated_at"] = datetime.fromisoformat(script_data["generated_at"])

    # Parse segments
    script_data["intro"] = ScriptSegment(**script_data["intro"])
    script_data["segments"] = [ScriptSegment(**s) for s in script_data["segments"]]
    script_data["outro"] = ScriptSegment(**script_data["outro"])

    script = PodcastScript(**script_data)

    logger.info(f"Loaded script: {script.title}")
    logger.info(f"Segments: {len(script.segments)}")
    logger.info(f"Words: {script.word_count}")

    # Generate audio
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing TTS generator...")
    tts = TTSGenerator(output_dir=str(output_path), voice="Kore")

    logger.info("Generating audio (this may take a few minutes)...")
    audio_episode = await tts.generate_episode_audio(script)

    # Stitch segments
    logger.info("Stitching audio segments...")
    stitcher = AudioStitcher(output_dir=str(output_path))
    audio_path = stitcher.stitch_episode(audio_episode)
    manifest_path = stitcher.save_manifest(audio_episode)

    print("\n" + "=" * 60)
    print("AUDIO GENERATION COMPLETE")
    print("=" * 60)
    print(f"Episode: {script.title}")
    print(f"Duration: ~{audio_episode.total_duration_seconds / 60:.1f} minutes")
    print(f"Segments: {len(audio_episode.segments) + 2}")  # +2 for intro/outro
    print(f"\nAudio file: {audio_path}")
    print(f"Manifest: {manifest_path}")
    print("=" * 60 + "\n")

    # List individual segment files
    print("Individual segment files:")
    episode_dir = output_path / script.id
    if episode_dir.exists():
        for wav_file in sorted(episode_dir.glob("*.wav")):
            print(f"  - {wav_file}")

    return audio_path


if __name__ == "__main__":
    import sys

    script_path = sys.argv[1] if len(sys.argv) > 1 else "./output/human_podcast_script.json"

    audio_path = asyncio.run(generate_audio_from_script(script_path))
    print(f"\n🎧 Your podcast audio is ready at: {audio_path}")
