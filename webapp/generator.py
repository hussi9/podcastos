"""
Podcast Generator Integration.
Connects the webapp to the actual podcast generation pipeline.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from webapp.models import (
    PodcastProfile, Host, Episode, TopicHistory,
    TopicAvoidance, GenerationJob
)


class PodcastGeneratorIntegration:
    """Integrates webapp with podcast generation pipeline."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent / 'podcast_studio.db'
        self.engine = create_engine(f'sqlite:///{db_path}')
        self.Session = sessionmaker(bind=self.engine)

    def get_profile_context(self, profile_id: int) -> dict:
        """Get full context for script generation."""
        session = self.Session()
        try:
            profile = session.query(PodcastProfile).get(profile_id)
            if not profile:
                return None

            # Get hosts
            hosts = [
                {
                    'name': h.name,
                    'persona': h.persona,
                    'voice_name': h.voice_name,
                    'speaking_style': h.speaking_style,
                    'expertise_areas': h.expertise_areas or [],
                }
                for h in profile.hosts
            ]

            # Get recent topics (last 14 days)
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=14)

            recent_topics = session.query(TopicHistory).join(Episode).filter(
                Episode.profile_id == profile_id,
                Episode.date >= cutoff
            ).all()

            # Get avoided topics
            avoided = session.query(TopicAvoidance).filter_by(
                profile_id=profile_id,
                is_active=True
            ).all()

            # Get ongoing stories
            ongoing = session.query(TopicHistory).join(Episode).filter(
                Episode.profile_id == profile_id,
                TopicHistory.is_ongoing == True
            ).all()

            return {
                'profile': {
                    'name': profile.name,
                    'description': profile.description,
                    'target_audience': profile.target_audience,
                    'tone': profile.tone,
                    'language': profile.language,
                    'target_duration_minutes': profile.target_duration_minutes,
                    'topic_count': profile.topic_count,
                    'categories': profile.categories or [],
                },
                'hosts': hosts,
                'recent_topics': [
                    {
                        'title': t.title,
                        'category': t.category,
                        'summary': t.summary,
                        'key_points': t.key_points or [],
                        'facts_mentioned': t.facts_mentioned or [],
                        'date': t.created_at.isoformat() if t.created_at else None,
                    }
                    for t in recent_topics
                ],
                'topics_to_avoid': [
                    {
                        'keyword': a.keyword,
                        'reason': a.reason,
                        'type': a.avoidance_type,
                        'min_days_between': a.min_days_between,
                    }
                    for a in avoided
                ],
                'ongoing_stories': [
                    {
                        'title': o.title,
                        'summary': o.summary,
                        'follow_up_notes': o.follow_up_notes,
                    }
                    for o in ongoing
                ],
            }
        finally:
            session.close()

    def build_continuity_prompt(self, context: dict) -> str:
        """Build a prompt section for continuity with previous episodes."""
        lines = []

        # Recent topics to avoid repeating
        if context['recent_topics']:
            lines.append("TOPICS COVERED RECENTLY (avoid repeating):")
            for topic in context['recent_topics'][:10]:
                lines.append(f"  - {topic['title']} ({topic['date'][:10] if topic['date'] else 'Unknown'})")
                if topic['key_points']:
                    for point in topic['key_points'][:2]:
                        lines.append(f"    * {point[:80]}...")
            lines.append("")

        # Topics to explicitly avoid
        if context['topics_to_avoid']:
            lines.append("TOPICS TO AVOID OR REDUCE:")
            for topic in context['topics_to_avoid']:
                reason = f" - {topic['reason']}" if topic['reason'] else ""
                lines.append(f"  - {topic['keyword']} ({topic['type']}){reason}")
            lines.append("")

        # Ongoing stories to follow up on
        if context['ongoing_stories']:
            lines.append("ONGOING STORIES (consider following up):")
            for story in context['ongoing_stories']:
                lines.append(f"  - {story['title']}")
                if story['follow_up_notes']:
                    lines.append(f"    Notes: {story['follow_up_notes']}")
            lines.append("")

        return "\n".join(lines)

    def build_host_prompt(self, hosts: list) -> str:
        """Build prompt section describing the hosts."""
        lines = ["PODCAST HOSTS:"]

        for host in hosts:
            lines.append(f"\n{host['name']}:")
            lines.append(f"  Background: {host['persona']}")
            if host['speaking_style']:
                lines.append(f"  Speaking Style: {host['speaking_style']}")
            if host['expertise_areas']:
                lines.append(f"  Expertise: {', '.join(host['expertise_areas'])}")

        return "\n".join(lines)

    def save_episode(
        self,
        profile_id: int,
        episode_id: str,
        title: str,
        date: datetime,
        topics: list,
        script: str,
        audio_path: str = None,
        duration_seconds: int = None,
    ):
        """Save a generated episode to the database."""
        session = self.Session()
        try:
            episode = Episode(
                profile_id=profile_id,
                episode_id=episode_id,
                title=title,
                date=date,
                topics_covered=[t['title'] for t in topics],
                script=script,
                summary=self._generate_summary(topics),
                key_facts=self._extract_key_facts(topics),
                audio_path=audio_path,
                duration_seconds=duration_seconds,
                status='published',
            )
            session.add(episode)
            session.commit()

            # Save topic history
            for topic in topics:
                topic_history = TopicHistory(
                    episode_id=episode.id,
                    title=topic['title'],
                    category=topic.get('category'),
                    summary=topic.get('summary'),
                    key_points=topic.get('key_points', []),
                    facts_mentioned=topic.get('facts', []),
                    is_ongoing=topic.get('is_ongoing', False),
                    follow_up_notes=topic.get('follow_up_notes'),
                    importance_score=topic.get('importance', 0.5),
                )
                session.add(topic_history)

            session.commit()
            return episode.id

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def update_job_status(
        self,
        job_id: str,
        status: str = None,
        current_stage: str = None,
        progress: int = None,
        stage_completed: str = None,
        error: str = None,
        episode_id: int = None,
    ):
        """Update generation job status."""
        session = self.Session()
        try:
            job = session.query(GenerationJob).filter_by(job_id=job_id).first()
            if not job:
                return False

            if status:
                job.status = status
            if current_stage:
                job.current_stage = current_stage
            if progress is not None:
                job.progress_percent = progress
            if stage_completed:
                completed = job.stages_completed or []
                if stage_completed not in completed:
                    completed.append(stage_completed)
                job.stages_completed = completed
                # Remove from pending
                pending = job.stages_pending or []
                if stage_completed in pending:
                    pending.remove(stage_completed)
                job.stages_pending = pending
            if error:
                job.error_message = error
            if episode_id:
                job.episode_id = episode_id

            if status == 'running' and not job.started_at:
                job.started_at = datetime.utcnow()
            if status in ('completed', 'failed'):
                job.completed_at = datetime.utcnow()

            session.commit()
            return True
        finally:
            session.close()

    def _generate_summary(self, topics: list) -> str:
        """Generate episode summary from topics."""
        topic_titles = [t['title'] for t in topics]
        return f"Today's episode covers: {', '.join(topic_titles)}"

    def _extract_key_facts(self, topics: list) -> list:
        """Extract key facts from all topics."""
        facts = []
        for topic in topics:
            facts.extend(topic.get('facts', [])[:3])
        return facts[:10]


