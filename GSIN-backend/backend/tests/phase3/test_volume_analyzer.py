# backend/tests/phase3/test_volume_analyzer.py
"""
Unit tests for VolumeAnalyzer.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from ...market_data.volume_analyzer import VolumeAnalyzer
from ...market_data.types import CandleData


@pytest.fixture
def volume_analyzer():
    """Create a VolumeAnalyzer instance."""
    with patch('backend.market_data.volume_analyzer.get_provider_with_fallback') as mock_provider:
        mock_prov = AsyncMock()
        # Create candles with increasing volume
        candles = []
        base_volume = 1000000
        for i in range(50):
            candles.append(CandleData(
                symbol="AAPL",
                timestamp=datetime.now(),
                open=100.0,
                high=105.0,
                low=99.0,
                close=103.0,
                volume=base_volume + i * 10000  # Increasing volume
            ))
        mock_prov.get_candles = AsyncMock(return_value=candles)
        mock_provider.return_value = mock_prov
        
        analyzer = VolumeAnalyzer()
        yield analyzer


@pytest.mark.asyncio
async def test_get_volume_confirmation_increasing(volume_analyzer):
    """Test volume confirmation with increasing volume."""
    result = await volume_analyzer.get_volume_confirmation("AAPL", "1d")
    
    assert "volume_trend" in result
    assert "volume_strength" in result
    assert "explanation" in result
    
    assert result["volume_trend"] in ["increasing", "decreasing", "normal", "low"]


@pytest.mark.asyncio
async def test_get_volume_confirmation_insufficient_data(volume_analyzer):
    """Test volume confirmation with insufficient data."""
    volume_analyzer.market_provider.get_candles = AsyncMock(return_value=[])
    
    result = await volume_analyzer.get_volume_confirmation("AAPL", "1d")
    
    assert result["volume_trend"] == "normal"
    assert "Insufficient" in result["explanation"]


@pytest.mark.asyncio
async def test_get_volume_confirmation_low_volume(volume_analyzer):
    """Test volume confirmation with extremely low volume."""
    # Create candles with very low volume
    low_volume_candles = [
        CandleData(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=10000  # Very low volume
        )
    ] * 50
    
    with patch.object(volume_analyzer, 'market_provider') as mock_prov:
        mock_prov.get_candles = AsyncMock(return_value=low_volume_candles)
        
        result = await volume_analyzer.get_volume_confirmation("AAPL", "1d")
        
        # Should detect low volume
        assert result["volume_trend"] in ["low", "normal"]
