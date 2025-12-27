"""
Main podcast generation orchestrator
Coordinates content aggregation, script generation, and audio synthesis
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import logging

from .aggregators import ContentRanker, PodcastTopic
from .generators import ScriptGenerator, EnhancedScriptGenerator, PodcastScript, EditorialReviewer, EpisodeHistoryTracker
from .research import TopicResearcher
from .tts import ElevenLabsTTS, GoogleTTS

logger = logging.getLogger(__name__)


class SegmentMetadata(BaseModel):
    """Metadata for a distinct audio segment (topic)"""
    
    sequence: int
    topic_id: str
    title: str
    audio_path: str
    duration_seconds: float
    transcript: Optional[str] = None


class EpisodeMetadata(BaseModel):
    """Metadata for a generated episode"""

    episode_id: str
    title: str
    description: str
    date: str
    duration_seconds: int
    topics: list[str]
    segments: list[SegmentMetadata] = []
    audio_url: Optional[str] = None
    script_path: Optional[str] = None
    audio_path: Optional[str] = None
    generated_at: str


class PodcastEngine:
    """
    Main orchestrator for podcast generation
    """

    def __init__(
        self,
        gemini_api_key: str,
        elevenlabs_api_key: Optional[str] = None,
        google_tts_api_key: Optional[str] = None,
        tts_provider: str = "google",  # "google" or "elevenlabs"
        reddit_client_id: Optional[str] = None,
        reddit_client_secret: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        voice_raj: Optional[str] = None,
        voice_priya: Optional[str] = None,
        use_indian_accent: bool = False,
        output_dir: str = "output",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tts_provider = tts_provider

        # Initialize components
        self.content_ranker = ContentRanker(
            reddit_client_id=reddit_client_id,
            reddit_client_secret=reddit_client_secret,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
        )

        self.script_generator = ScriptGenerator(api_key=gemini_api_key)
        self.enhanced_script_generator = EnhancedScriptGenerator(api_key=gemini_api_key)
        self.topic_researcher = TopicResearcher(api_key=gemini_api_key)
        self.editorial_reviewer = EditorialReviewer(api_key=gemini_api_key)
        self.episode_history = EpisodeHistoryTracker(history_file=str(self.output_dir / "episode_history.json"))

        # Initialize TTS provider based on configuration
        if tts_provider == "elevenlabs" and elevenlabs_api_key:
            self.tts = ElevenLabsTTS(
                api_key=elevenlabs_api_key,
                voice_raj=voice_raj,
                voice_priya=voice_priya,
                output_dir=str(self.output_dir / "audio"),
            )
            logger.info("Using ElevenLabs TTS")
        elif google_tts_api_key or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            self.tts = GoogleTTS(
                api_key=google_tts_api_key,
                credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
                use_indian_accent=use_indian_accent,
                output_dir=str(self.output_dir / "audio"),
            )
            logger.info(f"Using Google TTS (Indian accent: {use_indian_accent})")
        else:
            raise ValueError("No TTS credentials provided. Set GOOGLE_TTS_API_KEY, GOOGLE_APPLICATION_CREDENTIALS, or ELEVENLABS_API_KEY")

        # Episode storage
        self.episodes_dir = self.output_dir / "episodes"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)

        self.scripts_dir = self.output_dir / "scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

    async def generate_episode(
        self,
        target_date: Optional[datetime] = None,
        topic_count: int = 5,
        target_duration_minutes: int = 12,
        generate_audio: bool = True,
    ) -> EpisodeMetadata:
        """
        Generate a complete podcast episode

        Args:
            target_date: Date for the episode (defaults to today)
            topic_count: Number of topics to include
            target_duration_minutes: Target episode length
            generate_audio: Whether to generate TTS audio

        Returns:
            EpisodeMetadata with paths and information about the generated episode
        """
        if not target_date:
            target_date = datetime.now()

        episode_id = f"dd-{target_date.strftime('%Y%m%d')}"
        logger.info(f"Starting episode generation: {episode_id}")

        # Step 1: Gather and rank content
        logger.info("Step 1: Gathering content from sources...")
        topics = await self.content_ranker.get_ranked_topics(limit=topic_count)
        logger.info(f"Found {len(topics)} topics to cover")

        if not topics:
            logger.warning("No topics found! Generating minimal episode.")
            topics = [
                PodcastTopic(
                    id="general",
                    title="Community Updates",
                    summary="General updates for the desi community",
                    category="community",
                    score=1.0,
                    sources=["general"],
                    source_count=1,
                    key_points=["Stay connected with your community"],
                )
            ]

        # Step 2: Generate script
        logger.info("Step 2: Generating script with AI...")
        script = await self.script_generator.generate_script(
            topics=topics,
            episode_date=target_date,
            target_duration_minutes=target_duration_minutes,
        )

        # Save script
        script_path = self.scripts_dir / f"{episode_id}.json"
        with open(script_path, "w") as f:
            f.write(script.model_dump_json(indent=2))
        logger.info(f"Script saved: {script_path}")

        # Step 3: Generate audio (if enabled)
        audio_path = None
        segments_map = {}
        segment_durations = {}

        if generate_audio:
            logger.info("Step 3: Generating audio with TTS...")
            script_blocks = script.to_ssml_blocks()

            audio_segments = await self.tts.generate_episode_audio(
                script_blocks=script_blocks,
                episode_id=episode_id,
            )

            if audio_segments:
                # Calculate durations per section
                for seg in audio_segments:
                    sec = seg.section or "unknown"
                    segment_durations[sec] = segment_durations.get(sec, 0.0) + (seg.duration_ms / 1000.0)

                # Combine audio by section (for interactive player)
                if hasattr(self.tts, 'combine_segments_by_section'):
                    segments_map = await self.tts.combine_segments_by_section(
                        audio_segments,
                        episode_id
                    )

                # Combine into single file (legacy support + RSS)
                # Use Mixer if BGM is enabled (for now, simplistic)
                from src.audio.mixer import AudioMixer
                mixer = AudioMixer(assets_dir="assets")
                
                # We need a list of file paths. 
                # audio_segments has logic, let's extract paths
                segment_paths = [seg.audio_path for seg in audio_segments]
                
                # Check for music preference (could come from profile/arguments)
                # For demo, we'll try to find a file, else fall back to simple stitch
                
                mixed_path = mixer.mix_episode(
                    speech_segments=segment_paths,
                    output_path=str(self.episodes_dir / f"{episode_id}.mp3"),
                    bg_music='random', # Try to find random music
                    ducking_volume=-10
                )
                
                if mixed_path:
                    audio_path = mixed_path
                else:
                    # Fallback to simple stitch if mix failed
                    audio_path = await self.tts.combine_audio_segments(
                        segments=audio_segments,
                        output_filename=f"{episode_id}.mp3",
                    )

        # Step 4: Generate metadata
        logger.info("Step 4: Saving episode metadata...")
        description = self._generate_description(topics, script)

        # Build SegmentMetadata list
        segment_list = []
        
        # 1. Intro
        if "intro" in segments_map:
            segment_list.append(SegmentMetadata(
                sequence=0,
                topic_id="intro",
                title="Introduction",
                audio_path=segments_map["intro"],
                duration_seconds=segment_durations.get("intro", 0.0)
            ))

        # 2. Main Segments
        for i, seg in enumerate(script.segments):
            if seg.topic_id in segments_map:
                segment_list.append(SegmentMetadata(
                    sequence=len(segment_list),
                    topic_id=seg.topic_id,
                    title=seg.topic_title,
                    audio_path=segments_map[seg.topic_id],
                    duration_seconds=segment_durations.get(seg.topic_id, seg.duration_estimate)
                ))

        # 3. Outro
        if "outro" in segments_map:
            segment_list.append(SegmentMetadata(
                sequence=len(segment_list),
                topic_id="outro",
                title="Closing",
                audio_path=segments_map["outro"],
                duration_seconds=segment_durations.get("outro", 0.0)
            ))

        metadata = EpisodeMetadata(
            episode_id=episode_id,
            title=script.episode_title,
            description=description,
            date=target_date.isoformat(),
            duration_seconds=script.duration_estimate,
            topics=[t.title for t in topics],
            segments=segment_list,
            script_path=str(script_path),
            audio_path=audio_path,
            generated_at=datetime.now().isoformat(),
        )

        # Save metadata
        metadata_path = self.episodes_dir / f"{episode_id}.json"
        with open(metadata_path, "w") as f:
            f.write(metadata.model_dump_json(indent=2))

        logger.info(f"Episode generation complete: {episode_id}")
        return metadata

    async def generate_enhanced_episode(
        self,
        target_date: Optional[datetime] = None,
        topic_count: int = 5,
        target_duration_minutes: int = 15,
        generate_audio: bool = True,
    ) -> EpisodeMetadata:
        """
        Generate an enhanced podcast episode with deep research.

        This uses Gemini with Google Search to:
        1. Research each topic deeply for facts, statistics, context
        2. Generate more natural, fact-rich dialogue
        3. Include historical context and future implications
        """
        if not target_date:
            target_date = datetime.now()

        episode_id = f"dd-{target_date.strftime('%Y%m%d')}"
        logger.info(f"Starting ENHANCED episode generation: {episode_id}")

        # Step 1: Gather and rank content
        logger.info("Step 1: Gathering content from sources...")
        topics = await self.content_ranker.get_ranked_topics(limit=topic_count)
        logger.info(f"Found {len(topics)} topics to cover")

        if not topics:
            logger.warning("No topics found!")
            return await self.generate_episode(target_date, topic_count, target_duration_minutes, generate_audio)

        # Step 2: Deep research each topic with Gemini + Google Search
        logger.info("Step 2: Deep researching topics with AI + Google Search...")
        researched_topics = await self.topic_researcher.research_all_topics(topics)
        logger.info(f"Completed deep research on {len(researched_topics)} topics")

        # Log research quality
        for rt in researched_topics:
            facts_count = len(rt.key_facts)
            experts_count = len(rt.expert_opinions)
            logger.info(f"  - {rt.topic_title}: {facts_count} facts, {experts_count} expert opinions")

        # Get continuity context from previous episodes
        continuity_context = self.episode_history.get_continuity_context()
        if continuity_context:
            logger.info("Including continuity context from previous episodes")

        # Step 3: Generate enhanced script with researched content
        logger.info("Step 3: Generating natural, fact-rich script...")
        script = await self.enhanced_script_generator.generate_script(
            researched_topics=researched_topics,
            episode_date=target_date,
            target_duration_minutes=target_duration_minutes,
            continuity_context=continuity_context,
        )

        # Step 3.5: Editorial review for flow and engagement
        logger.info("Step 3.5: Editorial review for flow and engagement...")
        script_data = json.loads(script.model_dump_json())
        previous_episodes = self.episode_history.get_recent_episodes(3)
        refined_data = await self.editorial_reviewer.review_script(script_data, previous_episodes)

        # Rebuild script from refined data
        from .generators import DialogueLine, PodcastSegment
        script = PodcastScript(
            episode_id=refined_data.get("episode_id", script.episode_id),
            episode_title=refined_data.get("episode_title", script.episode_title),
            episode_date=refined_data.get("episode_date", script.episode_date),
            duration_estimate=refined_data.get("duration_estimate", script.duration_estimate),
            intro=[DialogueLine(**line) for line in refined_data.get("intro", [])],
            segments=[
                PodcastSegment(
                    topic_id=seg.get("topic_id", "unknown"),
                    topic_title=seg.get("topic_title", "Discussion"),
                    duration_estimate=seg.get("duration_estimate", 120),
                    dialogue=[DialogueLine(**line) for line in seg.get("dialogue", [])]
                )
                for seg in refined_data.get("segments", [])
            ],
            outro=[DialogueLine(**line) for line in refined_data.get("outro", [])],
        )
        logger.info("Editorial review complete")

        # Save script
        script_path = self.scripts_dir / f"{episode_id}.json"
        with open(script_path, "w") as f:
            f.write(script.model_dump_json(indent=2))
        logger.info(f"Script saved: {script_path}")

        # Save research data too (for reference)
        research_path = self.scripts_dir / f"{episode_id}_research.json"
        research_data = [rt.model_dump() for rt in researched_topics]
        with open(research_path, "w") as f:
            json.dump(research_data, f, indent=2)
        logger.info(f"Research saved: {research_path}")

        # Step 4: Generate audio (if enabled)
        audio_path = None
        segments_map = {}
        segment_durations = {}

        if generate_audio:
            logger.info("Step 4: Generating audio with TTS...")
            script_blocks = script.to_ssml_blocks()

            audio_segments = await self.tts.generate_episode_audio(
                script_blocks=script_blocks,
                episode_id=episode_id,
            )

            if audio_segments:
                for seg in audio_segments:
                    sec = seg.section or "unknown"
                    segment_durations[sec] = segment_durations.get(sec, 0.0) + (seg.duration_ms / 1000.0)

                if hasattr(self.tts, 'combine_segments_by_section'):
                    segments_map = await self.tts.combine_segments_by_section(
                        audio_segments,
                        episode_id
                    )

                from src.audio.mixer import AudioMixer
                mixer = AudioMixer(assets_dir="assets")
                segment_paths = [seg.audio_path for seg in audio_segments]
                
                mixed_path = mixer.mix_episode(
                    speech_segments=segment_paths,
                    output_path=str(self.episodes_dir / f"{episode_id}.mp3"),
                    bg_music='random',
                    ducking_volume=-10
                )
                
                if mixed_path:
                    audio_path = mixed_path
                else:
                    audio_path = await self.tts.combine_audio_segments(
                        segments=audio_segments,
                        output_filename=f"{episode_id}.mp3",
                    )

        # Step 5: Generate metadata
        logger.info("Step 5: Saving episode metadata...")
        description = self._generate_enhanced_description(researched_topics, script)

        # Build SegmentMetadata list
        segment_list = []
        if "intro" in segments_map:
            segment_list.append(SegmentMetadata(
                sequence=0,
                topic_id="intro",
                title="Introduction",
                audio_path=segments_map["intro"],
                duration_seconds=segment_durations.get("intro", 0.0)
            ))

        for i, seg in enumerate(script.segments):
            if seg.topic_id in segments_map:
                segment_list.append(SegmentMetadata(
                    sequence=len(segment_list),
                    topic_id=seg.topic_id,
                    title=seg.topic_title,
                    audio_path=segments_map[seg.topic_id],
                    duration_seconds=segment_durations.get(seg.topic_id, seg.duration_estimate)
                ))

        if "outro" in segments_map:
            segment_list.append(SegmentMetadata(
                sequence=len(segment_list),
                topic_id="outro",
                title="Closing",
                audio_path=segments_map["outro"],
                duration_seconds=segment_durations.get("outro", 0.0)
            ))

        metadata = EpisodeMetadata(
            episode_id=episode_id,
            title=script.episode_title,
            description=description,
            date=target_date.isoformat(),
            duration_seconds=script.duration_estimate,
            topics=[rt.topic_title for rt in researched_topics],
            segments=segment_list,
            script_path=str(script_path),
            audio_path=audio_path,
            generated_at=datetime.now().isoformat(),
        )

        metadata_path = self.episodes_dir / f"{episode_id}.json"
        with open(metadata_path, "w") as f:
            f.write(metadata.model_dump_json(indent=2))

        # Step 6: Track episode in history for future continuity
        key_facts = []
        for rt in researched_topics:
            key_facts.extend([f.fact for f in rt.key_facts[:2]])

        self.episode_history.add_episode(
            episode_id=episode_id,
            title=script.episode_title,
            date=target_date.isoformat(),
            topics=[rt.topic_title for rt in researched_topics],
            key_facts=key_facts[:10],
            summary=description[:500],
        )
        logger.info("Episode added to history tracker")

        logger.info(f"ENHANCED episode generation complete: {episode_id}")
        return metadata

    def _generate_enhanced_description(
        self, researched_topics, script: PodcastScript
    ) -> str:
        """Generate rich episode description with research highlights"""
        lines = [
            f"In today's in-depth episode of Desi Daily, Raj and Priya dive deep into:",
            "",
        ]

        for rt in researched_topics:
            lines.append(f"• {rt.topic_title}")
            # Add a key fact if available
            if rt.key_facts:
                lines.append(f"  - {rt.key_facts[0].fact}")

        lines.extend([
            "",
            "Featuring real statistics, expert opinions, historical context, and practical advice.",
            "",
            f"Episode duration: ~{script.duration_estimate // 60} minutes",
        ])

        return "\n".join(lines)

    async def generate_script_only(
        self,
        target_date: Optional[datetime] = None,
        topic_count: int = 5,
        target_duration_minutes: int = 12,
        subreddits: list[str] = None,
    ) -> PodcastScript:
        """Generate only the script (no audio)"""
        if not target_date:
            target_date = datetime.now()

        topics = await self.content_ranker.get_ranked_topics(limit=topic_count, subreddits=subreddits)

        script = await self.script_generator.generate_script(
            topics=topics,
            episode_date=target_date,
            target_duration_minutes=target_duration_minutes,
        )

        # Save script
        episode_id = f"dd-{target_date.strftime('%Y%m%d')}"
        script_path = self.scripts_dir / f"{episode_id}.json"
        with open(script_path, "w") as f:
            f.write(script.model_dump_json(indent=2))

        return script

    async def generate_audio_from_script(
        self, script_path: str
    ) -> Optional[str]:
        """Generate audio from an existing script file"""
        with open(script_path, "r") as f:
            script_data = json.load(f)

        script = PodcastScript(**script_data)
        script_blocks = script.to_ssml_blocks()

        audio_segments = await self.tts.generate_episode_audio(
            script_blocks=script_blocks,
            episode_id=script.episode_id,
        )

        if audio_segments:
            return await self.tts.combine_audio_segments(
                segments=audio_segments,
                output_filename=f"{script.episode_id}.mp3",
            )
        return None

    def _generate_description(
        self, topics: list[PodcastTopic], script: PodcastScript
    ) -> str:
        """Generate episode description for RSS feed"""
        lines = [
            f"In today's episode of Desi Daily, Raj and Priya discuss:",
            "",
        ]

        for topic in topics:
            status = ""
            if topic.is_breaking:
                status = " [BREAKING]"
            elif topic.is_trending:
                status = " [TRENDING]"
            lines.append(f"• {topic.title}{status}")

        lines.extend([
            "",
            "Tune in for practical advice, community insights, and everything "
            "you need to know as a South Asian in America.",
            "",
            f"Episode duration: ~{script.duration_estimate // 60} minutes",
        ])

        return "\n".join(lines)

    async def get_content_preview(self) -> dict:
        """Get a preview of today's content without generating"""
        topics = await self.content_ranker.get_ranked_topics(limit=5)

        return {
            "date": datetime.now().isoformat(),
            "topic_count": len(topics),
            "topics": [
                {
                    "title": t.title,
                    "category": t.category,
                    "score": t.score,
                    "is_breaking": t.is_breaking,
                    "is_trending": t.is_trending,
                    "sources": t.sources,
                    "key_points": t.key_points[:3],
                }
                for t in topics
            ],
        }

    def list_episodes(self) -> list[EpisodeMetadata]:
        """List all generated episodes"""
        episodes = []
        for meta_file in self.episodes_dir.glob("*.json"):
            with open(meta_file, "r") as f:
                data = json.load(f)
                episodes.append(EpisodeMetadata(**data))

        # Sort by date, newest first
        episodes.sort(key=lambda x: x.date, reverse=True)
        return episodes

    def get_episode(self, episode_id: str) -> Optional[EpisodeMetadata]:
        """Get a specific episode by ID"""
        meta_path = self.episodes_dir / f"{episode_id}.json"
        if meta_path.exists():
            with open(meta_path, "r") as f:
                return EpisodeMetadata(**json.load(f))
        return None


async def create_engine_from_env() -> PodcastEngine:
    """Create a PodcastEngine instance from environment variables"""
    from dotenv import load_dotenv
    load_dotenv()

    # Determine TTS provider (prefer Google if key available, as it's cheaper)
    google_key = os.getenv("GOOGLE_TTS_API_KEY")
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    tts_provider = os.getenv("TTS_PROVIDER", "google" if google_key else "elevenlabs")

    return PodcastEngine(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        google_tts_api_key=google_key,
        elevenlabs_api_key=elevenlabs_key,
        tts_provider=tts_provider,
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_SERVICE_KEY"),
        voice_raj=os.getenv("ELEVENLABS_VOICE_1"),
        voice_priya=os.getenv("ELEVENLABS_VOICE_2"),
        use_indian_accent=os.getenv("USE_INDIAN_ACCENT", "false").lower() == "true",
        output_dir=os.getenv("OUTPUT_DIR", "output"),
    )
