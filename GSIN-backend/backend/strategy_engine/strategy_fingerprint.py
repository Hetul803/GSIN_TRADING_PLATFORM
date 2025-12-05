# backend/strategy_engine/strategy_fingerprint.py
"""
Strategy Fingerprinting - Creates a unique "DNA" hash for duplicate detection.

A strategy fingerprint is based on:
- Primary symbol(s)
- Timeframe
- Direction (long/short/both)
- Entry rules (indicator types + operators + parameters)
- Exit rules (stop loss, take profit, etc.)
"""
import json
import hashlib
from typing import Dict, Any, List, Optional


def normalize_symbols(symbols: Any) -> List[str]:
    """Normalize symbols to a sorted list."""
    if isinstance(symbols, str):
        return sorted([s.strip().upper() for s in symbols.split(',')])
    elif isinstance(symbols, list):
        return sorted([str(s).strip().upper() for s in symbols])
    elif isinstance(symbols, dict):
        # If it's a dict with symbol keys, extract keys
        return sorted([str(k).strip().upper() for k in symbols.keys()])
    else:
        return []


def extract_primary_symbols(ruleset: Dict[str, Any]) -> List[str]:
    """Extract primary symbols from ruleset."""
    # Try various fields where symbols might be stored
    symbol_fields = ['ticker', 'symbol', 'symbols', 'default_symbol', 'symbol_universe']
    
    for field in symbol_fields:
        if field in ruleset:
            symbols = normalize_symbols(ruleset[field])
            if symbols:
                return symbols
    
    # Default to empty list if no symbols found
    return []


def extract_direction(ruleset: Dict[str, Any]) -> str:
    """Extract trading direction from ruleset."""
    direction = ruleset.get('direction', 'both').lower()
    if direction in ['long', 'short', 'both']:
        return direction
    return 'both'  # Default


def normalize_entry_rules(ruleset: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize entry rules to a consistent format."""
    entry_rules = []
    
    # Try various field names
    entry_fields = ['entry_conditions', 'entry_rules', 'entry', 'conditions']
    
    for field in entry_fields:
        if field in ruleset:
            rules = ruleset[field]
            if isinstance(rules, list):
                entry_rules = rules
                break
            elif isinstance(rules, dict):
                entry_rules = [rules]
                break
    
    # Normalize each rule
    normalized = []
    for rule in entry_rules:
        if isinstance(rule, dict):
            normalized_rule = {
                'indicator': str(rule.get('indicator', '')).lower(),
                'operator': str(rule.get('operator', rule.get('condition', ''))).lower(),
                'value': rule.get('value', rule.get('threshold', None)),
                'period': rule.get('period', rule.get('lookback', None)),
            }
            # Remove None values for consistent hashing
            normalized_rule = {k: v for k, v in normalized_rule.items() if v is not None}
            normalized.append(normalized_rule)
    
    # Sort for consistent hashing
    return sorted(normalized, key=lambda x: json.dumps(x, sort_keys=True))


def normalize_exit_rules(ruleset: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize exit rules to a consistent format."""
    exit_rules = {}
    
    # Try various field names
    exit_fields = ['exit_rules', 'exit_conditions', 'exit']
    
    for field in exit_fields:
        if field in ruleset:
            rules = ruleset[field]
            if isinstance(rules, dict):
                exit_rules = rules
                break
    
    # Extract key exit parameters
    normalized = {
        'stop_loss_percent': ruleset.get('stop_loss', ruleset.get('stop_loss_percent', None)),
        'take_profit_percent': ruleset.get('take_profit', ruleset.get('take_profit_percent', None)),
        'trailing_stop_percent': ruleset.get('trailing_stop', ruleset.get('trailing_stop_percent', None)),
    }
    
    # Also check exit_rules dict
    if isinstance(exit_rules, dict):
        normalized.update({
            'stop_loss_percent': exit_rules.get('stop_loss', exit_rules.get('stop_loss_percent', normalized.get('stop_loss_percent'))),
            'take_profit_percent': exit_rules.get('take_profit', exit_rules.get('take_profit_percent', normalized.get('take_profit_percent'))),
            'trailing_stop_percent': exit_rules.get('trailing_stop', exit_rules.get('trailing_stop_percent', normalized.get('trailing_stop_percent'))),
        })
    
    # Remove None values for consistent hashing
    return {k: v for k, v in normalized.items() if v is not None}


def create_strategy_fingerprint(
    ruleset: Dict[str, Any],
    timeframe: Optional[str] = None
) -> str:
    """
    Create a unique fingerprint for a strategy based on its core characteristics.
    
    Args:
        ruleset: Strategy ruleset dictionary
        timeframe: Optional explicit timeframe (if not in ruleset)
    
    Returns:
        SHA256 hash string representing the strategy's "DNA"
    """
    # Extract components
    primary_symbols = extract_primary_symbols(ruleset)
    direction = extract_direction(ruleset)
    tf = timeframe or ruleset.get('timeframe', '1d')
    entry_rules = normalize_entry_rules(ruleset)
    exit_rules = normalize_exit_rules(ruleset)
    
    # Create fingerprint dictionary
    fingerprint_data = {
        'primary_symbols': sorted(primary_symbols),
        'timeframe': str(tf).lower(),
        'direction': direction,
        'entry_rules': entry_rules,
        'exit_rules': exit_rules,
    }
    
    # Convert to JSON string (sorted keys for consistency)
    fingerprint_json = json.dumps(fingerprint_data, sort_keys=True, separators=(',', ':'))
    
    # Hash it
    fingerprint_hash = hashlib.sha256(fingerprint_json.encode('utf-8')).hexdigest()
    
    return fingerprint_hash


def strategies_match_fingerprint(
    strategy1_ruleset: Dict[str, Any],
    strategy2_ruleset: Dict[str, Any],
    strategy1_timeframe: Optional[str] = None,
    strategy2_timeframe: Optional[str] = None
) -> bool:
    """
    Check if two strategies have matching fingerprints (duplicates).
    
    Args:
        strategy1_ruleset: First strategy's ruleset
        strategy2_ruleset: Second strategy's ruleset
        strategy1_timeframe: Optional explicit timeframe for strategy 1
        strategy2_timeframe: Optional explicit timeframe for strategy 2
    
    Returns:
        True if strategies match (are duplicates)
    """
    fp1 = create_strategy_fingerprint(strategy1_ruleset, strategy1_timeframe)
    fp2 = create_strategy_fingerprint(strategy2_ruleset, strategy2_timeframe)
    
    return fp1 == fp2

