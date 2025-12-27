"""
Deep Integration Tests for Full Generation Flow
Tests the complete podcast generation pipeline with real database operations.
"""

import pytest
import os
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import threading


@pytest.mark.integration
class TestFullGenerationPipeline:
    """
    Tests the complete podcast generation pipeline from profile creation
    through episode publication.
    """

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, tmp_path):
        """Set up test environment with temp directories."""
        self.output_dir = tmp_path / "output"
        self.output_dir.mkdir()
        (self.output_dir / "scripts").mkdir()
        (self.output_dir / "audio").mkdir()
        (self.output_dir / "episodes").mkdir()

        # Set environment variables
        os.environ['GEMINI_API_KEY'] = 'test-key'
        os.environ['TESTING'] = '1'

        yield

        # Cleanup
        os.environ.pop('TESTING', None)

    @pytest.fixture
    def mock_all_external_apis(self):
        """Mock all external API calls for isolated testing."""
        # Mock Gemini API
        mock_genai = MagicMock()
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(
            text=json.dumps({
                "intro": [
                    {"speaker": "raj", "text": "Welcome to today's episode!"},
                    {"speaker": "priya", "text": "Great to be here!"}
                ],
                "segments": [
                    {
                        "topic_id": "topic-1",
                        "topic_title": "Breaking Tech News",
                        "dialogue": [
                            {"speaker": "raj", "text": "Let's discuss the latest tech news."},
                            {"speaker": "priya", "text": "This is really exciting!"},
                            {"speaker": "raj", "text": "The implications are significant."},
                            {"speaker": "priya", "text": "What should our listeners know?"},
                            {"speaker": "raj", "text": "Here are the key takeaways."},
                        ]
                    },
                    {
                        "topic_id": "topic-2",
                        "topic_title": "Community Updates",
                        "dialogue": [
                            {"speaker": "priya", "text": "Now let's talk community."},
                            {"speaker": "raj", "text": "Great updates from the community."},
                            {"speaker": "priya", "text": "Very inspiring stories."},
                        ]
                    }
                ],
                "outro": [
                    {"speaker": "raj", "text": "Thanks for listening!"},
                    {"speaker": "priya", "text": "See you next time!"}
                ]
            })
        )
        mock_genai.GenerativeModel.return_value = mock_model

        # Mock Reddit API
        mock_reddit_post = MagicMock()
        mock_reddit_post.title = "Exciting Tech Announcement"
        mock_reddit_post.selftext = "This is a detailed post about technology."
        mock_reddit_post.score = 500
        mock_reddit_post.url = "https://reddit.com/r/tech/123"
        mock_reddit_post.created_utc = datetime.now().timestamp()
        mock_reddit_post.num_comments = 150

        patches = {
            'genai': patch('google.generativeai.configure'),
            'genai_model': patch('google.generativeai.GenerativeModel', return_value=mock_model),
            'src_genai': patch('src.generators.script_generator.genai', mock_genai),
            'enhanced_genai': patch('src.generators.enhanced_script_generator.genai', mock_genai),
        }

        started_patches = {name: p.start() for name, p in patches.items()}
        yield started_patches

        for p in patches.values():
            p.stop()

    def test_complete_profile_creation_flow(self, db_session):
        """Test creating a complete profile with all settings."""
        from webapp.models import PodcastProfile, Host, ContentSource

        # Create profile
        profile = PodcastProfile(
            name="Tech Daily",
            description="Daily technology news and insights",
            target_audience="Software developers and tech enthusiasts",
            tone="conversational",
            language="en-US",
            target_duration_minutes=15,
            topic_count=5,
            categories=["technology", "programming", "startups"],
            schedule_enabled=True,
            schedule_hour=6,
            schedule_minute=0,
            schedule_days=["mon", "tue", "wed", "thu", "fri"],
            timezone="America/New_York",
        )
        db_session.add(profile)
        db_session.commit()

        # Add hosts
        host1 = Host(
            profile_id=profile.id,
            name="Alex",
            persona="A seasoned tech professional with 15 years of experience",
            voice_name="Orus",
            speaking_style="analytical yet approachable",
            expertise_areas=["cloud computing", "AI", "startups"],
        )
        host2 = Host(
            profile_id=profile.id,
            name="Sam",
            persona="A community advocate and open source contributor",
            voice_name="Aoede",
            speaking_style="enthusiastic and empathetic",
            expertise_areas=["open source", "community", "developer experience"],
        )
        db_session.add_all([host1, host2])
        db_session.commit()

        # Add content sources
        source1 = ContentSource(
            profile_id=profile.id,
            name="r/programming",
            source_type="reddit",
            config={"subreddit": "programming"},
            priority=1,
            is_active=True,
        )
        source2 = ContentSource(
            profile_id=profile.id,
            name="Hacker News",
            source_type="rss",
            config={"feed_url": "https://news.ycombinator.com/rss"},
            priority=2,
            is_active=True,
        )
        db_session.add_all([source1, source2])
        db_session.commit()

        # Verify complete setup
        db_session.refresh(profile)

        assert profile.id is not None
        assert len(profile.hosts) == 2
        assert len(profile.sources) == 2
        assert profile.schedule_enabled is True
        assert "technology" in profile.categories

    def test_job_creation_and_status_tracking(self, db_session, sample_profile):
        """Test job creation and status tracking throughout lifecycle."""
        from webapp.models import GenerationJob

        # Create job
        job = GenerationJob(
            profile_id=sample_profile.id,
            job_id="test-lifecycle-job",
            target_date=datetime.now(),
            status="pending",
            current_stage="initializing",
            progress_percent=0,
            stages_completed=[],
            stages_pending=["research", "synthesis", "script", "audio", "newsletter"],
            stage_details={"activity_log": []},
        )
        db_session.add(job)
        db_session.commit()

        # Simulate stage progression
        stages = [
            ("research", 20, ["initializing"]),
            ("synthesis", 35, ["initializing", "research"]),
            ("script", 55, ["initializing", "research", "synthesis"]),
            ("audio", 85, ["initializing", "research", "synthesis", "script"]),
            ("newsletter", 95, ["initializing", "research", "synthesis", "script", "audio"]),
        ]

        for stage_name, progress, completed in stages:
            job.status = "running"
            job.current_stage = stage_name
            job.progress_percent = progress
            job.stages_completed = completed
            job.stages_pending = [s for s in ["research", "synthesis", "script", "audio", "newsletter"]
                                   if s not in completed and s != stage_name]

            # Add activity log entry
            details = dict(job.stage_details or {})
            log = details.get("activity_log", [])
            log.append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Started {stage_name}",
                "level": "info",
            })
            details["activity_log"] = log
            details["current_activity"] = f"Processing {stage_name}"
            job.stage_details = details

            db_session.commit()
            db_session.refresh(job)

            assert job.current_stage == stage_name
            assert job.progress_percent == progress

        # Complete job
        job.status = "completed"
        job.progress_percent = 100
        job.completed_at = datetime.utcnow()
        db_session.commit()

        db_session.refresh(job)
        assert job.status == "completed"
        assert job.completed_at is not None
        assert len(job.stage_details["activity_log"]) >= 5

    def test_episode_creation_with_segments(self, db_session, sample_profile):
        """Test creating an episode with all related data."""
        from webapp.models import Episode, Segment, TopicHistory, Newsletter

        # Create episode
        episode = Episode(
            profile_id=sample_profile.id,
            episode_id="ep-2024-12-25",
            title="Tech Daily - December 25, 2024",
            date=datetime.now(),
            topics_covered=["AI Breakthroughs", "Open Source Updates", "Developer Tools"],
            script=json.dumps({
                "intro": [{"speaker": "alex", "text": "Welcome!"}],
                "segments": [
                    {"topic_id": "topic-1", "topic_title": "AI", "dialogue": []},
                    {"topic_id": "topic-2", "topic_title": "OSS", "dialogue": []},
                ],
                "outro": [{"speaker": "sam", "text": "Goodbye!"}],
            }),
            summary="A comprehensive look at the week's biggest tech stories.",
            audio_path="/output/episodes/ep-2024-12-25.mp3",
            duration_seconds=900,
            status="published",
        )
        db_session.add(episode)
        db_session.commit()

        # Add segments
        segments = [
            Segment(
                episode_id=episode.id,
                sequence_index=0,
                topic_id="intro",
                title="Introduction",
                content_type="intro",
                audio_path="/output/audio/ep-2024-12-25-intro.mp3",
                duration_seconds=60,
            ),
            Segment(
                episode_id=episode.id,
                sequence_index=1,
                topic_id="topic-1",
                title="AI Breakthroughs",
                content_type="topic",
                audio_path="/output/audio/ep-2024-12-25-topic-1.mp3",
                duration_seconds=300,
            ),
            Segment(
                episode_id=episode.id,
                sequence_index=2,
                topic_id="topic-2",
                title="Open Source Updates",
                content_type="topic",
                audio_path="/output/audio/ep-2024-12-25-topic-2.mp3",
                duration_seconds=300,
            ),
            Segment(
                episode_id=episode.id,
                sequence_index=3,
                topic_id="outro",
                title="Closing",
                content_type="outro",
                audio_path="/output/audio/ep-2024-12-25-outro.mp3",
                duration_seconds=60,
            ),
        ]
        db_session.add_all(segments)

        # Add topic history
        for topic in episode.topics_covered:
            history = TopicHistory(
                episode_id=episode.id,
                title=topic,
                category="technology",
            )
            db_session.add(history)

        # Add newsletter
        newsletter = Newsletter(
            episode_id=episode.id,
            profile_id=sample_profile.id,
            title="Tech Daily Newsletter",
            subtitle="Your weekly tech digest",
            issue_date=datetime.now(),
            intro="Welcome to this week's newsletter!",
            outro="Thanks for reading!",
            sections=[
                {
                    "headline": "AI Breakthroughs",
                    "body": "Major advances in AI this week...",
                    "sources": ["TechCrunch", "Ars Technica"],
                },
                {
                    "headline": "Open Source Updates",
                    "body": "The OSS community has been busy...",
                    "sources": ["GitHub Blog"],
                },
            ],
            total_word_count=500,
            reading_time_minutes=3,
        )
        db_session.add(newsletter)
        db_session.commit()

        # Verify relationships
        db_session.refresh(episode)

        assert len(episode.segments) == 4
        assert len(episode.topics) == 3
        assert episode.newsletter is not None
        assert episode.newsletter.title == "Tech Daily Newsletter"

        # Verify segment ordering
        sorted_segments = sorted(episode.segments, key=lambda s: s.sequence_index)
        assert sorted_segments[0].content_type == "intro"
        assert sorted_segments[-1].content_type == "outro"


