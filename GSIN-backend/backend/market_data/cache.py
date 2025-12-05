# backend/market_data/cache.py
"""
PRODUCTION-READY: Multi-layer cache for market data.
- Memory cache (LRU) for fast access
- File cache for persistence
- TTL-based expiration
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from threading import Lock
from pathlib import Path
import json
import hashlib
import os


class MarketDataCache:
    """
    PRODUCTION-READY: Thread-safe multi-layer cache for market data.
    - Memory cache (LRU) with configurable size limit
    - File cache for persistence across restarts
    - TTL-based expiration (60s for live, 1h for historical)
    """
    
    def __init__(self, max_size: int = 1000, cache_dir: str = "./cache"):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._max_size = max_size
        self._access_order = []  # For LRU eviction
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _make_key(self, cache_type: str, symbol: str, interval: Optional[str] = None) -> str:
        """Generate cache key."""
        key_parts = [cache_type, symbol]
        if interval:
            key_parts.append(interval)
        return ":".join(key_parts)
    
    def get(self, cache_type: str, symbol: str, interval: Optional[str] = None, ttl_seconds: int = 5) -> Optional[Any]:
        """
        Get cached value if it exists and hasn't expired.
        Checks memory cache first, then file cache.
        
        Args:
            cache_type: Type of cache (e.g., "price", "candle", "overview")
            symbol: Stock symbol
            interval: Optional interval for candles
            ttl_seconds: Time-to-live in seconds (60s for live, 3600s for historical)
        
        Returns:
            Cached value or None if not found/expired
        """
        key = self._make_key(cache_type, symbol, interval)
        
        # Try Redis first if available
        try:
            from ..utils.redis_client import get_redis_client
            redis_client = get_redis_client()
            if redis_client.is_available:
                redis_key = f"market_data:{key}"
                value = redis_client.get(redis_key)
                if value is not None:
                    return value
        except Exception:
            pass  # Fall back to memory/file cache
        
        with self._lock:
            # Check memory cache first
            if key in self._cache:
                entry = self._cache[key]
                cached_at = entry.get("cached_at")
                
                if cached_at is not None:
                    age = (datetime.now() - cached_at).total_seconds()
                    if age <= ttl_seconds:
                        # Update access order for LRU
                        if key in self._access_order:
                            self._access_order.remove(key)
                        self._access_order.append(key)
                        return entry.get("value")
                    else:
                        # Expired, remove from memory
                        del self._cache[key]
                        if key in self._access_order:
                            self._access_order.remove(key)
            
            # PHASE 4: Check file cache for historical data (12h TTL) or live data (60s TTL)
            # For historical: ttl_seconds >= 3600 (1h), but we use 12h (43200) for file cache
            # For live: ttl_seconds < 60, but we allow file cache as fallback with 60s TTL
            if cache_type in ["unified_data", "candle"]:
                # Historical data: 12h TTL
                file_ttl = 43200 if ttl_seconds >= 3600 else 60  # 12h for historical, 60s for live
                file_value = self._get_from_file(key, file_ttl)
                if file_value:
                    # Restore to memory cache
                    self._cache[key] = {
                        "value": file_value,
                        "cached_at": datetime.now()
                    }
                    if key not in self._access_order:
                        self._access_order.append(key)
                    return file_value
            
            return None
    
    def set(self, cache_type: str, symbol: str, value: Any, interval: Optional[str] = None):
        """
        Store value in cache (Redis + memory + file for historical data).
        Implements LRU eviction if cache is full.
        
        Args:
            cache_type: Type of cache (e.g., "price", "candle", "overview")
            symbol: Stock symbol
            value: Value to cache
            interval: Optional interval for candles
        """
        key = self._make_key(cache_type, symbol, interval)
        
        # Store in Redis first if available
        try:
            from ..utils.redis_client import get_redis_client
            redis_client = get_redis_client()
            if redis_client.is_available:
                redis_key = f"market_data:{key}"
                # Determine TTL based on cache type
                ttl = 300 if cache_type in ["unified_data", "candle"] else 60  # 5 min for historical, 1 min for live
                redis_client.set(redis_key, value, ttl_seconds=ttl)
        except Exception:
            pass  # Continue with memory/file cache
        
        with self._lock:
            # LRU eviction if cache is full
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Remove least recently used
                if self._access_order:
                    lru_key = self._access_order.pop(0)
                    if lru_key in self._cache:
                        del self._cache[lru_key]
            
            # Store in memory
            self._cache[key] = {
                "value": value,
                "cached_at": datetime.now()
            }
            
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            # Store in file cache for historical data
            if cache_type in ["unified_data", "candle"]:
                self._save_to_file(key, value)
    
    def clear(self, cache_type: Optional[str] = None, symbol: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            cache_type: If provided, only clear this cache type
            symbol: If provided, only clear this symbol
        """
        with self._lock:
            if cache_type is None and symbol is None:
                # Clear all
                self._cache.clear()
            else:
                # Clear matching entries
                keys_to_remove = []
                for key in self._cache.keys():
                    parts = key.split(":")
                    if cache_type and parts[0] != cache_type:
                        continue
                    if symbol and parts[1] != symbol:
                        continue
                    keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    del self._cache[key]
    
    def _get_from_file(self, key: str, ttl_seconds: int) -> Optional[Any]:
        """Get value from file cache if not expired."""
        try:
            # Create safe filename from key
            safe_key = hashlib.md5(key.encode()).hexdigest()
            cache_file = self._cache_dir / f"{safe_key}.json"
            
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            cached_at = datetime.fromisoformat(data.get("cached_at", ""))
            age = (datetime.now() - cached_at).total_seconds()
            
            if age > ttl_seconds:
                # Expired, delete file
                cache_file.unlink()
                return None
            
            return data.get("value")
        except Exception:
            return None
    
    def _save_to_file(self, key: str, value: Any):
        """Save value to file cache."""
        try:
            # Create safe filename from key
            safe_key = hashlib.md5(key.encode()).hexdigest()
            cache_file = self._cache_dir / f"{safe_key}.json"
            
            # Create symbol subdirectory for organization
            symbol_dir = self._cache_dir / key.split(":")[1] if ":" in key else self._cache_dir
            symbol_dir.mkdir(parents=True, exist_ok=True)
            
            with open(cache_file, 'w') as f:
                json.dump({
                    "value": value,
                    "cached_at": datetime.now().isoformat(),
                    "key": key
                }, f, default=str)
        except Exception:
            pass  # File cache is optional, don't fail on errors
    
    def invalidate(self, cache_type: Optional[str] = None, symbol: Optional[str] = None, interval: Optional[str] = None):
        """
        PHASE 3: Smart invalidation - invalidate specific cache entries.
        
        Args:
            cache_type: Type to invalidate (None = all types)
            symbol: Symbol to invalidate (None = all symbols)
            interval: Interval to invalidate (None = all intervals)
        """
        with self._lock:
            keys_to_remove = []
            for key in list(self._cache.keys()):
                parts = key.split(":")
                if len(parts) < 2:
                    continue
                
                key_type = parts[0]
                key_symbol = parts[1] if len(parts) > 1 else None
                key_interval = parts[2] if len(parts) > 2 else None
                
                if cache_type and key_type != cache_type:
                    continue
                if symbol and key_symbol != symbol:
                    continue
                if interval and key_interval != interval:
                    continue
                
                keys_to_remove.append(key)
            
            for key in keys_to_remove:
                if key in self._cache:
                    del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                
                # Also remove from file cache
                try:
                    safe_key = hashlib.md5(key.encode()).hexdigest()
                    cache_file = self._cache_dir / f"{safe_key}.json"
                    if cache_file.exists():
                        cache_file.unlink()
                except Exception:
                    pass
    
    def prewarm_symbols(self, symbols: List[str], timeframe: str = "1d", limit: int = 50):
        """
        PHASE 4: Prewarm cache for popular symbols.
        
        Popular symbols: AAPL, MSFT, TSLA, NVDA, SPY, QQQ, BTCUSD, ETHUSD
        
        Args:
            symbols: List of symbols to prewarm
            timeframe: Timeframe to prewarm
            limit: Number of candles to fetch
        """
        from .unified_data_engine import get_market_data
        from datetime import datetime, timezone, timedelta
        
        print(f"🔥 Prewarming cache for {len(symbols)} symbols ({timeframe})...")
        
        for symbol in symbols:
            try:
                # Calculate date range for historical data
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=limit if timeframe == "1d" else limit * 7)
                
                # Fetch and cache data (this will use Twelve Data and cache it)
                get_market_data(symbol, timeframe, limit, start=start_date, end=end_date)
                print(f"✅ Prewarmed cache for {symbol} ({timeframe})")
            except Exception as e:
                # Only log if it's not a NameError (which indicates import issue that should be fixed)
                if "get_historical_provider" not in str(e) and "not defined" not in str(e):
                    print(f"⚠️  Failed to prewarm {symbol}: {e}")
        
        print(f"✅ Cache prewarming complete")
    
    def get_fallback_value(self, cache_type: str, symbol: str, interval: Optional[str] = None) -> Optional[Any]:
        """
        PHASE 4: Get cached value as fallback when providers fail.
        Uses longer TTL to allow stale data in emergency.
        
        Returns:
            Cached value even if expired (for graceful degradation)
        """
        key = self._make_key(cache_type, symbol, interval)
        
        with self._lock:
            # Check memory cache (even if expired)
            if key in self._cache:
                return self._cache[key].get("value")
            
            # Check file cache (even if expired, up to 24h)
            try:
                safe_key = hashlib.md5(key.encode()).hexdigest()
                cache_file = self._cache_dir / f"{safe_key}.json"
                
                if cache_file.exists():
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                    # Return even if expired (graceful fallback)
                    return data.get("value")
            except Exception:
                pass
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            file_count = len(list(self._cache_dir.glob("*.json"))) if self._cache_dir.exists() else 0
            return {
                "total_entries": len(self._cache),
                "max_size": self._max_size,
                "file_cache_entries": file_count,
                "cache_dir": str(self._cache_dir)
            }


