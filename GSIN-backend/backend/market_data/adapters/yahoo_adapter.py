# backend/market_data/adapters/yahoo_adapter.py
"""
Yahoo Finance market data provider adapter.
Uses yfinance library for free market data (no API key required).
"""
from typing import Optional, List
from datetime import datetime, timedelta
from ..market_data_provider import BaseMarketDataProvider
from ..types import (
    PriceData,
    CandleData,
    SentimentData,
    VolatilityData,
    MarketOverview,
    MarketDataError
)

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None


class YahooDataProvider(BaseMarketDataProvider):
    """Yahoo Finance market data provider (free, no API key required)."""
    
    def __init__(self):
        if not YFINANCE_AVAILABLE:
            raise MarketDataError("yfinance library not installed. Install with: pip install yfinance")
        self._available = True
    
    def is_available(self) -> bool:
        """Check if provider is available."""
        return self._available and YFINANCE_AVAILABLE
    
    def get_price(self, symbol: str) -> PriceData:
        """Get real-time price for a symbol."""
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            
            # Get current price
            current_price = info.get("regularMarketPrice") or info.get("currentPrice") or 0.0
            previous_close = info.get("previousClose") or current_price
            
            # Calculate change
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close > 0 else 0.0
            
            # Get volume
            volume = info.get("regularMarketVolume") or info.get("volume") or 0
            
            return PriceData(
                symbol=symbol.upper(),
                price=float(current_price),
                timestamp=datetime.now(),
                volume=int(volume),
                change=float(change),
                change_percent=float(change_percent)
            )
        except Exception as e:
            raise MarketDataError(f"Error fetching price from Yahoo Finance for {symbol}: {str(e)}")
    
    def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 50,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[CandleData]:
        """
        Get historical OHLCV candles.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            interval: Time interval (e.g., "1d", "1h", "15m", "5m", "1m")
            limit: Number of candles to return
        
        Returns:
            List of CandleData, ordered by timestamp (oldest first)
        """
        try:
            ticker = yf.Ticker(symbol.upper())
            
            # Map interval to yfinance period/interval
            # yfinance uses: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
            interval_map = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "30m": "30m",
                "1h": "1h",
                "4h": "4h",  # yfinance doesn't support 4h, use 1h and aggregate
                "1d": "1d",
                "1w": "1wk",
                "1M": "1mo"
            }
            
            yf_interval = interval_map.get(interval, "1d")
            
            # Use start/end dates if provided, otherwise use period
            if start and end:
                # Convert to datetime if needed
                start_dt = start if isinstance(start, datetime) else datetime.fromisoformat(start)
                end_dt = end if isinstance(end, datetime) else datetime.fromisoformat(end)
                
                # Fetch data with date range
                hist = ticker.history(start=start_dt, end=end_dt, interval=yf_interval)
            else:
                # Calculate period based on limit and interval
                # For intraday, max period is 7 days
                # For daily, max period is 1 year
                if interval in ["1m", "5m", "15m", "30m", "1h"]:
                    # Intraday data - max 7 days
                    period = "7d"
                elif interval == "4h":
                    # 4h not directly supported, use 1d and we'll aggregate
                    period = "1mo"
                    yf_interval = "1d"
                elif interval == "1d":
                    period = "1y"  # 1 year of daily data
                else:
                    period = "1y"
                
                # Fetch data
                hist = ticker.history(period=period, interval=yf_interval)
            
            if hist.empty:
                print(f"⚠️  Yahoo Finance returned empty data for {symbol} ({interval})")
                return []
            
            # Convert to CandleData list
            candles = []
            # Limit to requested number of candles
            data_to_process = hist.tail(limit) if len(hist) > limit else hist
            
            for idx, row in data_to_process.iterrows():
                # Handle timezone-aware timestamps
                timestamp = idx
                if hasattr(timestamp, 'to_pydatetime'):
                    timestamp = timestamp.to_pydatetime()
                elif isinstance(timestamp, datetime):
                    pass
                else:
                    timestamp = datetime.fromtimestamp(timestamp.timestamp())
                
                # Ensure timezone-naive (Yahoo Finance returns timezone-aware)
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.replace(tzinfo=None)
                
                candles.append(CandleData(
                    timestamp=timestamp,
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']) if 'Volume' in row else 0
                ))
            
            # Sort by timestamp (oldest first)
            candles.sort(key=lambda x: x.timestamp)
            
            # Always return a list (never None)
            if len(candles) == 0:
                print(f"⚠️  Yahoo Finance returned 0 candles for {symbol} ({interval})")
            else:
                print(f"✅ Yahoo Finance returned {len(candles)} candles for {symbol} ({interval})")
            
            return candles
            
        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(f"Error fetching candles from Yahoo Finance for {symbol}: {str(e)}")
    
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Get sentiment data for a symbol. Returns None if not available."""
        # Yahoo Finance doesn't provide sentiment data
        return None
    
    def get_overview(self) -> Optional[MarketOverview]:
        """Get overall market overview. Returns None if not available."""
        # Yahoo Finance doesn't provide market overview - return None
        return None
    
    def get_volatility(self, symbol: str) -> Optional[VolatilityData]:
        """Get volatility data for a symbol."""
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            
            # Get 52-week high/low for volatility calculation
            week_52_high = info.get("fiftyTwoWeekHigh") or 0.0
            week_52_low = info.get("fiftyTwoWeekLow") or 0.0
            current_price = info.get("regularMarketPrice") or info.get("currentPrice") or 0.0
            
            if week_52_high > 0 and week_52_low > 0:
                # Calculate volatility as percentage of 52-week range
                volatility = ((week_52_high - week_52_low) / week_52_low) * 100 if week_52_low > 0 else 0.0
            else:
                volatility = 0.0
            
            return VolatilityData(
                symbol=symbol.upper(),
                volatility=volatility / 100.0,  # Convert to 0-1 scale
                timestamp=datetime.now()
            )
        except Exception:
            return None
    
    def get_market_overview(self, symbol: str) -> Optional[MarketOverview]:
        """Get market overview for a symbol."""
        try:
            price_data = self.get_price(symbol)
            volatility_data = self.get_volatility(symbol)
            
            return MarketOverview(
                symbol=symbol.upper(),
                price=price_data.price,
                change=price_data.change,
                change_percent=price_data.change_percent,
                volume=price_data.volume,
                volatility=volatility_data.volatility if volatility_data else 0.0,
                timestamp=datetime.now()
            )
        except Exception:
            return None

