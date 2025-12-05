# backend/utils/redis_client.py
"""
Redis Client - Centralized Redis connection and utilities.

This module provides:
1. Response caching (replaces in-memory cache)
2. Market data caching (shared across instances)
3. Distributed locks (for worker coordination)
4. Rate limiting (shared across instances)
"""
import os
from typing import Optional, Any, Dict
from pathlib import Path
from dotenv import dotenv_values
import json
from datetime import datetime, timedelta, timezone

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False
    print("WARNING: redis package not installed. Install with: pip install redis")


class RedisClient:
    """
    Centralized Redis client for caching, locks, and rate limiting.
    Falls back gracefully if Redis is not available.
    """
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.is_available = False
        
        # Load Redis URL from config/.env or environment first
        CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
        cfg = {}
        if CFG_PATH.exists():
            cfg = dotenv_values(str(CFG_PATH))
        
        redis_url = os.getenv("REDIS_URL") or cfg.get("REDIS_URL")
        
        if not REDIS_AVAILABLE:
            # Only show warning if REDIS_URL is actually set (not placeholder)
            if redis_url and "your-redis-url" not in redis_url.lower() and "placeholder" not in redis_url.lower():
                print("⚠️  Redis package not installed - using in-memory fallback. Install with: pip install redis")
            return
        
        if not redis_url:
            print("⚠️  REDIS_URL not set - using in-memory fallback")
            return
        
        try:
            # Parse Redis URL and create client
            self.client = redis.from_url(
                redis_url,
                decode_responses=True,  # Automatically decode strings
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.client.ping()
            self.is_available = True
            print("✅ Redis connected successfully")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e} - using in-memory fallback")
            self.client = None
            self.is_available = False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        if not self.is_available or not self.client:
            return None
        
        try:
            value = self.client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Return as string if not JSON
                return value
        except Exception as e:
            print(f"⚠️  Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set value in Redis cache with optional TTL."""
        if not self.is_available or not self.client:
            return False
        
        try:
            # Serialize value
            if isinstance(value, (dict, list)):
                serialized = json.dumps(value)
            else:
                serialized = str(value)
            
            if ttl_seconds:
                self.client.setex(key, ttl_seconds, serialized)
            else:
                self.client.set(key, serialized)
            
            return True
        except Exception as e:
            print(f"⚠️  Redis set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self.is_available or not self.client:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"⚠️  Redis delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.is_available or not self.client:
            return False
        
        try:
            return self.client.exists(key) > 0
        except Exception:
            return False
    
    def acquire_lock(self, lock_key: str, timeout_seconds: int = 60, blocking: bool = True) -> Optional[Any]:
        """
        Acquire a distributed lock.
        
        Args:
            lock_key: Lock identifier
            timeout_seconds: Lock expiration time (prevents deadlocks)
            blocking: If True, wait for lock; if False, return immediately if locked
        
        Returns:
            Lock object if acquired, None otherwise
        """
        if not self.is_available or not self.client:
            return None
        
        try:
            # Use Redis SET with NX (only set if not exists) and EX (expiration)
            lock_acquired = self.client.set(
                lock_key,
                "locked",
                nx=True,  # Only set if key doesn't exist
                ex=timeout_seconds  # Expire after timeout
            )
            
            if lock_acquired:
                return {"key": lock_key, "timeout": timeout_seconds}
            else:
                return None
        except Exception as e:
            print(f"⚠️  Redis lock acquire error: {e}")
            return None
    
    def release_lock(self, lock_obj: Dict[str, Any]) -> bool:
        """Release a distributed lock."""
        if not self.is_available or not self.client or not lock_obj:
            return False
        
        try:
            lock_key = lock_obj.get("key")
            if lock_key:
                self.client.delete(lock_key)
                return True
            return False
        except Exception as e:
            print(f"⚠️  Redis lock release error: {e}")
            return False
    
    def increment(self, key: str, amount: int = 1, ttl_seconds: Optional[int] = None) -> Optional[int]:
        """Increment a counter in Redis."""
        if not self.is_available or not self.client:
            return None
        
        try:
            value = self.client.incrby(key, amount)
            if ttl_seconds and not self.client.ttl(key):
                self.client.expire(key, ttl_seconds)
            return value
        except Exception as e:
            print(f"⚠️  Redis increment error: {e}")
            return None
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes (helper for MCN pruning)."""
        try:
            path = Path(file_path)
            if path.exists():
                return path.stat().st_size
            return None
        except Exception:
            return None


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get or create global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client