@pytest.mark.integration
class TestScriptGenerationIntegration:
    """Integration tests for script generation with mocked AI."""

    @pytest.fixture
    def mock_gemini_response(self):
        """Mock Gemini API with realistic response."""
        response_data = {
            "intro": [
                {"speaker": "raj", "text": "Good morning everyone! Welcome to today's episode."},
                {"speaker": "priya", "text": "We have some exciting topics to cover today!"},
            ],
            "segments": [
                {
                    "topic_id": "topic-1",
                    "topic_title": "Breaking: Major Tech Acquisition",
                    "dialogue": [
                        {"speaker": "raj", "text": "Let's start with the biggest news of the week."},
                        {"speaker": "priya", "text": "Yes, this acquisition is huge for the industry."},
                        {"speaker": "raj", "text": "The deal is worth over 5 billion dollars."},
                        {"speaker": "priya", "text": "What does this mean for developers?"},
                        {"speaker": "raj", "text": "Well, there are several implications..."},
                        {"speaker": "priya", "text": "That's a really important point."},
                        {"speaker": "raj", "text": "For our listeners, the key takeaway is..."},
                        {"speaker": "priya", "text": "Great advice. Let's move on to our next topic."},
                    ]
                },
                {
                    "topic_id": "topic-2",
                    "topic_title": "New Programming Language Features",
                    "dialogue": [
                        {"speaker": "priya", "text": "Now let's talk about programming languages."},
                        {"speaker": "raj", "text": "There have been some exciting updates."},
                        {"speaker": "priya", "text": "Pattern matching is finally here!"},
                        {"speaker": "raj", "text": "This will change how we write code."},
                    ]
                },
            ],
            "outro": [
                {"speaker": "raj", "text": "That's all for today's episode!"},
                {"speaker": "priya", "text": "Thanks for listening, see you next time!"},
            ]
        }

        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text=json.dumps(response_data))

        with patch("src.generators.script_generator.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model
            yield mock_genai

    @pytest.mark.asyncio
    async def test_script_generation_produces_valid_output(self, mock_gemini_response):
        """Test that script generation produces valid, parseable output."""
        from src.generators.script_generator import ScriptGenerator
        from src.aggregators.content_ranker import PodcastTopic

        generator = ScriptGenerator(api_key="test-key")

        topics = [
            PodcastTopic(
                id="topic-1",
                title="Breaking: Major Tech Acquisition",
                summary="A major tech company was acquired for billions",
                score=9.5,
                category="technology",
                sources=["TechCrunch"],
                source_count=1,
                key_points=["$5B deal", "Industry implications", "Developer impact"],
                is_breaking=True,
                is_trending=True,
                community_sentiment="positive",
            ),
            PodcastTopic(
                id="topic-2",
                title="New Programming Language Features",
                summary="Popular languages get new features",
                score=8.0,
                category="programming",
                sources=["Dev.to"],
                source_count=1,
                key_points=["Pattern matching", "Better async"],
                is_breaking=False,
                is_trending=True,
                community_sentiment="excited",
            ),
        ]

        script = await generator.generate_script(
            topics=topics,
            episode_date=datetime.now(),
            target_duration_minutes=15,
            podcast_name="Tech Podcast",
        )

        # Validate script structure
        assert script is not None
        assert script.episode_id is not None
        assert len(script.intro) >= 2
        assert len(script.segments) >= 1
        assert len(script.outro) >= 2

        # Validate dialogue structure
        for segment in script.segments:
            assert segment.topic_id is not None
            assert segment.topic_title is not None
            assert len(segment.dialogue) >= 2

            for line in segment.dialogue:
                assert line.speaker.lower() in ["raj", "priya"]
                assert len(line.text) > 0

        # Validate SSML blocks
        blocks = script.to_ssml_blocks()
        assert len(blocks) > 0

        intro_blocks = [b for b in blocks if b["section"] == "intro"]
        assert len(intro_blocks) >= 2


@pytest.mark.integration
class TestDatabaseIntegrity:
    """Tests for database integrity and constraints."""

    def test_cascade_delete_profile(self, db_session):
        """Test that deleting a profile cascades to related records."""
        from webapp.models import PodcastProfile, Host, ContentSource, Episode

        # Create profile with related records
        profile = PodcastProfile(name="Cascade Test Profile")
        db_session.add(profile)
        db_session.commit()

        host = Host(profile_id=profile.id, name="Test Host")
        source = ContentSource(
            profile_id=profile.id,
            name="Test Source",
            source_type="reddit",
            config={"subreddit": "test"},
        )
        episode = Episode(
            profile_id=profile.id,
            episode_id="cascade-test-ep",
            title="Test Episode",
            date=datetime.now(),
        )
        db_session.add_all([host, source, episode])
        db_session.commit()

        host_id = host.id
        source_id = source.id
        episode_id = episode.id

        # Delete profile
        db_session.delete(profile)
        db_session.commit()

        # Verify cascade
        assert db_session.query(Host).get(host_id) is None
        assert db_session.query(ContentSource).get(source_id) is None
        assert db_session.query(Episode).get(episode_id) is None

    def test_unique_constraints(self, db_session):
        """Test unique constraints are enforced."""
        from webapp.models import PodcastProfile, Episode
        from sqlalchemy.exc import IntegrityError

        # Create profile
        profile = PodcastProfile(name="Unique Test Profile")
        db_session.add(profile)
        db_session.commit()

        # Try to create duplicate episode ID
        ep1 = Episode(
            profile_id=profile.id,
            episode_id="unique-test-ep",
            title="Episode 1",
            date=datetime.now(),
        )
        db_session.add(ep1)
        db_session.commit()

        ep2 = Episode(
            profile_id=profile.id,
            episode_id="unique-test-ep",  # Same ID
            title="Episode 2",
            date=datetime.now(),
        )
        db_session.add(ep2)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    def test_json_column_handling(self, db_session, sample_profile):
        """Test JSON columns store and retrieve correctly."""
        from webapp.models import Episode

        complex_script = {
            "intro": [
                {"speaker": "raj", "text": "Hello", "metadata": {"emotion": "excited"}},
            ],
            "segments": [
                {
                    "topic_id": "t1",
                    "topic_title": "Topic",
                    "dialogue": [],
                    "extras": {"research_depth": "deep", "sources": ["a", "b"]},
                }
            ],
            "outro": [],
        }

        episode = Episode(
            profile_id=sample_profile.id,
            episode_id="json-test-ep",
            title="JSON Test",
            date=datetime.now(),
            script=json.dumps(complex_script),
            topics_covered=["Topic 1", "Topic 2", "Topic 3"],
            key_facts=["Fact 1", "Fact 2"],
        )
        db_session.add(episode)
        db_session.commit()

        # Retrieve and verify
        db_session.refresh(episode)
        retrieved_script = json.loads(episode.script)

        assert retrieved_script["intro"][0]["metadata"]["emotion"] == "excited"
        assert len(episode.topics_covered) == 3
        assert "Fact 1" in episode.key_facts
