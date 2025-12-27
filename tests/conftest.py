"""
Pytest configuration and fixtures for PodcastOS tests.
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ['TESTING'] = '1'
os.environ.setdefault('GEMINI_API_KEY', 'test-api-key')


# ============================================================
# Database Fixtures
# ============================================================

@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test."""
    from webapp.models import init_db, Base
    from sqlalchemy.orm import sessionmaker

    db_path = Path(__file__).parent / "test_db.sqlite"
    if db_path.exists():
        db_path.unlink()

    engine = init_db(str(db_path))
    Session = sessionmaker(bind=engine)

    yield Session

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(scope="function")
def db_session(test_db):
    """Get a database session."""
    session = test_db()
    yield session
    session.close()


@pytest.fixture
def sample_profile(db_session):
    """Create a sample podcast profile."""
    from webapp.models import PodcastProfile

    profile = PodcastProfile(
        name="Test Podcast",
        description="A test podcast for unit testing",
        target_audience="Developers",
        tone="casual",
        language="en-US",
        target_duration_minutes=10,
        topic_count=3,
        categories=["tech", "programming"],
    )
    db_session.add(profile)
    db_session.commit()
    return profile


@pytest.fixture
def sample_episode(db_session, sample_profile):
    """Create a sample episode."""
    from webapp.models import Episode

    episode = Episode(
        profile_id=sample_profile.id,
        episode_id="test-ep-001",
        title="Test Episode - December 25, 2024",
        date=datetime.now(),
        topics_covered=["Topic 1", "Topic 2"],
        script='{"intro": [], "segments": [], "outro": []}',
        summary="Test episode summary",
        duration_seconds=600,
        status="published",
    )
    db_session.add(episode)
    db_session.commit()
    return episode


# ============================================================
# Mock Fixtures
# ============================================================

@pytest.fixture
def mock_gemini():
    """Mock Google Gemini API."""
    with patch('google.generativeai.configure'):
        with patch('google.generativeai.GenerativeModel') as mock_model:
            mock_instance = MagicMock()
            mock_instance.generate_content.return_value = MagicMock(
                text='{"intro": [], "segments": [], "outro": []}'
            )
            mock_model.return_value = mock_instance
            yield mock_instance


@pytest.fixture
def mock_tts():
    """Mock TTS service."""
    with patch('src.tts.google_tts.GoogleTTS') as mock_tts:
        mock_instance = MagicMock()
        mock_instance.generate_speech.return_value = b'fake-audio-bytes'
        mock_tts.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_reddit():
    """Mock Reddit aggregator."""
    with patch('src.aggregators.reddit_aggregator.RedditAggregator') as mock_reddit:
        mock_instance = MagicMock()
        mock_post = MagicMock()
        mock_post.title = "Test Post Title"
        mock_post.selftext = "Test post content"
        mock_post.score = 100
        mock_post.url = "https://reddit.com/test"
        mock_post.created_utc = datetime.now().timestamp()
        mock_instance.fetch_subreddit_posts.return_value = [mock_post]
        mock_reddit.return_value = mock_instance
        yield mock_instance


# ============================================================
# Flask App Fixtures
# ============================================================

@pytest.fixture
def app():
    """Create Flask test application."""
    from webapp.app import app as flask_app

    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    return flask_app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create Flask CLI test runner."""
    return app.test_cli_runner()


# ============================================================
# Async Fixtures
# ============================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================
# Sample Data Fixtures
# ============================================================

@pytest.fixture
def sample_topics():
    """Sample podcast topics for testing."""
    from src.aggregators.content_ranker import PodcastTopic

    return [
        PodcastTopic(
            id="topic-1",
            title="Breaking: New Tech Announcement",
            summary="A major tech company announced a new product",
            score=9.5,
            category="tech",
            sources=["TechCrunch", "The Verge"],
            source_count=2,
            key_points=["Point 1", "Point 2", "Point 3"],
            is_breaking=True,
            is_trending=False,
            community_sentiment="positive",
        ),
        PodcastTopic(
            id="topic-2",
            title="Programming Best Practices in 2024",
            summary="New programming patterns are emerging",
            score=8.0,
            category="programming",
            sources=["Dev.to", "Medium"],
            source_count=2,
            key_points=["Clean code", "Testing", "Documentation"],
            is_breaking=False,
            is_trending=True,
            community_sentiment="neutral",
        ),
    ]


@pytest.fixture
def sample_script():
    """Sample podcast script for testing."""
    from src.generators import PodcastScript, PodcastSegment, DialogueLine

    return PodcastScript(
        episode_id="test-script-001",
        episode_title="Test Script Episode",
        episode_date=datetime.now().isoformat(),
        duration_estimate=600,
        intro=[
            DialogueLine(speaker="raj", text="Welcome to the show!"),
            DialogueLine(speaker="priya", text="Great to be here!"),
        ],
        segments=[
            PodcastSegment(
                topic_id="topic-1",
                topic_title="Tech News",
                duration_estimate=180,
                dialogue=[
                    DialogueLine(speaker="raj", text="Let's talk tech."),
                    DialogueLine(speaker="priya", text="Exciting news today!"),
                ],
            ),
        ],
        outro=[
            DialogueLine(speaker="raj", text="Thanks for listening!"),
            DialogueLine(speaker="priya", text="See you next time!"),
        ],
    )
