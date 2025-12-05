# backend/utils/response_cache.py
"""
Response cache with Redis support (falls back to in-memory if Redis unavailable).
Useful for caching expensive computations or database queries.
"""
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta, timezone
from threading import Lock
import hashlib
import json

# Lazy initialization of Redis (don't initialize on import)
_redis = None
USE_REDIS = False

def _get_redis():
    """Lazy get Redis client (initialized on first use)."""
    global _redis, USE_REDIS
    if _redis is None:
        try:
            from .redis_client import get_redis_client
            _redis = get_redis_client()
            USE_REDIS = _redis.is_available
        except Exception:
            USE_REDIS = False
            _redis = None
    return _redis


class ResponseCache:
    """
    Thread-safe in-memory cache with TTL support.
    """
    
    def __init__(self, default_ttl_seconds: int = 60):
        """
        Initialize cache.
        
        Args:
            default_ttl_seconds: Default time-to-live for cached items (default: 60 seconds)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
        self.default_ttl = default_ttl_seconds
        # Track prefix for each key to enable prefix-based clearing
        self._prefix_map: Dict[str, str] = {}  # key -> prefix
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Create a cache key from prefix and arguments.
        
        Args:
            prefix: Cache key prefix
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Cache key string
        """
        key_parts = [prefix]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, prefix: str, *args, ttl_seconds: Optional[int] = None, **kwargs) -> Optional[Any]:
        """
        Get cached value (from Redis if available, otherwise in-memory).
        
        Args:
            prefix: Cache key prefix
            *args: Positional arguments for key generation
            ttl_seconds: Optional TTL override
            **kwargs: Keyword arguments for key generation
        
        Returns:
            Cached value or None if not found or expired
        """
        key = self._make_key(prefix, *args, **kwargs)
        ttl = ttl_seconds or self.default_ttl
        
        # Try Redis first if available
        redis_client = _get_redis()
        if USE_REDIS and redis_client:
            redis_key = f"cache:{key}"
            value = redis_client.get(redis_key)
            if value is not None:
                return value
        
        # Fallback to in-memory cache
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            expires_at = entry.get("expires_at")
            
            # Check if expired
            if expires_at and datetime.now(timezone.utc) > expires_at:
                del self.cache[key]
                return None
            
            return entry.get("value")
    
    def set(self, prefix: str, value: Any, *args, ttl_seconds: Optional[int] = None, **kwargs) -> None:
        """
        Set cached value (in Redis if available, otherwise in-memory).
        
        Args:
            prefix: Cache key prefix
            value: Value to cache
            *args: Positional arguments for key generation
            ttl_seconds: Optional TTL override
            **kwargs: Keyword arguments for key generation
        """
        key = self._make_key(prefix, *args, **kwargs)
        ttl = ttl_seconds or self.default_ttl
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        
        # Try Redis first if available
        redis_client = _get_redis()
        if USE_REDIS and redis_client:
            redis_key = f"cache:{key}"
            redis_client.set(redis_key, value, ttl_seconds=ttl)
        
        # Also store in-memory as fallback
        with self.lock:
            self.cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc)
            }
            # Track prefix for this key
            self._prefix_map[key] = prefix
    
    def clear(self, prefix: Optional[str] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            prefix: Optional prefix to clear only matching entries. If None, clears all.
        """
        with self.lock:
            if prefix is None:
                self.cache.clear()
                self._prefix_map.clear()
            else:
                # Clear entries matching prefix
                keys_to_delete = [
                    key for key, cached_prefix in self._prefix_map.items()
                    if cached_prefix == prefix
                ]
                for key in keys_to_delete:
                    del self.cache[key]
                    del self._prefix_map[key]
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        now = datetime.now(timezone.utc)
        removed = 0
        
        with self.lock:
            keys_to_delete = [
                key for key, entry in self.cache.items()
                if entry.get("expires_at") and entry["expires_at"] < now
            ]
            for key in keys_to_delete:
                del self.cache[key]
                self._prefix_map.pop(key, None)  # Remove from prefix map if exists
                removed += 1
        
        return removed
    
    def size(self) -> int:
        """Get current cache size."""
        with self.lock:
            return len(self.cache)


# Global cache instance
_global_cache: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ResponseCache(default_ttl_seconds=60)
    return _global_cache


def cached(prefix: str, ttl_seconds: int = 60):
    """
    Decorator to cache function results.
    
    Usage:
        @cached("user_strategy", ttl_seconds=300)
        def get_user_strategy(user_id: str, strategy_id: str):
            ...
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            cache_key = f"{prefix}:{func.__name__}"
            
            # Try to get from cache
            cached_value = cache.get(cache_key, *args, ttl_seconds=ttl_seconds, **kwargs)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, *args, ttl_seconds=ttl_seconds, **kwargs)
            return result
        
        return wrapper
    return decorator

