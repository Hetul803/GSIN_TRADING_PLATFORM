# backend/market_data/adapters/finnhub_adapter.py
"""
Finnhub market data provider adapter (free tier fallback).
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
# Go up from backend/market_data/adapters/finnhub_adapter.py -> adapters -> market_data -> backend -> GSIN-backend -> gsin_new_git (repo root)
CFG_PATH = Path(__file__).resolve().parents[4] / "config" / ".env"
cfg = {}
if CFG_PATH.exists():
    cfg = dotenv_values(str(CFG_PATH))
    # Validate that we got real values, not placeholders
    for key, value in list(cfg.items()):
        if value and ("your-" in str(value).lower() or "placeholder" in str(value).lower()):
            del cfg[key]


class FinnhubDataProvider(BaseMarketDataProvider):
    """Finnhub market data provider (free tier)."""
    
    BASE_URL = "https://finnhub.io/api/v1"
    
    def __init__(self):
        # Load API key from config/.env or environment variable
        self.api_key = (
            os.environ.get("FINNHUB_API_KEY") or 
            cfg.get("FINNHUB_API_KEY")
        )
        if not self.api_key:
            raise MarketDataError("FINNHUB_API_KEY not found in environment or config/.env")
        
        # Load webhook secret (optional, for webhook verification)
        self.webhook_secret = (
            os.environ.get("FINNHUB_WEBHOOK_SECRET") or 
            cfg.get("FINNHUB_WEBHOOK_SECRET")
        )
        
        self.client = httpx.Client(timeout=10.0)
    
    def is_available(self) -> bool:
        """Check if Finnhub API is available."""
        return self.api_key is not None and len(self.api_key) > 0
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to Finnhub API."""
        if params is None:
            params = {}
        params["token"] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise MarketDataError("Finnhub rate limit exceeded. Please try again later.")
            elif e.response.status_code == 401:
                raise MarketDataError("Finnhub API key invalid or expired.")
            else:
                raise MarketDataError(f"Finnhub API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise MarketDataError(f"Finnhub request failed: {str(e)}")
    
    def get_price(self, symbol: str) -> PriceData:
        """Get real-time price for a symbol."""
        try:
            data = self._make_request("quote", {"symbol": symbol.upper()})
            
            if not data or "c" not in data:  # 'c' is current price
                raise MarketDataError(f"Finnhub: No price data for {symbol}")
            
            current_price = float(data.get("c", 0))
            previous_close = float(data.get("pc", current_price))
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close > 0 else 0.0
            
            return PriceData(
                symbol=symbol.upper(),
                price=current_price,
                timestamp=datetime.now(),
                volume=int(data.get("v", 0)),
                change=change,
                change_percent=change_percent
            )
        except Exception as e:
            raise MarketDataError(f"Failed to get price from Finnhub: {str(e)}")
    
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
        try:
            # Map interval to Finnhub format
            # Finnhub supports: 1, 5, 15, 30, 60, D, W, M
            interval_map = {
                "1m": "1",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "1h": "60",
                "1d": "D",
                "1w": "W",
                "1M": "M"
            }
            
            finnhub_interval = interval_map.get(interval.lower(), "D")
            
            # Use provided start/end dates if available, otherwise calculate from limit
            if end:
                if isinstance(end, datetime):
                    end_time = int(end.timestamp())
                else:
                    end_time = int(datetime.now().timestamp())
            else:
                end_time = int(datetime.now().timestamp())
            
            if start:
                if isinstance(start, datetime):
                    start_time = int(start.timestamp())
                else:
                    # Calculate from limit if start is string but invalid
                    start_time = int((datetime.now() - timedelta(days=limit)).timestamp())
            else:
                # Calculate start time based on interval and limit
                if "m" in interval.lower():
                    minutes = int(interval.lower().replace("m", ""))
                    start_time = int((datetime.now() - timedelta(minutes=minutes * limit)).timestamp())
                elif "h" in interval.lower():
                    hours = int(interval.lower().replace("h", ""))
                    start_time = int((datetime.now() - timedelta(hours=hours * limit)).timestamp())
                elif "d" in interval.lower():
                    days = int(interval.lower().replace("d", ""))
                    start_time = int((datetime.now() - timedelta(days=days * limit)).timestamp())
                else:
                    start_time = int((datetime.now() - timedelta(days=limit)).timestamp())
            
            data = self._make_request("stock/candle", {
                "symbol": symbol.upper(),
                "resolution": finnhub_interval,
                "from": start_time,
                "to": end_time
            })
            
            # Defensive check: ensure data is valid
            if not data or not isinstance(data, dict):
                print(f"⚠️  Finnhub API returned invalid response for {symbol} ({interval})")
                return []
            
            if data.get("s") != "ok" or not data.get("c"):
                print(f"⚠️  Finnhub API: No candle data for {symbol} ({interval}), status: {data.get('s')}")
                return []
            
            candles = []
            closes = data.get("c", [])
            opens = data.get("o", [])
            highs = data.get("h", [])
            lows = data.get("l", [])
            volumes = data.get("v", [])
            timestamps = data.get("t", [])
            
            # Ensure all arrays have same length
            min_len = min(len(closes), len(opens), len(highs), len(lows), len(timestamps))
            
            for i in range(min(min_len, limit)):
                candles.append(CandleData(
                    symbol=symbol.upper(),
                    timestamp=datetime.fromtimestamp(timestamps[i]),
                    open=float(opens[i]) if i < len(opens) else 0.0,
                    high=float(highs[i]) if i < len(highs) else 0.0,
                    low=float(lows[i]) if i < len(lows) else 0.0,
                    close=float(closes[i]) if i < len(closes) else 0.0,
                    volume=int(volumes[i]) if i < len(volumes) else 0
                ))
            
            # Always return a list (never None)
            if len(candles) == 0:
                print(f"⚠️  Finnhub API returned 0 candles for {symbol} ({interval})")
            else:
                print(f"✅ Finnhub API returned {len(candles)} candles for {symbol} ({interval})")
            
            return candles
        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(f"Failed to get candles from Finnhub: {str(e)}")
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Get sentiment data for a symbol."""
        # Finnhub free tier doesn't provide sentiment
        return None
    
    def get_volatility(self, symbol: str) -> Optional[VolatilityData]:
        """Get volatility metrics for a symbol."""
        # Calculate from candles
        try:
            candles = self.get_candles(symbol, "1d", limit=30)
            if len(candles) < 2:
                return None
            
            # Calculate simple volatility
            returns = []
            for i in range(1, len(candles)):
                if candles[i-1].close > 0:
                    ret = (candles[i].close - candles[i-1].close) / candles[i-1].close
                    returns.append(ret)
            
            if not returns:
                return None
            
            import numpy as np
            volatility = np.std(returns) * np.sqrt(252)  # Annualized
            
            return VolatilityData(
                symbol=symbol.upper(),
                volatility=volatility,
                timestamp=datetime.now(),
                period="30d"
            )
        except:
            return None
    
    def get_overview(self) -> Optional[MarketOverview]:
        """Get overall market overview."""
        # Finnhub free tier doesn't provide market overview
        return None

