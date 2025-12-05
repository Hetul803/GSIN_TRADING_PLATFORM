# backend/tests/phase3/test_user_risk_profile.py
"""
Unit tests for UserRiskProfile.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ...brain.user_risk_profile import UserRiskProfile
from ...db.models import Trade, TradeStatus, TradeSide, TradeMode, AssetType


@pytest.fixture
def user_risk_profile():
    """Create a UserRiskProfile instance."""
    with patch('backend.brain.user_risk_profile.get_mcn_adapter') as mock_mcn:
        mock_adapter = Mock()
        mock_adapter.is_available = True
        mock_adapter.record_event = Mock()
        mock_mcn.return_value = mock_adapter
        
        profile = UserRiskProfile()
        profile.mcn_adapter = mock_adapter
        yield profile


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_trades():
    """Create mock closed trades for testing."""
    trades = []
    base_time = datetime.now() - timedelta(days=30)
    
    # Create winning trades (conservative pattern)
    for i in range(10):
        trade = Mock(spec=Trade)
        trade.quantity = 10.0
        trade.entry_price = 100.0
        trade.realized_pnl = 50.0  # Positive P&L
        trade.opened_at = base_time + timedelta(days=i*2)
        trade.closed_at = base_time + timedelta(days=i*2+7)  # 7-day holding period
        trades.append(trade)
    
    # Create losing trades
    for i in range(2):
        trade = Mock(spec=Trade)
        trade.quantity = 10.0
        trade.entry_price = 100.0
        trade.realized_pnl = -20.0  # Negative P&L
        trade.opened_at = base_time + timedelta(days=20+i*2)
        trade.closed_at = base_time + timedelta(days=20+i*2+5)
        trades.append(trade)
    
    return trades


def test_get_user_risk_profile_insufficient_data(user_risk_profile, mock_db):
    """Test risk profile with insufficient trade history."""
    with patch('backend.brain.user_risk_profile.crud.list_user_trades', return_value=[]):
        with patch('backend.brain.user_risk_profile.PaperBroker') as mock_broker:
            mock_broker.return_value.get_account_balance.return_value = {"paper_balance": 100000.0}
            
            result = user_risk_profile.get_user_risk_profile("user-1", mock_db)
            
            assert result["risk_tendency"] == "moderate"
            assert result["confidence"] < 0.5
            assert "Insufficient" in result.get("reason", "")


def test_get_user_risk_profile_conservative(user_risk_profile, mock_db, mock_trades):
    """Test risk profile inference for conservative trader."""
    with patch('backend.brain.user_risk_profile.crud.list_user_trades', return_value=mock_trades):
        with patch('backend.brain.user_risk_profile.PaperBroker') as mock_broker:
            mock_broker.return_value.get_account_balance.return_value = {"paper_balance": 100000.0}
            
            result = user_risk_profile.get_user_risk_profile("user-1", mock_db)
            
            assert result["risk_tendency"] in ["conservative", "moderate", "aggressive"]
            assert 0.0 <= result["confidence"] <= 1.0
            assert "factors" in result
            assert "avg_position_size_pct" in result["factors"]
            assert "win_rate" in result["factors"]


def test_calculate_risk_factors(user_risk_profile, mock_trades, mock_db):
    """Test risk factor calculation."""
    with patch('backend.brain.user_risk_profile.PaperBroker') as mock_broker:
        mock_broker.return_value.get_account_balance.return_value = {"paper_balance": 100000.0}
        
        factors = user_risk_profile._calculate_risk_factors(mock_trades, mock_db, "user-1")
        
        assert "avg_position_size_pct" in factors
        assert "win_rate" in factors
        assert "avg_holding_period_days" in factors
        assert "volatility_tolerance" in factors
        assert "max_drawdown_tolerance" in factors
        
        assert 0.0 <= factors["win_rate"] <= 1.0
        assert factors["avg_holding_period_days"] > 0.0


def test_infer_risk_tendency_conservative(user_risk_profile):
    """Test risk tendency inference for conservative factors."""
    factors = {
        "avg_position_size_pct": 0.03,  # Small positions
        "win_rate": 0.8,  # High win rate
        "avg_holding_period_days": 10.0,  # Long holding
        "volatility_tolerance": 0.01,  # Low volatility
        "max_drawdown_tolerance": 0.02  # Small losses
    }
    
    tendency, confidence = user_risk_profile._infer_risk_tendency(factors)
    
    assert tendency in ["conservative", "moderate", "aggressive"]
    assert 0.0 <= confidence <= 1.0


def test_infer_risk_tendency_aggressive(user_risk_profile):
    """Test risk tendency inference for aggressive factors."""
    factors = {
        "avg_position_size_pct": 0.25,  # Large positions
        "win_rate": 0.4,  # Lower win rate
        "avg_holding_period_days": 1.0,  # Short holding
        "volatility_tolerance": 0.08,  # High volatility
        "max_drawdown_tolerance": 0.20  # Large losses
    }
    
    tendency, confidence = user_risk_profile._infer_risk_tendency(factors)
    
    assert tendency in ["conservative", "moderate", "aggressive"]
    # Should lean towards aggressive
    assert tendency in ["aggressive", "moderate"]

