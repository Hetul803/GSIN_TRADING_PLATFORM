# backend/market_data/request_queue.py
"""
Market Data Request Queue - Prevents rate limiting and manages provider requests.

Features:
- Global request queue
- Provider rate tracking
- Exponential backoff
- Cache reuse
- Prevents duplicate simultaneous requests
- Ensures evolution worker & backtests never hit raw providers
"""
import os
import asyncio
import time
from typing import Dict, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta
from threading import Lock
from collections import deque
import hashlib

from .cache import MarketDataCache


class RateTracker:
    """Tracks rate limits per provider."""
    
    def __init__(self, max_requests_per_minute: int = 60):
        self.max_requests = max_requests_per_minute
        self.requests: deque = deque(maxlen=max_requests_per_minute)
        self.lock = Lock()
    
    def can_make_request(self) -> bool:
        """Check if we can make a request without exceeding rate limit."""
        with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()
            
            return len(self.requests) < self.max_requests
    
    def record_request(self):
        """Record a request."""
        with self.lock:
            self.requests.append(time.time())
    
    def wait_time(self) -> float:
        """Calculate how long to wait before next request."""
        with self.lock:
            if not self.requests:
                return 0.0
            
            now = time.time()
            # Remove old requests
            while self.requests and self.requests[0] < now - 60:
                self.requests.popleft()
            
            if len(self.requests) < self.max_requests:
                return 0.0
            
            # Wait until oldest request is 1 minute old
            oldest = self.requests[0]
            wait = 60 - (now - oldest) + 0.1  # Add 0.1s buffer
            return max(0.0, wait)


