# backend/market_data/sector_cache.py
"""
Sector metadata cache for symbols.
PHASE 4: Caches sector information from Alpaca API.
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from threading import Lock
import time

# In-memory cache with TTL
_sector_cache: Dict[str, Dict[str, any]] = {}
_cache_lock = Lock()
CACHE_TTL_HOURS = 24  # Cache sector data for 24 hours


class SectorCache:
    """Cache for symbol sector metadata."""
    
    @staticmethod
    def get(symbol: str) -> Optional[str]:
        """
        Get cached sector for a symbol.
        
        Returns:
            Sector name if cached and not expired, None otherwise
        """
        with _cache_lock:
            symbol_upper = symbol.upper()
            if symbol_upper in _sector_cache:
                entry = _sector_cache[symbol_upper]
                # Check if expired
                if time.time() - entry["timestamp"] < (CACHE_TTL_HOURS * 3600):
                    return entry["sector"]
                else:
                    # Expired, remove
                    del _sector_cache[symbol_upper]
            return None
    
    @staticmethod
    def set(symbol: str, sector: Optional[str]):
        """
        Cache sector for a symbol.
        
        Args:
            symbol: Stock symbol
            sector: Sector name (or None if not available)
        """
        with _cache_lock:
            _sector_cache[symbol.upper()] = {
                "sector": sector,
                "timestamp": time.time()
            }
    
    @staticmethod
    def clear():
        """Clear all cached sectors."""
        with _cache_lock:
            _sector_cache.clear()
    
    @staticmethod
    def size() -> int:
        """Get number of cached entries."""
        with _cache_lock:
            return len(_sector_cache)

