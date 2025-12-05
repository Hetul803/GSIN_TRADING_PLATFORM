# backend/market_data/asset_router.py
"""
Asset overview endpoint - combines price, volatility, sentiment for a symbol.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

from .market_data_provider import call_with_fallback
from .cache import get_cache
from .types import PriceData, VolatilityData, SentimentData, MarketDataError

router = APIRouter(prefix="/asset", tags=["asset"])


class AssetOverviewResponse(BaseModel):
    """Asset overview combining price, volatility, and sentiment."""
    symbol: str
    last_price: float
    change: Optional[float] = None
    change_pct: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    volatility: Optional[float] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None  # "bullish", "bearish", "neutral"
    timestamp: datetime


@router.get("/overview")
def get_asset_overview(
    symbol: str = Query(..., description="Stock symbol (e.g., AAPL)")
):
    """
    Get comprehensive overview for a symbol.
    Combines price, volatility, and sentiment data.
    Uses PRIMARY provider (Alpaca) with automatic fallback to SECONDARY (Polygon).
    Cached for 5 seconds to reduce API rate limits.
    Returns: { symbol, last_price, change_pct, ohlc, volume, volatility, sentiment }
    """
    cache = get_cache()
    
    # Check cache first (5 second TTL for overview)
    cached = cache.get("overview", symbol, ttl_seconds=5)
    if cached is not None:
        return cached
    
    try:
        # Get price data (with fallback) - this will use its own cache
        price_data = call_with_fallback("get_price", symbol)
        if not price_data:
            raise HTTPException(status_code=404, detail=f"Price data not available for {symbol}")
        
        # Get latest candle for OHLC (with fallback) - this will use its own cache
        candles = call_with_fallback("get_candles", symbol, "1d", 1)
        latest_candle = candles[0] if candles else None
        
        # Get volatility (optional, with fallback)
        volatility_data = None
        try:
            volatility_data = call_with_fallback("get_volatility", symbol)
        except:
            pass  # Volatility is optional
        
        # Get sentiment (optional, with fallback)
        sentiment_data = None
        try:
            sentiment_data = call_with_fallback("get_sentiment", symbol)
        except:
            pass  # Sentiment is optional
        
        # Determine sentiment label
        sentiment_label = None
        sentiment_score = None
        if sentiment_data and sentiment_data.sentiment_score is not None:
            sentiment_score = sentiment_data.sentiment_score
            if sentiment_score > 0.3:
                sentiment_label = "bullish"
            elif sentiment_score < -0.3:
                sentiment_label = "bearish"
            else:
                sentiment_label = "neutral"
        
        result = {
            "symbol": symbol.upper(),
            "last_price": price_data.price,
            "change_pct": price_data.change_percent or price_data.change_pct,
            "ohlc": {
                "open": latest_candle.open if latest_candle else None,
                "high": latest_candle.high if latest_candle else None,
                "low": latest_candle.low if latest_candle else None,
                "close": latest_candle.close if latest_candle else None,
            },
            "volume": price_data.volume or (latest_candle.volume if latest_candle else None),
            "volatility": volatility_data.volatility if volatility_data else None,
            "sentiment": {
                "score": sentiment_score,
                "label": sentiment_label
            } if sentiment_score is not None else None
        }
        
        # Cache the result
        cache.set("overview", symbol, result)
        return result
    except HTTPException:
        raise
    except MarketDataError as e:
        # Check if it's a rate limit error
        error_msg = str(e).lower()
        if "429" in error_msg or "rate limit" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Market data temporarily unavailable due to provider rate limits. Please try again shortly."
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching asset overview: {str(e)}")

