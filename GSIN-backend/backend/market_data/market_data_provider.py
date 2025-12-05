# backend/market_data/market_data_provider.py
"""
Base market data provider interface and provider registry.
"""
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from .types import (
    PriceData,
    CandleData,
    SentimentData,
    VolatilityData,
    MarketOverview,
    MarketDataError
)


class BaseMarketDataProvider(ABC):
    """Base interface for all market data providers."""
    
    @abstractmethod
    def get_price(self, symbol: str) -> PriceData:
        """Get real-time price for a symbol."""
        pass
    
    @abstractmethod
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
            interval: Time interval (e.g., "1d", "1h", "15m", "5m")
            limit: Number of candles to return
            start: Optional start date (ISO format or datetime)
            end: Optional end date (ISO format or datetime)
        
        Returns:
            List of CandleData, ordered by timestamp (oldest first)
            Never returns None - returns empty list on error
        """
        pass
    
    @abstractmethod
    def get_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Get sentiment data for a symbol. Returns None if not available."""
        pass
    
    @abstractmethod
    def get_volatility(self, symbol: str) -> Optional[VolatilityData]:
        """Get volatility metrics for a symbol. Returns None if not available."""
        pass
    
    @abstractmethod
    def get_overview(self) -> Optional[MarketOverview]:
        """Get overall market overview. Returns None if not available."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available (API key valid, etc.)."""
        pass


# Provider registry
_providers: dict[str, type[BaseMarketDataProvider]] = {}
# TASK 1 FIX: Separate historical vs live providers
_historical_provider: Optional[BaseMarketDataProvider] = None
_live_primary_provider: Optional[BaseMarketDataProvider] = None
_live_secondary_provider: Optional[BaseMarketDataProvider] = None
_provider_hierarchy_printed: bool = False  # STABILITY: Flag to print hierarchy only once
# Legacy support (deprecated - use _historical_provider and _live_*_provider)
_primary_provider: Optional[BaseMarketDataProvider] = None
_secondary_provider: Optional[BaseMarketDataProvider] = None


def register_provider(name: str, provider_class: type[BaseMarketDataProvider]):
    """Register a market data provider."""
    _providers[name.lower()] = provider_class


def _get_provider_instance(name: str) -> Optional[BaseMarketDataProvider]:
    """
    Create a provider instance by name.
    
    Args:
        name: Provider name (e.g., "alpaca", "polygon")
    
    Returns:
        Provider instance or None if not available
    """
    if name not in _providers:
        return None
    
    provider_class = _providers[name]
    try:
        provider = provider_class()
        if not provider.is_available():
            return None
        return provider
    except Exception as e:
        # Log error but don't crash - allow fallback to secondary provider
        print(f"⚠️  Error initializing provider {name}: {e}")
        # If it's an authentication error, log it clearly
        error_msg = str(e).lower()
        if "401" in error_msg or "authentication" in error_msg or "unauthorized" in error_msg:
            print(f"   → Authentication failed for {name}. This is expected if Broker API credentials are used with Market Data API.")
            print(f"   → Will fallback to secondary provider.")
        return None


# PHASE: Global flag to ensure provider logs only appear once on startup
_providers_initialized = False

