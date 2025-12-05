# backend/tests/unit/test_backtest_engine.py
"""
PHASE 6: Unit tests for backtesting engine.
"""
import pytest
from datetime import datetime, timezone, timedelta
from backend.strategy_engine.backtest_engine import BacktestEngine


class TestBacktestEngine:
    """Test backtesting engine."""
    
    def test_backtest_engine_init(self):
        """Test backtest engine initialization."""
        engine = BacktestEngine()
        assert engine is not None
        assert engine.market_provider is not None
    
    def test_backtest_simple_strategy(self):
        """Test running a simple backtest."""
        engine = BacktestEngine()
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)
        
        # Simple buy-and-hold strategy
        ruleset = {
            "ticker": "AAPL",
            "timeframe": "1d",
            "entry_rules": {
                "condition": "always_true"
            },
            "exit_rules": {
                "condition": "never"
            }
        }
        
        try:
            results = engine.run_backtest(
                symbol="AAPL",
                ruleset=ruleset,
                timeframe="1d",
                start_date=start_date,
                end_date=end_date
            )
            
            assert results is not None
            assert "total_return" in results
            assert "win_rate" in results
            assert "total_trades" in results
        except ValueError as e:
            # If insufficient data, that's OK for unit test
            if "Insufficient data" in str(e):
                pytest.skip("Insufficient data for backtest")
            else:
                raise
    
    def test_backtest_min_candles(self):
        """Test that backtest requires minimum candles."""
        engine = BacktestEngine()
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=1)  # Too short
        
        ruleset = {
            "ticker": "AAPL",
            "timeframe": "1d",
            "entry_rules": {"condition": "always_true"},
            "exit_rules": {"condition": "never"}
        }
        
        with pytest.raises(ValueError, match="Insufficient data"):
            engine.run_backtest(
                symbol="AAPL",
                ruleset=ruleset,
                timeframe="1d",
                start_date=start_date,
                end_date=end_date
            )
    
    def test_cross_asset_backtest(self):
        """Test cross-asset backtesting."""
        engine = BacktestEngine()
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)
        
        ruleset = {
            "ticker": "AAPL",
            "timeframe": "1d",
            "entry_rules": {"condition": "always_true"},
            "exit_rules": {"condition": "never"}
        }
        
        try:
            results = engine.execute_backtest_across_assets(
                strategy_ruleset=ruleset,
                timeframe="1d",
                start_date=start_date,
                end_date=end_date,
                symbols=["AAPL", "MSFT"]
            )
            
            assert results is not None
            assert "per_symbol_results" in results
            assert "aggregated_metrics" in results
        except ValueError as e:
            if "Insufficient data" in str(e):
                pytest.skip("Insufficient data for cross-asset backtest")
            else:
                raise

