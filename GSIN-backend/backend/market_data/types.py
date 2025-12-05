# backend/market_data/types.py
"""
Type definitions for market data.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class PriceData(BaseModel):
    """Real-time price data for a symbol."""
    symbol: str
    price: float
    timestamp: datetime
    volume: Optional[int] = None
    change: Optional[float] = None  # Change from previous close
    change_percent: Optional[float] = None  # Percentage change
    
    @property
    def last_price(self) -> float:
        """Alias for price (for compatibility)."""
        return self.price
    
    @property
    def change_pct(self) -> Optional[float]:
        """Alias for change_percent (for compatibility)."""
        return self.change_percent
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CandleData(BaseModel):
    """OHLCV candle data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class CandleResponse(BaseModel):
    """Response containing multiple candles."""
    symbol: str
    interval: str  # e.g., "1d", "1h", "15m"
    candles: List[CandleData]


class SentimentData(BaseModel):
    """Market sentiment data for a symbol."""
    symbol: str
    sentiment_score: float  # -1.0 to 1.0 (negative = bearish, positive = bullish)
    timestamp: datetime
    source: Optional[str] = None  # Provider name
    confidence: Optional[float] = None  # 0.0 to 1.0


class VolatilityData(BaseModel):
    """Volatility metrics for a symbol."""
    symbol: str
    volatility: float  # Annualized volatility (e.g., 0.25 = 25%)
    timestamp: datetime
    period: Optional[str] = None  # e.g., "30d", "1y"
    beta: Optional[float] = None  # Beta vs market


class MarketOverview(BaseModel):
    """Overall market overview."""
    timestamp: datetime
    total_symbols: int
    gainers: int
    losers: int
    unchanged: int
    avg_volume: Optional[float] = None
    market_cap_total: Optional[float] = None


class MarketDataError(Exception):
    """Custom exception for market data errors."""
    pass

