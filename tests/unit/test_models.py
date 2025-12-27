"""
Unit tests for database models.
"""

import pytest
from datetime import datetime


@pytest.mark.unit
class TestPodcastProfile:
    """Tests for PodcastProfile model."""

    def test_create_profile(self, db_session):
        """Test creating a podcast profile."""
        from webapp.models import PodcastProfile

        profile = PodcastProfile(
            name="My Podcast",
            description="A test podcast",
            target_audience="Tech enthusiasts",
            tone="conversational",
            language="en-US",
            target_duration_minutes=15,
            topic_count=5,
        )
        db_session.add(profile)
        db_session.commit()

        assert profile.id is not None
        assert profile.name == "My Podcast"
        assert profile.is_active is True
        assert profile.created_at is not None

    def test_profile_defaults(self, db_session):
        """Test that profile defaults are applied correctly."""
        from webapp.models import PodcastProfile

        profile = PodcastProfile(name="Minimal Profile")
        db_session.add(profile)
        db_session.commit()

        assert profile.tone == "conversational"
        assert profile.language == "en-US"
        assert profile.target_duration_minutes == 10
        assert profile.topic_count == 5
        assert profile.is_active is True
        assert profile.schedule_enabled is False

    def test_profile_relationships(self, sample_profile, db_session):
        """Test profile relationships with hosts and episodes."""
        from webapp.models import Host, Episode

        # Add host
        host = Host(
            profile_id=sample_profile.id,
            name="Test Host",
            persona="A friendly host",
            voice_name="Puck",
        )
        db_session.add(host)
        db_session.commit()

        # Verify relationship
        assert len(sample_profile.hosts) == 1
        assert sample_profile.hosts[0].name == "Test Host"


@pytest.mark.unit
class TestEpisode:
    """Tests for Episode model."""

    def test_create_episode(self, sample_profile, db_session):
        """Test creating an episode."""
        from webapp.models import Episode

        episode = Episode(
            profile_id=sample_profile.id,
            episode_id="ep-001",
            title="First Episode",
            date=datetime.now(),
            topics_covered=["Topic A", "Topic B"],
            status="draft",
        )
        db_session.add(episode)
        db_session.commit()

        assert episode.id is not None
        assert episode.episode_id == "ep-001"
        assert episode.status == "draft"
        assert len(episode.topics_covered) == 2

    def test_episode_relationship_to_profile(self, sample_episode, sample_profile):
        """Test episode's relationship to profile."""
        assert sample_episode.profile_id == sample_profile.id
        assert sample_episode.profile.name == sample_profile.name


@pytest.mark.unit
class TestHost:
    """Tests for Host model."""

    def test_create_host(self, sample_profile, db_session):
        """Test creating a host."""
        from webapp.models import Host

        host = Host(
            profile_id=sample_profile.id,
            name="Raj",
            persona="Tech expert with immigration experience",
            voice_name="Orus",
            speaking_style="analytical, warm",
            expertise_areas=["technology", "immigration"],
        )
        db_session.add(host)
        db_session.commit()

        assert host.id is not None
        assert host.name == "Raj"
        assert "technology" in host.expertise_areas

    def test_host_defaults(self, sample_profile, db_session):
        """Test host defaults."""
        from webapp.models import Host

        host = Host(profile_id=sample_profile.id, name="Minimal Host")
        db_session.add(host)
        db_session.commit()

        assert host.expertise_areas == []


@pytest.mark.unit
class TestGenerationJob:
    """Tests for GenerationJob model."""

    def test_create_job(self, sample_profile, db_session):
        """Test creating a generation job."""
        from webapp.models import GenerationJob

        job = GenerationJob(
            profile_id=sample_profile.id,
            job_id="job-abc123",
            target_date=datetime.now(),
            status="pending",
            current_stage="initializing",
            progress_percent=0,
            stages_completed=[],
            stages_pending=["research", "scripting", "audio"],
        )
        db_session.add(job)
        db_session.commit()

        assert job.id is not None
        assert job.status == "pending"
        assert len(job.stages_pending) == 3

    def test_job_status_transitions(self, sample_profile, db_session):
        """Test job status updates."""
        from webapp.models import GenerationJob

        job = GenerationJob(
            profile_id=sample_profile.id,
            job_id="job-xyz789",
            target_date=datetime.now(),
            status="pending",
        )
        db_session.add(job)
        db_session.commit()

        # Simulate status progression
        job.status = "running"
        job.progress_percent = 25
        db_session.commit()
        assert job.status == "running"

        job.status = "completed"
        job.progress_percent = 100
        job.completed_at = datetime.utcnow()
        db_session.commit()
        assert job.completed_at is not None


@pytest.mark.unit
class TestNewsletter:
    """Tests for Newsletter model."""

    def test_create_newsletter(self, sample_episode, db_session):
        """Test creating a newsletter."""
        from webapp.models import Newsletter

        newsletter = Newsletter(
            episode_id=sample_episode.id,
            profile_id=sample_episode.profile_id,
            title="Weekly Update",
            subtitle="Your curated news digest",
            issue_date=datetime.now(),
            intro="Welcome to this week's newsletter.",
            outro="Thanks for reading!",
            sections=[
                {"headline": "Section 1", "body": "Content here"},
                {"headline": "Section 2", "body": "More content"},
            ],
            total_word_count=500,
            reading_time_minutes=3,
        )
        db_session.add(newsletter)
        db_session.commit()

        assert newsletter.id is not None
        assert len(newsletter.sections) == 2
        assert newsletter.episode.id == sample_episode.id


@pytest.mark.unit
class TestContentSource:
    """Tests for ContentSource model."""

    def test_create_reddit_source(self, sample_profile, db_session):
        """Test creating a Reddit content source."""
        from webapp.models import ContentSource

        source = ContentSource(
            profile_id=sample_profile.id,
            name="r/technology",
            source_type="reddit",
            config={"subreddit": "technology"},
            priority=1,
            is_active=True,
        )
        db_session.add(source)
        db_session.commit()

        assert source.id is not None
        assert source.source_type == "reddit"
        assert source.config["subreddit"] == "technology"

    def test_create_rss_source(self, sample_profile, db_session):
        """Test creating an RSS content source."""
        from webapp.models import ContentSource

        source = ContentSource(
            profile_id=sample_profile.id,
            name="Tech Blog",
            source_type="rss",
            config={"feed_url": "https://example.com/feed.xml"},
            priority=2,
        )
        db_session.add(source)
        db_session.commit()

        assert source.source_type == "rss"
        assert "feed_url" in source.config
