"""
Audio Mixer Module
Responsible for mixing speech with background music and sound effects.
"""

import os
import random
from pathlib import Path
from typing import Optional, List
import logging
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class AudioMixer:
    """
    Mixer for combining speech segments with background music and effects.
    """
    
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = Path(assets_dir)
        self.music_dir = self.assets_dir / "music"
        self.sfx_dir = self.assets_dir / "sfx"
        
        # Ensure directories exist
        self.music_dir.mkdir(parents=True, exist_ok=True)
        self.sfx_dir.mkdir(parents=True, exist_ok=True)

    def mix_episode(
        self,
        speech_segments: List[str],
        output_path: str,
        bg_music: Optional[str] = None,
        transition_sfx: Optional[str] = None,
        fade_in: int = 2000,
        fade_out: int = 3000,
        ducking_volume: int = -12  # volume reduction for music when speaking (dB)
    ) -> Optional[str]:
        """
        Mixes a list of speech audio files into a single episode with BGM.
        
        Args:
            speech_segments: List of paths to speech audio files (mp3/wav)
            output_path: Path to save the final mix
            bg_music: Filename of music in assets/music (or 'random')
            transition_sfx: Filename of SFX for transitions (optional)
            
        Returns:
            Path to the mixed audio file
        """
        try:
            # 1. Load all speech segments
            full_speech = AudioSegment.empty()
            pause = AudioSegment.silent(duration=500) # 0.5s pause between segments
            
            # Optionally load transition sound
            sfx = None
            if transition_sfx:
                sfx_path = self.sfx_dir / transition_sfx
                if sfx_path.exists():
                    sfx = AudioSegment.from_file(sfx_path)
            
            for i, seg_path in enumerate(speech_segments):
                try:
                    seg = AudioSegment.from_file(seg_path)
                    
                    # Add SFX between major segments if provided (you'd need logic to know which are major)
                    # For now, just simple concatenation
                    full_speech += seg
                    if i < len(speech_segments) - 1:
                        full_speech += pause
                        
                except Exception as e:
                    logger.warning(f"Failed to load segment {seg_path}: {e}")
                    continue
            
            if len(full_speech) == 0:
                logger.error("No speech audio loaded")
                return None

            # 2. handle Background Music
            if not bg_music:
                # No music, just return speech
                full_speech.export(output_path, format="mp3", bitrate="192k")
                return output_path
                
            # Pick music file
            music_file = None
            if bg_music == 'random':
                files = list(self.music_dir.glob("*.mp3")) + list(self.music_dir.glob("*.wav"))
                if files:
                    music_file = random.choice(files)
            else:
                music_file = self.music_dir / bg_music
                
            if not music_file or not music_file.exists():
                logger.warning(f"Music file not found: {bg_music}")
                full_speech.export(output_path, format="mp3", bitrate="192k")
                return output_path

            # Load music
            music = AudioSegment.from_file(music_file)
            
            # Loop music if shorter than speech
            target_duration = len(full_speech) + fade_out + 1000
            while len(music) < target_duration:
                music += music
                
            # Trim to length (plus a bit for fade out)
            music = music[:target_duration]
            
            # Apply ducking (lower volume)
            # A simple approach: just lower the whole track volume. 
            # Advanced 'sidechain' ducking requires segment-aware volume automation, 
            # which is complex for now. We'll stick to a bed level.
            music = music - abs(ducking_volume) 
            
            # Fade in/out
            music = music.fade_in(fade_in).fade_out(fade_out)
            
            # Overlay
            # position=0 means start at beginning
            final_mix = music.overlay(full_speech, position=500) # Start speech 0.5s in
            
            # Export
            try:
                final_mix.export(output_path, format="mp3", bitrate="192k")
                logger.info(f"Mixed audio saved to {output_path}")
                return output_path
            except (FileNotFoundError, OSError) as e:
                # Fallback to WAV if ffmpeg is missing
                logger.warning(f"MP3 export failed (ffmpeg missing?), falling back to WAV: {e}")
                wav_path = str(Path(output_path).with_suffix('.wav'))
                final_mix.export(wav_path, format="wav")
                return wav_path

        except Exception as e:
            logger.error(f"Mixing failed: {e}")
            return None
