# backend/strategy_engine/ruleset_parser.py
"""
Strategy DSL (Domain-Specific Language) Parser.
Parses JSON rulesets into executable strategy logic.

Example ruleset:
{
  "type": "trend_follow",
  "conditions": [
    {"indicator": "EMA", "length": 50, "relation": ">", "other": "EMA_200"},
    {"indicator": "RSI", "length": 14, "relation": "<", "value": 70},
    {"logic": "AND"}
  ],
  "entry": "close",
  "exit": {"take_profit": 0.03, "stop_loss": 0.01}
}
"""
from typing import Dict, Any, List, Optional
from .indicators import IndicatorCalculator
from ..market_data.types import CandleData


class RulesetParser:
    """Parser for strategy rulesets."""
    
    def __init__(self):
        self.indicator_calc = IndicatorCalculator()
    
    def parse_ruleset(self, ruleset: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a ruleset into executable logic.
        
        Returns:
            Dictionary with parsed conditions and entry/exit rules
        """
        parsed = {
            "type": ruleset.get("type", "custom"),
            "conditions": self._parse_conditions(ruleset.get("conditions", [])),
            "entry": ruleset.get("entry", "close"),
            "exit": ruleset.get("exit", {}),
            "timeframe": ruleset.get("timeframe", "1d"),
        }
        return parsed
    
    def _parse_conditions(self, conditions: List[Any]) -> List[Dict[str, Any]]:
        """Parse condition list into executable conditions."""
        parsed = []
        current_logic = "AND"  # Default logic
        
        for item in conditions:
            if isinstance(item, dict):
                if "logic" in item:
                    # Logic operator (AND/OR)
                    current_logic = item.get("logic", "AND")
                elif "indicator" in item:
                    # Indicator condition
                    parsed.append({
                        "type": "indicator",
                        "indicator": item.get("indicator"),
                        "length": item.get("length"),
                        "relation": item.get("relation"),  # >, <, >=, <=, ==
                        "value": item.get("value"),
                        "other": item.get("other"),  # Compare to another indicator
                        "logic": current_logic,
                    })
                elif "condition" in item:
                    # Nested condition group
                    parsed.append({
                        "type": "group",
                        "conditions": self._parse_conditions(item.get("condition", [])),
                        "logic": current_logic,
                    })
        
        return parsed
    
    def evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        indicators: Dict[str, Any],
        current_index: int
    ) -> bool:
        """
        Evaluate parsed conditions against current market state.
        
        Args:
            conditions: Parsed conditions
            indicators: Pre-calculated indicators
            current_index: Current candle index
        
        Returns:
            True if all conditions are met (with AND/OR logic)
        """
        if not conditions:
            return True
        
        results = []
        current_logic = "AND"
        
        for condition in conditions:
            if condition.get("type") == "indicator":
                result = self._evaluate_indicator_condition(
                    condition, indicators, current_index
                )
                results.append(result)
                current_logic = condition.get("logic", "AND")
            elif condition.get("type") == "group":
                # Recursive evaluation of nested group
                result = self.evaluate_conditions(
                    condition.get("conditions", []),
                    indicators,
                    current_index
                )
                results.append(result)
                current_logic = condition.get("logic", "AND")
        
        # Apply logic
        if current_logic == "OR":
            return any(results)
        else:  # AND
            return all(results)
    
    def _evaluate_indicator_condition(
        self,
        condition: Dict[str, Any],
        indicators: Dict[str, Any],
        current_index: int
    ) -> bool:
        """Evaluate a single indicator condition."""
        indicator_name = condition.get("indicator", "").upper()
        length = condition.get("length")
        relation = condition.get("relation", ">")
        value = condition.get("value")
        other = condition.get("other")
        
        # Get indicator value
        indicator_key = self._get_indicator_key(indicator_name, length)
        indicator_values = indicators.get(indicator_key, [])
        
        if not indicator_values or current_index >= len(indicator_values):
            return False
        
        current_value = indicator_values[current_index]
        
        # Compare
        if other:
            # Compare to another indicator
            other_key = self._get_indicator_key(other, None)
            other_values = indicators.get(other_key, [])
            if not other_values or current_index >= len(other_values):
                return False
            other_value = other_values[current_index]
            return self._compare(current_value, relation, other_value)
        elif value is not None:
            # Compare to fixed value
            return self._compare(current_value, relation, value)
        else:
            return False
    
    def _get_indicator_key(self, indicator_name: str, length: Optional[int]) -> str:
        """Get the key for an indicator in the indicators dict."""
        if indicator_name == "SMA":
            return f"sma_{length}" if length else "sma_20"
        elif indicator_name == "EMA":
            return f"ema_{length}" if length else "ema_12"
        elif indicator_name == "RSI":
            return "rsi"
        elif indicator_name == "MACD":
            return "macd"
        elif indicator_name == "BOLLINGER":
            return "bollinger"
        elif indicator_name == "ATR":
            return "atr"
        elif indicator_name == "VWAP":
            return "vwap"
        else:
            return indicator_name.lower()
    
    def _compare(self, a: float, relation: str, b: float) -> bool:
        """Compare two values with a relation operator."""
        if relation == ">":
            return a > b
        elif relation == ">=":
            return a >= b
        elif relation == "<":
            return a < b
        elif relation == "<=":
            return a <= b
        elif relation == "==":
            return abs(a - b) < 0.0001  # Float comparison
        elif relation == "!=":
            return abs(a - b) >= 0.0001
        else:
            return False
    
    def calculate_exit_prices(
        self,
        entry_price: float,
        side: str,
        exit_rules: Dict[str, Any],
        atr: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate stop loss and take profit from exit rules.
        
        Supports:
        - Percentage-based: {"take_profit": 0.03, "stop_loss": 0.01}
        - ATR-based: {"take_profit_atr": 2.0, "stop_loss_atr": 1.0}
        - Fixed: {"take_profit_fixed": 150.0, "stop_loss_fixed": 145.0}
        """
        stop_loss = None
        take_profit = None
        
        # ATR-based (preferred if ATR available)
        if atr and atr > 0:
            if "take_profit_atr" in exit_rules:
                atr_multiplier = exit_rules["take_profit_atr"]
                if side == "BUY":
                    take_profit = entry_price + (atr * atr_multiplier)
                else:
                    take_profit = entry_price - (atr * atr_multiplier)
            
            if "stop_loss_atr" in exit_rules:
                atr_multiplier = exit_rules["stop_loss_atr"]
                if side == "BUY":
                    stop_loss = entry_price - (atr * atr_multiplier)
                else:
                    stop_loss = entry_price + (atr * atr_multiplier)
        
        # Percentage-based (fallback or if specified)
        if "take_profit" in exit_rules and take_profit is None:
            pct = exit_rules["take_profit"]
            if side == "BUY":
                take_profit = entry_price * (1 + pct)
            else:
                take_profit = entry_price * (1 - pct)
        
        if "stop_loss" in exit_rules and stop_loss is None:
            pct = exit_rules["stop_loss"]
            if side == "BUY":
                stop_loss = entry_price * (1 - pct)
            else:
                stop_loss = entry_price * (1 + pct)
        
        # Fixed (override)
        if "take_profit_fixed" in exit_rules:
            take_profit = exit_rules["take_profit_fixed"]
        
        if "stop_loss_fixed" in exit_rules:
            stop_loss = exit_rules["stop_loss_fixed"]
        
        return {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