class RequestQueue:
    """
    Global request queue for market data providers.
    Prevents rate limiting and manages concurrent requests.
    """
    
    def __init__(self):
        self.cache = MarketDataCache()
        self.rate_trackers: Dict[str, RateTracker] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.lock = Lock()
        self.backoff_times: Dict[str, float] = {}  # Provider -> backoff until timestamp
        self.request_counts: Dict[str, int] = {}  # Provider -> consecutive failures
    
    def _get_rate_tracker(self, provider_name: str) -> RateTracker:
        """Get or create rate tracker for provider."""
        if provider_name not in self.rate_trackers:
            # Default: 60 requests per minute (conservative)
            max_requests = int(os.environ.get(f"{provider_name.upper()}_RATE_LIMIT", "60"))
            self.rate_trackers[provider_name] = RateTracker(max_requests)
        return self.rate_trackers[provider_name]
    
    def _make_request_key(self, provider: str, func_name: str, *args, **kwargs) -> str:
        """Create a unique key for a request to prevent duplicates."""
        key_parts = [provider, func_name]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_str = ":".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def execute_with_queue(
        self,
        provider_name: str,
        func: Callable,
        func_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a market data function through the queue.
        
        Args:
            provider_name: Name of provider (e.g., "alpaca", "polygon")
            func: Function to call
            func_name: Name of function (e.g., "get_price", "get_candles")
            *args, **kwargs: Arguments to pass to function
        
        Returns:
            Result from function
        """
        import os
        
        # Check cache first
        cache_type = func_name.replace("get_", "")
        symbol = args[0] if args else kwargs.get("symbol", "")
        interval = kwargs.get("interval") if "interval" in kwargs else None
        
        cached_value = self.cache.get(cache_type, symbol, interval, ttl_seconds=5)
        if cached_value is not None:
            return cached_value
        
        # Check if provider is in backoff
        if provider_name in self.backoff_times:
            backoff_until = self.backoff_times[provider_name]
            if time.time() < backoff_until:
                wait_time = backoff_until - time.time()
                await asyncio.sleep(wait_time)
                # Clear backoff after waiting
                if time.time() >= backoff_until:
                    del self.backoff_times[provider_name]
                    self.request_counts[provider_name] = 0
        
        # Check for duplicate request
        request_key = self._make_request_key(provider_name, func_name, *args, **kwargs)
        
        with self.lock:
            if request_key in self.pending_requests:
                # Wait for existing request to complete
                future = self.pending_requests[request_key]
                try:
                    return await asyncio.wait_for(future, timeout=30.0)
                except asyncio.TimeoutError:
                    # Remove stale future
                    del self.pending_requests[request_key]
        
        # Check rate limit
        rate_tracker = self._get_rate_tracker(provider_name)
        
        if not rate_tracker.can_make_request():
            wait_time = rate_tracker.wait_time()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        # Create future for this request
        future = asyncio.Future()
        with self.lock:
            self.pending_requests[request_key] = future
        
        try:
            # Record request
            rate_tracker.record_request()
            
            # Execute function
            result = await asyncio.to_thread(func, *args, **kwargs)
            
            # Cache result
            self.cache.set(cache_type, symbol, result, interval)
            
            # Reset failure count on success
            if provider_name in self.request_counts:
                self.request_counts[provider_name] = 0
            
            # Set future result
            future.set_result(result)
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if rate limit error
            is_rate_limit = (
                "429" in error_msg or
                "rate limit" in error_msg or
                "too many requests" in error_msg
            )
            
            if is_rate_limit:
                # Exponential backoff
                failure_count = self.request_counts.get(provider_name, 0) + 1
                self.request_counts[provider_name] = failure_count
                
                # Exponential backoff: 2^failures seconds, max 60 seconds
                backoff_seconds = min(2 ** failure_count, 60)
                self.backoff_times[provider_name] = time.time() + backoff_seconds
                
                # Wait before retrying
                await asyncio.sleep(backoff_seconds)
                
                # Retry once
                try:
                    result = await asyncio.to_thread(func, *args, **kwargs)
                    self.cache.set(cache_type, symbol, result, interval)
                    future.set_result(result)
                    return result
                except Exception as e2:
                    future.set_exception(e2)
                    raise e2
            else:
                # Non-rate-limit error
                future.set_exception(e)
                raise e
        
        finally:
            # Remove future from pending
            with self.lock:
                if request_key in self.pending_requests:
                    del self.pending_requests[request_key]
    
    def execute_sync(
        self,
        provider_name: str,
        func: Callable,
        func_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Synchronous version of execute_with_queue.
        For use in non-async contexts (like evolution worker).
        """
        import asyncio
        
        # Check cache first
        cache_type = func_name.replace("get_", "")
        symbol = args[0] if args else kwargs.get("symbol", "")
        interval = kwargs.get("interval") if "interval" in kwargs else None
        
        cached_value = self.cache.get(cache_type, symbol, interval, ttl_seconds=5)
        if cached_value is not None:
            return cached_value
        
        # Check rate limit
        rate_tracker = self._get_rate_tracker(provider_name)
        
        if not rate_tracker.can_make_request():
            wait_time = rate_tracker.wait_time()
            if wait_time > 0:
                time.sleep(wait_time)
        
        # Record request
        rate_tracker.record_request()
        
        try:
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            self.cache.set(cache_type, symbol, result, interval)
            
            # Reset failure count
            if provider_name in self.request_counts:
                self.request_counts[provider_name] = 0
            
            return result
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if rate limit error
            is_rate_limit = (
                "429" in error_msg or
                "rate limit" in error_msg or
                "too many requests" in error_msg
            )
            
            if is_rate_limit:
                # Exponential backoff
                failure_count = self.request_counts.get(provider_name, 0) + 1
                self.request_counts[provider_name] = failure_count
                
                backoff_seconds = min(2 ** failure_count, 60)
                self.backoff_times[provider_name] = time.time() + backoff_seconds
                
                # Wait
                time.sleep(backoff_seconds)
                
                # Retry once
                try:
                    result = func(*args, **kwargs)
                    self.cache.set(cache_type, symbol, result, interval)
                    return result
                except:
                    raise e
            else:
                raise e


# Global request queue instance
_request_queue: Optional[RequestQueue] = None


def get_request_queue() -> RequestQueue:
    """Get or create the global request queue instance."""
    global _request_queue
    if _request_queue is None:
        _request_queue = RequestQueue()
    return _request_queue

