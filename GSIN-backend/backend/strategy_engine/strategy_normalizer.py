# backend/strategy_engine/strategy_normalizer.py
"""
Strategy Normalizer - Converts various strategy formats into a standardized structure.

This module:
1. Normalizes seed strategies from different formats (entry/exit, entry_rules/exit_rules, conditions)
2. Auto-infers rules for user-uploaded strategies when needed
3. Ensures all strategies have entry_conditions and exit_conditions/exit_rules
"""
from typing import Dict, Any, List, Optional


def normalize_strategy_ruleset(ruleset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a strategy ruleset to the standard format.
    
    Handles multiple input formats:
    - entry/exit (seed format)
    - entry_rules/exit_rules (proven strategies format)
    - conditions (legacy format)
    - entry_conditions/exit_conditions (standard format)
    
    Returns:
        Normalized ruleset with entry_conditions and exit_conditions/exit_rules
    """
    if not ruleset:
        return {}
    
    normalized = ruleset.copy()
    
    # Normalize entry conditions
    entry_conditions = (
        normalized.get("entry_conditions") or
        normalized.get("entry_rules") or
        normalized.get("entry") or
        normalized.get("conditions") or
        []
    )
    
    # Convert to list if it's a dict or single item
    if isinstance(entry_conditions, dict):
        entry_conditions = [entry_conditions]
    elif not isinstance(entry_conditions, list):
        entry_conditions = [entry_conditions] if entry_conditions else []
    
    # Normalize exit conditions/rules
    exit_rules = normalized.get("exit_rules") or {}
    exit_conditions_raw = normalized.get("exit_conditions") or []
    exit_list = normalized.get("exit")
    
    # If exit is a list, convert to exit_conditions
    if isinstance(exit_list, list) and len(exit_list) > 0:
        if not isinstance(exit_rules, dict):
            exit_rules = {}
        exit_rules["exit_conditions"] = exit_list
    elif isinstance(exit_list, dict):
        exit_rules = exit_list
    elif isinstance(exit_conditions_raw, list) and len(exit_conditions_raw) > 0:
        if not isinstance(exit_rules, dict):
            exit_rules = {}
        exit_rules["exit_conditions"] = exit_conditions_raw
    
    # Ensure exit_rules is a dict
    if not isinstance(exit_rules, dict):
        exit_rules = {}
    
    # If exit_rules is empty or missing required fields, try to populate from other sources
    has_exit_rule = (
        exit_rules.get("exit_conditions") or 
        exit_rules.get("stop_loss") is not None or 
        exit_rules.get("take_profit") is not None or
        exit_rules.get("stop_loss_percent") is not None or
        exit_rules.get("take_profit_percent") is not None
    )
    
    if not has_exit_rule:
        # Try to infer from parameters
        params = normalized.get("parameters", {})
        if "stop_loss" in params:
            exit_rules["stop_loss"] = params["stop_loss"]
        if "take_profit" in params:
            exit_rules["take_profit"] = params["take_profit"]
        if "atr_stop_multiplier" in params:
            exit_rules["stop_loss"] = params.get("atr_stop_multiplier", 0.02)
        if "stop_loss_percent" in params:
            exit_rules["stop_loss"] = params["stop_loss_percent"]
        if "take_profit_percent" in params:
            exit_rules["take_profit"] = params["take_profit_percent"]
        
        # Check again if we now have exit rules
        has_exit_rule = (
            exit_rules.get("exit_conditions") or 
            exit_rules.get("stop_loss") is not None or 
            exit_rules.get("take_profit") is not None
        )
        
        # If still empty, add default exit conditions from entry (opposite)
        if not has_exit_rule:
            if entry_conditions:
                try:
                    exit_rules["exit_conditions"] = _infer_exit_from_entry(entry_conditions)
                except Exception:
                    # If inference fails, use defaults
                    exit_rules = {
                        "stop_loss": 0.02,
                        "take_profit": 0.05
                    }
            else:
                # Last resort: default exit rules (ALWAYS ensure these exist)
                exit_rules = {
                    "stop_loss": 0.02,
                    "take_profit": 0.05
                }
    
    # FINAL SAFETY CHECK: Ensure exit_rules ALWAYS has at least stop_loss or take_profit
    if not exit_rules.get("exit_conditions") and exit_rules.get("stop_loss") is None and exit_rules.get("take_profit") is None:
        # Force default exit rules if somehow still missing
        if "stop_loss" not in exit_rules:
            exit_rules["stop_loss"] = 0.02
        if "take_profit" not in exit_rules:
            exit_rules["take_profit"] = 0.05
    
    # Store normalized format
    normalized["entry_conditions"] = entry_conditions
    normalized["exit_rules"] = exit_rules
    
    # Keep original fields for backward compatibility but prioritize normalized ones
    if "entry" in normalized and "entry_conditions" in normalized:
        # Keep entry for backward compat but entry_conditions takes precedence
        pass
    if "conditions" in normalized and "entry_conditions" in normalized:
        # Keep conditions for backward compat but entry_conditions takes precedence
        pass
    
    return normalized


def _infer_exit_from_entry(entry_conditions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Infer exit conditions from entry conditions (opposite logic).
    
    For example:
    - entry: SMA(50) crosses above SMA(200) -> exit: SMA(50) crosses below SMA(200)
    - entry: RSI < 30 -> exit: RSI > 70
    """
    exit_conditions = []
    
    for condition in entry_conditions:
        exit_cond = condition.copy()
        
        # Reverse crossover directions
        if condition.get("condition") == "crosses_above":
            exit_cond["condition"] = "crosses_below"
        elif condition.get("condition") == "crosses_below":
            exit_cond["condition"] = "crosses_above"
        # Reverse operators
        elif condition.get("operator") == "<":
            exit_cond["operator"] = ">"
            # Adjust threshold (e.g., RSI < 30 -> RSI > 70)
            if "threshold" in exit_cond:
                exit_cond["threshold"] = 100 - exit_cond["threshold"] if exit_cond["threshold"] < 50 else exit_cond["threshold"]
        elif condition.get("operator") == ">":
            exit_cond["operator"] = "<"
            if "threshold" in exit_cond:
                exit_cond["threshold"] = 100 - exit_cond["threshold"] if exit_cond["threshold"] > 50 else exit_cond["threshold"]
        
        exit_conditions.append(exit_cond)
    
    return exit_conditions


def auto_infer_rules_for_user_strategy(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    simple_ruleset: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Auto-infer structured rules for user-uploaded strategies.
    
    Handles simple formats like:
    - Basic fields: symbol, timeframe, entry_price, take_profit, stop_loss
    - Simple descriptions: "SMA crossover", "RSI mean reversion", etc.
    
    Returns:
        Normalized ruleset with entry_conditions and exit_rules
    """
    ruleset = simple_ruleset or {}
    normalized = {}
    
    # Extract basic fields
    symbol = ruleset.get("symbol") or ruleset.get("ticker") or parameters.get("symbol")
    timeframe = ruleset.get("timeframe") or parameters.get("timeframe", "1d")
    entry_price = ruleset.get("entry_price") or parameters.get("entry_price")
    take_profit = ruleset.get("take_profit") or parameters.get("take_profit") or parameters.get("profit_target")
    stop_loss = ruleset.get("stop_loss") or parameters.get("stop_loss")
    
    # Infer from description if no explicit rules
    desc_lower = (description or "").lower()
    name_lower = (name or "").lower()
    
    entry_conditions = []
    exit_rules = {}
    
    # Pattern matching for common strategy types
    if "sma" in desc_lower or "moving average" in desc_lower or "crossover" in desc_lower:
        # SMA crossover strategy
        fast_period = parameters.get("sma_fast") or parameters.get("fast_sma") or 50
        slow_period = parameters.get("sma_slow") or parameters.get("slow_sma") or 200
        
        entry_conditions.append({
            "indicator": "SMA",
            "field": "close",
            "period": fast_period,
            "condition": "crosses_above",
            "compare_to": {"indicator": "SMA", "field": "close", "period": slow_period}
        })
        
        exit_rules["exit_conditions"] = [{
            "indicator": "SMA",
            "field": "close",
            "period": fast_period,
            "condition": "crosses_below",
            "compare_to": {"indicator": "SMA", "field": "close", "period": slow_period}
        }]
    
    elif "rsi" in desc_lower or "mean reversion" in desc_lower:
        # RSI mean reversion
        rsi_period = parameters.get("rsi_period") or 14
        oversold = parameters.get("oversold") or 30
        overbought = parameters.get("overbought") or 70
        
        entry_conditions.append({
            "indicator": "RSI",
            "period": rsi_period,
            "operator": "<",
            "threshold": oversold
        })
        
        exit_rules["exit_conditions"] = [{
            "indicator": "RSI",
            "period": rsi_period,
            "operator": ">",
            "threshold": overbought
        }]
    
    elif "momentum" in desc_lower or "breakout" in desc_lower:
        # Momentum/breakout strategy
        entry_conditions.append({
            "indicator": "price",
            "condition": "above",
            "value": "sma_20"
        })
        
        exit_rules["stop_loss"] = stop_loss or 0.02
        exit_rules["take_profit"] = take_profit or 0.05
    
    elif entry_price or take_profit or stop_loss:
        # Simple price-based strategy
        if entry_price:
            entry_conditions.append({
                "indicator": "price",
                "operator": "<=",
                "value": entry_price
            })
        
        if stop_loss:
            exit_rules["stop_loss"] = stop_loss
        if take_profit:
            exit_rules["take_profit"] = take_profit
    
    # PHASE: If no conditions inferred, create default SMA crossover entry
    if not entry_conditions:
        entry_conditions = [{
            "indicator": "SMA",
            "field": "close",
            "period": 20,
            "condition": "crosses_above",
            "compare_to": {"indicator": "SMA", "field": "close", "period": 50}
        }]
    
    # PHASE: Ensure exit_rules always has stop_loss and take_profit defaults
    if not exit_rules:
        exit_rules = {}
    if not exit_rules.get("stop_loss") and not exit_rules.get("exit_conditions"):
        exit_rules["stop_loss"] = stop_loss or 0.02  # Default 2% stop loss
    if not exit_rules.get("take_profit") and not exit_rules.get("exit_conditions"):
        exit_rules["take_profit"] = take_profit or 0.03  # Default 3% take profit
    if not exit_rules.get("exit_conditions") and not exit_rules.get("stop_loss") and not exit_rules.get("take_profit"):
        # Last resort: reverse crossover exit
        exit_rules["exit_conditions"] = [{
            "indicator": "SMA",
            "field": "close",
            "period": 20,
            "condition": "crosses_below",
            "compare_to": {"indicator": "SMA", "field": "close", "period": 50}
        }]
    
    # Build normalized ruleset
    normalized = {
        "entry_conditions": entry_conditions,
        "exit_rules": exit_rules,
        "timeframe": timeframe,
    }
    
    if symbol:
        normalized["symbol"] = symbol
        normalized["ticker"] = symbol
    
    # Merge with existing ruleset (user-provided fields take precedence)
    normalized.update(ruleset)
    normalized["entry_conditions"] = entry_conditions  # Ensure normalized entry_conditions
    normalized["exit_rules"] = exit_rules  # Ensure normalized exit_rules
    
    return normalized

