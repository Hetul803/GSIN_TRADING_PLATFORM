# backend/middleware/rate_limiter.py
"""
PHASE 6: Rate Limiting Middleware
Per-user and per-IP rate limiting for production.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing import Dict, Tuple
from collections import defaultdict
import time
import os
from datetime import datetime, timedelta


class RateLimiter:
    """In-memory rate limiter (for production, use Redis)."""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 300  # Clean up every 5 minutes
        self.last_cleanup = time.time()
    
    def _cleanup_old_entries(self):
        """Remove old entries to prevent memory leak."""
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            cutoff = current_time - 3600  # Keep last hour
            for key in list(self.requests.keys()):
                self.requests[key] = [
                    ts for ts in self.requests[key] if ts > cutoff
                ]
                if not self.requests[key]:
                    del self.requests[key]
            self.last_cleanup = current_time
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if request is allowed.
        
        Returns:
            (is_allowed, remaining_requests)
        """
        self._cleanup_old_entries()
        
        current_time = time.time()
        cutoff = current_time - window_seconds
        
        # Remove old requests
        self.requests[key] = [
            ts for ts in self.requests[key] if ts > cutoff
        ]
        
        # Check limit
        if len(self.requests[key]) >= max_requests:
            return False, 0
        
        # Add current request
        self.requests[key].append(current_time)
        
        remaining = max_requests - len(self.requests[key])
        return True, remaining


# Global rate limiter instance
rate_limiter = RateLimiter()

# PHASE 5: Try to use Redis if available
try:
    from .rate_limiter_redis import redis_rate_limiter
    # Use Redis if available, otherwise fall back to in-memory
    if redis_rate_limiter.use_redis:
        rate_limiter = redis_rate_limiter
        print("✅ Using Redis for rate limiting")
except ImportError:
    pass


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.
    Limits requests per user (JWT) and per IP address.
    """
    
    # Rate limits (requests per window)
    RATE_LIMITS = {
        "default": (100, 60),  # 100 requests per 60 seconds
        "brain": (20, 60),  # 20 Brain requests per 60 seconds
        "trading": (50, 60),  # 50 trading requests per 60 seconds
        "market_data": (200, 60),  # 200 market data requests per 60 seconds
    }
    
    # Per-IP limits (stricter)
    IP_LIMITS = {
        "default": (200, 60),  # 200 requests per 60 seconds per IP
    }
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for OPTIONS requests (CORS preflight) and health checks
        if request.method == "OPTIONS" or request.url.path in ["/health", "/api/system/integrity"]:
            return await call_next(request)
        
        # Determine rate limit based on endpoint
        path = request.url.path
        if "/brain" in path:
            limit_type = "brain"
        elif "/broker" in path or "/trades" in path:
            limit_type = "trading"
        elif "/market" in path:
            limit_type = "market_data"
        else:
            limit_type = "default"
        
        max_requests, window = self.RATE_LIMITS.get(limit_type, self.RATE_LIMITS["default"])
        
        # Get user ID from JWT (if available)
        user_id = getattr(request.state, "user_id", None)
        
        # Get IP address
        ip_address = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        
        # Check per-IP limit
        ip_max, ip_window = self.IP_LIMITS.get("default", (200, 60))
        ip_allowed, ip_remaining = rate_limiter.is_allowed(
            f"ip:{ip_address}",
            ip_max,
            ip_window
        )
        
        if not ip_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded (IP). Please try again later.",
                    "retry_after": ip_window
                },
                headers={
                    "X-RateLimit-Limit": str(ip_max),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + ip_window),
                    "Retry-After": str(ip_window)
                }
            )
        
        # Check per-user limit (if authenticated)
        if user_id:
            user_allowed, user_remaining = rate_limiter.is_allowed(
                f"user:{user_id}:{limit_type}",
                max_requests,
                window
            )
            
            if not user_allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded ({limit_type}). Please try again later.",
                        "retry_after": window
                    },
                    headers={
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + window),
                        "Retry-After": str(window)
                    }
                )
            
            # Add rate limit headers
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(user_remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)
            return response
        else:
            # Unauthenticated requests use IP limit
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(ip_max)
            response.headers["X-RateLimit-Remaining"] = str(ip_remaining)
            return response

