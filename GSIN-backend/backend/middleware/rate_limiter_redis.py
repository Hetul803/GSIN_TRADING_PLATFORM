# backend/middleware/rate_limiter_redis.py
"""
PHASE 5: Redis-compatible rate limiter.
Falls back to in-memory if Redis is not available.
"""
import os
from typing import Optional, Tuple
import time

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class RedisRateLimiter:
    """Redis-based rate limiter with in-memory fallback."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.use_redis = False
        
        # Try to connect to Redis
        if REDIS_AVAILABLE:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                # Test connection
                self.redis_client.ping()
                self.use_redis = True
                print("✅ Redis rate limiter connected")
            except Exception as e:
                print(f"⚠️  Redis not available, using in-memory rate limiter: {e}")
                self.use_redis = False
        else:
            print("⚠️  Redis not installed, using in-memory rate limiter")
    
    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Check if request is allowed using Redis or in-memory fallback.
        
        Returns:
            (is_allowed, remaining_requests)
        """
        if self.use_redis and self.redis_client:
            return self._redis_check(key, max_requests, window_seconds)
        else:
            return self._memory_check(key, max_requests, window_seconds)
    
    def _redis_check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """Check rate limit using Redis."""
        try:
            # Use Redis sliding window log algorithm
            now = time.time()
            window_start = now - window_seconds
            
            # Remove old entries
            self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            current_count = self.redis_client.zcard(key)
            
            if current_count >= max_requests:
                # Calculate TTL for the oldest entry
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    ttl = int(oldest[0][1] + window_seconds - now)
                else:
                    ttl = window_seconds
                return False, 0
            
            # Add current request
            self.redis_client.zadd(key, {str(now): now})
            self.redis_client.expire(key, window_seconds)
            
            remaining = max_requests - current_count - 1
            return True, max(0, remaining)
        except Exception as e:
            print(f"⚠️  Redis rate limit check failed: {e}, falling back to memory")
            return self._memory_check(key, max_requests, window_seconds)
    
    def _memory_check(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """Fallback in-memory check."""
        from .rate_limiter import rate_limiter
        return rate_limiter.is_allowed(key, max_requests, window_seconds)


# Global Redis rate limiter instance
redis_rate_limiter = RedisRateLimiter()

