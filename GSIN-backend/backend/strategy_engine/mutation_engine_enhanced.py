# backend/strategy_engine/mutation_engine_enhanced.py
"""
Enhanced Mutation Engine with Genetic Algorithm.
Implements:
- Elite selection
- Crossover
- Adaptive mutation
- Diversity preservation
"""
from typing import List, Dict, Any, Optional
import random
import copy
import numpy as np

from ..db.models import UserStrategy
from ..db import crud
from sqlalchemy.orm import Session
from .constants import DEFAULT_SYMBOLS


class EnhancedMutationEngine:
    """Enhanced mutation engine with genetic algorithm."""
    
    def __init__(self):
        self.mutation_rate = 0.2  # 20% mutation rate
        self.crossover_rate = 0.7  # 70% crossover rate
        self.elite_size = 0.1  # Top 10% are elite
    
    def mutate_strategy(
        self,
        strategy: UserStrategy,
        num_mutations: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Create mutated versions of a strategy.
        
        This method wraps _mutate_adaptive to provide compatibility with
        the evolution worker that expects a mutate_strategy method.
        
        Args:
            strategy: Original strategy to mutate
            num_mutations: Number of mutations to create (1-3)
        
        Returns:
            List of mutation dictionaries with:
            - mutation_type: Type of mutation
            - mutation_params: Parameters changed
            - mutated_strategy: New strategy data
        """
        mutations = []
        
        for _ in range(min(num_mutations, 3)):
            mutation = self._mutate_adaptive(strategy)
            mutations.append(mutation)
        
        return mutations
    
    def evolve_population(
        self,
        strategies: List[UserStrategy],
        db: Session,
        num_offspring: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Evolve a population of strategies using genetic algorithm with tournament selection.
        
        IMPROVEMENT: Changed from "Top 10% Elite Selection" to "Tournament Selection"
        to prevent premature convergence and increase genetic diversity.
        
        Args:
            strategies: List of parent strategies
            db: Database session
            num_offspring: Number of offspring to create
        
        Returns:
            List of new strategy mutations
        """
        if not strategies:
            return []
        
        # Create offspring using tournament selection
        offspring = []
        
        for _ in range(num_offspring):
            # Tournament Selection: Pick best of 4 random strategies
            tournament_size = min(4, len(strategies))
            tournament = random.sample(strategies, tournament_size)
            
            # Sort tournament by score (best first)
            tournament_sorted = sorted(
                tournament,
                key=lambda s: s.score if s.score is not None else 0.0,
                reverse=True
            )
            
            # Best strategy from tournament
            winner = tournament_sorted[0]
            
            # Crossover or mutation
            if random.random() < self.crossover_rate and len(strategies) >= 2:
                # Crossover: combine winner with another random strategy (not necessarily elite)
                # This increases diversity by allowing non-elite strategies to contribute
                other_parent = random.choice([s for s in strategies if s.id != winner.id])
                if other_parent:
                    child = self._crossover(winner, other_parent)
                else:
                    # Fallback to mutation if no other parent available
                    child = self._mutate_adaptive(winner)
            else:
                # Mutation: mutate the tournament winner
                child = self._mutate_adaptive(winner)
            
            offspring.append(child)
        
        return offspring
    
    def _crossover(
        self,
        parent1: UserStrategy,
        parent2: UserStrategy
    ) -> Dict[str, Any]:
        """
        Crossover two strategies to create a child.
        
        Combines parameters and ruleset from both parents.
        """
        # Crossover parameters
        child_params = {}
        params1 = dict(parent1.parameters)
        params2 = dict(parent2.parameters)
        
        # Combine parameters (take average for numeric, random choice for others)
        all_keys = set(params1.keys()) | set(params2.keys())
        for key in all_keys:
            val1 = params1.get(key)
            val2 = params2.get(key)
            
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Average for numeric
                child_params[key] = (val1 + val2) / 2
            elif val1 is not None:
                child_params[key] = val1
            else:
                child_params[key] = val2
        
        # Crossover ruleset
        child_ruleset = copy.deepcopy(dict(parent1.ruleset))
        ruleset2 = dict(parent2.ruleset)
        
        # Combine timeframes (random choice)
        if "timeframe" in ruleset2:
            child_ruleset["timeframe"] = random.choice([
                parent1.ruleset.get("timeframe", "1d"),
                ruleset2.get("timeframe", "1d")
            ])
        
        # Combine indicators
        indicators1 = parent1.ruleset.get("indicators", {})
        indicators2 = ruleset2.get("indicators", {})
        child_indicators = {}
        
        for key in set(indicators1.keys()) | set(indicators2.keys()):
            val1 = indicators1.get(key)
            val2 = indicators2.get(key)
            
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                child_indicators[key] = (val1 + val2) / 2
            elif val1 is not None:
                child_indicators[key] = val1
            else:
                child_indicators[key] = val2
        
        child_ruleset["indicators"] = child_indicators
        
        return {
            "mutation_type": "crossover",
            "mutation_params": {
                "parent1_id": str(parent1.id),
                "parent2_id": str(parent2.id),
            },
            "mutated_strategy": {
                "name": f"{parent1.name} × {parent2.name}",
                "description": f"Crossover of {parent1.name} and {parent2.name}",
                "parameters": child_params,
                "ruleset": child_ruleset,
                "asset_type": parent1.asset_type,
            }
        }
    
    def _mutate_adaptive(
        self,
        strategy: UserStrategy
    ) -> Dict[str, Any]:
        """
        Adaptive mutation based on strategy performance.
        
        Better strategies get smaller mutations (fine-tuning).
        Poor strategies get larger mutations (exploration).
        """
        # Determine mutation strength based on score
        score = strategy.score if strategy.score is not None else 0.5
        
        if score >= 0.8:
            # Elite strategy: small mutations (fine-tuning)
            mutation_strength = 0.05  # ±5%
        elif score >= 0.6:
            # Good strategy: medium mutations
            mutation_strength = 0.10  # ±10%
        else:
            # Poor strategy: large mutations (exploration)
            mutation_strength = 0.20  # ±20%
        
        # PHASE: Choose mutation type (3 core types: parameter shift, indicator substitution, cross-asset transplant)
        mutation_type = random.choice([
            "parameter_tweak",  # Parameter shift
            "indicator_substitution",  # Indicator substitution (SMA, EMA, RSI, MACD)
            "cross_asset_transplant",  # Cross-asset transplant
            "timeframe_change",
            "indicator_threshold",
            "trailing_stop",
            "volume_threshold"
        ])
        
        if mutation_type == "parameter_tweak":
            return self._mutate_parameters_adaptive(strategy, mutation_strength)
        elif mutation_type == "indicator_substitution":
            return self._mutate_indicator_substitution(strategy)
        elif mutation_type == "cross_asset_transplant":
            return self._mutate_cross_asset_transplant(strategy)
        elif mutation_type == "timeframe_change":
            return self._mutate_timeframe(strategy)
        elif mutation_type == "trailing_stop":
            return self._mutate_trailing_stop_adaptive(strategy, mutation_strength)
        elif mutation_type == "volume_threshold":
            return self._mutate_volume_threshold_adaptive(strategy, mutation_strength)
        else:
            return self._mutate_indicator_threshold_adaptive(strategy, mutation_strength)
    
    def _mutate_parameters_adaptive(
        self,
        strategy: UserStrategy,
        strength: float
    ) -> Dict[str, Any]:
        """Mutate parameters with adaptive strength."""
        new_parameters = copy.deepcopy(dict(strategy.parameters))
        
        for key, value in new_parameters.items():
            if isinstance(value, (int, float)) and value > 0:
                # Apply mutation with adaptive strength
                tweak_factor = random.uniform(1.0 - strength, 1.0 + strength)
                new_value = int(value * tweak_factor) if isinstance(value, int) else value * tweak_factor
                new_parameters[key] = max(1, new_value)
        
        return {
            "mutation_type": "parameter_tweak_adaptive",
            "mutation_params": {
                "strength": strength,
                "changed_params": list(new_parameters.keys())
            },
            "mutated_strategy": {
                "name": f"{strategy.name} (Adaptive Mutated)",
                "description": f"Adaptive mutation of {strategy.name} (strength: {strength:.0%})",
                "parameters": new_parameters,
                "ruleset": dict(strategy.ruleset),
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_timeframe(self, strategy: UserStrategy) -> Dict[str, Any]:
        """Change strategy timeframe."""
        timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        current_timeframe = strategy.ruleset.get("timeframe", "1d")
        
        available = [tf for tf in timeframes if tf != current_timeframe]
        new_timeframe = random.choice(available) if available else current_timeframe
        
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        new_ruleset["timeframe"] = new_timeframe
        
        return {
            "mutation_type": "timeframe_change",
            "mutation_params": {
                "old_timeframe": current_timeframe,
                "new_timeframe": new_timeframe
            },
            "mutated_strategy": {
                "name": f"{strategy.name} ({new_timeframe})",
                "description": f"Timeframe-changed version of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_trailing_stop_adaptive(
        self,
        strategy: UserStrategy,
        strength: float
    ) -> Dict[str, Any]:
        """
        PHASE 2: Mutate trailing stop with adaptive strength.
        Better strategies get fine-tuned trailing stops.
        """
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        
        # Get exit_rules - handle both "exit" and "exit_rules" keys, and handle list vs dict
        exit_rules = new_ruleset.get("exit_rules") or new_ruleset.get("exit")
        
        # Ensure exit_rules is a dict (not a list)
        if isinstance(exit_rules, list):
            # Convert list to dict - find trailing_stop in list or create new
            exit_rules_dict = {}
            for item in exit_rules:
                if isinstance(item, dict):
                    # If item itself is a trailing_stop dict, use it directly
                    if "trailing_stop" in item:
                        exit_rules_dict["trailing_stop"] = item["trailing_stop"]
                    # If item has keys like stop_loss, take_profit, etc., merge them
                    elif any(k in item for k in ["stop_loss", "take_profit", "trailing_stop", "distance_pct", "atr_multiplier"]):
                        exit_rules_dict.update(item)
                    # Otherwise, treat the whole item as trailing_stop if it has relevant keys
                    elif any(k in item for k in ["distance_pct", "atr_multiplier"]):
                        exit_rules_dict["trailing_stop"] = item
            exit_rules = exit_rules_dict if exit_rules_dict else {}
        elif not isinstance(exit_rules, dict):
            exit_rules = {}
        
        # Ensure trailing_stop exists
        if "trailing_stop" not in exit_rules:
            exit_rules["trailing_stop"] = {}
        
        # Adaptive mutation based on strength
        if "distance_pct" in exit_rules["trailing_stop"]:
            current = exit_rules["trailing_stop"]["distance_pct"]
            exit_rules["trailing_stop"]["distance_pct"] = current * random.uniform(1.0 - strength, 1.0 + strength)
        else:
            exit_rules["trailing_stop"]["distance_pct"] = random.uniform(0.01, 0.05)
        
        if "atr_multiplier" in exit_rules["trailing_stop"]:
            current = exit_rules["trailing_stop"]["atr_multiplier"]
            exit_rules["trailing_stop"]["atr_multiplier"] = current * random.uniform(1.0 - strength, 1.0 + strength)
        else:
            exit_rules["trailing_stop"]["atr_multiplier"] = random.uniform(1.0, 3.0)
        
        # Store back in ruleset (use exit_rules key if it existed, otherwise exit)
        if "exit_rules" in new_ruleset:
            new_ruleset["exit_rules"] = exit_rules
        else:
            new_ruleset["exit"] = exit_rules
        
        return {
            "mutation_type": "trailing_stop_adaptive",
            "mutation_params": {
                "strength": strength,
                "trailing_stop_distance": exit_rules["trailing_stop"].get("distance_pct"),
                "atr_multiplier": exit_rules["trailing_stop"].get("atr_multiplier")
            },
            "mutated_strategy": {
                "name": f"{strategy.name} (Trailing Stop)",
                "description": f"Adaptive trailing-stop mutation of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_volume_threshold_adaptive(
        self,
        strategy: UserStrategy,
        strength: float
    ) -> Dict[str, Any]:
        """
        PHASE 2: Mutate volume threshold with MCN guidance and adaptive strength.
        """
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        
        # Get MCN guidance
        try:
            from ..brain.mcn_adapter import get_mcn_adapter
            mcn_adapter = get_mcn_adapter()
            if mcn_adapter and mcn_adapter.is_available:
                # Query MCN for successful volume patterns
                mcn_guidance = 1.0  # Simplified - could query actual patterns
            else:
                mcn_guidance = 1.0
        except Exception:
            mcn_guidance = 1.0
        
        conditions = new_ruleset.get("conditions", [])
        if not isinstance(conditions, list):
            conditions = []
        
        volume_condition_exists = False
        for condition in conditions:
            if isinstance(condition, dict) and condition.get("indicator") == "volume":
                volume_condition_exists = True
                if "threshold" in condition:
                    current = condition["threshold"]
                    adjustment = random.uniform(1.0 - strength, 1.0 + strength) * mcn_guidance
                    condition["threshold"] = max(0.1, current * adjustment)
                elif "min_volume_multiplier" in condition:
                    current = condition["min_volume_multiplier"]
                    adjustment = random.uniform(1.0 - strength, 1.0 + strength) * mcn_guidance
                    condition["min_volume_multiplier"] = max(0.5, current * adjustment)
                break
        
        if not volume_condition_exists:
            conditions.append({
                "indicator": "volume",
                "operator": ">",
                "min_volume_multiplier": random.uniform(1.0, 3.0) * mcn_guidance,
                "description": "MCN-guided volume confirmation filter"
            })
        
        new_ruleset["conditions"] = conditions
        
        return {
            "mutation_type": "volume_threshold_adaptive",
            "mutation_params": {
                "strength": strength,
                "mcn_guided": mcn_guidance != 1.0,
                "volume_threshold_adjusted": True
            },
            "mutated_strategy": {
                "name": f"{strategy.name} (Volume Filter)",
                "description": f"Adaptive MCN-guided volume-threshold mutation of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_indicator_threshold_adaptive(
        self,
        strategy: UserStrategy,
        strength: float
    ) -> Dict[str, Any]:
        """Mutate indicator thresholds with adaptive strength."""
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        conditions = new_ruleset.get("conditions", [])
        
        if isinstance(conditions, list):
            for condition in conditions:
                if isinstance(condition, dict):
                    for key in ["threshold", "value", "level"]:
                        if key in condition and isinstance(condition[key], (int, float)):
                            tweak = random.uniform(1.0 - strength, 1.0 + strength)
                            condition[key] = condition[key] * tweak
        
        return {
            "mutation_type": "indicator_threshold_adaptive",
            "mutation_params": {
                "strength": strength,
                "changed_conditions": len(conditions)
            },
            "mutated_strategy": {
                "name": f"{strategy.name} (Threshold Adjusted)",
                "description": f"Adaptive threshold mutation of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }
    
    def preserve_diversity(
        self,
        strategies: List[UserStrategy],
        similarity_threshold: float = 0.9
    ) -> List[UserStrategy]:
        """
        Preserve diversity by removing very similar strategies.
        
        Args:
            strategies: List of strategies
            similarity_threshold: Strategies with similarity > threshold are considered duplicates
        
        Returns:
            Filtered list with diversity preserved
        """
        if len(strategies) <= 1:
            return strategies
        
        # Simple diversity preservation: keep strategies with different parameters
        diverse = []
        seen_params = []
        
        for strategy in strategies:
            params_hash = hash(tuple(sorted(strategy.parameters.items())))
            
            # Check if similar parameters already seen
            is_similar = False
            for seen_hash in seen_params:
                # Simple similarity check (could be improved)
                if abs(params_hash - seen_hash) < 100:  # Arbitrary threshold
                    is_similar = True
                    break
            
            if not is_similar:
                diverse.append(strategy)
                seen_params.append(params_hash)
        
        return diverse
    
    def _mutate_indicator_substitution(self, strategy: UserStrategy) -> Dict[str, Any]:
        """
        PHASE: Indicator substitution mutation.
        
        Substitutes one indicator with another (SMA → EMA, RSI → MACD, etc.)
        """
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        entry_conditions = new_ruleset.get("entry_conditions", [])
        
        # Ensure entry_conditions is a list (not a dict)
        if isinstance(entry_conditions, dict):
            entry_conditions = [entry_conditions]
        elif not isinstance(entry_conditions, list):
            entry_conditions = [entry_conditions] if entry_conditions else []
        
        # Indicator substitution map
        indicator_map = {
            "SMA": "EMA",
            "EMA": "SMA",
            "RSI": "MACD",
            "MACD": "RSI",
            "BB": "ATR",
            "ATR": "BB"
        }
        
        # Find and substitute indicators in entry conditions
        modified = False
        for condition in entry_conditions:
            if isinstance(condition, dict):
                indicator = condition.get("indicator")
                if indicator and indicator in indicator_map:
                    condition["indicator"] = indicator_map[indicator]
                    modified = True
                    # Adjust period if needed (EMA typically uses shorter periods)
                    if indicator == "SMA" and condition.get("period"):
                        condition["period"] = max(5, int(condition["period"] * 0.8))
                    elif indicator == "EMA" and condition.get("period"):
                        condition["period"] = max(5, int(condition["period"] * 1.2))
        
        if not modified:
            # If no substitution happened, add a new indicator condition
            entry_conditions.append({
                "indicator": random.choice(["SMA", "EMA", "RSI"]),
                "field": "close",
                "period": random.choice([14, 20, 50]),
                "operator": random.choice([">", "<"]),
                "threshold": random.uniform(0.5, 0.9)
            })
        
        new_ruleset["entry_conditions"] = entry_conditions
        
        return {
            "mutation_type": "indicator_substitution",
            "mutation_params": {
                "substituted_indicators": [ind for ind in indicator_map.keys() if ind in str(entry_conditions)]
            },
            "mutated_strategy": {
                "name": f"{strategy.name} (Indicator Substituted)",
                "description": f"Indicator substitution mutation of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_cross_asset_transplant(self, strategy: UserStrategy) -> Dict[str, Any]:
        """
        PHASE: Cross-asset transplant mutation.
        
        Transplants strategy to a different asset (e.g., AAPL → TSLA, BTC → ETH)
        """
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        
        # Get current symbol
        current_symbol = new_ruleset.get("symbol") or new_ruleset.get("ticker")
        
        # Choose a different symbol from DEFAULT_SYMBOLS
        available_symbols = [s for s in DEFAULT_SYMBOLS if s != current_symbol]
        if not available_symbols:
            available_symbols = DEFAULT_SYMBOLS
        
        new_symbol = random.choice(available_symbols)
        
        new_ruleset["symbol"] = new_symbol
        new_ruleset["ticker"] = new_symbol
        
        return {
            "mutation_type": "cross_asset_transplant",
            "mutation_params": {
                "old_symbol": current_symbol,
                "new_symbol": new_symbol
            },
            "mutated_strategy": {
                "name": f"{strategy.name} ({new_symbol})",
                "description": f"Cross-asset transplant of {strategy.name} to {new_symbol}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }

