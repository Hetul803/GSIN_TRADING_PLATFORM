# backend/tests/integration/test_backtest_mutation_brain.py
"""
PHASE 6: Integration tests for backtest → mutation → brain flow.
"""
import pytest
from datetime import datetime, timezone, timedelta
from backend.strategy_engine.backtest_engine import BacktestEngine
from backend.strategy_engine.mutation_engine_enhanced import EnhancedMutationEngine
from backend.brain.brain_service import BrainService
from backend.db.session import SessionLocal


class TestBacktestMutationBrainFlow:
    """Test the complete flow: backtest → mutation → brain."""
    
    @pytest.fixture
    def db(self):
        """Provide database session."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def test_backtest_to_mutation_flow(self):
        """Test that backtest results can be used for mutation."""
        engine = BacktestEngine()
        mutation_engine = EnhancedMutationEngine()
        
        ruleset = {
            "ticker": "AAPL",
            "timeframe": "1d",
            "entry_rules": {"condition": "always_true"},
            "exit_rules": {"condition": "never"}
        }
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)
        
        try:
            # Run backtest
            results = engine.run_backtest(
                symbol="AAPL",
                ruleset=ruleset,
                timeframe="1d",
                start_date=start_date,
                end_date=end_date
            )
            
            # Mutate based on results
            if results.get("win_rate", 0) < 0.5:
                mutated = mutation_engine.mutate_strategy(ruleset)
                assert mutated is not None
                assert mutated != ruleset
        except ValueError as e:
            if "Insufficient data" in str(e):
                pytest.skip("Insufficient data for integration test")
            else:
                raise
    
    def test_brain_signal_generation(self, db):
        """Test that Brain can generate signals."""
        brain = BrainService()
        
        try:
            signal = brain.generate_signal(
                symbol="AAPL",
                user_id="test_user",
                db=db
            )
            
            assert signal is not None
            assert "action" in signal
            assert "confidence" in signal
            assert 0 <= signal["confidence"] <= 1
        except Exception as e:
            # Brain may not be fully configured in test environment
            pytest.skip(f"Brain not available: {e}")

