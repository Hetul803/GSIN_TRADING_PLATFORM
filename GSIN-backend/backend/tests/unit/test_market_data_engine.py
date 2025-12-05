# backend/tests/unit/test_market_data_engine.py
"""
Unit tests for unified market data engine fallback logic.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from backend.market_data.unified_data_engine import get_market_data, MarketDataError
from backend.market_data.adapters.alpaca_adapter import AlpacaDataProvider
from backend.market_data.adapters.polygon_adapter import PolygonDataProvider
from backend.market_data.adapters.finnhub_adapter import FinnhubDataProvider


class TestUnifiedDataEngine:
    """Test unified market data engine fallback logic."""
    
    @pytest.fixture
    def mock_alpaca_provider(self):
        """Create a mock Alpaca provider."""
        provider = Mock(spec=AlpacaDataProvider)
        provider.is_available.return_value = True
        provider.get_price = Mock(return_value=Mock(
            symbol="AAPL",
            price=150.0,
            change_percent=0.02,
            timestamp=datetime.now()
        ))
        return provider
    
    @pytest.fixture
    def mock_polygon_provider(self):
        """Create a mock Polygon provider."""
        provider = Mock(spec=PolygonDataProvider)
        provider.is_available.return_value = True
        provider.get_price = Mock(return_value=Mock(
            symbol="AAPL",
            price=150.0,
            change_percent=0.02,
            timestamp=datetime.now()
        ))
        return provider
    
    @pytest.fixture
    def mock_finnhub_provider(self):
        """Create a mock Finnhub provider."""
        provider = Mock(spec=FinnhubDataProvider)
        provider.is_available.return_value = True
        provider.get_price = Mock(return_value=Mock(
            symbol="AAPL",
            price=150.0,
            change_percent=0.02,
            timestamp=datetime.now()
        ))
        return provider
    
    @patch('backend.market_data.unified_data_engine.AlpacaDataProvider')
    @patch('backend.market_data.unified_data_engine.PolygonDataProvider')
    @patch('backend.market_data.unified_data_engine.FinnhubDataProvider')
    @pytest.mark.asyncio
    async def test_primary_provider_success(
        self, mock_finnhub, mock_polygon, mock_alpaca, mock_alpaca_provider
    ):
        """Test that primary provider (Alpaca) is used when available."""
        mock_alpaca.return_value = mock_alpaca_provider
        
        result = await get_market_data("AAPL", "price")
        
        assert result is not None
        assert result.price == 150.0
        mock_alpaca_provider.get_price.assert_called_once()
    
    @patch('backend.market_data.unified_data_engine.AlpacaDataProvider')
    @patch('backend.market_data.unified_data_engine.PolygonDataProvider')
    @patch('backend.market_data.unified_data_engine.FinnhubDataProvider')
    @pytest.mark.asyncio
    async def test_fallback_to_polygon(
        self, mock_finnhub, mock_polygon, mock_alpaca, mock_alpaca_provider, mock_polygon_provider
    ):
        """Test fallback to Polygon when Alpaca fails."""
        mock_alpaca.return_value = mock_alpaca_provider
        mock_polygon.return_value = mock_polygon_provider
        
        # Make Alpaca fail
        mock_alpaca_provider.is_available.return_value = False
        
        result = await get_market_data("AAPL", "price")
        
        assert result is not None
        assert result.price == 150.0
        mock_polygon_provider.get_price.assert_called_once()
    
    @patch('backend.market_data.unified_data_engine.AlpacaDataProvider')
    @patch('backend.market_data.unified_data_engine.PolygonDataProvider')
    @patch('backend.market_data.unified_data_engine.FinnhubDataProvider')
    @pytest.mark.asyncio
    async def test_fallback_to_finnhub(
        self, mock_finnhub, mock_polygon, mock_alpaca, mock_alpaca_provider, 
        mock_polygon_provider, mock_finnhub_provider
    ):
        """Test fallback to Finnhub when Alpaca and Polygon fail."""
        mock_alpaca.return_value = mock_alpaca_provider
        mock_polygon.return_value = mock_polygon_provider
        mock_finnhub.return_value = mock_finnhub_provider
        
        # Make Alpaca and Polygon fail
        mock_alpaca_provider.is_available.return_value = False
        mock_polygon_provider.is_available.return_value = False
        
        result = await get_market_data("AAPL", "price")
        
        assert result is not None
        assert result.price == 150.0
        mock_finnhub_provider.get_price.assert_called_once()

