# backend/strategy_engine/mutation_engine.py
"""
Strategy mutation engine.
Creates mutated versions of strategies by tweaking parameters, timeframes, and indicators.
"""
from typing import List, Dict, Any
import random
import copy
import uuid

from ..db.models import UserStrategy


class MutationEngine:
    """Engine for mutating strategies."""
    
    def mutate_strategy(
        self,
        strategy: UserStrategy,
        num_mutations: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Create mutated versions of a strategy.
        
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
        
        for i in range(min(num_mutations, 3)):
            mutation_type = random.choice([
                "parameter_tweak",
                "timeframe_change",
                "indicator_threshold",
                "trailing_stop",  # PHASE 2: Added
                "volume_threshold"  # PHASE 2: Added
            ])
            
            if mutation_type == "parameter_tweak":
                mutation = self._mutate_parameters(strategy)
            elif mutation_type == "timeframe_change":
                mutation = self._mutate_timeframe(strategy)
            elif mutation_type == "indicator_threshold":
                mutation = self._mutate_indicator_threshold(strategy)
            elif mutation_type == "trailing_stop":
                mutation = self._mutate_trailing_stop(strategy)
            elif mutation_type == "volume_threshold":
                mutation = self._mutate_volume_threshold(strategy)
            else:
                continue
            
            mutations.append(mutation)
        
        return mutations
    
    def _mutate_parameters(self, strategy: UserStrategy) -> Dict[str, Any]:
        """Mutate strategy parameters (e.g., RSI period, EMA periods)."""
        new_parameters = copy.deepcopy(dict(strategy.parameters))
        
        # Randomly tweak numeric parameters by ±20%
        for key, value in new_parameters.items():
            if isinstance(value, (int, float)) and value > 0:
                # Apply random tweak between -20% and +20%
                tweak_factor = random.uniform(0.8, 1.2)
                new_value = int(value * tweak_factor) if isinstance(value, int) else value * tweak_factor
                new_parameters[key] = max(1, new_value)  # Ensure positive
        
        return {
            "mutation_type": "parameter_tweak",
            "mutation_params": {"changed_params": list(new_parameters.keys())},
            "mutated_strategy": {
                "name": f"{strategy.name} (Mutated)",
                "description": f"Parameter-tweaked version of {strategy.name}",
                "parameters": new_parameters,
                "ruleset": dict(strategy.ruleset),
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_timeframe(self, strategy: UserStrategy) -> Dict[str, Any]:
        """Change strategy timeframe."""
        timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        current_timeframe = strategy.ruleset.get("timeframe", "1d")
        
        # Pick a different timeframe
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
    
    def _mutate_indicator_threshold(self, strategy: UserStrategy) -> Dict[str, Any]:
        """Mutate indicator thresholds in ruleset."""
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        
        # Look for threshold values in conditions
        conditions = new_ruleset.get("conditions", [])
        if isinstance(conditions, list):
            for condition in conditions:
                if isinstance(condition, dict):
                    # Look for threshold-like fields
                    for key in ["threshold", "value", "level"]:
                        if key in condition and isinstance(condition[key], (int, float)):
                            # Tweak threshold by ±10%
                            tweak = random.uniform(0.9, 1.1)
                            condition[key] = condition[key] * tweak
        
        return {
            "mutation_type": "indicator_threshold",
            "mutation_params": {"changed_conditions": len(conditions)},
            "mutated_strategy": {
                "name": f"{strategy.name} (Threshold Adjusted)",
                "description": f"Indicator-threshold-adjusted version of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_trailing_stop(self, strategy: UserStrategy) -> Dict[str, Any]:
        """
        PHASE 2: Mutate trailing stop distance in exit rules.
        """
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        exit_rules = new_ruleset.get("exit", {})
        
        # Add or modify trailing stop
        if "trailing_stop" not in exit_rules:
            exit_rules["trailing_stop"] = {}
        
        # Mutate trailing stop distance (percentage or ATR multiplier)
        if "distance_pct" in exit_rules["trailing_stop"]:
            # Adjust percentage by ±20%
            current = exit_rules["trailing_stop"]["distance_pct"]
            exit_rules["trailing_stop"]["distance_pct"] = current * random.uniform(0.8, 1.2)
        else:
            # Add new trailing stop (1-5% default)
            exit_rules["trailing_stop"]["distance_pct"] = random.uniform(0.01, 0.05)
        
        # Add ATR multiplier if not present
        if "atr_multiplier" not in exit_rules["trailing_stop"]:
            exit_rules["trailing_stop"]["atr_multiplier"] = random.uniform(1.0, 3.0)
        else:
            # Adjust ATR multiplier by ±15%
            current = exit_rules["trailing_stop"]["atr_multiplier"]
            exit_rules["trailing_stop"]["atr_multiplier"] = current * random.uniform(0.85, 1.15)
        
        new_ruleset["exit"] = exit_rules
        
        return {
            "mutation_type": "trailing_stop",
            "mutation_params": {
                "trailing_stop_distance": exit_rules["trailing_stop"].get("distance_pct"),
                "atr_multiplier": exit_rules["trailing_stop"].get("atr_multiplier")
            },
            "mutated_strategy": {
                "name": f"{strategy.name} (Trailing Stop)",
                "description": f"Trailing-stop-adjusted version of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }
    
    def _mutate_volume_threshold(self, strategy: UserStrategy) -> Dict[str, Any]:
        """
        PHASE 2: Mutate volume threshold (MCN-guided if available).
        """
        new_ruleset = copy.deepcopy(dict(strategy.ruleset))
        
        # Get MCN guidance for volume thresholds (if available)
        try:
            from ..brain.mcn_adapter import get_mcn_adapter
            mcn_adapter = get_mcn_adapter()
            if mcn_adapter and mcn_adapter.is_available:
                # Query MCN for successful volume threshold patterns
                # This is a simplified version - could be enhanced
                mcn_guidance = 1.0  # Default multiplier
            else:
                mcn_guidance = 1.0
        except Exception:
            mcn_guidance = 1.0
        
        # Add or modify volume filter in entry conditions
        conditions = new_ruleset.get("conditions", [])
        if not isinstance(conditions, list):
            conditions = []
        
        # Check if volume condition exists
        volume_condition_exists = False
        for condition in conditions:
            if isinstance(condition, dict) and condition.get("indicator") == "volume":
                volume_condition_exists = True
                # Mutate volume threshold by ±20% (MCN-guided adjustment)
                if "threshold" in condition:
                    current = condition["threshold"]
                    adjustment = random.uniform(0.8, 1.2) * mcn_guidance
                    condition["threshold"] = max(0.1, current * adjustment)
                elif "min_volume_multiplier" in condition:
                    current = condition["min_volume_multiplier"]
                    adjustment = random.uniform(0.8, 1.2) * mcn_guidance
                    condition["min_volume_multiplier"] = max(0.5, current * adjustment)
                break
        
        # If no volume condition, add one
        if not volume_condition_exists:
            conditions.append({
                "indicator": "volume",
                "operator": ">",
                "min_volume_multiplier": random.uniform(1.0, 3.0) * mcn_guidance,  # 1x to 3x average volume
                "description": "Volume confirmation filter"
            })
        
        new_ruleset["conditions"] = conditions
        
        return {
            "mutation_type": "volume_threshold",
            "mutation_params": {
                "volume_threshold_adjusted": True,
                "mcn_guided": mcn_guidance != 1.0
            },
            "mutated_strategy": {
                "name": f"{strategy.name} (Volume Filter)",
                "description": f"Volume-threshold-adjusted version of {strategy.name}",
                "parameters": dict(strategy.parameters),
                "ruleset": new_ruleset,
                "asset_type": strategy.asset_type
            }
        }

