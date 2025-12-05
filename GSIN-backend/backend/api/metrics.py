# backend/api/metrics.py
"""
Prometheus-style metrics endpoint for production observability.
Only enabled in non-public mode or behind ADMIN_API_KEY.
"""
from fastapi import APIRouter, Header, HTTPException, status
from typing import Optional
import os
from collections import defaultdict
from datetime import datetime, timedelta
import time

router = APIRouter(prefix="/metrics", tags=["metrics"])

# In-memory metrics storage (in production, use proper metrics backend)
_metrics = {
    "request_count": defaultdict(lambda: defaultdict(int)),
    "error_count": defaultdict(int),
    "brain_signal_latency": [],
    "backtest_latency": [],
    "market_data_requests": defaultdict(int),
    "rate_limit_hits": defaultdict(int),
    "trade_execution_count": defaultdict(int),
}


def record_request(endpoint: str, status_code: int):
    """Record a request."""
    _metrics["request_count"][endpoint][status_code] += 1


def record_error(endpoint: str):
    """Record an error."""
    _metrics["error_count"][endpoint] += 1


def record_brain_signal_latency(latency_ms: float):
    """Record brain signal generation latency."""
    _metrics["brain_signal_latency"].append({
        "latency_ms": latency_ms,
        "timestamp": datetime.now().isoformat(),
    })
    # Keep only last 1000 entries
    if len(_metrics["brain_signal_latency"]) > 1000:
        _metrics["brain_signal_latency"] = _metrics["brain_signal_latency"][-1000:]


def record_backtest_latency(latency_ms: float):
    """Record backtest latency."""
    _metrics["backtest_latency"].append({
        "latency_ms": latency_ms,
        "timestamp": datetime.now().isoformat(),
    })
    # Keep only last 1000 entries
    if len(_metrics["backtest_latency"]) > 1000:
        _metrics["backtest_latency"] = _metrics["backtest_latency"][-1000:]


def record_market_data_request(provider: str):
    """Record market data request."""
    _metrics["market_data_requests"][provider] += 1


def record_rate_limit_hit(provider: str):
    """Record rate limit hit."""
    _metrics["rate_limit_hits"][provider] += 1


def record_trade_execution(mode: str):
    """Record trade execution."""
    _metrics["trade_execution_count"][mode] += 1


def _check_metrics_access(admin_api_key: Optional[str] = None) -> bool:
    """Check if metrics endpoint should be accessible."""
    env = os.getenv("ENVIRONMENT", "development")
    
    # In production, require ADMIN_API_KEY
    if env == "production":
        expected_key = os.getenv("ADMIN_API_KEY")
        if not expected_key or admin_api_key != expected_key:
            return False
    
    # In development, allow access
    return True


@router.get("")
def get_metrics(admin_api_key: Optional[str] = Header(None, alias="X-Admin-API-Key")):
    """
    Get Prometheus-style metrics.
    
    Requires ADMIN_API_KEY header in production.
    """
    if not _check_metrics_access(admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Metrics endpoint requires ADMIN_API_KEY in production"
        )
    
    # Calculate histogram stats
    brain_latencies = [m["latency_ms"] for m in _metrics["brain_signal_latency"][-100:]]
    backtest_latencies = [m["latency_ms"] for m in _metrics["backtest_latency"][-100:]]
    
    def calc_stats(latencies):
        if not latencies:
            return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        return {
            "min": min(sorted_latencies),
            "max": max(sorted_latencies),
            "avg": sum(sorted_latencies) / n,
            "p50": sorted_latencies[int(n * 0.5)],
            "p95": sorted_latencies[int(n * 0.95)] if n > 1 else sorted_latencies[0],
            "p99": sorted_latencies[int(n * 0.99)] if n > 1 else sorted_latencies[0],
        }
    
    return {
        "request_count": dict(_metrics["request_count"]),
        "error_count": dict(_metrics["error_count"]),
        "brain_signal_latency": calc_stats(brain_latencies),
        "backtest_latency": calc_stats(backtest_latencies),
        "market_data_requests": dict(_metrics["market_data_requests"]),
        "rate_limit_hits": dict(_metrics["rate_limit_hits"]),
        "trade_execution_count": dict(_metrics["trade_execution_count"]),
        "timestamp": datetime.now().isoformat(),
    }

