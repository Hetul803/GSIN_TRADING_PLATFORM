# backend/strategy_engine/strategy_explanation.py
"""
PHASE 1: Generate human-readable explanations for strategies.
"""
from typing import Dict, Any, Optional


def generate_human_explanation(
    strategy: Dict[str, Any],
    stats: Optional[Dict[str, Any]] = None
) -> tuple[str, str]:
    """
    Generate human-readable explanation and risk note for a strategy.
    
    Args:
        strategy: Strategy data (name, ruleset, parameters, etc.)
        stats: Optional backtest stats (win_rate, sharpe_ratio, max_drawdown, total_trades)
    
    Returns:
        Tuple of (explanation_human, risk_note)
    """
    ruleset = strategy.get("ruleset", {})
    name = strategy.get("name", "Strategy")
    asset_type = strategy.get("asset_type", "STOCK")
    timeframe = ruleset.get("timeframe", "1d")
    
    # Extract entry/exit conditions
    entry_conditions = ruleset.get("entry_conditions") or ruleset.get("conditions") or ruleset.get("entry_rules") or []
    exit_rules = ruleset.get("exit_rules") or ruleset.get("exit_conditions") or []
    symbol = ruleset.get("symbol") or ruleset.get("ticker") or "the asset"
    direction = ruleset.get("direction", "long")
    
    # Build explanation parts
    explanation_parts = []
    
    # Entry logic
    if entry_conditions:
        entry_desc = _describe_conditions(entry_conditions, symbol, direction)
        if entry_desc:
            explanation_parts.append(entry_desc)
    else:
        # Fallback: use simple fields
        if "entry_price" in ruleset:
            explanation_parts.append(f"Enters {direction} position when price reaches {ruleset['entry_price']}")
        else:
            explanation_parts.append(f"Enters {direction} position based on configured conditions")
    
    # Exit logic
    if exit_rules:
        exit_desc = _describe_exit_rules(exit_rules)
        if exit_desc:
            explanation_parts.append(exit_desc)
    else:
        # Fallback: use simple fields
        if "take_profit" in ruleset:
            explanation_parts.append(f"Exits when profit target of {ruleset['take_profit']}% is reached")
        if "stop_loss" in ruleset:
            explanation_parts.append(f"Exits when stop loss of {ruleset['stop_loss']}% is hit")
    
    # Timeframe context
    timeframe_desc = {
        "1d": "daily",
        "4h": "4-hour",
        "1h": "hourly",
        "15m": "15-minute",
        "5m": "5-minute",
        "1m": "1-minute"
    }.get(timeframe, timeframe)
    explanation_parts.append(f"Operates on {timeframe_desc} timeframe")
    
    # Combine into full explanation
    if explanation_parts:
        explanation = f"{name}: " + ". ".join(explanation_parts) + "."
    else:
        explanation = f"{name}: A trading strategy for {symbol} on {timeframe_desc} timeframe."
    
    # Generate risk note
    risk_note = _generate_risk_note(stats, ruleset, asset_type)
    
    return explanation, risk_note


def _describe_conditions(conditions: list, symbol: str, direction: str) -> str:
    """Describe entry conditions in plain English."""
    if not conditions:
        return ""
    
    desc_parts = []
    for cond in conditions[:3]:  # Limit to first 3 conditions
        if isinstance(cond, dict):
            indicator = cond.get("indicator") or cond.get("type", "")
            operator = cond.get("operator", "")
            value = cond.get("value", "")
            
            if indicator and operator:
                if indicator.lower() in ["sma", "ema", "ma"]:
                    period = cond.get("period", value)
                    desc_parts.append(f"{indicator.upper()}({period})")
                elif indicator.lower() == "rsi":
                    period = cond.get("period", 14)
                    desc_parts.append(f"RSI({period}) {operator} {value}")
                elif indicator.lower() == "price":
                    desc_parts.append(f"price {operator} {value}")
                else:
                    desc_parts.append(f"{indicator} {operator} {value}")
    
    if desc_parts:
        return f"Buys {symbol} when " + " and ".join(desc_parts[:2])
    return ""


def _describe_exit_rules(exit_rules: list) -> str:
    """Describe exit rules in plain English."""
    if not exit_rules:
        return ""
    
    desc_parts = []
    for rule in exit_rules[:2]:  # Limit to first 2 rules
        if isinstance(rule, dict):
            rule_type = rule.get("type") or rule.get("rule_type", "")
            if rule_type == "take_profit" or "take_profit" in rule:
                tp = rule.get("take_profit") or rule.get("value", "")
                desc_parts.append(f"profit target of {tp}%")
            elif rule_type == "stop_loss" or "stop_loss" in rule:
                sl = rule.get("stop_loss") or rule.get("value", "")
                desc_parts.append(f"stop loss of {sl}%")
            elif rule_type == "trailing_stop":
                ts = rule.get("trailing_stop") or rule.get("value", "")
                desc_parts.append(f"trailing stop of {ts}%")
    
    if desc_parts:
        return "Exits when " + " or ".join(desc_parts)
    return ""


def _generate_risk_note(
    stats: Optional[Dict[str, Any]],
    ruleset: Dict[str, Any],
    asset_type: str
) -> str:
    """Generate risk warning note based on stats and strategy characteristics."""
    risk_parts = []
    
    if stats:
        win_rate = stats.get("win_rate", 0)
        sharpe = stats.get("sharpe_ratio", 0)
        max_dd = stats.get("max_drawdown", 0)
        trades = stats.get("total_trades", 0)
        
        # Sample size warning
        if trades < 50:
            risk_parts.append(f"Small sample size ({trades} trades) - results may not be reliable")
        elif trades < 100:
            risk_parts.append(f"Moderate sample size ({trades} trades) - use smaller position sizes until more data is available")
        
        # Win rate warning
        if win_rate < 0.5:
            risk_parts.append("Low win rate - high risk of losses")
        elif win_rate > 0.7:
            risk_parts.append("High win rate but verify with more trades")
        
        # Drawdown warning
        if max_dd > 0.2:
            risk_parts.append(f"High maximum drawdown ({max_dd:.1%}) - use strict risk management")
        elif max_dd > 0.15:
            risk_parts.append(f"Moderate drawdown risk ({max_dd:.1%})")
        
        # Sharpe warning
        if sharpe < 1.0:
            risk_parts.append("Low Sharpe ratio - risk-adjusted returns may be poor")
    
    # Asset type warning
    if asset_type == "CRYPTO":
        risk_parts.append("Cryptocurrency trading involves high volatility and risk")
    elif asset_type == "FOREX":
        risk_parts.append("Forex trading involves leverage and currency risk")
    
    # Timeframe warning
    timeframe = ruleset.get("timeframe", "1d")
    if timeframe in ["1m", "5m"]:
        risk_parts.append("Short timeframe strategies may have higher transaction costs and slippage")
    
    if risk_parts:
        return ". ".join(risk_parts[:3]) + "."  # Limit to 3 warnings
    else:
        return "Standard trading risks apply. Past performance does not guarantee future results."

