# backend/tests/unit/test_brain_signal.py
"""
Unit tests for Brain signal generation logic.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from backend.brain.brain_service import BrainService
from backend.brain.types import BrainSignalResponse


class TestBrainSignalGeneration:
    """Test Brain signal generation logic."""
    
    @pytest.fixture
    def brain_service(self):
        """Create BrainService instance."""
        return BrainService()
    
    @pytest.fixture
    def mock_strategy(self):
        """Create a mock strategy."""
        strategy = Mock()
        strategy.id = "test-strategy-123"
        strategy.user_id = "test-user-123"
        strategy.name = "Test Strategy"
        strategy.ruleset = {"entry": "price > sma_20", "exit": "price < sma_20"}
        strategy.score = 0.85
        strategy.status = "proposable"
        strategy.is_proposable = True
        strategy.last_backtest_results = {
            "total_trades": 100,
            "winning_trades": 60,
            "win_rate": 0.6,
            "avg_return": 0.05,
        }
        return strategy
    
    @pytest.fixture
    def mock_market_data(self):
        """Create mock market data."""
        return {
            "price": 100.0,
            "volatility": 0.15,
            "sentiment": 0.2,
            "timestamp": datetime.now(),
        }
    
    @patch('backend.brain.brain_service.crud')
    @patch('backend.brain.brain_service.get_provider')
    def test_signal_generation_requires_proposable_strategy(
        self, mock_get_provider, mock_crud, brain_service, mock_strategy, db_session
    ):
        """Test that signal generation requires proposable strategy."""
        # Set up mocks
        mock_crud.get_user_strategy.return_value = mock_strategy
        mock_provider = Mock()
        mock_provider.get_price.return_value = Mock(price=100.0, timestamp=datetime.now())
        mock_provider.get_volatility.return_value = Mock(volatility=0.15)
        mock_provider.get_sentiment.return_value = Mock(sentiment_score=0.2)
        mock_get_provider.return_value = mock_provider
        
        # Test with non-proposable strategy
        mock_strategy.status = "experiment"
        mock_strategy.is_proposable = False
        
        with pytest.raises(ValueError, match="not yet reliable"):
            brain_service.generate_signal(
                strategy_id="test-strategy-123",
                user_id="test-user-123",
                symbol="AAPL",
                db=db_session
            )
    
    @patch('backend.brain.brain_service.crud')
    @patch('backend.brain.brain_service.get_provider')
    def test_signal_generation_requires_minimum_score(
        self, mock_get_provider, mock_crud, brain_service, mock_strategy, db_session
    ):
        """Test that signal generation requires minimum score."""
        mock_crud.get_user_strategy.return_value = mock_strategy
        mock_provider = Mock()
        mock_get_provider.return_value = mock_provider
        
        # Test with low score
        mock_strategy.score = 0.65
        
        with pytest.raises(ValueError, match="score too low"):
            brain_service.generate_signal(
                strategy_id="test-strategy-123",
                user_id="test-user-123",
                symbol="AAPL",
                db=db_session
            )
    
    @patch('backend.brain.brain_service.crud')
    @patch('backend.brain.brain_service.get_provider')
    def test_signal_generation_requires_minimum_sample_size(
        self, mock_get_provider, mock_crud, brain_service, mock_strategy, db_session
    ):
        """Test that signal generation requires minimum sample size."""
        mock_crud.get_user_strategy.return_value = mock_strategy
        mock_provider = Mock()
        mock_get_provider.return_value = mock_provider
        
        # Test with insufficient sample size
        mock_strategy.last_backtest_results = {"total_trades": 30}
        
        with pytest.raises(ValueError, match="insufficient sample size"):
            brain_service.generate_signal(
                strategy_id="test-strategy-123",
                user_id="test-user-123",
                symbol="AAPL",
                db=db_session
            )

