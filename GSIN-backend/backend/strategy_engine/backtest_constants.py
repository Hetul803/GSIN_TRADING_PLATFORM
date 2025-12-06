# backend/strategy_engine/backtest_constants.py
"""
PHASE 2: Timeframe-specific minimum candle requirements for backtesting.
"""
from typing import Dict

# PHASE 2: Dynamic minimum candle requirements by timeframe
REQUIRED_CANDLES: Dict[str, int] = {
    "1d": 3000,   # Daily: ~12 years of trading days
    "4h": 500,    # 4-hour: ~83 days
    "1h": 200,    # Hourly: ~8-10 days
    "15m": 100,   # 15-minute: ~25 hours
    "5m": 100,    # 5-minute: ~8 hours
    "1m": 60      # 1-minute: ~1 hour
}

def get_required_candles(timeframe: str) -> int:
    """
    Get minimum required candles for a timeframe.
    
    Args:
        timeframe: Time interval (e.g., "1d", "4h", "1h", "15m", "5m", "1m")
    
    Returns:
        Minimum number of candles required
    """
    return REQUIRED_CANDLES.get(timeframe.lower(), 1000)  # Default to 1000 if unknown

