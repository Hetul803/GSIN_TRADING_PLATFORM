# backend/tests/phase3/test_portfolio_risk.py
"""
Unit tests for PortfolioRiskManager.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from ...brain.portfolio_risk import PortfolioRiskManager
from ...db.models import Trade, TradeStatus, TradeSide, TradeMode, AssetType


@pytest.fixture
def portfolio_risk_manager():
    """Create a PortfolioRiskManager instance."""
    with patch('backend.brain.portfolio_risk.get_provider_with_fallback') as mock_provider:
        mock_prov = AsyncMock()
        mock_prov.get_asset_details = AsyncMock(return_value={"sector": "Technology"})
        mock_provider.return_value = mock_prov
        
        manager = PortfolioRiskManager()
        manager.market_provider = mock_prov
        yield manager


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_paper_broker():
    """Create a mock paper broker."""
    broker = Mock()
    broker.get_account_balance = Mock(return_value={"paper_balance": 100000.0})
    return broker


@pytest.mark.asyncio
async def test_evaluate_portfolio_risk_allowed(portfolio_risk_manager, mock_db, mock_paper_broker):
    """Test portfolio risk evaluation when trade is allowed."""
    with patch('backend.brain.portfolio_risk.PaperBroker', return_value=mock_paper_broker):
        with patch.object(portfolio_risk_manager, '_get_user_portfolio', return_value=[]):
            proposed_trade = {
                "symbol": "AAPL",
                "side": "BUY",
                "position_size": 10.0,
                "entry_price": 150.0,
                "asset_type": AssetType.STOCK
            }
            
            result = await portfolio_risk_manager.evaluate_portfolio_risk(
                "user-1", proposed_trade, mock_db
            )
            
            assert result["allowed"] is True
            assert "risk_factors" in result


@pytest.mark.asyncio
async def test_evaluate_portfolio_risk_symbol_exposure_limit(portfolio_risk_manager, mock_db, mock_paper_broker):
    """Test portfolio risk when symbol exposure exceeds limit."""
    with patch('backend.brain.portfolio_risk.PaperBroker', return_value=mock_paper_broker):
        # Create portfolio with high exposure to same symbol
        portfolio = [
            {
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": 100.0,
                "entry_price": 150.0,
                "current_value": 15000.0
            }
        ]
        
        with patch.object(portfolio_risk_manager, '_get_user_portfolio', return_value=portfolio):
            proposed_trade = {
                "symbol": "AAPL",
                "side": "BUY",
                "position_size": 200.0,  # Large position
                "entry_price": 150.0,
                "asset_type": AssetType.STOCK
            }
            
            result = await portfolio_risk_manager.evaluate_portfolio_risk(
                "user-1", proposed_trade, mock_db
            )
            
            # Should be blocked or adjusted if exposure > 20%
            assert "risk_factors" in result
            assert "symbol_exposure" in result["risk_factors"]


@pytest.mark.asyncio
async def test_evaluate_portfolio_risk_insufficient_capital(portfolio_risk_manager, mock_db):
    """Test portfolio risk with insufficient capital."""
    mock_broker = Mock()
    mock_broker.get_account_balance = Mock(return_value={"paper_balance": 0.0})
    
    with patch('backend.brain.portfolio_risk.PaperBroker', return_value=mock_broker):
        proposed_trade = {
            "symbol": "AAPL",
            "side": "BUY",
            "position_size": 10.0,
            "entry_price": 150.0,
            "asset_type": AssetType.STOCK
        }
        
        result = await portfolio_risk_manager.evaluate_portfolio_risk(
            "user-1", proposed_trade, mock_db
        )
        
        assert result["allowed"] is False
        assert "Insufficient" in result["reason"]


def test_calculate_symbol_exposure(portfolio_risk_manager):
    """Test symbol exposure calculation."""
    portfolio = [
        {"symbol": "AAPL", "side": "BUY", "quantity": 10.0, "entry_price": 150.0, "current_value": 1500.0}
    ]
    total_capital = 10000.0
    proposed_value = 2000.0
    
    exposure = portfolio_risk_manager._calculate_symbol_exposure(
        "AAPL", portfolio, total_capital, proposed_value, "BUY"
    )
    
    assert exposure > 0.0
    assert exposure <= 1.0  # Should be normalized


def test_calculate_leverage_risk(portfolio_risk_manager):
    """Test leverage risk calculation."""
    portfolio = [
        {"quantity": 10.0, "entry_price": 150.0, "current_value": 1500.0}
    ]
    total_capital = 10000.0
    proposed_value = 5000.0
    
    leverage = portfolio_risk_manager._calculate_leverage_risk(
        portfolio, total_capital, proposed_value, "BUY"
    )
    
    assert leverage > 0.0
    # Leverage = (1500 + 5000) / 10000 = 0.65
    assert leverage == 0.65
