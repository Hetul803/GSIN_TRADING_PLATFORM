# backend/tests/phase3/test_brain_integration.py
"""
Integration tests for Brain signal generation with Phase 3 components.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.orm import Session

from ...brain.brain_service import BrainService
from ...db.models import UserStrategy, StrategyStatus, AssetType


@pytest.fixture
def mock_strategy():
    """Create a mock strategy."""
    strategy = Mock(spec=UserStrategy)
    strategy.id = "strategy-1"
    strategy.user_id = "user-1"
    strategy.name = "Test Strategy"
    strategy.ruleset = {"timeframe": "1d", "indicators": ["RSI"]}
    strategy.parameters = {"rsi_threshold": 30}
    strategy.asset_type = AssetType.STOCK
    strategy.score = 0.75
    strategy.status = StrategyStatus.READY
    return strategy


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def brain_service():
    """Create a BrainService instance with mocked dependencies."""
    with patch('backend.brain.brain_service.get_mcn_adapter') as mock_mcn:
        with patch('backend.brain.brain_service.StrategyService') as mock_strategy_service:
            with patch('backend.brain.brain_service.get_provider') as mock_provider:
                mock_adapter = Mock()
                mock_adapter.is_available = True
                mock_adapter.get_regime_context = Mock(return_value={})
                mock_adapter.get_user_profile_memory = Mock(return_value={"risk_tendency": "moderate"})
                mock_adapter.get_strategy_lineage_memory = Mock(return_value={})
                mock_adapter.recommend_trade = Mock(return_value={
                    "side": "BUY",
                    "entry": 100.0,
                    "stop_loss": 95.0,
                    "take_profit": 110.0,
                    "confidence": 0.7,
                    "explanation": "MCN recommendation"
                })
                mock_adapter.record_event = Mock()
                mock_mcn.return_value = mock_adapter
                
                mock_strategy_svc = Mock()
                mock_strategy_svc.generate_signal = Mock(return_value={
                    "side": "BUY",
                    "entry": 100.0,
                    "confidence": 0.6,
                    "reasoning": "RSI oversold"
                })
                
                mock_prov = AsyncMock()
                mock_prov.get_price = AsyncMock(return_value=Mock(price=100.0))
                mock_prov.get_volatility = AsyncMock(return_value=Mock(volatility=0.02))
                mock_prov.get_sentiment = AsyncMock(return_value=Mock(sentiment_score=0.1))
                mock_prov.get_candles = AsyncMock(return_value=[])
                
                service = BrainService()
                service.mcn_adapter = mock_adapter
                service.strategy_service = mock_strategy_svc
                service.market_provider = mock_prov
                
                # Mock Phase 3 components
                service.regime_detector.get_market_regime = AsyncMock(return_value={
                    "regime": "bull_trend",
                    "confidence": 0.8
                })
                service.multi_timeframe_analyzer.get_multi_timeframe_trend = AsyncMock(return_value={
                    "alignment_score": 0.7
                })
                service.volume_analyzer.get_volume_confirmation = AsyncMock(return_value={
                    "volume_strength": 0.6,
                    "recommendation": "caution"
                })
                service.portfolio_risk_manager.evaluate_portfolio_risk = AsyncMock(return_value={
                    "allowed": True,
                    "adjustment": 1.0
                })
                service.user_risk_profile.get_user_risk_profile = Mock(return_value={
                    "risk_tendency": "moderate",
                    "confidence": 0.7,
                    "factors": {}
                })
                
                yield service


@pytest.mark.asyncio
async def test_generate_signal_integration(brain_service, mock_strategy, mock_db):
    """Test end-to-end signal generation with Phase 3 components."""
    with patch('backend.brain.brain_service.crud.get_user_strategy', return_value=mock_strategy):
        with patch.object(brain_service, '_calculate_position_size', return_value=10.0):
            with patch.object(brain_service, '_determine_risk_level', return_value="moderate"):
                with patch.object(brain_service, '_calculate_target_alignment', return_value=0.5):
                    signal = await brain_service.generate_signal(
                        "strategy-1",
                        "user-1",
                        "AAPL",
                        mock_db
                    )
                    
                    assert signal.strategy_id == "strategy-1"
                    assert signal.symbol == "AAPL"
                    assert signal.side in ["BUY", "SELL"]
                    assert 0.0 <= signal.confidence <= 1.0
                    assert signal.mcn_adjustments is not None
                    assert "market_regime_detected" in signal.mcn_adjustments
                    assert "multi_timeframe_trend" in signal.mcn_adjustments
                    assert "volume_confirmation" in signal.mcn_adjustments
                    assert "portfolio_risk" in signal.mcn_adjustments


@pytest.mark.asyncio
async def test_generate_signal_low_confidence_rejection(brain_service, mock_strategy, mock_db):
    """Test signal generation rejection when confidence is too low."""
    # Mock low confidence calibration
    brain_service.confidence_calibrator.calibrate_confidence = Mock(return_value=0.3)
    
    with patch('backend.brain.brain_service.crud.get_user_strategy', return_value=mock_strategy):
        with pytest.raises(ValueError, match="confidence too low"):
            await brain_service.generate_signal(
                "strategy-1",
                "user-1",
                "AAPL",
                mock_db
            )


@pytest.mark.asyncio
async def test_generate_signal_portfolio_risk_block(brain_service, mock_strategy, mock_db):
    """Test signal generation when portfolio risk blocks the trade."""
    brain_service.portfolio_risk_manager.evaluate_portfolio_risk = AsyncMock(return_value={
        "allowed": False,
        "reason": "Symbol exposure exceeds limit"
    })
    
    with patch('backend.brain.brain_service.crud.get_user_strategy', return_value=mock_strategy):
        with pytest.raises(ValueError, match="portfolio risk"):
            await brain_service.generate_signal(
                "strategy-1",
                "user-1",
                "AAPL",
                mock_db
            )
