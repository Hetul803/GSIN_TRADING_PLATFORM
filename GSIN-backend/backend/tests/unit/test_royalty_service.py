# backend/tests/unit/test_royalty_service.py
"""
Unit tests for RoyaltyService fee calculation.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from backend.services.royalty_service import RoyaltyService
from backend.db.models import Trade, TradeStatus, UserStrategy, User, SubscriptionTier


class TestRoyaltyService:
    """Test RoyaltyService calculations."""
    
    @pytest.fixture
    def royalty_service(self):
        """Create RoyaltyService instance."""
        return RoyaltyService()
    
    @pytest.fixture
    def mock_trade(self):
        """Create a mock trade with profit."""
        trade = Mock(spec=Trade)
        trade.id = "trade-123"
        trade.realized_pnl = 1000.0  # $1000 profit
        trade.status = TradeStatus.CLOSED
        trade.strategy_id = "strategy-123"
        return trade
    
    @pytest.fixture
    def mock_strategy_owner_default(self):
        """Create a mock strategy owner with default tier."""
        owner = Mock(spec=User)
        owner.id = "owner-123"
        owner.subscription_tier = SubscriptionTier.USER  # Default tier
        return owner
    
    @pytest.fixture
    def mock_strategy_owner_creator(self):
        """Create a mock strategy owner with creator tier."""
        owner = Mock(spec=User)
        owner.id = "owner-123"
        owner.subscription_tier = SubscriptionTier.CREATOR  # Creator tier
        return owner
    
    def test_default_royalty_calculation(self, royalty_service, mock_trade, mock_strategy_owner_default, db_session):
        """Test royalty calculation for default tier (5%)."""
        with patch('backend.services.royalty_service.crud') as mock_crud:
            mock_crud.get_user_strategy.return_value = Mock(user_id="owner-123")
            mock_crud.get_user.return_value = mock_strategy_owner_default
            
            result = royalty_service.calculate_royalty(mock_trade, db_session)
            
            assert result is not None
            assert result["trade_profit"] == 1000.0
            assert result["royalty_rate"] == 0.05  # 5% default
            assert result["royalty_amount"] == 50.0  # 5% of $1000
            assert result["platform_fee_rate"] == 0.05  # 5% platform fee
            assert result["platform_fee"] == 2.5  # 5% of $50
            assert result["net_amount"] == 47.5  # $50 - $2.50
    
    def test_creator_royalty_calculation(self, royalty_service, mock_trade, mock_strategy_owner_creator, db_session):
        """Test royalty calculation for creator tier (3%)."""
        with patch('backend.services.royalty_service.crud') as mock_crud:
            mock_crud.get_user_strategy.return_value = Mock(user_id="owner-123")
            mock_crud.get_user.return_value = mock_strategy_owner_creator
            
            result = royalty_service.calculate_royalty(mock_trade, db_session)
            
            assert result is not None
            assert result["royalty_rate"] == 0.03  # 3% creator
            assert result["royalty_amount"] == 30.0  # 3% of $1000
            assert result["platform_fee"] == 1.5  # 5% of $30
            assert result["net_amount"] == 28.5  # $30 - $1.50
    
    def test_no_royalty_for_loss(self, royalty_service, mock_trade, db_session):
        """Test that no royalty is calculated for losing trades."""
        mock_trade.realized_pnl = -500.0  # Loss
        
        result = royalty_service.calculate_royalty(mock_trade, db_session)
        
        assert result is None
    
    def test_no_royalty_for_open_trades(self, royalty_service, mock_trade, db_session):
        """Test that no royalty is calculated for open trades."""
        mock_trade.status = TradeStatus.OPEN
        
        result = royalty_service.calculate_royalty(mock_trade, db_session)
        
        assert result is None

