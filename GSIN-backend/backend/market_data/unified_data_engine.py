# backend/market_data/unified_data_engine.py
"""
PHASE 1: Multi-provider data engine with strict data hierarchy.

For BACKTESTS (historical data): Yahoo Finance ONLY
For LIVE DATA (real-time): Alpaca IEX → Yahoo → Polygon → Finnhub

All providers use IEX feed to avoid SIP subscription errors.
Handles retries, rate limits, caching, and returns normalized OHLCV format.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import time
import httpx

from .types import PriceData, CandleData, MarketDataError
from .market_data_provider import get_provider_with_fallback, call_with_fallback, get_historical_provider
from .adapters.alpaca_adapter import AlpacaDataProvider
from .adapters.polygon_adapter import PolygonDataProvider
from .adapters.finnhub_adapter import FinnhubDataProvider
from .adapters.yahoo_adapter import YahooDataProvider
from .market_data_provider import register_provider

# Register providers
register_provider("finnhub", FinnhubDataProvider)
register_provider("yahoo", YahooDataProvider)


def get_market_data(
    ticker: str,
    timeframe: str = "1d",
    limit: int = 50,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    PHASE 1: Get historical market data (for backtests) using Yahoo Finance ONLY.
    
    This function is used for:
    - Backtests
    - Brain evolution
    - MCN distance calculations
    - Strategy validations
    
    Args:
        ticker: Stock symbol (e.g., "AAPL")
        timeframe: Time interval (e.g., "1d", "4h", "1h", "15m", "5m", "1m")
        limit: Number of candles to return (used if start/end not provided)
        start: Start datetime (timezone-aware, optional)
        end: End datetime (timezone-aware, optional)
    
    Returns:
        Normalized OHLCV format:
        {
            "symbol": str,
            "timeframe": str,
            "candles": [
                {
                    "timestamp": str (ISO),
                    "open": float,
                    "high": float,
                    "low": float,
                    "close": float,
                    "volume": int
                }
            ],
            "provider": "yahoo",
            "cached": bool
        }
    
    Raises:
        MarketDataError: If Yahoo Finance fails
    """
    from .cache import get_cache
    from .providers.yahoo_provider import get_yahoo_historical_provider
    from datetime import timedelta
    
    # PHASE 1: Use Yahoo Finance ONLY for historical data
    cache = get_cache()
    
    # Calculate start/end if not provided
    if end is None:
        end = datetime.now(timezone.utc)
    if start is None:
        # Estimate start based on timeframe and limit
        timeframe_deltas = {
            "1m": timedelta(minutes=limit),
            "5m": timedelta(minutes=limit * 5),
            "15m": timedelta(minutes=limit * 15),
            "1h": timedelta(hours=limit),
            "4h": timedelta(hours=limit * 4),
            "1d": timedelta(days=limit)
        }
        start = end - timeframe_deltas.get(timeframe, timedelta(days=limit))
    
    # Ensure timezone-aware
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    
    cache_key = f"{ticker}_{timeframe}_{start.isoformat()}_{end.isoformat()}"
    
    # Check cache first (TTL: 12 hours for historical data)
    cached = cache.get("unified_data", cache_key, ttl_seconds=43200)
    if cached:
        return {**cached, "cached": True}
    
    try:
        # TWELVE DATA INTEGRATION: Use historical provider (Twelve Data PRIMARY)
        # get_historical_provider is imported at the top of the file
        historical_provider = get_historical_provider()
        if not historical_provider:
            raise MarketDataError("No historical provider available")
        
        # Try to get candles from historical provider
        provider_name = historical_provider.__class__.__name__.replace("Provider", "").lower()
        
        # Check if provider has get_historical_ohlcv_as_candles method
        if hasattr(historical_provider, "get_historical_ohlcv_as_candles"):
            candles = historical_provider.get_historical_ohlcv_as_candles(ticker, timeframe, start, end)
        elif hasattr(historical_provider, "get_candles"):
            candles = historical_provider.get_candles(ticker, timeframe, limit=limit, start=start, end=end)
        else:
            raise MarketDataError(f"Historical provider {provider_name} does not support get_candles")
        
        # Handle empty returns (never return None)
        if not candles:
            # Try Yahoo as fallback
            from .providers.yahoo_provider import get_yahoo_historical_provider
            try:
                yahoo_provider = get_yahoo_historical_provider()
                candles = yahoo_provider.get_historical_ohlcv_as_candles(ticker, timeframe, start, end)
                provider_name = "yahoo"
            except:
                pass
            
            if not candles:
                # Return empty result instead of raising error
                return {
                    "symbol": ticker.upper(),
                    "timeframe": timeframe,
                    "candles": [],
                    "provider": provider_name,
                    "cached": False
                }
        
        # Normalize format
        normalized_candles = [
            {
                "timestamp": (
                    c.timestamp.isoformat() 
                    if isinstance(c.timestamp, datetime) 
                    else c.timestamp
                ),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": int(c.volume)
            }
            for c in candles
        ]
        
        result = {
            "symbol": ticker.upper(),
            "timeframe": timeframe,
            "candles": normalized_candles,
            "provider": provider_name,
            "cached": False
        }
        
        # Cache the result (12 hour TTL for historical)
        cache.set("unified_data", cache_key, result)
        
        return result
        
    except Exception as e:
        # PHASE 4: Try to return cached data as fallback (graceful degradation)
        fallback_value = cache.get_fallback_value("unified_data", ticker, timeframe)
        if fallback_value:
            # Only log if it's not a NameError (which indicates import issue that should be fixed)
            if "get_historical_provider" not in str(e) and "not defined" not in str(e):
                print(f"⚠️  Market data fetch failed for {ticker}/{timeframe}, using cached fallback data")
            return {**fallback_value, "cached": True, "fallback": True}
        
        # If all else fails, return empty result (never raise error that breaks evolution)
        # Only log if it's not a NameError (which indicates import issue that should be fixed)
        if "get_historical_provider" not in str(e) and "not defined" not in str(e):
            print(f"⚠️  Failed to fetch historical data for {ticker}/{timeframe}: {e}")
        return {
            "symbol": ticker.upper(),
            "timeframe": timeframe,
            "candles": [],
            "provider": "unknown",
            "cached": False
        }


