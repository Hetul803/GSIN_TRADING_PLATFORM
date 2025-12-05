# backend/strategy_engine/strategy_service.py
"""
Strategy service for business logic and signal generation.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..market_data.market_data_provider import get_provider, call_with_fallback
from ..market_data.types import PriceData, CandleData
from .scoring import score_strategy
from .indicators import IndicatorCalculator
from .ruleset_parser import RulesetParser


class StrategyService:
    """Service for strategy operations and signal generation."""
    
    def __init__(self):
        self.market_provider = get_provider()
        self.indicator_calc = IndicatorCalculator()
        self.ruleset_parser = RulesetParser()
    
    def generate_signal(
        self,
        strategy_id: str,
        strategy_ruleset: Dict[str, Any],
        strategy_score: Optional[float],
        symbol: str
    ) -> Dict[str, Any]:
        """
        Generate a trading signal from a strategy.
        
        Args:
            strategy_id: Strategy ID
            strategy_ruleset: Strategy ruleset
            strategy_score: Strategy score (0-1)
            symbol: Symbol to generate signal for
        
        Returns:
            Signal dictionary with side, entry, exit, stop_loss, take_profit, confidence
        """
        # Get current price through request queue
        price_data = call_with_fallback("get_price", symbol)
        if not price_data:
            raise ValueError(f"Could not fetch price data for {symbol}")
        
        current_price = price_data.price if hasattr(price_data, 'price') else float(price_data)
        
        # Get recent candles for indicator calculation through request queue
        timeframe = strategy_ruleset.get("timeframe", "1d")
        candles = call_with_fallback("get_candles", symbol, timeframe, limit=200)  # More candles for indicators
        if len(candles) < 2:
            raise ValueError(f"Insufficient data for signal generation: only {len(candles)} candles")
        
        # Parse ruleset and evaluate conditions
        parsed = self.ruleset_parser.parse_ruleset(strategy_ruleset)
        conditions = parsed.get("conditions", [])
        exit_rules = parsed.get("exit", {})
        
        # Calculate all indicators
        indicators = self.indicator_calc.calculate_all_indicators(candles)
        
        # Evaluate entry conditions
        current_index = len(candles) - 1
        conditions_met = self.ruleset_parser.evaluate_conditions(conditions, indicators, current_index)
        
        if not conditions_met:
            # No signal
            return {
                "strategy_id": strategy_id,
                "symbol": symbol,
                "side": "HOLD",
                "entry": current_price,
                "exit": None,
                "stop_loss": None,
                "take_profit": None,
                "confidence": 0.0,
                "reasoning": "Entry conditions not met",
                "timestamp": datetime.now()
            }
        
        # Determine side from ruleset or default to BUY
        side = strategy_ruleset.get("side", "BUY")
        
        # Get entry price
        entry_price = current_price
        if parsed.get("entry") == "open":
            entry_price = candles[-1].open
        elif parsed.get("entry") == "high":
            entry_price = candles[-1].high
        elif parsed.get("entry") == "low":
            entry_price = candles[-1].low
        
        # Calculate exit prices using ATR if available
        atr_values = indicators.get("atr", [])
        atr = atr_values[-1] if atr_values else None
        exit_prices = self.ruleset_parser.calculate_exit_prices(entry_price, side, exit_rules, atr)
        
        stop_loss = exit_prices.get("stop_loss")
        take_profit = exit_prices.get("take_profit")
        
        # Calculate signal strength (how strongly conditions are met)
        signal_strength = self._calculate_signal_strength(conditions, indicators, current_index)
        
        # Calculate confidence based on strategy score and signal strength
        confidence = self._calculate_confidence(strategy_score, signal_strength)
        
        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "side": side,
            "entry": entry_price,
            "exit": None,  # Will be set when trade closes
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "confidence": confidence,
            "reasoning": f"Strategy ruleset evaluation: {len([c for c in conditions if conditions_met])} conditions met",
            "timestamp": datetime.now()
        }
    
    def _calculate_signal_strength(
        self,
        conditions: List[Dict[str, Any]],
        indicators: Dict[str, Any],
        current_index: int
    ) -> float:
        """
        Calculate signal strength (0.0 to 1.0) based on how strongly conditions are met.
        
        Returns:
            Signal strength between 0.0 and 1.0
        """
        if not conditions:
            return 0.5  # Neutral
        
        strengths = []
        for condition in conditions:
            if condition.get("type") == "indicator":
                # Calculate how far the condition is from threshold
                indicator_name = condition.get("indicator", "").upper()
                length = condition.get("length")
                relation = condition.get("relation", ">")
                value = condition.get("value")
                other = condition.get("other")
                
                indicator_key = self.ruleset_parser._get_indicator_key(indicator_name, length)
                indicator_values = indicators.get(indicator_key, [])
                
                if indicator_values and current_index < len(indicator_values):
                    current_value = indicator_values[current_index]
                    
                    if other:
                        other_key = self.ruleset_parser._get_indicator_key(other, None)
                        other_values = indicators.get(other_key, [])
                        if other_values and current_index < len(other_values):
                            other_value = other_values[current_index]
                            # Calculate strength based on distance
                            if relation == ">":
                                diff = current_value - other_value
                                strength = min(1.0, max(0.0, 0.5 + (diff / (other_value * 0.1))))  # Normalize
                            elif relation == "<":
                                diff = other_value - current_value
                                strength = min(1.0, max(0.0, 0.5 + (diff / (other_value * 0.1))))
                            else:
                                strength = 0.5
                            strengths.append(strength)
                    elif value is not None:
                        # Calculate strength based on distance from threshold
                        if relation == ">":
                            diff = current_value - value
                            strength = min(1.0, max(0.0, 0.5 + (diff / (value * 0.1))))
                        elif relation == "<":
                            diff = value - current_value
                            strength = min(1.0, max(0.0, 0.5 + (diff / (value * 0.1))))
                        else:
                            strength = 0.5
                        strengths.append(strength)
        
        if strengths:
            # Average strength (could weight by condition importance)
            return sum(strengths) / len(strengths)
        else:
            return 0.5
    
    def _calculate_confidence(
        self,
        strategy_score: Optional[float],
        signal_strength: float
    ) -> float:
        """
        Calculate signal confidence.
        
        Combines strategy score (if available) with signal strength.
        """
        if strategy_score is not None:
            # Weighted: 70% strategy score, 30% signal strength
            confidence = (strategy_score * 0.7) + (signal_strength * 0.3)
        else:
            # If no strategy score, use signal strength only
            confidence = signal_strength * 0.8  # Slightly lower if no score
        
        return max(0.0, min(1.0, confidence))

