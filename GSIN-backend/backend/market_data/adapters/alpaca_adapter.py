# backend/market_data/adapters/alpaca_adapter.py
"""
Alpaca market data provider adapter.
Uses Alpaca Market Data API with IEX feed for real-time and historical data.
IEX feed eliminates SIP subscription errors and provides reliable data access.
"""
import os
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import dotenv_values
import httpx
from ..market_data_provider import BaseMarketDataProvider
from ..symbol_utils import normalize_symbol
from ..types import (
    PriceData,
    CandleData,
    SentimentData,
    VolatilityData,
    MarketOverview,
    MarketDataError
)

# Load from config/.env or environment variable
# Go up from backend/market_data/adapters/alpaca_adapter.py -> adapters -> market_data -> backend -> GSIN-backend -> gsin_new_git (repo root)
CFG_PATH = Path(__file__).resolve().parents[4] / "config" / ".env"
cfg = {}
if CFG_PATH.exists():
    cfg = dotenv_values(str(CFG_PATH))
    # Validate that we got real values, not placeholders
    for key, value in list(cfg.items()):
        if value and ("your-" in str(value).lower() or "placeholder" in str(value).lower()):
            del cfg[key]


class AlpacaDataProvider(BaseMarketDataProvider):
    # ISSUE 5 FIX: Track warned symbols to avoid spam
    _warned_symbols: set = set()
    """Alpaca market data provider."""
    
    # Alpaca Market Data API base URL (free tier)
    BASE_URL = "https://data.alpaca.markets"
    
    def __init__(self):
        # Load API credentials from config/.env or environment variables
        self.api_key = os.environ.get("ALPACA_API_KEY") or cfg.get("ALPACA_API_KEY")
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY") or cfg.get("ALPACA_SECRET_KEY")
        self.base_url = os.environ.get("ALPACA_BASE_URL") or cfg.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        
        if not self.api_key or not self.secret_key:
            raise MarketDataError("ALPACA_API_KEY and ALPACA_SECRET_KEY not found in environment or config/.env")
        
        # Use Market Data API (different from trading API)
        # For market data, we use data.alpaca.markets
        # NOTE: Broker API credentials (broker-api.sandbox.alpaca.markets) may not work with Market Data API
        # Market Data API requires separate Trading API credentials
        self.client = httpx.Client(
            timeout=10.0,
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
            }
        )
    
    def is_available(self) -> bool:
        """Check if Alpaca API is available."""
        return self.api_key is not None and self.secret_key is not None and len(self.api_key) > 0
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Make a request to Alpaca Market Data API.
        
        Returns:
            dict: JSON response from API (never None)
        
        Raises:
            MarketDataError: If request fails or response is invalid
        """
        if params is None:
            params = {}
        
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Ensure we never return None
            if data is None:
                raise MarketDataError(f"Alpaca API returned None for {endpoint}")
            
            # Ensure data is a dict
            if not isinstance(data, dict):
                raise MarketDataError(f"Alpaca API returned invalid response type for {endpoint}: {type(data)}")
            
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise MarketDataError(f"Symbol not found or not supported by Alpaca")
            elif e.response.status_code == 401:
                raise MarketDataError(f"Alpaca API authentication failed. Check ALPACA_API_KEY and ALPACA_SECRET_KEY")
            elif e.response.status_code == 429:
                raise MarketDataError(f"Alpaca API rate limit exceeded")
            else:
                raise MarketDataError(f"Alpaca API error: {e.response.status_code} - {e.response.text}")
        except httpx.HTTPError as e:
            raise MarketDataError(f"HTTP error calling Alpaca API: {str(e)}")
        except Exception as e:
            raise MarketDataError(f"Error calling Alpaca API: {str(e)}")
    
    def get_price(self, symbol: str) -> PriceData:
        """Get real-time price for a symbol using IEX feed (no SIP errors)."""
        # ISSUE 2 FIX: Normalize symbol before using
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            raise MarketDataError(f"Invalid symbol: '{symbol}' (normalized to empty string)")
        
        try:
            # Get latest trade using IEX feed (avoids SIP subscription errors)
            data = self._make_request(f"/v2/stocks/{symbol_normalized}/trades/latest", {"feed": "iex"})
            
            if "trade" not in data:
                raise MarketDataError(f"No price data found for {symbol}")
            
            trade = data["trade"]
            price = float(trade.get("p", 0))  # Price
            timestamp_str = trade.get("t")  # Timestamp in ISO format or Unix timestamp
            volume = int(trade.get("s", 0))  # Size (volume)
            
            # Parse timestamp
            if isinstance(timestamp_str, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except:
                    timestamp = datetime.now()
            elif isinstance(timestamp_str, (int, float)):
                # Unix timestamp in nanoseconds
                timestamp = datetime.fromtimestamp(timestamp_str / 1e9)
            else:
                timestamp = datetime.now()
            
            # Get previous close for change calculation using IEX feed
            try:
                # ISSUE 2 FIX: Normalize symbol
                symbol_normalized = normalize_symbol(symbol)
                if not symbol_normalized:
                    raise MarketDataError(f"Invalid symbol: '{symbol}' (normalized to empty string)")
                
                bars_data = self._make_request(f"/v2/stocks/{symbol_normalized}/bars", {
                    "feed": "iex",  # Use IEX feed to avoid SIP errors
                    "timeframe": "1Day",
                    "limit": 2,
                    "adjustment": "raw"
                })
                
                if "bars" in bars_data and len(bars_data["bars"]) >= 2:
                    prev_close = float(bars_data["bars"][-2].get("c", price))  # Previous close
                    change = price - prev_close
                    change_percent = (change / prev_close * 100) if prev_close > 0 else 0
                else:
                    change = None
                    change_percent = None
            except:
                change = None
                change_percent = None
            
            return PriceData(
                symbol=symbol_normalized,
                price=price,
                timestamp=timestamp,
                volume=volume,
                change=change,
                change_percent=change_percent
            )
        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(f"Error fetching price for {symbol}: {str(e)}")
    
    def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 50,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> list[CandleData]:
        """
        Get historical OHLCV candles.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            interval: Time interval (e.g., "1d", "1h", "15m")
            limit: Maximum number of candles to return
            start: Optional start date (ISO format or datetime)
            end: Optional end date (ISO format or datetime)
        
        Returns:
            List of CandleData (never None, empty list on error)
        
        Raises:
            MarketDataError: If API call fails
        """
        # Map interval to Alpaca's timeframe format
        # Alpaca supports: 1Min, 5Min, 15Min, 30Min, 1Hour, 1Day, 1Week, 1Month
        interval_map = {
            "1m": "1Min",
            "5m": "5Min",
            "15m": "15Min",
            "30m": "30Min",
            "1h": "1Hour",
            "4h": "1Hour",  # Alpaca doesn't support 4h, use 1h
            "1d": "1Day",
            "1w": "1Week",
            "1M": "1Month",
        }
        
        timeframe = interval_map.get(interval, "1Day")
        
        try:
            # Build request parameters with IEX feed (avoids SIP subscription errors)
            params = {
                "feed": "iex",  # Use IEX feed to avoid SIP errors
                "timeframe": timeframe,
                "limit": min(limit, 10000),  # Alpaca max limit
                "adjustment": "raw",  # Raw prices, not adjusted
                "sort": "asc"  # Oldest first
            }
            
            # Add start/end dates if provided (Alpaca expects ISO format)
            if start:
                if isinstance(start, datetime):
                    # Convert to ISO format, ensure timezone-aware
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    params["start"] = start.isoformat()
                elif isinstance(start, str):
                    params["start"] = start
            
            if end:
                if isinstance(end, datetime):
                    # Convert to ISO format, ensure timezone-aware
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    params["end"] = end.isoformat()
                elif isinstance(end, str):
                    params["end"] = end
            
            # ISSUE 2 FIX: Normalize symbol before using
            symbol_normalized = normalize_symbol(symbol)
            if not symbol_normalized:
                raise MarketDataError(f"Invalid symbol: '{symbol}' (normalized to empty string)")
            
            # Make API request
            data = self._make_request(f"/v2/stocks/{symbol_normalized}/bars", params)
            
            # Defensive check: ensure data is a dict and has expected structure
            if not isinstance(data, dict):
                raise MarketDataError(f"Alpaca API returned invalid response type: {type(data)}")
            
            # ISSUE 5 FIX: Check if bars key exists and is a list (log once per symbol/timeframe)
            if "bars" not in data:
                warning_key = f"{symbol_normalized}:{interval}:missing_bars"
                if warning_key not in self._warned_symbols:
                    print(f"⚠️  Alpaca API response for {symbol_normalized} ({interval}) missing 'bars' key (will use cached data if available)")
                    self._warned_symbols.add(warning_key)
                
                # Try to use last cached candle as fallback
                from ..cache import get_cache
                cache = get_cache()
                cached = cache.get("candle", symbol_normalized, interval)
                if cached and isinstance(cached, list) and len(cached) > 0:
                    return cached[-1:]  # Return last candle as list
                return []
            
            bars = data["bars"]
            
            # ISSUE 5 FIX: Handle NoneType bars gracefully (log once per symbol/timeframe)
            if bars is None:
                warning_key = f"{symbol_normalized}:{interval}:none_bars"
                if warning_key not in self._warned_symbols:
                    print(f"⚠️  Alpaca API response for {symbol_normalized} ({interval}) 'bars' is None (will use cached data if available)")
                    self._warned_symbols.add(warning_key)
                
                # Try to use last cached candle as fallback
                from ..cache import get_cache
                cache = get_cache()
                cached = cache.get("candle", symbol_normalized, interval)
                if cached and isinstance(cached, list) and len(cached) > 0:
                    return cached[-1:]  # Return last candle as list
                return []
            
            if not isinstance(bars, list):
                warning_key = f"{symbol_normalized}:{interval}:not_list"
                if warning_key not in self._warned_symbols:
                    print(f"⚠️  Alpaca API response for {symbol_normalized} ({interval}) 'bars' is not a list: {type(bars)} (will use cached data if available)")
                    self._warned_symbols.add(warning_key)
                
                # Try to use last cached candle as fallback
                from ..cache import get_cache
                cache = get_cache()
                cached = cache.get("candle", symbol_normalized, interval)
                if cached and isinstance(cached, list) and len(cached) > 0:
                    return cached[-1:]  # Return last candle as list
                return []
            
            # Parse bars into CandleData objects
            candles = []
            for bar in bars:
                if not isinstance(bar, dict):
                    continue  # Skip invalid bars
                
                # Parse timestamp
                timestamp_str = bar.get("t")
                if isinstance(timestamp_str, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except:
                        timestamp = datetime.now()
                elif isinstance(timestamp_str, (int, float)):
                    timestamp = datetime.fromtimestamp(timestamp_str / 1e9)
                else:
                    timestamp = datetime.now()
                
                candles.append(CandleData(
                    symbol=symbol_normalized,
                    timestamp=timestamp,
                    open=float(bar.get("o", 0)),
                    high=float(bar.get("h", 0)),
                    low=float(bar.get("l", 0)),
                    close=float(bar.get("c", 0)),
                    volume=int(bar.get("v", 0))
                ))
            
            # Log result for debugging
            if len(candles) == 0:
                print(f"⚠️  Alpaca API returned 0 candles for {symbol} ({interval}) with params: {params}")
            else:
                print(f"✅ Alpaca API returned {len(candles)} candles for {symbol} ({interval})")
            
            # Always return a list (never None)
            return candles
            
        except MarketDataError:
            # Re-raise MarketDataError as-is
            raise
        except Exception as e:
            # Wrap any other exception in MarketDataError
            raise MarketDataError(f"Error fetching candles for {symbol}: {str(e)}")
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """
        Get sentiment data for a symbol.
        Alpaca doesn't provide sentiment data directly.
        Returns None to indicate not available.
        """
        return None
    
    def get_volatility(self, symbol: str) -> Optional[VolatilityData]:
        """
        Calculate volatility from recent price data.
        Uses 30-day historical data to compute annualized volatility.
        """
        try:
            # Get last 30 days of daily candles
            candles = self.get_candles(symbol, "1d", limit=30)
            
            if len(candles) < 2:
                return None
            
            # Calculate returns
            returns = []
            for i in range(1, len(candles)):
                prev_close = candles[i-1].close
                curr_close = candles[i].close
                if prev_close > 0:
                    ret = (curr_close - prev_close) / prev_close
                    returns.append(ret)
            
            if len(returns) < 2:
                return None
            
            # Calculate standard deviation of returns
            import statistics
            mean_return = statistics.mean(returns)
            variance = statistics.variance(returns, mean_return) if len(returns) > 1 else 0
            std_dev = variance ** 0.5
            
            # Annualize volatility (assuming 252 trading days)
            annualized_vol = std_dev * (252 ** 0.5)
            
            return VolatilityData(
                symbol=symbol_normalized,
                volatility=annualized_vol,
                timestamp=datetime.now(),
                period="30d"
            )
        except Exception as e:
            print(f"Error calculating volatility for {symbol}: {e}")
            return None
    
    def get_overview(self) -> Optional[MarketOverview]:
        """
        Get overall market overview.
        Alpaca doesn't provide comprehensive market overview in free tier.
        Returns None to indicate not available.
        """
        return None
    
    def get_asset_details(self, symbol: str) -> Optional[dict]:
        """
        Get asset details including sector information.
        PHASE 4: Fetches sector from Alpaca Assets API.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
        
        Returns:
            Dictionary with asset details:
            {
                "symbol": str,
                "sector": Optional[str],
                "industry": Optional[str],
                "name": Optional[str],
                "exchange": Optional[str],
                ...
            }
        """
        try:
            # Alpaca Assets API endpoint
            # Note: This uses the trading API base URL, not market data API
            # We need to use the broker API base URL for assets
            base_url = self.base_url or "https://paper-api.alpaca.markets"
            url = f"{base_url}/v2/assets/{symbol_normalized}"
            
            # Use trading API credentials (same as market data for Alpaca)
            response = self.client.get(
                url,
                headers={
                    "APCA-API-KEY-ID": self.api_key,
                    "APCA-API-SECRET-KEY": self.secret_key,
                }
            )
            
            if response.status_code == 404:
                return None  # Asset not found
            
            response.raise_for_status()
            asset_data = response.json()
            
            return {
                "symbol": asset_data.get("symbol", symbol_normalized),
                "sector": asset_data.get("sector"),
                "industry": asset_data.get("industry"),
                "name": asset_data.get("name"),
                "exchange": asset_data.get("exchange"),
                "asset_class": asset_data.get("class"),
                "status": asset_data.get("status"),
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise MarketDataError(f"Error fetching asset details for {symbol}: {e.response.status_code}")
        except Exception as e:
            raise MarketDataError(f"Error fetching asset details for {symbol}: {str(e)}")
    
    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()

