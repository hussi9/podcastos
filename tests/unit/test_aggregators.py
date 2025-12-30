"""
Unit tests for content aggregators.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch


class TestRedditPost:
    """Tests for RedditPost model."""

    def test_create_reddit_post(self):
        """Test creating a RedditPost."""
        from src.aggregators.reddit_aggregator import RedditPost

        post = RedditPost(
            id="abc123",
            subreddit="immigration",
            title="H1B Update Discussion",
            selftext="Here's the latest on H1B visas...",
            score=150,
            num_comments=45,
            url="https://reddit.com/r/immigration/abc123",
            created_utc=datetime.now(),
            author="user123",
            permalink="/r/immigration/comments/abc123",
            flair="Discussion",
        )

        assert post.id == "abc123"
        assert post.subreddit == "immigration"
        assert post.score == 150

    def test_engagement_score(self):
        """Test engagement score calculation."""
        from src.aggregators.reddit_aggregator import RedditPost

        post = RedditPost(
            id="test",
            subreddit="test",
            title="Test",
            selftext="",
            score=100,
            num_comments=50,
            url="https://reddit.com/test",
            created_utc=datetime.now(),
            author="user",
            permalink="/r/test",
        )

        # Engagement = score + (comments * 2)
        expected = 100 + (50 * 2)
        assert post.engagement_score == expected


class TestRedditAggregator:
    """Tests for RedditAggregator."""

    def test_init_with_credentials(self):
        """Test initialization with credentials."""
        from src.aggregators.reddit_aggregator import RedditAggregator

        agg = RedditAggregator(
            client_id="test_id",
            client_secret="test_secret",
            user_agent="TestBot/1.0",
        )

        assert agg.client_id == "test_id"
        assert agg.client_secret == "test_secret"
        assert agg.user_agent == "TestBot/1.0"

    def test_init_without_credentials(self):
        """Test initialization without credentials."""
        from src.aggregators.reddit_aggregator import RedditAggregator

        agg = RedditAggregator()

        assert agg.client_id is None
        assert agg.client_secret is None

    def test_default_subreddits(self):
        """Test default subreddits are configured."""
        from src.aggregators.reddit_aggregator import RedditAggregator

        assert len(RedditAggregator.DEFAULT_SUBREDDITS) > 0
        # Default subreddits should include general tech/news categories
        assert "technology" in RedditAggregator.DEFAULT_SUBREDDITS or \
               "news" in RedditAggregator.DEFAULT_SUBREDDITS

    @pytest.mark.asyncio
    async def test_get_access_token_no_credentials(self):
        """Test access token returns None without credentials."""
        from src.aggregators.reddit_aggregator import RedditAggregator

        agg = RedditAggregator()
        token = await agg._get_access_token()

        assert token is None

    @pytest.mark.asyncio
    async def test_get_access_token_cached(self):
        """Test access token is cached."""
        from src.aggregators.reddit_aggregator import RedditAggregator

        agg = RedditAggregator(client_id="id", client_secret="secret")
        agg.access_token = "cached_token"
        agg.token_expiry = datetime.now() + timedelta(hours=1)

        token = await agg._get_access_token()

        assert token == "cached_token"


class TestPodcastTopic:
    """Tests for PodcastTopic model."""

    def test_create_podcast_topic(self):
        """Test creating a PodcastTopic."""
        from src.aggregators.content_ranker import PodcastTopic

        topic = PodcastTopic(
            id="topic-1",
            title="H1B Visa Processing Updates",
            summary="USCIS announces new processing times",
            category="immigration",
            score=9.5,
            sources=["USCIS", "Reddit"],
            source_count=2,
            key_points=["Point 1", "Point 2"],
            community_sentiment="positive",
            is_breaking=True,
            is_trending=False,
        )

        assert topic.id == "topic-1"
        assert topic.score == 9.5
        assert topic.is_breaking is True
        assert len(topic.key_points) == 2

    def test_podcast_topic_defaults(self):
        """Test PodcastTopic default values."""
        from src.aggregators.content_ranker import PodcastTopic

        topic = PodcastTopic(
            id="topic-2",
            title="Test Topic",
            summary="Test summary",
            category="general",
            score=5.0,
            sources=["Source1"],
            source_count=1,
            key_points=[],
        )

        assert topic.community_sentiment is None
        assert topic.is_breaking is False
        assert topic.is_trending is False
        assert topic.news_articles == []
        assert topic.reddit_posts == []


class TestContentRanker:
    """Tests for ContentRanker."""

    def test_init(self):
        """Test ContentRanker initialization."""
        from src.aggregators.content_ranker import ContentRanker

        ranker = ContentRanker(
            reddit_client_id="reddit_id",
            reddit_client_secret="reddit_secret",
            supabase_url="https://supabase.co",
            supabase_key="supabase_key",
        )

        assert ranker.reddit is not None
        assert ranker.news is not None
        # Note: uscis aggregator was removed from ContentRanker

    @pytest.mark.asyncio
    async def test_gather_all_content_returns_dict(self):
        """Test gather_all_content returns a dict with expected keys."""
        from src.aggregators.content_ranker import ContentRanker

        ranker = ContentRanker()

        # Call without any sources configured - should return empty content dict
        result = await ranker.gather_all_content()

        # Should return dict structure even if empty
        assert isinstance(result, dict)
        assert "reddit" in result
        assert "news" in result
        # Values should be lists (possibly empty without API keys)
        assert isinstance(result["reddit"], list)
        assert isinstance(result["news"], list)


class TestNewsAggregator:
    """Tests for NewsAggregator (basic structure tests)."""

    def test_import(self):
        """Test NewsAggregator can be imported."""
        from src.aggregators.news_aggregator import NewsAggregator

        assert NewsAggregator is not None


class TestUSCISAggregator:
    """Tests for USCISAggregator (basic structure tests)."""

    def test_import(self):
        """Test USCISAggregator can be imported."""
        from src.aggregators.uscis_aggregator import USCISAggregator

        assert USCISAggregator is not None
