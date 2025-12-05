# backend/tests/phase3/test_regime_detector.py
"""
Unit tests for RegimeDetector.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from ...brain.regime_detector import RegimeDetector
from ...market_data.types import CandleData


@pytest.fixture
def regime_detector():
    """Create a RegimeDetector instance for testing."""
    with patch('backend.brain.regime_detector.get_mcn_adapter') as mock_mcn:
        mock_adapter = Mock()
        mock_adapter.is_available = True
        mock_adapter.mcn = Mock()
        mock_adapter._market_to_vector = Mock(return_value=[[0.1, 0.2, 0.3]])
        mock_mcn.return_value = mock_adapter
        
        with patch('backend.brain.regime_detector.get_provider_with_fallback') as mock_provider:
            mock_prov = AsyncMock()
            mock_prov.get_candles = AsyncMock(return_value=[
                CandleData(
                    symbol="AAPL",
                    timestamp=datetime.now(),
                    open=100.0,
                    high=105.0,
                    low=99.0,
                    close=103.0,
                    volume=1000000
                )
            ] * 50)
            mock_provider.return_value = mock_prov
            
            detector = RegimeDetector()
            detector.mcn_adapter = mock_adapter
            detector.market_provider = mock_prov
            yield detector


@pytest.mark.asyncio
async def test_get_market_regime_success(regime_detector):
    """Test successful regime detection."""
    # Mock MCN search results
    regime_detector.mcn_adapter.mcn.search = Mock(return_value=(
        [
            {"event_type": "market_snapshot", "payload": {"market_regime": "bull_trend"}},
            {"event_type": "market_snapshot", "payload": {"market_regime": "bull_trend"}},
        ],
        [0.8, 0.7]
    ))
    
    market_data = {"price": 100.0, "volatility": 0.02}
    result = await regime_detector.get_market_regime("AAPL", market_data)
    
    assert result["regime"] in ["bull_trend", "bear_trend", "ranging", "high_vol", "low_vol", "mixed", "unknown"]
    assert 0.0 <= result["confidence"] <= 1.0
    assert "explanation" in result


@pytest.mark.asyncio
async def test_get_market_regime_mcn_unavailable(regime_detector):
    """Test regime detection when MCN is unavailable."""
    regime_detector.mcn_adapter.is_available = False
    
    result = await regime_detector.get_market_regime("AAPL")
    
    assert result["regime"] == "unknown"
    assert result["confidence"] == 0.0
    assert "MCN unavailable" in result["explanation"]


@pytest.mark.asyncio
async def test_get_market_regime_insufficient_data(regime_detector):
    """Test regime detection with insufficient market data."""
    regime_detector.market_provider.get_candles = AsyncMock(return_value=[])
    
    result = await regime_detector.get_market_regime("AAPL")
    
    assert result["regime"] == "unknown"
    assert result["confidence"] == 0.0
    assert "Insufficient" in result["explanation"]
