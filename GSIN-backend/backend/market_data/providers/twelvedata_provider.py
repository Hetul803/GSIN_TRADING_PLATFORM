# backend/market_data/providers/twelvedata_provider.py
"""
Twelve Data market data provider.
Primary provider for historical OHLCV, live prices, news, sentiment, and fundamentals.
"""
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import dotenv_values
import httpx
import pandas as pd

from ..market_data_provider import BaseMarketDataProvider
from ..symbol_utils import normalize_symbol, normalize_symbol_for_twelvedata
from ..types import (
    PriceData,
    CandleData,
    SentimentData,
    VolatilityData,
    MarketOverview,
    MarketDataError
)

# Load from config/.env or environment variable
# Go up from backend/market_data/providers/twelvedata_provider.py -> providers -> market_data -> backend -> GSIN-backend -> gsin_new_git (repo root)
CFG_PATH = Path(__file__).resolve().parents[4] / "config" / ".env"
cfg = {}
if CFG_PATH.exists():
    cfg = dotenv_values(str(CFG_PATH))
    # Validate that we got real values, not placeholders
    for key, value in list(cfg.items()):
        if value and ("your-" in str(value).lower() or "placeholder" in str(value).lower()):
            # Remove placeholder values
            del cfg[key]

# Twelve Data API base URL
TWELVEDATA_BASE_URL = "https://api.twelvedata.com"


