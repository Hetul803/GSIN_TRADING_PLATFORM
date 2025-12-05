# backend/market_data/adapters/polygon_adapter.py
"""
Polygon.io market data provider adapter.
"""
import os
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import dotenv_values
import httpx
from ..market_data_provider import BaseMarketDataProvider
from ..types import (
    PriceData,
    CandleData,
    SentimentData,
    VolatilityData,
    MarketOverview,
    MarketDataError
)

# Load from config/.env or environment variable
# Go up from backend/market_data/adapters/polygon_adapter.py -> adapters -> market_data -> backend -> GSIN-backend -> gsin_new_git (repo root)
CFG_PATH = Path(__file__).resolve().parents[4] / "config" / ".env"
cfg = {}
if CFG_PATH.exists():
    cfg = dotenv_values(str(CFG_PATH))
    # Validate that we got real values, not placeholders
    for key, value in list(cfg.items()):
        if value and ("your-" in str(value).lower() or "placeholder" in str(value).lower()):
            del cfg[key]


class PolygonDataProvider(BaseMarketDataProvider):
    """Polygon.io market data provider."""
    
    BASE_URL = "https://api.polygon.io"
    
    def __init__(self):
        # Load API key from config/.env or environment variable
        # Support both MARKET_DATA_API_KEY and MARKET_DATA_API_KEY_POLYGON
        self.api_key = (
            os.environ.get("MARKET_DATA_API_KEY_POLYGON") or 
            cfg.get("MARKET_DATA_API_KEY_POLYGON") or
            os.environ.get("MARKET_DATA_API_KEY") or 
            cfg.get("MARKET_DATA_API_KEY")
        )
        if not self.api_key:
            raise MarketDataError("MARKET_DATA_API_KEY_POLYGON or MARKET_DATA_API_KEY not found in environment or config/.env")
        self.client = httpx.Client(timeout=10.0)
    
    def is_available(self) -> bool:
        """Check if Polygon API is available."""
        return self.api_key is not None and len(self.api_key) > 0
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to Polygon API."""
        if params is None:
            params = {}
        params["apiKey"] = self.api_key
        
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "ERROR":
                raise MarketDataError(f"Polygon API error: {data.get('error', 'Unknown error')}")
            
            return data
        except httpx.HTTPError as e:
            raise MarketDataError(f"HTTP error calling Polygon API: {str(e)}")
        except Exception as e:
            raise MarketDataError(f"Error calling Polygon API: {str(e)}")
    
    def get_price(self, symbol: str) -> PriceData:
        """Get real-time price for a symbol."""
        # Use previous close for now (free tier limitation)
        # For real-time, would need websocket or premium tier
        data = self._make_request(f"/v2/aggs/ticker/{symbol.upper()}/prev", {
            "adjusted": "true"
        })
        
        if "results" not in data or len(data["results"]) == 0:
            raise MarketDataError(f"No price data found for {symbol}")
        
        result = data["results"][0]
        timestamp_ms = result.get("t", 0)  # Unix timestamp in milliseconds
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
        
        close = result.get("c", 0)  # Close price
        open_price = result.get("o", close)
        change = close - open_price
        change_percent = (change / open_price * 100) if open_price > 0 else 0
        
        return PriceData(
            symbol=symbol.upper(),
            price=close,
            timestamp=timestamp,
            volume=result.get("v", 0),
            change=change,
            change_percent=change_percent
        )
    
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
        
        Returns:
            List of CandleData (never None, empty list on error)
        """
        # Map interval to Polygon's timespan
        # Polygon uses: minute, hour, day, week, month
        interval_map = {
            "1m": ("minute", 1),
            "5m": ("minute", 5),
            "15m": ("minute", 15),
            "30m": ("minute", 30),
            "1h": ("hour", 1),
            "4h": ("hour", 4),
            "1d": ("day", 1),
            "1w": ("week", 1),
            "1M": ("month", 1),
        }
        
        # Default to daily if not found
        timespan, multiplier = interval_map.get(interval, ("day", 1))
        
        # Use provided start/end dates if available, otherwise calculate from limit
        if end:
            to_date = end if isinstance(end, datetime) else datetime.now()
        else:
            to_date = datetime.now()
        
        if start:
            from_date = start if isinstance(start, datetime) else (to_date - timedelta(days=limit * 2))
        else:
            from_date = to_date - timedelta(days=limit * 2)  # Extra buffer
        
        try:
            data = self._make_request(f"/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{timespan}/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}", {
                "adjusted": "true",
                "sort": "asc",
                "limit": limit
            })
            
            # Defensive check: ensure data is valid
            if not isinstance(data, dict):
                print(f"⚠️  Polygon API returned invalid response type for {symbol} ({interval})")
                return []
            
            if "results" not in data:
                print(f"⚠️  Polygon API response missing 'results' key for {symbol} ({interval})")
                return []
            
            results = data["results"]
            if not isinstance(results, list):
                print(f"⚠️  Polygon API 'results' is not a list for {symbol} ({interval})")
                return []
            
            candles = []
            for result in results:
                if not isinstance(result, dict):
                    continue  # Skip invalid results
                
                timestamp_ms = result.get("t", 0)
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                
                candles.append(CandleData(
                    symbol=symbol.upper(),
                    timestamp=timestamp,
                    open=float(result.get("o", 0)),
                    high=float(result.get("h", 0)),
                    low=float(result.get("l", 0)),
                    close=float(result.get("c", 0)),
                    volume=int(result.get("v", 0))
                ))
            
            # Always return a list (never None)
            if len(candles) == 0:
                print(f"⚠️  Polygon API returned 0 candles for {symbol} ({interval})")
            else:
                print(f"✅ Polygon API returned {len(candles)} candles for {symbol} ({interval})")
            
            return candles
        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(f"Error fetching candles from Polygon for {symbol}: {str(e)}")
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """
        Get sentiment data for a symbol.
        Note: Polygon free tier doesn't include sentiment.
        Returns a placeholder for now.
        """
        # Polygon doesn't have sentiment in free tier
        # Return None to indicate not available
        # In production, could integrate with alternative provider or ML model
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
                symbol=symbol.upper(),
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
        Polygon free tier has limited market-wide data.
        Returns a placeholder for now.
        """
        # Polygon free tier doesn't have comprehensive market overview
        # Return None to indicate not available
        # In production, could aggregate from multiple symbols or use premium tier
        return None
    
    def __del__(self):
        """Cleanup HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()

