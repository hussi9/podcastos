"""
Rate Limiting Module for PodcastOS Flask App.

Provides configurable rate limiting to protect API endpoints from abuse.
"""

import os
import time
import logging
from functools import wraps
from collections import defaultdict
from threading import Lock
from typing import Optional, Callable
from flask import request, jsonify, g

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter with sliding window.
    
    For production, consider using Redis-backed rate limiting.
    """
    
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = Lock()
    
    def _get_key(self, key_func: Optional[Callable] = None) -> str:
        """Get the rate limit key for the current request."""
        if key_func:
            return key_func()
        
        # Default: use IP address
        if request.headers.get('X-Forwarded-For'):
            ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        else:
            ip = request.remote_addr or 'unknown'
        
        return f"{ip}:{request.endpoint}"
    
    def _clean_old_requests(self, key: str, window_seconds: int):
        """Remove requests outside the current window."""
        cutoff = time.time() - window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
    
    def is_rate_limited(
        self,
        max_requests: int,
        window_seconds: int,
        key_func: Optional[Callable] = None
    ) -> tuple[bool, dict]:
        """
        Check if the current request is rate limited.
        
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            key_func: Optional function to generate rate limit key
            
        Returns:
            Tuple of (is_limited, info_dict)
        """
        key = self._get_key(key_func)
        
        with self._lock:
            self._clean_old_requests(key, window_seconds)
            
            current_count = len(self._requests[key])
            remaining = max(0, max_requests - current_count)
            
            if current_count >= max_requests:
                # Calculate retry-after
                if self._requests[key]:
                    oldest = min(self._requests[key])
                    retry_after = int(oldest + window_seconds - time.time()) + 1
                else:
                    retry_after = window_seconds
                
                return True, {
                    'limit': max_requests,
                    'remaining': 0,
                    'reset': retry_after,
                    'retry_after': retry_after
                }
            
            # Record this request
            self._requests[key].append(time.time())
            
            return False, {
                'limit': max_requests,
                'remaining': remaining - 1,
                'reset': window_seconds
            }
    
    def get_stats(self, key: str) -> dict:
        """Get current rate limit stats for a key."""
        with self._lock:
            return {
                'key': key,
                'request_count': len(self._requests.get(key, []))
            }


# Global rate limiter instance
_limiter = RateLimiter()


def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    key_func: Optional[Callable] = None,
    error_message: str = "Rate limit exceeded. Please try again later."
):
    """
    Decorator to rate limit a Flask route.
    
    Args:
        max_requests: Maximum requests per window (default: 60)
        window_seconds: Time window in seconds (default: 60)
        key_func: Optional function to generate rate limit key
        error_message: Error message when rate limited
        
    Usage:
        @app.route('/api/generate')
        @rate_limit(max_requests=10, window_seconds=60)
        def generate():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_limited, info = _limiter.is_rate_limited(
                max_requests=max_requests,
                window_seconds=window_seconds,
                key_func=key_func
            )
            
            # Store rate limit info in request context
            g.rate_limit_info = info
            
            if is_limited:
                logger.warning(
                    f"Rate limit exceeded for {request.endpoint} "
                    f"from {request.remote_addr}"
                )
                
                response = jsonify({
                    'error': error_message,
                    'retry_after': info['retry_after']
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(info['retry_after'])
                response.headers['X-RateLimit-Limit'] = str(info['limit'])
                response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                return response
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def rate_limit_by_user(
    max_requests: int = 60,
    window_seconds: int = 60,
    error_message: str = "Rate limit exceeded. Please try again later."
):
    """
    Rate limit by user ID (from session) if available, else by IP.
    """
    def get_user_key():
        from flask import session
        user_id = session.get('user_id')
        if user_id:
            return f"user:{user_id}:{request.endpoint}"
        
        # Fallback to IP
        if request.headers.get('X-Forwarded-For'):
            ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        else:
            ip = request.remote_addr or 'unknown'
        return f"ip:{ip}:{request.endpoint}"
    
    return rate_limit(
        max_requests=max_requests,
        window_seconds=window_seconds,
        key_func=get_user_key,
        error_message=error_message
    )


# Pre-configured rate limiters for common use cases
def api_rate_limit(f):
    """Standard API rate limit: 60 requests per minute."""
    return rate_limit(max_requests=60, window_seconds=60)(f)


def generation_rate_limit(f):
    """Generation endpoint rate limit: 5 per minute (expensive operation)."""
    return rate_limit(
        max_requests=5,
        window_seconds=60,
        error_message="Too many generation requests. Please wait before generating another episode."
    )(f)


def auth_rate_limit(f):
    """Auth endpoint rate limit: 10 per minute (prevent brute force)."""
    return rate_limit(
        max_requests=10,
        window_seconds=60,
        error_message="Too many authentication attempts. Please try again later."
    )(f)


def strict_rate_limit(f):
    """Strict rate limit: 10 per minute (for sensitive operations)."""
    return rate_limit(max_requests=10, window_seconds=60)(f)


# Add rate limit headers to all responses
def add_rate_limit_headers(response):
    """Add rate limit headers to response (call from after_request)."""
    if hasattr(g, 'rate_limit_info'):
        info = g.rate_limit_info
        response.headers['X-RateLimit-Limit'] = str(info.get('limit', ''))
        response.headers['X-RateLimit-Remaining'] = str(info.get('remaining', ''))
        response.headers['X-RateLimit-Reset'] = str(info.get('reset', ''))
    return response