async def run_generation_pipeline(job_id: str, profile_id: int, options: dict = None):
    """
    Run the full podcast generation pipeline.
    This is called asynchronously when a generation job is started.
    """
    from dotenv import load_dotenv
    load_dotenv()

    integration = PodcastGeneratorIntegration()
    options = options or {}

    try:
        # Update status to running
        integration.update_job_status(job_id, status='running', current_stage='content_gathering', progress=0)

        # Get profile context
        context = integration.get_profile_context(profile_id)
        if not context:
            raise ValueError(f"Profile {profile_id} not found")

        # Stage 1: Content Gathering
        integration.update_job_status(job_id, current_stage='content_gathering', progress=10)

        from src.aggregators import ContentRanker
        ranker = ContentRanker(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_SERVICE_KEY"),
        )
        topics = await ranker.get_ranked_topics(limit=context['profile']['topic_count'])

        integration.update_job_status(job_id, stage_completed='content_gathering', progress=20)

        # Stage 2: Deep Research
        integration.update_job_status(job_id, current_stage='research', progress=25)

        from src.research import TopicResearcher
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and options.get('deep_research', True):
            researcher = TopicResearcher(api_key=gemini_key)
            researched_topics = await researcher.research_all_topics(topics)
        else:
            researched_topics = topics

        integration.update_job_status(job_id, stage_completed='research', progress=40)

        # Stage 3: Script Generation
        integration.update_job_status(job_id, current_stage='scripting', progress=45)

        # Build the full prompt with continuity
        continuity_prompt = integration.build_continuity_prompt(context)
        host_prompt = integration.build_host_prompt(context['hosts'])

        # Generate dialogue
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)

        # Build content for script generation
        content_text = build_content_text(researched_topics, context)

        script_prompt = f"""You are writing a podcast script for "{context['profile']['name']}".

{context['profile']['description']}

TARGET AUDIENCE: {context['profile']['target_audience']}
TONE: {context['profile']['tone']}
TARGET DURATION: {context['profile']['target_duration_minutes']} minutes

{host_prompt}

{continuity_prompt}

RULES:
1. Format as: "HostName: [dialogue]" on separate lines
2. Sound like smart friends having a real conversation
3. Include specific facts, statistics, and expert quotes
4. Show genuine emotions - frustration, hope, surprise, empathy
5. DO NOT use forced slang like "yaar", "na?", "accha"
6. Group related topics together with clear transitions
7. Start with a warm greeting, end with a hopeful takeaway

CONTENT TO DISCUSS:
{content_text}

Write the complete dialogue script:"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=script_prompt,
        )
        dialogue = response.text

        integration.update_job_status(job_id, stage_completed='scripting', progress=60)

        # Stage 4: Editorial Review
        if options.get('editorial_review', True):
            integration.update_job_status(job_id, current_stage='review', progress=65)
            # Optional: Add editorial review step
            integration.update_job_status(job_id, stage_completed='review', progress=75)
        else:
            integration.update_job_status(job_id, stage_completed='review', progress=75)

        # Stage 5: Audio Generation
        integration.update_job_status(job_id, current_stage='audio', progress=80)

        # Build speaker configs
        speaker_configs = []
        for host in context['hosts']:
            speaker_configs.append(
                types.SpeakerVoiceConfig(
                    speaker=host['name'],
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=host['voice_name'] or 'Puck',
                        )
                    )
                )
            )

        tts_prompt = f"""TTS the following podcast conversation:

