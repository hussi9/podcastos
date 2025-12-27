"""
Unit tests for rate limiting functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
import time


class TestRateLimiterCore:
    """Tests for RateLimiter core functionality."""

    def test_rate_limiter_init(self):
        """Test RateLimiter initialization."""
        from webapp.rate_limiter import RateLimiter

        limiter = RateLimiter()
        assert limiter._requests is not None
        assert limiter._lock is not None

    def test_clean_old_requests(self):
        """Test cleaning old requests from sliding window."""
        from webapp.rate_limiter import RateLimiter

        limiter = RateLimiter()

        # Add some old timestamps
        old_time = time.time() - 120  # 2 minutes ago
        limiter._requests["test_key"] = [old_time, old_time + 1, time.time()]

        limiter._clean_old_requests("test_key", window_seconds=60)

        # Old requests should be removed
        assert len(limiter._requests["test_key"]) == 1

    def test_get_stats(self):
        """Test getting rate limit stats."""
        from webapp.rate_limiter import RateLimiter

        limiter = RateLimiter()
        limiter._requests["test_key"] = [time.time(), time.time()]

        stats = limiter.get_stats("test_key")
        assert stats['key'] == "test_key"
        assert stats['request_count'] == 2


class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""

    def test_decorator_structure(self):
        """Test decorator is properly structured."""
        from webapp.rate_limiter import rate_limit

        @rate_limit(max_requests=10, window_seconds=60)
        def test_endpoint():
            return "success"

        # Should be a wrapped function
        assert callable(test_endpoint)
        assert hasattr(test_endpoint, '__wrapped__')


class TestPreConfiguredLimiters:
    """Tests for pre-configured rate limiters."""

    def test_api_rate_limit_decorator(self):
        """Test API rate limit decorator exists."""
        from webapp.rate_limiter import api_rate_limit

        @api_rate_limit
        def api_endpoint():
            return "api response"

        assert callable(api_endpoint)

    def test_generation_rate_limit_decorator(self):
        """Test generation rate limit decorator exists."""
        from webapp.rate_limiter import generation_rate_limit

        @generation_rate_limit
        def generation_endpoint():
            return "generation response"

        assert callable(generation_endpoint)

    def test_auth_rate_limit_decorator(self):
        """Test auth rate limit decorator exists."""
        from webapp.rate_limiter import auth_rate_limit

        @auth_rate_limit
        def auth_endpoint():
            return "auth response"

        assert callable(auth_endpoint)

    def test_strict_rate_limit_decorator(self):
        """Test strict rate limit decorator exists."""
        from webapp.rate_limiter import strict_rate_limit

        @strict_rate_limit
        def strict_endpoint():
            return "strict response"

        assert callable(strict_endpoint)


class TestRateLimitWithFlaskContext:
    """Tests that require Flask application context."""

    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        from flask import Flask
        app = Flask(__name__)
        app.config['TESTING'] = True
        return app

    def test_is_rate_limited(self, app):
        """Test is_rate_limited method with Flask context."""
        from webapp.rate_limiter import RateLimiter

        limiter = RateLimiter()

        with app.test_request_context('/test', environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            # First request should be allowed
            is_limited, info = limiter.is_rate_limited(max_requests=5, window_seconds=60)
            assert is_limited is False
            assert info['remaining'] >= 0

    def test_rate_limit_exceeded(self, app):
        """Test rate limit exceeded behavior."""
        from webapp.rate_limiter import RateLimiter

        limiter = RateLimiter()

        with app.test_request_context('/test2', environ_base={'REMOTE_ADDR': '127.0.0.2'}):
            # Use up the limit
            for _ in range(3):
                limiter.is_rate_limited(max_requests=3, window_seconds=60)

            # Should be rate limited
            is_limited, info = limiter.is_rate_limited(max_requests=3, window_seconds=60)
            assert is_limited is True
            assert info['remaining'] == 0

    def test_add_rate_limit_headers(self, app):
        """Test adding rate limit headers to response."""
        from webapp.rate_limiter import add_rate_limit_headers
        from flask import g

        with app.app_context():
            mock_response = MagicMock()
            mock_response.headers = {}

            g.rate_limit_info = {
                'limit': 60,
                'remaining': 55,
                'reset': 60
            }

            result = add_rate_limit_headers(mock_response)

            assert result.headers['X-RateLimit-Limit'] == '60'
            assert result.headers['X-RateLimit-Remaining'] == '55'

    def test_add_rate_limit_headers_no_info(self, app):
        """Test headers not added when no rate limit info."""
        from webapp.rate_limiter import add_rate_limit_headers
        from flask import g

        with app.app_context():
            mock_response = MagicMock()
            mock_response.headers = {}

            # Simulate no rate_limit_info
            if hasattr(g, 'rate_limit_info'):
                delattr(g, 'rate_limit_info')

            result = add_rate_limit_headers(mock_response)

            # Headers should not be set
            assert 'X-RateLimit-Limit' not in result.headers
