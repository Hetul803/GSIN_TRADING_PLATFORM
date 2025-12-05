# backend/tests/unit/test_response_cache.py
"""Unit tests for response cache."""
import pytest
import time
from backend.utils.response_cache import ResponseCache, get_cache


class TestResponseCache:
    """Test response cache functionality."""
    
    def test_cache_set_and_get(self):
        """Test setting and getting from cache."""
        cache = ResponseCache(default_ttl_seconds=60)
        cache.set("test", "value", "key1", "key2")
        result = cache.get("test", "key1", "key2")
        assert result == "value"
    
    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = ResponseCache(default_ttl_seconds=1)
        cache.set("test", "value", "key")
        time.sleep(1.1)
        result = cache.get("test", "key")
        assert result is None
    
    def test_cache_clear(self):
        """Test clearing cache."""
        cache = ResponseCache()
        cache.set("test", "value", "key")
        assert cache.size() == 1
        cache.clear()
        assert cache.size() == 0
    
    def test_cache_clear_prefix(self):
        """Test clearing cache by prefix."""
        cache = ResponseCache()
        cache.set("prefix1", "value1", "key")
        cache.set("prefix2", "value2", "key")
        assert cache.size() == 2
        cache.clear("prefix1")
        assert cache.size() == 1
    
    def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = ResponseCache(default_ttl_seconds=1)
        cache.set("test", "value", "key")
        time.sleep(1.1)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.size() == 0
    
    def test_get_cache_singleton(self):
        """Test that get_cache returns singleton."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