def _initialize_providers():
    """
    TWELVE DATA INTEGRATION: Initialize historical and live providers separately.
    
    Historical: Twelve Data PRIMARY (for backtests, Brain, MCN)
    Live: Twelve Data PRIMARY, Alpaca secondary (for charts, terminal, WebSocket)
    Yahoo: Last-resort fallback only
    
    PHASE: Logs only appear ONCE on startup to prevent spam.
    """
    global _historical_provider, _live_primary_provider, _live_secondary_provider, _primary_provider, _secondary_provider, _providers_initialized
    
    # PHASE: If already initialized, skip logging (prevent spam)
    if _providers_initialized:
        return
    
    _providers_initialized = True
    
    import os
    from pathlib import Path
    from dotenv import dotenv_values
    
    # TWELVE DATA INTEGRATION: Ensure providers are registered before initialization
    # Import and register providers if not already registered
    if "twelvedata" not in _providers:
        from .providers.twelvedata_provider import TwelveDataProvider
        register_provider("twelvedata", TwelveDataProvider)
    if "yahoo" not in _providers:
        from .adapters.yahoo_adapter import YahooDataProvider
        register_provider("yahoo", YahooDataProvider)
    if "alpaca" not in _providers:
        from .adapters.alpaca_adapter import AlpacaDataProvider
        register_provider("alpaca", AlpacaDataProvider)
    if "polygon" not in _providers:
        from .adapters.polygon_adapter import PolygonDataProvider
        register_provider("polygon", PolygonDataProvider)
    if "finnhub" not in _providers:
        from .adapters.finnhub_adapter import FinnhubDataProvider
        register_provider("finnhub", FinnhubDataProvider)
    
    # Load from config/.env or environment variables
    CFG_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
    cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
    
    # TWELVE DATA INTEGRATION: Historical provider (Twelve Data PRIMARY)
    historical_name = os.environ.get("MARKET_DATA_PROVIDER_HISTORICAL") or cfg.get("MARKET_DATA_PROVIDER_HISTORICAL", "twelvedata").lower()
    
    if _historical_provider is None:
        try:
            _historical_provider = _get_provider_instance(historical_name)
            if _historical_provider:
                print(f"✅ Historical data provider: {historical_name}")
            else:
                # Fallback to Yahoo if Twelve Data fails
                print(f"⚠️  Historical provider ({historical_name}) failed to initialize, falling back to yahoo")
                _historical_provider = _get_provider_instance("yahoo")
                if _historical_provider:
                    print(f"✅ Historical data provider: yahoo (fallback)")
        except Exception as e:
            print(f"⚠️  Historical provider ({historical_name}) initialization error: {e}")
            # Try Yahoo as fallback
            try:
                _historical_provider = _get_provider_instance("yahoo")
                if _historical_provider:
                    print(f"✅ Historical data provider: yahoo (fallback)")
            except:
                _historical_provider = None
    
    # TWELVE DATA INTEGRATION: Live primary provider (Twelve Data PRIMARY)
    live_primary_name = os.environ.get("MARKET_DATA_PROVIDER_LIVE_PRIMARY") or cfg.get("MARKET_DATA_PROVIDER_LIVE_PRIMARY", "twelvedata").lower()
    
    if _live_primary_provider is None:
        try:
            _live_primary_provider = _get_provider_instance(live_primary_name)
            if _live_primary_provider:
                print(f"✅ Live data primary provider: {live_primary_name}")
            else:
                # Fallback to Alpaca if Twelve Data fails
                print(f"⚠️  Live primary provider ({live_primary_name}) failed to initialize, falling back to alpaca")
                _live_primary_provider = _get_provider_instance("alpaca")
                if _live_primary_provider:
                    print(f"✅ Live data primary provider: alpaca (fallback)")
        except Exception as e:
            print(f"⚠️  Live primary provider ({live_primary_name}) initialization error: {e}")
            # Try Alpaca as fallback
            try:
                _live_primary_provider = _get_provider_instance("alpaca")
                if _live_primary_provider:
                    print(f"✅ Live data primary provider: alpaca (fallback)")
            except:
                _live_primary_provider = None
    
    # TWELVE DATA INTEGRATION: Live secondary provider (Alpaca for last_price fallback, Yahoo as last resort)
    live_secondary_name = os.environ.get("MARKET_DATA_PROVIDER_LIVE_SECONDARY") or cfg.get("MARKET_DATA_PROVIDER_LIVE_SECONDARY", "alpaca").lower()
    
    if _live_secondary_provider is None and live_secondary_name:
        try:
            _live_secondary_provider = _get_provider_instance(live_secondary_name)
            if _live_secondary_provider:
                print(f"✅ Live data secondary provider: {live_secondary_name}")
        except Exception as e:
            print(f"⚠️  Live secondary provider ({live_secondary_name}) initialization error: {e}")
            # Try Yahoo as last resort
            try:
                _live_secondary_provider = _get_provider_instance("yahoo")
                if _live_secondary_provider:
                    print(f"✅ Live data secondary provider: yahoo (fallback)")
            except:
                _live_secondary_provider = None
    
    # STABILITY: Print provider hierarchy only once per process
    global _provider_hierarchy_printed
    if not _provider_hierarchy_printed:
        print(f"✅ Provider hierarchy:")
        print(f"   Historical: {_historical_provider.__class__.__name__ if _historical_provider else 'None'}")
        print(f"   Live primary: {_live_primary_provider.__class__.__name__ if _live_primary_provider else 'None'}")
        print(f"   Live secondary: {_live_secondary_provider.__class__.__name__ if _live_secondary_provider else 'None'}")
        print(f"   Yahoo: fallback only")
        _provider_hierarchy_printed = True
    
    # Legacy support: Set _primary_provider and _secondary_provider for backward compatibility
    _primary_provider = _live_primary_provider
    _secondary_provider = _live_secondary_provider