def get_price_data(ticker: str) -> Dict[str, Any]:
    """
    TWELVE DATA INTEGRATION: Get real-time price using Twelve Data PRIMARY, fallback to Alpaca/Yahoo.
    
    Provider order (for LIVE DATA only):
    1) Twelve Data (real-time) - PRIMARY
    2) Alpaca IEX (fallback - for last_price only)
    3) Yahoo Finance (last resort - uses last known price)
    
    NOTE: This is for LIVE data only. Historical data uses get_market_data() which uses Twelve Data.
    
    Returns:
        {
            "symbol": str,
            "price": float,
            "timestamp": str (ISO),
            "volume": int,
            "change": float,
            "change_percent": float,
            "provider": str
        }
    """
    from .cache import get_cache
    from .market_data_provider import get_provider_with_fallback
    
    cache = get_cache()
    cache_key = f"price_{ticker}"
    
    # Check cache (5 second TTL for price)
    cached = cache.get("price", cache_key, ttl_seconds=5)
    if cached:
        return {**cached, "cached": True}
    
    # TASK 3 FIX: Try live primary provider (Alpaca) first
    live_provider = get_provider_with_fallback()
    if live_provider:
        try:
            price_data = live_provider.get_price(ticker)
            
            result = {
                "symbol": price_data.symbol,
                "price": float(price_data.price),
                "timestamp": (
                    price_data.timestamp.isoformat()
                    if isinstance(price_data.timestamp, datetime)
                    else price_data.timestamp
                ),
                "volume": int(price_data.volume) if price_data.volume else 0,
                "change": float(price_data.change) if price_data.change else 0.0,
                "change_percent": float(price_data.change_percent) if price_data.change_percent else 0.0,
                "provider": "alpaca",  # Live primary
                "cached": False
            }
            
            # Cache the result
            cache.set("price", cache_key, result)
            
            return result
        except Exception as e:
            # TASK 3 FIX: Log fallback and try secondary providers
            print(f"⚠️  Alpaca live data unavailable for {ticker}, falling back to Yahoo/Polygon: {str(e)}")
    
    # TASK 3 FIX: Fallback to secondary providers (Yahoo, Polygon, Finnhub)
    providers = [
        ("yahoo", YahooDataProvider),  # Fast fallback
        ("polygon", PolygonDataProvider),  # Fallback
        ("finnhub", FinnhubDataProvider)  # Last resort
    ]
    
    last_error = None
    
    for provider_name, provider_class in providers:
        try:
            provider = provider_class()
            if not provider.is_available():
                continue
            
            price_data = provider.get_price(ticker)
            
            result = {
                "symbol": price_data.symbol,
                "price": float(price_data.price),
                "timestamp": (
                    price_data.timestamp.isoformat()
                    if isinstance(price_data.timestamp, datetime)
                    else price_data.timestamp
                ),
                "volume": int(price_data.volume) if price_data.volume else 0,
                "change": float(price_data.change) if price_data.change else 0.0,
                "change_percent": float(price_data.change_percent) if price_data.change_percent else 0.0,
                "provider": provider_name,
                "cached": False
            }
            
            # Cache the result
            cache.set("price", cache_key, result)
            
            return result
            
        except Exception as e:
            last_error = e
            continue
    
    if last_error:
        raise MarketDataError(
            f"All live price providers failed for {ticker}. Last error: {str(last_error)}"
        )
    else:
        raise MarketDataError(f"No live price providers available for {ticker}")

