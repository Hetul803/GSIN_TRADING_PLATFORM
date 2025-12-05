# backend/tests/unit/test_strategy_mutation.py
"""
PHASE 6: Unit tests for strategy mutation engine.
"""
import pytest
from backend.strategy_engine.mutation_engine import MutationEngine
from backend.strategy_engine.mutation_engine_enhanced import EnhancedMutationEngine


class TestStrategyMutation:
    """Test strategy mutation engines."""
    
    def test_mutation_engine_init(self):
        """Test mutation engine initialization."""
        engine = MutationEngine()
        assert engine is not None
    
    def test_enhanced_mutation_engine_init(self):
        """Test enhanced mutation engine initialization."""
        engine = EnhancedMutationEngine()
        assert engine is not None
    
    def test_mutate_strategy(self):
        """Test mutating a strategy."""
        engine = MutationEngine()
        
        original_ruleset = {
            "ticker": "AAPL",
            "timeframe": "1d",
            "entry_rules": {
                "condition": "price_above_sma",
                "sma_period": 20
            },
            "exit_rules": {
                "condition": "price_below_sma",
                "sma_period": 20
            }
        }
        
        mutated = engine.mutate_strategy(original_ruleset)
        
        assert mutated is not None
        assert "entry_rules" in mutated
        assert "exit_rules" in mutated
        # Mutation should change something
        assert mutated != original_ruleset
    
    def test_enhanced_mutate_strategy(self):
        """Test enhanced mutation engine."""
        engine = EnhancedMutationEngine()
        
        original_ruleset = {
            "ticker": "AAPL",
            "timeframe": "1d",
            "entry_rules": {
                "condition": "price_above_sma",
                "sma_period": 20
            },
            "exit_rules": {
                "condition": "price_below_sma",
                "sma_period": 20
            }
        }
        
        mutated = engine.mutate_strategy(original_ruleset)
        
        assert mutated is not None
        assert "entry_rules" in mutated
        assert "exit_rules" in mutated

