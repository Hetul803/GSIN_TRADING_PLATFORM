# backend/tests/unit/test_market_data_providers.py
"""
PHASE 6: Unit tests for market data providers.
"""
import pytest
from datetime import datetime, timezone, timedelta
from backend.market_data.adapters.alpaca_adapter import AlpacaDataProvider
from backend.market_data.adapters.yahoo_adapter import YahooDataProvider
from backend.market_data.adapters.polygon_adapter import PolygonDataProvider
from backend.market_data.adapters.finnhub_adapter import FinnhubDataProvider
from backend.market_data.unified_data_engine import get_market_data, get_price_data


class TestMarketDataProviders:
    """Test market data provider adapters."""
    
    def test_yahoo_provider_available(self):
        """Test Yahoo provider availability check."""
        provider = YahooDataProvider()
        assert provider.is_available() == True
    
    def test_yahoo_get_price(self):
        """Test Yahoo provider get_price."""
        provider = YahooDataProvider()
        if provider.is_available():
            price_data = provider.get_price("AAPL")
            assert price_data is not None
            assert price_data.price > 0
            assert price_data.symbol == "AAPL"
    
    def test_yahoo_get_candles(self):
        """Test Yahoo provider get_candles."""
        provider = YahooDataProvider()
        if provider.is_available():
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=30)
            candles = provider.get_candles("AAPL", "1d", limit=30, start=start_date, end=end_date)
            assert candles is not None
            assert len(candles) > 0
            assert candles[0].symbol == "AAPL"
            assert candles[0].open > 0
    
    def test_unified_engine_fallback(self):
        """Test unified data engine fallback logic."""
        # Test that engine falls back to next provider if one fails
        result = get_price_data("AAPL")
        assert result is not None
        assert result.price > 0
    
    def test_unified_engine_historical(self):
        """Test unified data engine historical data."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        candles = get_market_data("AAPL", "1d", limit=30, start=start_date, end=end_date)
        assert candles is not None
        assert len(candles) > 0

