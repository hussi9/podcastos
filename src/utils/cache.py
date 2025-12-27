"""
Caching Module for PodcastOS.

Provides caching for expensive operations like research results.
Supports both in-memory cache and Redis (when available).
"""

import os
import json
import time
import hashlib
import logging
from typing import Optional, Any, Callable
from functools import wraps
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


class CacheBackend:
    """Base cache backend interface."""
    
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        raise NotImplementedError
    
    def clear(self) -> bool:
        raise NotImplementedError


class InMemoryCache(CacheBackend):
    """
    Thread-safe in-memory cache with TTL support.
    
    Good for single-process deployments.
    """
    
    def __init__(self, max_size: int = 1000):
        self._cache = {}
        self._lock = Lock()
        self._max_size = max_size
    
    def _is_expired(self, entry: dict) -> bool:
        """Check if cache entry is expired."""
        if entry.get('expires_at') is None:
            return False
        return time.time() > entry['expires_at']
    
    def _evict_if_needed(self):
        """Evict oldest entries if cache is full."""
        if len(self._cache) >= self._max_size:
            # Remove 10% of oldest entries
            entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].get('created_at', 0)
            )
            for key, _ in entries[:self._max_size // 10]:
                del self._cache[key]
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            if self._is_expired(entry):
                del self._cache[key]
                return None
            
            return entry.get('value')
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        with self._lock:
            self._evict_if_needed()
            
            self._cache[key] = {
                'value': value,
                'created_at': time.time(),
                'expires_at': time.time() + ttl if ttl > 0 else None
            }
            return True
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> bool:
        with self._lock:
            self._cache.clear()
            return True
    
    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            expired = sum(1 for e in self._cache.values() if self._is_expired(e))
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'expired_entries': expired
            }


class FileCache(CacheBackend):
    """
    File-based cache for persistence across restarts.
    
    Stores cache entries as JSON files.
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
    
    def _get_path(self, key: str) -> Path:
        """Get file path for cache key."""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self._cache_dir / f"{key_hash}.json"
    
    def get(self, key: str) -> Optional[Any]:
        path = self._get_path(key)
        
        with self._lock:
            if not path.exists():
                return None
            
            try:
                with open(path, 'r') as f:
                    entry = json.load(f)
                
                # Check expiration
                if entry.get('expires_at') and time.time() > entry['expires_at']:
                    path.unlink()
                    return None
                
                return entry.get('value')
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read cache file {path}: {e}")
                return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        path = self._get_path(key)
        
        with self._lock:
            try:
                entry = {
                    'key': key,
                    'value': value,
                    'created_at': time.time(),
                    'expires_at': time.time() + ttl if ttl > 0 else None
                }
                
                with open(path, 'w') as f:
                    json.dump(entry, f)
                
                return True
            except (IOError, TypeError) as e:
                logger.warning(f"Failed to write cache file {path}: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        path = self._get_path(key)
        
        with self._lock:
            if path.exists():
                path.unlink()
                return True
            return False
    
    def clear(self) -> bool:
        with self._lock:
            for path in self._cache_dir.glob("*.json"):
                try:
                    path.unlink()
                except IOError:
                    pass
            return True


class RedisCache(CacheBackend):
    """
    Redis-based cache for distributed deployments.
    
    Falls back to in-memory if Redis unavailable.
    """
    
    def __init__(self, redis_url: Optional[str] = None, prefix: str = "podcastos"):
        self._prefix = prefix
        self._client = None
        self._fallback = InMemoryCache()
        
        redis_url = redis_url or os.getenv("REDIS_URL")
        
        if redis_url:
            try:
                import redis
                self._client = redis.from_url(redis_url)
                self._client.ping()
                logger.info(f"Connected to Redis: {redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
                self._client = None
    
    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._prefix}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        if self._client is None:
            return self._fallback.get(key)
        
        try:
            value = self._client.get(self._key(key))
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return self._fallback.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        if self._client is None:
            return self._fallback.set(key, value, ttl)
        
        try:
            self._client.setex(
                self._key(key),
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            return self._fallback.set(key, value, ttl)
    
    def delete(self, key: str) -> bool:
        if self._client is None:
            return self._fallback.delete(key)
        
        try:
            self._client.delete(self._key(key))
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
            return self._fallback.delete(key)
    
    def clear(self) -> bool:
        if self._client is None:
            return self._fallback.clear()
        
        try:
            keys = self._client.keys(f"{self._prefix}:*")
            if keys:
                self._client.delete(*keys)
            return True
        except Exception as e:
            logger.warning(f"Redis clear failed: {e}")
            return False


# Global cache instance
_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get the global cache instance."""
    global _cache
    
    if _cache is None:
        # Try Redis first, then file cache, then in-memory
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            _cache = RedisCache(redis_url)
        else:
            # Use file cache for persistence
            cache_dir = os.getenv("CACHE_DIR", "cache/research")
            _cache = FileCache(cache_dir)
    
    return _cache


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    key_parts = [str(a) for a in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = ":".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(ttl: int = 3600, key_prefix: str = ""):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time-to-live in seconds (default: 1 hour)
        key_prefix: Optional prefix for cache key
        
    Usage:
        @cached(ttl=3600, key_prefix="research")
        async def research_topic(topic: str) -> dict:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cache = get_cache()
            cached_result = cache.get(key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for {key}")
                return cached_result
            
            # Execute function
            logger.debug(f"Cache miss for {key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            cache.set(key, result, ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cache = get_cache()
            cached_result = cache.get(key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for {key}")
                return cached_result
            
            # Execute function
            logger.debug(f"Cache miss for {key}")
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(key, result, ttl)
            
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Convenience functions
def cache_research_result(topic: str, result: dict, ttl: int = 7200) -> bool:
    """Cache a research result for a topic."""
    key = f"research:{cache_key(topic)}"
    return get_cache().set(key, result, ttl)


def get_cached_research(topic: str) -> Optional[dict]:
    """Get cached research result for a topic."""
    key = f"research:{cache_key(topic)}"
    return get_cache().get(key)


def invalidate_research_cache(topic: Optional[str] = None) -> bool:
    """Invalidate research cache for a topic or all topics."""
    if topic:
        key = f"research:{cache_key(topic)}"
        return get_cache().delete(key)
    # Clear all research cache (only works well with Redis)
    return get_cache().clear()