class TwelveDataProvider(BaseMarketDataProvider):
    """Twelve Data market data provider."""
    
    # Interval mapping: GSIN format -> Twelve Data format
    INTERVAL_MAP = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1hour",
        "4h": "4hour",
        "1d": "1day",
        "1w": "1week",
        "1M": "1month"
    }
    
    def __init__(self):
        # Load API key from environment or config
        self.api_key = os.environ.get("TWELVEDATA_API_KEY") or cfg.get("TWELVEDATA_API_KEY")
        
        if not self.api_key:
            raise MarketDataError("TWELVEDATA_API_KEY not found in environment or config/.env")
        
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "GSIN-Backend/1.0"
            }
        )
    
    def is_available(self) -> bool:
        """Check if Twelve Data API is available."""
        return self.api_key is not None and len(self.api_key) > 0
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Make a request to Twelve Data API.
        
        Returns:
            dict: JSON response from API (never None)
        
        Raises:
            MarketDataError: If request fails or response is invalid
        """
        if params is None:
            params = {}
        
        # Always include API key
        params["apikey"] = self.api_key
        
        url = f"{TWELVEDATA_BASE_URL}{endpoint}"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors in response
            if isinstance(data, dict) and "status" in data:
                if data.get("status") == "error":
                    error_message = data.get("message", "Unknown error")
                    code = data.get("code", "")
                    raise MarketDataError(f"Twelve Data API error ({code}): {error_message}")
            
            # Ensure we never return None
            if data is None:
                raise MarketDataError(f"Twelve Data API returned None for {endpoint}")
            
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise MarketDataError("Twelve Data API authentication failed. Check TWELVEDATA_API_KEY")
            elif e.response.status_code == 429:
                raise MarketDataError("Twelve Data API rate limit exceeded")
            elif e.response.status_code == 404:
                raise MarketDataError(f"Symbol not found or not supported by Twelve Data")
            else:
                raise MarketDataError(f"Twelve Data API error: {e.response.status_code} - {e.response.text}")
        except httpx.HTTPError as e:
            raise MarketDataError(f"HTTP error calling Twelve Data API: {str(e)}")
        except Exception as e:
            raise MarketDataError(f"Error calling Twelve Data API: {str(e)}")
    
    def get_price(self, symbol: str) -> PriceData:
        """
        Get real-time price for a symbol.
        
        Uses Twelve Data price endpoint.
        """
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            raise MarketDataError(f"Invalid symbol: {symbol}")
        
        # Convert to Twelve Data format (BTC-USD → BTC/USD for crypto)
        symbol_td = normalize_symbol_for_twelvedata(symbol_normalized)
        
        try:
            # Use real-time price endpoint
            data = self._make_request("/price", {
                "symbol": symbol_td,
                "format": "json"
            })
            
            # Response format: {"price": "150.25", "timestamp": 1234567890}
            price = float(data.get("price", 0))
            timestamp_str = data.get("timestamp", "")
            
            # Parse timestamp (can be ISO string or Unix timestamp)
            if timestamp_str:
                try:
                    if isinstance(timestamp_str, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp_str, tz=timezone.utc)
                    else:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except:
                    timestamp = datetime.now(timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)
            
            # Get change from previous close (if available)
            change = data.get("change", 0.0)
            change_percent = data.get("percent_change", 0.0)
            
            return PriceData(
                symbol=symbol_normalized,  # Return normalized symbol (not TD format)
                price=price,
                timestamp=timestamp,
                change=float(change) if change else None,
                change_percent=float(change_percent) / 100.0 if change_percent else None
            )
        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(f"Error fetching price for {symbol_normalized}: {str(e)}")
    
    def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 50,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[CandleData]:
        """
        Get historical OHLCV candles from Twelve Data.
        
        PHASE 1: For daily backtests, requests "last N candles" instead of date range.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            interval: Time interval (e.g., "1d", "1h", "15m", "5m", "1m")
            limit: Number of candles to return (max 5000 for some intervals)
            start: Optional start date (ignored for daily backtests - uses last N candles)
            end: Optional end date (ignored for daily backtests - uses last N candles)
        
        Returns:
            List of CandleData, ordered by timestamp (oldest first)
            Never returns None - returns empty list on error
        """
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            return []
        
        # Convert to Twelve Data format (BTC-USD → BTC/USD for crypto)
        symbol_td = normalize_symbol_for_twelvedata(symbol_normalized)
        
        # Map interval to Twelve Data format
        td_interval = self.INTERVAL_MAP.get(interval, "1day")
        
        try:
            # PHASE 1: For daily backtests, request "last N candles" instead of date range
            # Twelve Data returns the most recent N candles when outputsize is specified
            max_limit = 5000
            requested_limit = min(max(limit, 100), max_limit)  # Request at least 100, up to 5000
            
            params = {
                "symbol": symbol_td,
                "interval": td_interval,
                "format": "json",
                "outputsize": requested_limit  # Request last N candles
            }
            
            # PHASE 1: Do NOT add date range for daily backtests - use "last N candles" approach
            # Only add date range for non-daily timeframes if explicitly needed
            # For daily, Twelve Data will return the most recent N candles automatically
            
            data = self._make_request("/time_series", params)
            
            # Response format: {"values": [{"datetime": "...", "open": "...", "high": "...", "low": "...", "close": "...", "volume": "..."}, ...]}
            values = data.get("values", [])
            
            if not values or not isinstance(values, list):
                return []
            
            candles = []
            for item in reversed(values):  # Reverse to get oldest first
                try:
                    # Parse datetime
                    dt_str = item.get("datetime", "")
                    if not dt_str:
                        continue
                    
                    # PHASE C: Parse timestamp correctly from Twelve Data ISO strings
                    # Do NOT replace with "today" - use actual historical dates
                    try:
                        if "T" in dt_str or "Z" in dt_str:
                            # ISO format: "2024-01-15T10:30:00Z" or "2024-01-15T10:30:00+00:00"
                            timestamp = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        elif len(dt_str) >= 10:
                            # Try parsing as "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD"
                            try:
                                timestamp = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                # Try date-only format
                                timestamp = datetime.strptime(dt_str[:10], "%Y-%m-%d")
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        else:
                            raise ValueError(f"Invalid datetime string: {dt_str}")
                        
                        # PHASE C: Only cap future dates, preserve historical dates
                        now = datetime.now(timezone.utc)
                        if timestamp > now:
                            # If timestamp is in future, cap it (but log warning)
                            print(f"⚠️  PHASE C: Candle timestamp in future: {dt_str}, capping to now")
                            timestamp = now
                    except Exception as e:
                        # PHASE C: Log error but don't use "today" - this breaks historical backtests
                        print(f"⚠️  PHASE C: Failed to parse candle timestamp '{dt_str}': {e}")
                        # Use a very old date instead of "today" to avoid breaking backtests
                        timestamp = datetime(2000, 1, 1, tzinfo=timezone.utc)
                    
                    # Parse OHLCV
                    open_price = float(item.get("open", 0))
                    high_price = float(item.get("high", 0))
                    low_price = float(item.get("low", 0))
                    close_price = float(item.get("close", 0))
                    volume = int(float(item.get("volume", 0)))
                    
                    candles.append(CandleData(
                        symbol=symbol_normalized,
                        timestamp=timestamp,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume
                    ))
                except (ValueError, KeyError) as e:
                    # Skip invalid candles
                    continue
            
            return candles
            
        except MarketDataError:
            # Return empty list instead of raising (allows fallback)
            return []
        except Exception as e:
            # Return empty list on any error (allows fallback)
            return []
    
    def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """
        Get historical OHLCV as pandas DataFrame (for backtesting).
        
        Requests maximum history (up to 5000 candles) from Twelve Data.
        Compatible with BacktestEngine.
        """
        candles = self.get_candles(symbol, timeframe, limit=5000, start=start, end=end)
        
        if not candles:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        
        # Convert to DataFrame
        data = {
            'open': [c.open for c in candles],
            'high': [c.high for c in candles],
            'low': [c.low for c in candles],
            'close': [c.close for c in candles],
            'volume': [c.volume for c in candles]
        }
        
        df = pd.DataFrame(data, index=[c.timestamp for c in candles])
        df.index.name = 'timestamp'
        
        return df
    
    def get_historical_ohlcv_as_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> List[CandleData]:
        """
        Get historical OHLCV as CandleData list.
        
        PHASE 1: For daily backtests, requests "last N candles" (5000 max) instead of date range.
        The start/end dates are ignored for daily - Twelve Data returns most recent candles.
        """
        # PHASE 1: For daily, request last 5000 candles (ignores start/end)
        # For other timeframes, still use date range if needed
        if timeframe == "1d":
            return self.get_candles(symbol, timeframe, limit=5000, start=None, end=None)
        else:
            return self.get_candles(symbol, timeframe, limit=5000, start=start, end=end)
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """
        Get sentiment data for a symbol.
        
        Uses Twelve Data sentiment endpoint (if available in Grow plan).
        NOTE: Sentiment endpoint returns 404 - not available in current plan.
        Returns None silently without logging errors.
        """
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            return None
        
        try:
            # Try sentiment endpoint (may not be available in all plans)
            # FIX: Handle 404 gracefully - sentiment endpoint doesn't exist
            url = f"{TWELVEDATA_BASE_URL}/sentiment"
            params = {
                "symbol": symbol_normalized,
                "apikey": self.api_key
            }
            response = self.client.get(url, params=params)
            
            # If 404, sentiment is not available - return None silently
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Response format may vary - adapt based on actual API response
            sentiment_score = float(data.get("sentiment_score", 0.0))
            confidence = float(data.get("confidence", 0.5))
            
            return SentimentData(
                symbol=symbol_normalized,
                sentiment_score=sentiment_score,
                timestamp=datetime.now(timezone.utc),
                source="twelvedata",
                confidence=confidence
            )
        except httpx.HTTPStatusError as e:
            # 404 means endpoint doesn't exist - return None silently
            if e.response.status_code == 404:
                return None
            # Other HTTP errors - return None (sentiment is optional)
            return None
        except Exception:
            # Sentiment may not be available - return None (not an error)
            return None
    
    def get_volatility(self, symbol: str) -> Optional[VolatilityData]:
        """
        Get volatility metrics for a symbol.
        
        Calculates from recent price data.
        """
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            return None
        
        try:
            # Get recent candles for volatility calculation
            candles = self.get_candles(symbol_normalized, "1d", limit=30)
            
            if len(candles) < 2:
                return None
            
            # Calculate volatility from returns
            import numpy as np
            closes = [c.close for c in candles]
            returns = np.diff(closes) / closes[:-1]
            
            # Annualized volatility
            volatility = np.std(returns) * np.sqrt(252)  # 252 trading days
            
            return VolatilityData(
                symbol=symbol_normalized,
                volatility=float(volatility),
                timestamp=datetime.now(timezone.utc),
                period="30d"
            )
        except Exception:
            return None
    
    def get_overview(self) -> Optional[MarketOverview]:
        """Get overall market overview."""
        # Twelve Data may not have a direct market overview endpoint
        # Return None (not required for all providers)
        return None
    
    # Twelve Data-specific methods for news, sentiment, fundamentals
    
    def get_symbol_news(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get news articles for a symbol.
        
        Args:
            symbol: Stock symbol
            limit: Maximum number of articles to return
        
        Returns:
            List of news articles with title, url, text, etc.
        """
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            return []
        
        # Convert to Twelve Data format (BTC-USD → BTC/USD for crypto)
        symbol_td = normalize_symbol_for_twelvedata(symbol_normalized)
        
        try:
            data = self._make_request("/news", {
                "symbol": symbol_td,
                "limit": min(limit, 50)  # Twelve Data max is typically 50
            })
            
            # Response format: {"data": [{"title": "...", "url": "...", "text": "...", "source": "...", "published_at": "..."}, ...]}
            news_items = data.get("data", [])
            
            if not isinstance(news_items, list):
                return []
            
            return news_items[:limit]
        except Exception:
            return []
    
    def get_symbol_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get fundamental data for a symbol.
        
        Returns:
            Dictionary with fundamental metrics (earnings, P/E, etc.)
        """
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            return None
        
        # Convert to Twelve Data format (BTC-USD → BTC/USD for crypto)
        symbol_td = normalize_symbol_for_twelvedata(symbol_normalized)
        
        try:
            # Use fundamentals endpoint
            data = self._make_request("/fundamentals", {
                "symbol": symbol_td
            })
            
            # Response format may vary - return raw data
            return data
        except Exception:
            return None
    
    def get_intraday_series(
        self,
        symbol: str,
        interval: str,
        lookback: int = 100
    ) -> List[CandleData]:
        """
        Get intraday series for charts and short-term analytics.
        
        Args:
            symbol: Stock symbol
            interval: Time interval (e.g., "1m", "5m", "15m", "1h")
            lookback: Number of candles to return
        
        Returns:
            List of CandleData
        """
        end = datetime.now(timezone.utc)
        # Estimate start based on interval and lookback
        interval_deltas = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1)
        }
        delta = interval_deltas.get(interval, timedelta(days=1))
        start = end - (delta * lookback)
        
        return self.get_candles(symbol, interval, limit=lookback, start=start, end=end)


# Singleton instance
_twelvedata_provider: Optional[TwelveDataProvider] = None


def get_twelvedata_provider() -> TwelveDataProvider:
    """Get or create Twelve Data provider instance."""
    global _twelvedata_provider
    if _twelvedata_provider is None:
        _twelvedata_provider = TwelveDataProvider()
    return _twelvedata_provider

