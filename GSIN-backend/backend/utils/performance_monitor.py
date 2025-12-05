# backend/utils/performance_monitor.py
"""
Performance monitoring utilities.
"""
import time
import functools
from typing import Dict, Any, Callable
from collections import defaultdict
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, list] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
    
    def record_timing(self, operation: str, duration: float):
        """Record timing for an operation."""
        self.metrics[operation].append({
            "duration": duration,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        # Keep only last 1000 measurements
        if len(self.metrics[operation]) > 1000:
            self.metrics[operation] = self.metrics[operation][-1000:]
    
    def increment_counter(self, counter: str, value: int = 1):
        """Increment a counter."""
        self.counters[counter] += value
    
    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for an operation."""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        
        durations = [m["duration"] for m in self.metrics[operation]]
        return {
            "count": len(durations),
            "min": min(durations),
            "max": max(durations),
            "avg": sum(durations) / len(durations),
            "p50": sorted(durations)[len(durations) // 2],
            "p95": sorted(durations)[int(len(durations) * 0.95)],
            "p99": sorted(durations)[int(len(durations) * 0.99)],
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all operations."""
        return {
            "operations": {
                op: self.get_stats(op) for op in self.metrics.keys()
            },
            "counters": dict(self.counters)
        }


# Global monitor instance
_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    return _monitor


def monitor_performance(operation_name: str = None):
    """
    Decorator to monitor function performance.
    
    Usage:
        @monitor_performance("database_query")
        def query_db():
            ...
    """
    def decorator(func: Callable):
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                _monitor.record_timing(op_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start
                _monitor.record_timing(f"{op_name}_error", duration)
                raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                _monitor.record_timing(op_name, duration)
                return result
            except Exception as e:
                duration = time.time() - start
                _monitor.record_timing(f"{op_name}_error", duration)
                raise
        
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return wrapper
    
    return decorator

