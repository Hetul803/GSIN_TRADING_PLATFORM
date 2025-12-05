# backend/strategy_engine/backtest_constants.py
"""
PHASE 2: Timeframe-specific minimum candle requirements for backtesting.
"""
from typing import Dict

# PHASE 2: Dynamic minimum candle requirements by timeframe
REQUIRED_CANDLES: Dict[str, int] = {
    "1d": 350,   # Daily: ~1 year of trading days
    "4h": 150,   # 4-hour: ~25 days
    "1h": 100,   # Hourly: ~4-5 days
    "15m": 60,   # 15-minute: ~15 hours
    "5m": 50,    # 5-minute: ~4 hours
    "1m": 30     # 1-minute: ~30 minutes
}

def get_required_candles(timeframe: str) -> int:
    """
    Get minimum required candles for a timeframe.
    
    Args:
        timeframe: Time interval (e.g., "1d", "4h", "1h", "15m", "5m", "1m")
    
    Returns:
        Minimum number of candles required
    """
    return REQUIRED_CANDLES.get(timeframe.lower(), 50)  # Default to 50 if unknown

