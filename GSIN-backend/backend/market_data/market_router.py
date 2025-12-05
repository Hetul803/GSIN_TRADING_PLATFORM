# backend/market_data/market_router.py
"""
Market data API router.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from datetime import datetime

from .market_data_provider import get_provider, register_provider, call_with_fallback
from .adapters.polygon_adapter import PolygonDataProvider
from .adapters.alpaca_adapter import AlpacaDataProvider
from .adapters.finnhub_adapter import FinnhubDataProvider
from .unified_data_engine import get_market_data, get_price_data
from .cache import get_cache
from .types import (
    PriceData,
    CandleResponse,
    CandleData,
    SentimentData,
    VolatilityData,
    MarketOverview,
    MarketDataError
)

# Register providers
register_provider("polygon", PolygonDataProvider)
register_provider("alpaca", AlpacaDataProvider)
register_provider("finnhub", FinnhubDataProvider)

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/heartbeat")
def heartbeat():
    """
    PHASE 3: Heartbeat endpoint for provider health checks.
    
    Returns:
        {
            "status": "ok",
            "providers": {
                "yahoo": {"available": bool, "last_check": str},
                "alpaca": {"available": bool, "last_check": str},
                "polygon": {"available": bool, "last_check": str},
                "finnhub": {"available": bool, "last_check": str}
            }
        }
    """
    from .adapters.yahoo_adapter import YahooDataProvider
    from .adapters.alpaca_adapter import AlpacaDataProvider
    from .adapters.polygon_adapter import PolygonDataProvider
    from .adapters.finnhub_adapter import FinnhubDataProvider
    from datetime import datetime
    
    providers_status = {}
    
    for name, provider_class in [
        ("yahoo", YahooDataProvider),
        ("alpaca", AlpacaDataProvider),
        ("polygon", PolygonDataProvider),
        ("finnhub", FinnhubDataProvider)
    ]:
        try:
            provider = provider_class()
            available = provider.is_available()
            providers_status[name] = {
                "available": available,
                "last_check": datetime.now().isoformat()
            }
        except Exception as e:
            providers_status[name] = {
                "available": False,
                "last_check": datetime.now().isoformat(),
                "error": str(e)
            }
    
    return {
        "status": "ok",
        "providers": providers_status
    }


def get_market_provider():
    """Dependency to get market data provider with fallback."""
    provider = get_provider()
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="Market data provider is not available. Please check ALPACA_API_KEY, ALPACA_SECRET_KEY, MARKET_DATA_API_KEY_POLYGON, and MARKET_DATA_PROVIDER_PRIMARY/SECONDARY environment variables."
        )
    return provider


@router.get("/price")
def get_price(
    symbol: str = Query(..., description="Stock symbol (e.g., AAPL)")
):
    """
    Get real-time price for a symbol.
    Uses multi-provider fallback: Alpaca -> Polygon -> Finnhub.
    Cached for 5 seconds to reduce API rate limits.
    Returns: { symbol, last_price, change_pct, timestamp, provider }
    """
    try:
        price_data = get_price_data(symbol)
        return {
            "symbol": price_data["symbol"],
            "last_price": price_data["price"],
            "change_pct": price_data["change_percent"],
            "timestamp": price_data["timestamp"],
            "provider": price_data.get("provider", "unknown")
        }
    except MarketDataError as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "rate limit" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Market data temporarily unavailable due to provider rate limits. Please try again shortly."
            )
        if "401" in error_msg or "authentication" in error_msg:
            raise HTTPException(
                status_code=503,
                detail="Market data provider authentication failed. Check your API keys."
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching price: {str(e)}")


@router.get("/candle")
def get_candles(
    symbol: str = Query(..., description="Stock symbol (e.g., AAPL)"),
    interval: str = Query("1d", description="Time interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)"),
    limit: int = Query(50, ge=1, le=500, description="Number of candles to return")
):
    """
    Get historical OHLCV candles for a symbol.
    Uses multi-provider fallback: Alpaca -> Polygon -> Finnhub.
    Cached for 60 seconds (1 minute) for daily candles, 30 seconds for intraday.
    Returns: Array of { timestamp, open, high, low, close, volume } with provider info
    """
    try:
        data = get_market_data(symbol, interval, limit)
        return {
            "symbol": data["symbol"],
            "timeframe": data["timeframe"],
            "candles": data["candles"],
            "provider": data.get("provider", "unknown"),
            "cached": data.get("cached", False)
        }
    except MarketDataError as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "rate limit" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Market data temporarily unavailable due to provider rate limits. Please try again shortly."
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching candles: {str(e)}")


@router.get("/sentiment", response_model=SentimentData)
def get_sentiment(
    symbol: str = Query(..., description="Stock symbol (e.g., AAPL)")
):
    """
    Get sentiment data for a symbol.
    Returns neutral sentiment if not available (instead of error).
    """
    try:
        sentiment = call_with_fallback("get_sentiment", symbol)
        if sentiment is None:
            # Return neutral sentiment instead of error
            from datetime import datetime
            from ..market_data.types import SentimentData
            return SentimentData(
                symbol=symbol,
                sentiment_score=0.0,
                sentiment_label="neutral",
                source="fallback",
                timestamp=datetime.now()
            )
        return sentiment
    except HTTPException:
        # If HTTPException is raised, return neutral sentiment
        from datetime import datetime
        from ..market_data.types import SentimentData
        return SentimentData(
            symbol=symbol,
            sentiment_score=0.0,
            sentiment_label="neutral",
            source="fallback",
            timestamp=datetime.now()
        )
    except MarketDataError as e:
        # Return neutral sentiment on market data errors
        from datetime import datetime
        from ..market_data.types import SentimentData
        return SentimentData(
            symbol=symbol,
            sentiment_score=0.0,
            sentiment_label="neutral",
            source="fallback",
            timestamp=datetime.now()
        )
    except Exception as e:
        # Return neutral sentiment on any other error
        from datetime import datetime
        from ..market_data.types import SentimentData
        return SentimentData(
            symbol=symbol,
            sentiment_score=0.0,
            sentiment_label="neutral",
            source="fallback",
            timestamp=datetime.now()
        )


@router.get("/volatility", response_model=VolatilityData)
def get_volatility(
    symbol: str = Query(..., description="Stock symbol (e.g., AAPL)")
):
    """
    FIX 3: Get volatility metrics for a symbol.
    NEVER returns 500 - always returns safe defaults if data unavailable.
    """
    try:
        volatility = call_with_fallback("get_volatility", symbol)
        if volatility is None:
            # FIX 3: Return safe default instead of 404
            return VolatilityData(
                symbol=symbol,
                volatility=0.0,
                timestamp=datetime.now(timezone.utc)
            )
        return volatility
    except Exception as e:
        # FIX 3: Return safe default instead of raising error
        print(f"⚠️  Error fetching volatility for {symbol}: {e}")
        return VolatilityData(
            symbol=symbol,
            volatility=0.0,
            timestamp=datetime.now(timezone.utc)
        )


@router.get("/overview", response_model=MarketOverview)
def get_overview():
    """
    Get overall market overview.
    Returns 404 if overview is not available for either provider.
    """
    try:
        overview = call_with_fallback("get_overview")
        if overview is None:
            raise HTTPException(
                status_code=404,
                detail="Market overview is not available with the current providers."
            )
        return overview
    except HTTPException:
        raise
    except MarketDataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market overview: {str(e)}")


@router.get("/context")
def get_market_context(
    symbol: str = Query(..., description="Stock symbol (e.g., AAPL)")
):
    """
    PHASE 1: Get comprehensive market context with all required fields.
    
    Returns:
        {
            "symbol": str,
            "price": float,
            "volume": float,  # Latest volume (last candle or average of last 20)
            "annualized_volatility": float,  # PHASE 1: Annualized volatility
            "change_24h": float,  # PHASE 1: 24h percentage change
            "change_7d": float,  # PHASE 1: 7d percentage change
            "sentiment": str,  # "bullish" | "bearish" | "neutral"
            "regime": str,  # "risk-on" | "risk-off" | "neutral" (mapped from bull_trend/bear_trend/range)
            "regime_confidence": float,  # 0-1
            "timestamp": str
        }
    """
    from datetime import timezone, timedelta
    from ..brain.regime_detector import RegimeDetector
    from .market_data_provider import get_historical_provider
    
    try:
        # Get price data
        price_data = get_price_data(symbol)
        current_price = price_data.get("price", 0.0)
        
        # PHASE 1: Get historical candles from Twelve Data for volume, sentiment, regime
        historical_provider = get_historical_provider()
        volume = 0.0
        annualized_volatility = 0.0
        change_24h = 0.0
        change_7d = 0.0
        sentiment = "neutral"
        regime = "neutral"  # PHASE 1: Default to "neutral" instead of "unknown"
        regime_confidence = 0.0
        
        if historical_provider:
            try:
                # Get last 60 daily candles for calculations
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=60)
                
                if hasattr(historical_provider, "get_historical_ohlcv_as_candles"):
                    candles = historical_provider.get_historical_ohlcv_as_candles(
                        symbol, "1d", start_date, end_date
                    )
                elif hasattr(historical_provider, "get_candles"):
                    candles = historical_provider.get_candles(symbol, "1d", limit=60, start=None, end=None)
                else:
                    candles = []
                
                if candles and len(candles) >= 2:
                    # PHASE 1: Calculate volume (latest - last candle or average of last 20)
                    if len(candles) >= 20:
                        volume = sum(c.volume for c in candles[-20:]) / 20
                    else:
                        volume = candles[-1].volume if candles else 0.0
                    
                    # PHASE 1: Calculate price changes (24h and 7d)
                    last_close = candles[-1].close
                    prev_close = candles[-2].close if len(candles) >= 2 else last_close
                    change_24h = ((last_close / prev_close - 1) * 100) if prev_close > 0 else 0.0
                    
                    # PHASE 1: Calculate 7d change (7 trading days ≈ 7 candles for daily)
                    if len(candles) >= 7:
                        seven_days_ago_close = candles[-7].close
                        change_7d = ((last_close / seven_days_ago_close - 1) * 100) if seven_days_ago_close > 0 else 0.0
                    else:
                        change_7d = change_24h  # Fallback to 24h if not enough data
                    
                    # PHASE 1: Calculate annualized volatility
                    if len(candles) >= 20:
                        closes = [c.close for c in candles[-20:]]
                        returns = [(closes[i] / closes[i-1] - 1) for i in range(1, len(closes))]
                        if returns and len(returns) > 1:
                            import statistics
                            daily_volatility = statistics.stdev(returns)
                            # Annualize: multiply by sqrt(252 trading days)
                            annualized_volatility = daily_volatility * (252 ** 0.5) * 100  # As percentage
                    
                    # PHASE 1: Simple price-based sentiment
                    if change_24h > 2.0 or change_7d > 5.0:
                        sentiment = "bullish"
                    elif change_24h < -2.0 or change_7d < -5.0:
                        sentiment = "bearish"
                    else:
                        sentiment = "neutral"
                    
                    # PHASE 3: Rule-based regime fallback (if MCN fails)
                    if len(candles) >= 50:
                        closes = [c.close for c in candles]
                        
                        # Calculate 50-day and 200-day MAs (or shorter if not enough data)
                        ma_period_1 = min(50, len(closes) // 2)
                        ma_period_2 = min(200, len(closes))
                        
                        if ma_period_1 >= 2 and ma_period_2 >= 2:
                            ma_50 = sum(closes[-ma_period_1:]) / ma_period_1
                            ma_200 = sum(closes[-ma_period_2:]) / ma_period_2
                            
                            # Calculate volatility (standard deviation of returns)
                            returns = [(closes[i] / closes[i-1] - 1) for i in range(1, len(closes))]
                            if returns:
                                import statistics
                                volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
                            else:
                                volatility = 0.0
                            
                            # PHASE 1 & 4: Rule-based regime classification (mapped to risk-on/risk-off/neutral)
                            if current_price > ma_50 and current_price > ma_200 and volatility < 0.03:
                                regime = "risk-on"  # PHASE 1: Map bull_trend to risk-on
                            elif current_price < ma_50 and current_price < ma_200 and volatility > 0.03:
                                regime = "risk-off"  # PHASE 1: Map bear_trend to risk-off
                            elif abs(current_price - ma_50) / ma_50 < 0.05:
                                regime = "neutral"  # PHASE 1: Map sideways to neutral
                            else:
                                regime = "neutral"  # PHASE 1: Map range to neutral
                            
                            regime_confidence = 0.6  # Moderate confidence for rule-based
                
            except Exception as e:
                print(f"⚠️  Error calculating market context for {symbol}: {e}")
        
        # PHASE 1 & 4: Try MCN-based regime detection (with fallback to rule-based above)
        try:
            regime_detector = RegimeDetector()
            mcn_regime_result = regime_detector.get_market_regime(symbol)
            mcn_regime = mcn_regime_result.get("regime", "unknown")
            if mcn_regime != "unknown":
                # PHASE 1: Map MCN regime to risk-on/risk-off/neutral
                if mcn_regime in ["bull_trend", "high_vol"]:
                    regime = "risk-on"
                elif mcn_regime in ["bear_trend"]:
                    regime = "risk-off"
                else:
                    regime = "neutral"
                regime_confidence = mcn_regime_result.get("confidence", regime_confidence)
        except Exception as e:
            # PHASE 1 & 4: MCN failed, use rule-based regime from above
            print(f"⚠️  MCN regime detection failed for {symbol}, using rule-based: {e}")
        
        return {
            "symbol": symbol,
            "price": current_price,
            "volume": volume,
            "annualized_volatility": annualized_volatility,  # PHASE 1: Added
            "change_24h": change_24h,  # PHASE 1: Changed from change_1d
            "change_7d": change_7d,  # PHASE 1: Changed from change_5d
            "sentiment": sentiment,
            "regime": regime,  # PHASE 1: Now returns risk-on/risk-off/neutral
            "regime_confidence": regime_confidence,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        # PHASE 3: Return safe defaults on error
        print(f"⚠️  Error fetching market context for {symbol}: {e}")
        return {
            "symbol": symbol,
            "price": 0.0,
            "volume": 0.0,
            "annualized_volatility": 0.0,  # PHASE 1: Added
            "change_24h": 0.0,  # PHASE 1: Changed from change_1d
            "change_7d": 0.0,  # PHASE 1: Changed from change_5d
            "sentiment": "neutral",
            "regime": "neutral",  # PHASE 1: Changed from "unknown"
            "regime_confidence": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