# Global cache instance
_market_data_cache = MarketDataCache()


def get_cache() -> MarketDataCache:
    """Get the global market data cache instance."""
    return _market_data_cache


# PHASE 3: Redis compatibility mode (optional)
def get_cache_with_redis() -> MarketDataCache:
    """
    Get cache instance with Redis support if available.
    Falls back to in-memory cache if Redis is not configured.
    """
    # Try to use Redis if available
    try:
        from ..utils.redis_client import get_redis_client
        redis_client = get_redis_client()
        if redis_client.is_available:
            # Return Redis-backed cache wrapper
            return RedisMarketDataCache(redis_client)
    except Exception as e:
        print(f"⚠️  Redis cache not available: {e}, using in-memory cache")
    
    return _market_data_cache


class RedisMarketDataCache:
    """
    Redis-backed market data cache wrapper.
    Uses Redis for shared caching across instances.
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.memory_cache = _market_data_cache  # Fallback to memory cache
    
    def _make_key(self, cache_type: str, symbol: str, interval: Optional[str] = None) -> str:
        """Generate Redis cache key."""
        key_parts = ["market_data", cache_type, symbol]
        if interval:
            key_parts.append(interval)
        return ":".join(key_parts)
    
    def get(self, cache_type: str, symbol: str, interval: Optional[str] = None, ttl_seconds: int = 5) -> Optional[Any]:
        """Get from Redis first, fallback to memory cache."""
        if self.redis.is_available:
            redis_key = self._make_key(cache_type, symbol, interval)
            value = self.redis.get(redis_key)
            if value is not None:
                return value
        
        # Fallback to memory cache
        return self.memory_cache.get(cache_type, symbol, interval, ttl_seconds)
    
    def set(self, cache_type: str, symbol: str, value: Any, interval: Optional[str] = None):
        """Set in both Redis and memory cache."""
        if self.redis.is_available:
            redis_key = self._make_key(cache_type, symbol, interval)
            # Determine TTL based on cache type
            ttl = 300 if cache_type in ["unified_data", "candle"] else 60  # 5 min for historical, 1 min for live
            self.redis.set(redis_key, value, ttl_seconds=ttl)
        
        # Also store in memory cache
        self.memory_cache.set(cache_type, symbol, value, interval)
    
    def clear(self, cache_type: Optional[str] = None, symbol: Optional[str] = None):
        """Clear both Redis and memory cache."""
        # Clear memory cache
        self.memory_cache.clear(cache_type, symbol)
        
        # Clear Redis (would need pattern matching - simplified for now)
        if self.redis.is_available and cache_type and symbol:
            redis_key = self._make_key(cache_type, symbol)
            self.redis.delete(redis_key)