def get_provider_with_fallback() -> Optional[BaseMarketDataProvider]:
    """
    Get market data provider with fallback logic (for LIVE data only).
    
    TASK 3 FIX: Uses LIVE primary provider first, falls back to LIVE secondary if primary fails.
    For historical data, use get_historical_provider() instead.
    
    Returns:
        Provider instance or None if both are unavailable
    """
    global _live_primary_provider, _live_secondary_provider
    
    # Ensure providers are initialized
    _initialize_providers()
    
    # Return live primary if available, otherwise live secondary
    if _live_primary_provider:
        return _live_primary_provider
    elif _live_secondary_provider:
        print(f"⚠️  Using live secondary provider as primary is unavailable")
        return _live_secondary_provider
    else:
        return None


def get_historical_provider() -> Optional[BaseMarketDataProvider]:
    """
    TWELVE DATA INTEGRATION: Get historical data provider (Twelve Data PRIMARY).
    
    This should be used for:
    - Backtests
    - Strategy evolution
    - MCN regime detection
    - Any historical OHLCV requests
    
    Returns:
        Historical provider instance (Twelve Data) or None if unavailable
    """
    global _historical_provider
    
    # Ensure providers are initialized
    _initialize_providers()
    
    return _historical_provider


def get_provider(name: Optional[str] = None) -> Optional[BaseMarketDataProvider]:
    """
    Get the current market data provider with fallback support.
    
    Args:
        name: Provider name (e.g., "alpaca", "polygon"). If None, uses PRIMARY/SECONDARY from env.
    
    Returns:
        Provider instance or None if not available
    """
    if name is not None:
        # Direct provider request (for testing or specific use cases)
        return _get_provider_instance(name.lower())
    
    # Use fallback logic
    return get_provider_with_fallback()


