# backend/strategy_engine/validation.py
"""
Strategy validation utilities.
Validates user-uploaded strategies to ensure they have required fields.
"""
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status


def validate_strategy_ruleset(ruleset: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate a strategy ruleset.
    
    Required fields:
    - ticker (single or multiple symbols)
    - timeframe
    - entry rules (conditions)
    - exit rules (conditions)
    
    Returns:
        (is_valid, error_message)
    """
    if not isinstance(ruleset, dict):
        return False, "Ruleset must be a dictionary/object"
    
    # Check for ticker/symbol
    ticker = ruleset.get("ticker") or ruleset.get("symbol") or ruleset.get("symbols")
    if not ticker:
        return False, "Strategy must include a ticker or symbol. Provide either 'ticker', 'symbol', or 'symbols' field."
    
    # Ticker can be string (single) or list (multiple)
    if isinstance(ticker, str):
        if not ticker.strip():
            return False, "Ticker/symbol cannot be empty"
    elif isinstance(ticker, list):
        if len(ticker) == 0:
            return False, "Symbols list cannot be empty"
        if not all(isinstance(s, str) and s.strip() for s in ticker):
            return False, "All symbols in the list must be non-empty strings"
    else:
        return False, "Ticker/symbol must be a string or list of strings"
    
    # Check for timeframe
    timeframe = ruleset.get("timeframe") or ruleset.get("interval")
    if not timeframe:
        return False, "Strategy must include a timeframe (e.g., '1d', '1h', '15m')"
    
    if not isinstance(timeframe, str):
        return False, "Timeframe must be a string (e.g., '1d', '1h', '15m')"
    
    # Valid timeframes
    valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]
    if timeframe not in valid_timeframes:
        return False, f"Timeframe must be one of: {', '.join(valid_timeframes)}"
    
    # Check for entry rules
    entry_rules = ruleset.get("entry") or ruleset.get("entry_rules") or ruleset.get("conditions")
    if not entry_rules:
        return False, "Strategy must include entry rules. Provide 'entry', 'entry_rules', or 'conditions' field."
    
    # Entry rules can be a list of conditions or a dict
    if isinstance(entry_rules, list):
        if len(entry_rules) == 0:
            return False, "Entry rules list cannot be empty"
    elif isinstance(entry_rules, dict):
        # Check if dict has meaningful content
        if len(entry_rules) == 0:
            return False, "Entry rules dictionary cannot be empty"
    else:
        return False, "Entry rules must be a list or dictionary"
    
    # Check for exit rules
    exit_rules = ruleset.get("exit") or ruleset.get("exit_rules")
    if not exit_rules:
        return False, "Strategy must include exit rules. Provide 'exit' or 'exit_rules' field."
    
    # Exit rules can be a dict with stop_loss, take_profit, or conditions
    if isinstance(exit_rules, dict):
        if len(exit_rules) == 0:
            return False, "Exit rules dictionary cannot be empty"
        # Should have at least stop_loss or take_profit or exit_conditions
        if not any(key in exit_rules for key in ["stop_loss", "take_profit", "exit_conditions", "conditions"]):
            return False, "Exit rules must include at least one of: stop_loss, take_profit, or exit_conditions"
    elif isinstance(exit_rules, list):
        if len(exit_rules) == 0:
            return False, "Exit rules list cannot be empty"
    else:
        return False, "Exit rules must be a dictionary or list"
    
    return True, None


def validate_strategy_parameters(parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate strategy parameters.
    
    Parameters should be a dictionary with indicator settings.
    """
    if not isinstance(parameters, dict):
        return False, "Parameters must be a dictionary/object"
    
    # Parameters can be empty (optional), but if present, should be valid
    # No strict validation needed here - just ensure it's a dict
    return True, None


def validate_strategy_create(
    name: str,
    ruleset: Dict[str, Any],
    parameters: Optional[Dict[str, Any]] = None
) -> None:
    """
    Validate a complete strategy creation request.
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate name
    if not name or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strategy name is required and cannot be empty"
        )
    
    # Validate ruleset
    is_valid, error_msg = validate_strategy_ruleset(ruleset)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy ruleset: {error_msg}"
        )
    
    # Validate parameters (optional)
    if parameters is not None:
        is_valid, error_msg = validate_strategy_parameters(parameters)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid strategy parameters: {error_msg}"
            )

