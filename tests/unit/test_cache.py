"""
Unit tests for caching utilities.
"""

import pytest
import time
import tempfile
from pathlib import Path


class TestInMemoryCache:
    """Tests for InMemoryCache."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        from src.utils.cache import InMemoryCache

        cache = InMemoryCache(max_size=100)

        cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"

    def test_get_nonexistent(self):
        """Test get returns None for nonexistent key."""
        from src.utils.cache import InMemoryCache

        cache = InMemoryCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        from src.utils.cache import InMemoryCache

        cache = InMemoryCache()

        # Set with very short TTL (0.1 seconds)
        cache.set("key1", "value1", ttl=0.1)
        assert cache.get("key1") == "value1"

        time.sleep(0.15)  # Wait for expiration
        assert cache.get("key1") is None

    def test_delete(self):
        """Test delete operation."""
        from src.utils.cache import InMemoryCache

        cache = InMemoryCache()

        cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"

        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """Test clear operation."""
        from src.utils.cache import InMemoryCache

        cache = InMemoryCache()

        cache.set("key1", "value1", ttl=60)
        cache.set("key2", "value2", ttl=60)
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_max_size_eviction(self):
        """Test max size enforcement with eviction."""
        from src.utils.cache import InMemoryCache

        cache = InMemoryCache(max_size=10)

        # Fill cache past max size
        for i in range(15):
            cache.set(f"key{i}", f"value{i}", ttl=60)

        # Some older entries should be evicted
        # Cache should not exceed max_size
        stats = cache.stats()
        assert stats['size'] <= 10

    def test_stats(self):
        """Test cache statistics."""
        from src.utils.cache import InMemoryCache

        cache = InMemoryCache(max_size=100)

        cache.set("key1", "value1", ttl=60)
        cache.set("key2", "value2", ttl=60)

        stats = cache.stats()
        assert stats['size'] == 2
        assert stats['max_size'] == 100


class TestFileCache:
    """Tests for FileCache."""

    def test_set_and_get(self):
        """Test basic set and get with file cache."""
        from src.utils.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=tmpdir)

            cache.set("key1", {"data": "value1"}, ttl=60)
            assert cache.get("key1") == {"data": "value1"}

    def test_persistence(self):
        """Test data persists to disk."""
        from src.utils.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache1 = FileCache(cache_dir=tmpdir)
            cache1.set("key1", "value1", ttl=60)

            # Create new cache instance pointing to same dir
            cache2 = FileCache(cache_dir=tmpdir)
            assert cache2.get("key1") == "value1"

    def test_ttl_expiration(self):
        """Test TTL expiration for file cache."""
        from src.utils.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=tmpdir)

            cache.set("key1", "value1", ttl=0.1)
            assert cache.get("key1") == "value1"

            time.sleep(0.15)
            assert cache.get("key1") is None

    def test_delete(self):
        """Test delete removes file."""
        from src.utils.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=tmpdir)

            cache.set("key1", "value1", ttl=60)
            cache.delete("key1")

            assert cache.get("key1") is None

    def test_clear(self):
        """Test clear removes all cache files."""
        from src.utils.cache import FileCache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FileCache(cache_dir=tmpdir)

            cache.set("key1", "value1", ttl=60)
            cache.set("key2", "value2", ttl=60)
            cache.clear()

            assert cache.get("key1") is None
            assert cache.get("key2") is None


class TestCacheDecorator:
    """Tests for cached decorator."""

    def test_sync_function_caching(self):
        """Test decorator caches sync function results."""
        from src.utils.cache import cached

        call_count = 0

        @cached(ttl=60, key_prefix="test")
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # Reset global cache for test isolation
        import src.utils.cache as cache_module
        cache_module._cache = None

        # First call - should compute
        result1 = expensive_function(5)
        assert result1 == 10
        first_count = call_count

        # Second call with same arg - should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == first_count  # No additional call

        # Different arg - should compute again
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == first_count + 1


class TestResearchCache:
    """Tests for research-specific caching."""

    def test_cache_research_result(self):
        """Test caching research results."""
        from src.utils.cache import cache_research_result, get_cached_research
        import src.utils.cache as cache_module

        # Reset cache
        cache_module._cache = None

        topic = "test-topic-unique"
        data = {"findings": ["finding1", "finding2"]}

        cache_research_result(topic, data)
        result = get_cached_research(topic)

        assert result == data

    def test_research_cache_miss(self):
        """Test cache miss for research."""
        from src.utils.cache import get_cached_research
        import src.utils.cache as cache_module

        # Reset cache
        cache_module._cache = None

        result = get_cached_research("nonexistent-topic-xyz123")
        assert result is None


class TestCacheKey:
    """Tests for cache key generation."""

    def test_cache_key_generation(self):
        """Test cache key is generated consistently."""
        from src.utils.cache import cache_key

        key1 = cache_key("arg1", "arg2", kwarg1="val1")
        key2 = cache_key("arg1", "arg2", kwarg1="val1")

        assert key1 == key2

    def test_different_args_different_keys(self):
        """Test different args produce different keys."""
        from src.utils.cache import cache_key

        key1 = cache_key("arg1")
        key2 = cache_key("arg2")

        assert key1 != key2