def call_with_fallback(func_name: str, *args, **kwargs):
    """
    Call a provider method with automatic fallback through request queue.
    Only calls SECONDARY provider if PRIMARY fails with 4xx/5xx or specific errors.
    
    Args:
        func_name: Method name to call (e.g., "get_price", "get_candles")
        *args, **kwargs: Arguments to pass to the method
    
    Returns:
        Result from primary or secondary provider
    
    Raises:
        MarketDataError: If both providers fail
    """
    global _live_primary_provider, _live_secondary_provider
    
    # Ensure providers are initialized
    _initialize_providers()
    
    # Import request queue
    from .request_queue import get_request_queue
    queue = get_request_queue()
    
    # TASK 3 FIX: Use live providers for fallback
    # Determine provider name for queue
    primary_name = _live_primary_provider.__class__.__name__.replace("DataProvider", "").lower() if _live_primary_provider else None
    secondary_name = _live_secondary_provider.__class__.__name__.replace("DataProvider", "").lower() if _live_secondary_provider else None
    
    # Try live primary provider first through queue
    if _live_primary_provider and primary_name:
        try:
            method = getattr(_live_primary_provider, func_name)
            # Use queue for rate limiting and caching
            return queue.execute_sync(primary_name, method, func_name, *args, **kwargs)
        except MarketDataError as e:
            # Check if error is retryable (4xx/5xx, rate limit, symbol not supported, auth failed)
            error_msg = str(e).lower()
            should_fallback = (
                "429" in error_msg or
                "rate limit" in error_msg or
                "not supported" in error_msg or
                "not found" in error_msg or
                "404" in error_msg or
                "403" in error_msg or
                "401" in error_msg or  # Authentication failed - fallback to secondary
                "authentication" in error_msg or
                "500" in error_msg or
                "502" in error_msg or
                "503" in error_msg
            )
            
            # TASK 3 FIX: Live primary failed, try live secondary only if it's a retryable error
            if should_fallback and _live_secondary_provider and _live_secondary_provider != _live_primary_provider and secondary_name:
                try:
                    print(f"⚠️  Live primary provider failed for {func_name}, trying live secondary: {str(e)}")
                    method = getattr(_live_secondary_provider, func_name)
                    # Use queue for secondary provider too
                    return queue.execute_sync(secondary_name, method, func_name, *args, **kwargs)
                except Exception as e2:
                    # Both failed - check if secondary also rate limited
                    error_msg2 = str(e2).lower()
                    if "429" in error_msg2 or "rate limit" in error_msg2:
                        raise MarketDataError("Both providers rate limited. Please try again shortly.")
                    raise MarketDataError(f"Both providers failed. PRIMARY: {str(e)}, SECONDARY: {str(e2)}")
            else:
                # Don't fallback for non-retryable errors
                raise
        except Exception as e:
            # Unexpected error from primary - check if it's a retryable error
            error_msg = str(e).lower()
            should_fallback = (
                "429" in error_msg or
                "rate limit" in error_msg or
                "not supported" in error_msg or
                "not found" in error_msg or
                "404" in error_msg or
                "403" in error_msg or
                "401" in error_msg or  # Authentication failed - fallback to secondary
                "authentication" in error_msg or
                "unauthorized" in error_msg or
                "500" in error_msg or
                "502" in error_msg or
                "503" in error_msg
            )
            
            if should_fallback and _live_secondary_provider and _live_secondary_provider != _live_primary_provider and secondary_name:
                try:
                    print(f"⚠️  Live primary provider error for {func_name}, trying live secondary: {str(e)}")
                    method = getattr(_live_secondary_provider, func_name)
                    # Use queue for secondary provider too
                    return queue.execute_sync(secondary_name, method, func_name, *args, **kwargs)
                except Exception as e2:
                    error_msg2 = str(e2).lower()
                    if "429" in error_msg2 or "rate limit" in error_msg2:
                        raise MarketDataError("Both providers rate limited. Please try again shortly.")
                    raise MarketDataError(f"Both providers failed. PRIMARY: {str(e)}, SECONDARY: {str(e2)}")
            else:
                raise MarketDataError(f"Provider error: {str(e)}")
    elif _live_secondary_provider and secondary_name:
        # TASK 3 FIX: No live primary, try live secondary through queue
        method = getattr(_live_secondary_provider, func_name)
        return queue.execute_sync(secondary_name, method, func_name, *args, **kwargs)
    else:
        raise MarketDataError("No market data provider is available. Check API keys and configuration.")


def reset_provider():
    """Reset the cached providers (useful for testing or switching providers)."""
    global _primary_provider, _secondary_provider
    _primary_provider = None
    _secondary_provider = None

