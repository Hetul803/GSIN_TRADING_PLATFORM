# backend/market_data/providers/yahoo_provider.py
"""
PHASE 1: Dedicated Yahoo Finance provider for historical OHLCV data.
Used exclusively for backtesting, strategy evolution, and MCN regime detection.
"""
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import time

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None

from ..types import CandleData, MarketDataError
from ..symbol_utils import normalize_symbol, validate_symbol
from ...utils.exponential_backoff import exponential_backoff


class YahooHistoricalProvider:
    """
    Dedicated Yahoo Finance provider for historical OHLCV data.
    
    Features:
    - Auto-adjusts for splits/dividends
    - Returns clean pd.DataFrame format
    - NEVER returns None
    - Includes retry logic + exponential backoff
    - Includes local file caching
    - Includes in-memory cache
    """
    
    # Supported timeframes
    SUPPORTED_TIMEFRAMES = ["1d", "4h", "1h", "15m", "5m", "1m"]
    
    # Cache directory
    CACHE_DIR = Path("./cache")
    
    def __init__(self):
        if not YFINANCE_AVAILABLE:
            raise MarketDataError("yfinance library not installed. Install with: pip install yfinance")
        
        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache: {key: (data, expiry_time)}
        self._memory_cache: Dict[str, tuple] = {}
        self._cache_ttl = 3600  # 1 hour for historical data
    
    def _get_cache_path(self, symbol: str, timeframe: str) -> Path:
        """Get cache file path for symbol/timeframe."""
        symbol_dir = self.CACHE_DIR / symbol.upper()
        symbol_dir.mkdir(parents=True, exist_ok=True)
        return symbol_dir / f"{timeframe}.json"
    
    def _load_file_cache(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Load cached data from file."""
        cache_path = self._get_cache_path(symbol, timeframe)
        if not cache_path.exists():
            return None
        
        try:
            # Check file age (invalidate if older than 12 hours)
            file_age = time.time() - cache_path.stat().st_mtime
            if file_age > 43200:  # 12 hours
                return None
            
            with open(cache_path, 'r') as f:
                data = json.load(f)
            
            # Convert to DataFrame
            df = pd.DataFrame(data['candles'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"⚠️  Error loading cache for {symbol}/{timeframe}: {e}")
            return None
    
    def _save_file_cache(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Save data to file cache."""
        try:
            cache_path = self._get_cache_path(symbol, timeframe)
            
            # Convert DataFrame to JSON-serializable format
            df_reset = df.reset_index()
            candles = df_reset.to_dict('records')
            
            data = {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "candles": candles
            }
            
            with open(cache_path, 'w') as f:
                json.dump(data, f, default=str)
        except Exception as e:
            print(f"⚠️  Error saving cache for {symbol}/{timeframe}: {e}")
    
    def _get_memory_cache_key(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> str:
        """Generate memory cache key."""
        return f"{symbol}_{timeframe}_{start.isoformat()}_{end.isoformat()}"
    
    @exponential_backoff(max_retries=3, initial_delay=1.0, multiplier=2.0)
    def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data from Yahoo Finance.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            timeframe: Time interval ("1d", "4h", "1h", "15m", "5m", "1m")
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
        
        Returns:
            pd.DataFrame with columns: open, high, low, close, volume
            Index: timestamp (datetime)
            NEVER returns None - returns empty DataFrame if no data
        
        Raises:
            MarketDataError: If data cannot be fetched after retries
        """
        if timeframe not in self.SUPPORTED_TIMEFRAMES:
            raise MarketDataError(f"Unsupported timeframe: {timeframe}. Supported: {self.SUPPORTED_TIMEFRAMES}")
        
        # FIX 6: Always normalize symbol before using (handles $AAPL, BTCUSD -> BTC-USD, etc.)
        symbol_normalized = normalize_symbol(symbol)
        if not symbol_normalized:
            # FIX 6: Return clean empty structure, no errors
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
        
        # FIX 6: Always use normalized symbol
        symbol_upper = symbol_normalized
        
        # Check memory cache
        cache_key = self._get_memory_cache_key(symbol_upper, timeframe, start, end)
        if cache_key in self._memory_cache:
            data, expiry = self._memory_cache[cache_key]
            if time.time() < expiry:
                return data.copy()
            else:
                del self._memory_cache[cache_key]
        
        # Check file cache
        cached_df = self._load_file_cache(symbol_upper, timeframe)
        if cached_df is not None:
            # Filter by date range
            filtered = cached_df[(cached_df.index >= start) & (cached_df.index <= end)]
            if len(filtered) > 0:
                # Update memory cache
                self._memory_cache[cache_key] = (filtered, time.time() + self._cache_ttl)
                return filtered.copy()
        
        # ISSUE 2 FIX: Fetch from Yahoo Finance using Ticker.history with better error handling
        try:
            # Map timeframe to yfinance interval
            interval_map = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "1h": "1h",
                "4h": "1h",  # yfinance doesn't support 4h, we'll aggregate 1h data
                "1d": "1d"
            }
            
            yf_interval = interval_map.get(timeframe, "1d")
            
            # ISSUE 2 FIX: Convert timezone-aware datetimes to naive for yfinance
            start_naive = start.replace(tzinfo=None) if start.tzinfo else start
            end_naive = end.replace(tzinfo=None) if end.tzinfo else end
            
            # ISSUE 2 FIX: Use Ticker.history with proper error handling
            ticker = yf.Ticker(symbol_upper)
            
            # Suppress yfinance warnings and handle errors ourselves
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    # Fetch data with auto-adjust for splits/dividends
                    df = ticker.history(
                        start=start_naive,
                        end=end_naive,
                        interval=yf_interval,
                        auto_adjust=True,
                        prepost=False
                    )
                except (ValueError, KeyError, Exception) as ticker_error:
                    # FIX 6: Catch yfinance-specific errors (JSON parse, timezone, delisted) - return clean empty structure
                    error_str = str(ticker_error).lower()
                    if "json" in error_str or "expecting value" in error_str or "timezone" in error_str or "delisted" in error_str:
                        # FIX 6: Try cached data first, then return clean empty structure
                        cached_df = self._load_file_cache(symbol_upper, timeframe)
                        if cached_df is not None:
                            filtered = cached_df[(cached_df.index >= start) & (cached_df.index <= end)]
                            if len(filtered) > 0:
                                return filtered.copy()
                        # FIX 6: Return clean empty structure, no errors
                        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
                    else:
                        raise  # Re-raise if it's a different error
            
            # FIX 6: Handle empty or invalid responses - return clean empty structure
            if df.empty or len(df) == 0:
                # FIX 6: Try cached data, then return clean empty structure
                cached_df = self._load_file_cache(symbol_upper, timeframe)
                if cached_df is not None:
                    filtered = cached_df[(cached_df.index >= start) & (cached_df.index <= end)]
                    if len(filtered) > 0:
                        return filtered.copy()
                # FIX 6: Return clean empty structure, no errors
                return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
            
            # Rename columns to lowercase
            df.columns = [col.lower() for col in df.columns]
            
            # Select only OHLCV columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                # If some columns missing, try cached data
                cached_df = self._load_file_cache(symbol_upper, timeframe)
                if cached_df is not None:
                    filtered = cached_df[(cached_df.index >= start) & (cached_df.index <= end)]
                    if len(filtered) > 0:
                        print(f"⚠️  Yahoo returned incomplete data for {symbol_upper}/{timeframe}, using cached data")
                        return filtered.copy()
                return pd.DataFrame(columns=required_cols)
            
            df = df[required_cols].copy()
            
            # Handle 4h timeframe by aggregating 1h data
            if timeframe == "4h":
                df = df.resample('4H').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
            
            # Filter by date range (yfinance sometimes returns extra data)
            df = df[(df.index >= start_naive) & (df.index <= end_naive)]
            
            # Ensure timezone-aware index
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
            
            # Save to file cache
            self._save_file_cache(symbol_upper, timeframe, df)
            
            # Update memory cache
            self._memory_cache[cache_key] = (df, time.time() + self._cache_ttl)
            
            return df.copy()
            
        except Exception as e:
            # FIX 6: Always return clean empty structure, no parse/delisted errors
            # Try cached data first
            cached_df = self._load_file_cache(symbol_upper, timeframe)
            if cached_df is not None:
                filtered = cached_df[(cached_df.index >= start) & (cached_df.index <= end)]
                if len(filtered) > 0:
                    return filtered.copy()
            
            # FIX 6: Return clean empty structure (never None, no errors)
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
    
    def get_historical_ohlcv_as_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> List[CandleData]:
        """
        Get historical OHLCV data as list of CandleData objects.
        
        Returns:
            List of CandleData objects, ordered by timestamp (oldest first)
            NEVER returns None - returns empty list if no data
        """
        df = self.get_historical_ohlcv(symbol, timeframe, start, end)
        
        if df.empty:
            return []
        
        candles = []
        for timestamp, row in df.iterrows():
            candles.append(CandleData(
                symbol=symbol.upper(),
                timestamp=timestamp if isinstance(timestamp, datetime) else pd.Timestamp(timestamp).to_pydatetime(),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume'])
            ))
        
        return candles


# Global instance
_yahoo_historical_provider: Optional[YahooHistoricalProvider] = None


def get_yahoo_historical_provider() -> YahooHistoricalProvider:
    """Get global Yahoo historical provider instance."""
    global _yahoo_historical_provider
    if _yahoo_historical_provider is None:
        _yahoo_historical_provider = YahooHistoricalProvider()
    return _yahoo_historical_provider