{dialogue}"""

        audio_response = client.models.generate_content(
            model=options.get('tts_model', 'gemini-2.5-flash-preview-tts'),
            contents=tts_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=speaker_configs
                    )
                )
            )
        )

        # Save audio
        audio_data = audio_response.candidates[0].content.parts[0].inline_data.data
        today = datetime.now()
        episode_id = f"ep-{today.strftime('%Y%m%d')}"

        output_dir = Path(__file__).parent.parent / 'output' / 'audio'
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / f"{episode_id}.wav"

        import wave
        with wave.open(str(audio_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)

        integration.update_job_status(job_id, stage_completed='audio', progress=95)

        # Save episode to database
        topic_data = [
            {
                'title': t.title,
                'category': t.category,
                'summary': t.summary,
                'key_points': t.key_points or [],
                'facts': [],
            }
            for t in topics
        ]

        db_episode_id = integration.save_episode(
            profile_id=profile_id,
            episode_id=episode_id,
            title=f"{context['profile']['name']} - {today.strftime('%B %d, %Y')}",
            date=today,
            topics=topic_data,
            script=dialogue,
            audio_path=str(audio_path),
            duration_seconds=len(audio_data) // 48000,  # Rough estimate
        )

        # Complete
        integration.update_job_status(
            job_id,
            status='completed',
            progress=100,
            episode_id=db_episode_id
        )

        return db_episode_id

    except Exception as e:
        integration.update_job_status(job_id, status='failed', error=str(e))
        raise


def build_content_text(topics, context) -> str:
    """Build content text from topics for script generation."""
    lines = []
    for i, topic in enumerate(topics, 1):
        lines.append(f"## Topic {i}: {topic.title}")
        lines.append(f"Category: {topic.category}")
        if topic.summary:
            lines.append(f"Summary: {topic.summary}")
        if topic.key_points:
            lines.append("Key Points:")
            for point in topic.key_points:
                lines.append(f"  - {point}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    # Test the integration
    integration = PodcastGeneratorIntegration()
    context = integration.get_profile_context(1)
    if context:
        print(json.dumps(context, indent=2, default=str))
    else:
        print("No profile found")
