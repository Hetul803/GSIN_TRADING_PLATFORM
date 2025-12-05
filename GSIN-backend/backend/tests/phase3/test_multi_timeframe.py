# backend/tests/phase3/test_multi_timeframe.py
"""
Unit tests for MultiTimeframeAnalyzer.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from ...market_data.multi_timeframe import MultiTimeframeAnalyzer
from ...market_data.types import CandleData


@pytest.fixture
def multi_timeframe_analyzer():
    """Create a MultiTimeframeAnalyzer instance."""
    with patch('backend.market_data.multi_timeframe.get_provider_with_fallback') as mock_provider:
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
        
        analyzer = MultiTimeframeAnalyzer()
        analyzer.market_provider = mock_prov
        yield analyzer


@pytest.mark.asyncio
async def test_get_multi_timeframe_trend_success(multi_timeframe_analyzer):
    """Test successful multi-timeframe trend analysis."""
    result = await multi_timeframe_analyzer.get_multi_timeframe_trend("AAPL")
    
    assert "trend_short" in result
    assert "trend_medium" in result
    assert "trend_long" in result
    assert "alignment_score" in result
    assert "details" in result
    
    assert result["trend_short"] in ["up", "down", "flat"]
    assert 0.0 <= result["alignment_score"] <= 1.0


@pytest.mark.asyncio
async def test_get_multi_timeframe_trend_provider_unavailable(multi_timeframe_analyzer):
    """Test multi-timeframe analysis when provider is unavailable."""
    multi_timeframe_analyzer.market_provider = None
    
    result = await multi_timeframe_analyzer.get_multi_timeframe_trend("AAPL")
    
    assert result["trend_short"] == "flat"
    assert result["alignment_score"] == 0.0
    assert "reason" in result


def test_calculate_alignment_score_perfect(multi_timeframe_analyzer):
    """Test alignment score calculation with perfect alignment."""
    trend_scores = [1, 1, 1, 1, 1, 1]  # All up trends
    score = multi_timeframe_analyzer._calculate_alignment_score(trend_scores)
    
    assert score == 1.0


def test_calculate_alignment_score_conflicting(multi_timeframe_analyzer):
    """Test alignment score calculation with conflicting trends."""
    trend_scores = [1, -1, 1, -1, 1, -1]  # Conflicting trends
    score = multi_timeframe_analyzer._calculate_alignment_score(trend_scores)
    
    assert score < 0.5  # Should be low due to conflict


def test_aggregate_trend(multi_timeframe_analyzer):
    """Test trend aggregation."""
    trend_details = {
        "1m": {"trend": "up"},
        "5m": {"trend": "up"},
        "15m": {"trend": "down"},
    }
    
    aggregated = multi_timeframe_analyzer._aggregate_trend(trend_details, ["1m", "5m", "15m"])
    
    assert aggregated in ["up", "down", "flat"]
