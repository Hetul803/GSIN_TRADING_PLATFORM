# backend/market_data/symbol_utils.py
"""
ISSUE 2 FIX: Symbol normalization utilities.
Centralizes symbol cleaning to handle "$MSFT", "TSLA\n", BTCUSD, ETHUSD, etc.
"""
import re
from typing import Optional

# ISSUE 2 FIX: Special symbol mappings for Yahoo Finance
SPECIAL_SYMBOL_MAP = {
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "BTC": "BTC-USD",  # Common shorthand
    "ETH": "ETH-USD",  # Common shorthand
    # Add other crypto or FX mappings here if used
}

# Twelve Data uses different format for crypto: BTC-USD → BTC/USD
TWELVEDATA_CRYPTO_MAP = {
    "BTC-USD": "BTC/USD",
    "ETH-USD": "ETH/USD",
    "SOL-USD": "SOL/USD",
}


def normalize_symbol(symbol: str) -> str:
    """
    ISSUE 2 FIX: Normalize symbol string for market data providers.
    
    Strips:
    - Leading '$' or other currency symbols
    - Leading/trailing whitespace
    - Non-alphanumeric suffixes (for now, assumes US equities)
    
    Examples:
        "$MSFT " -> "MSFT"
        "TSLA\n" -> "TSLA"
        "  AAPL  " -> "AAPL"
        "$GOOGL" -> "GOOGL"
    
    Args:
        symbol: Raw symbol string (may contain $, whitespace, etc.)
    
    Returns:
        Normalized symbol string (uppercase, trimmed, no special chars)
    """
    if not symbol:
        return ""
    
    # Convert to string and strip whitespace
    normalized = str(symbol).strip()
    
    # Remove leading $ or other currency symbols
    normalized = re.sub(r'^[\$€£¥₹]+\s*', '', normalized)
    
    # Remove any trailing non-alphanumeric characters (except dots for some tickers like BRK.B)
    # For now, keep it simple - just strip trailing special chars
    normalized = re.sub(r'[^\w.]+$', '', normalized)
    
    # Convert to uppercase (standard for US equities)
    normalized = normalized.upper()
    
    # Final cleanup: remove any remaining whitespace
    normalized = normalized.strip()
    
    # ISSUE 2 FIX: Apply special symbol mappings (e.g., BTCUSD -> BTC-USD for Yahoo Finance)
    if normalized in SPECIAL_SYMBOL_MAP:
        normalized = SPECIAL_SYMBOL_MAP[normalized]
    
    return normalized


def normalize_symbol_for_twelvedata(symbol: str) -> str:
    """
    Normalize symbol for Twelve Data API.
    
    Twelve Data uses different format for crypto:
    - BTC-USD → BTC/USD
    - ETH-USD → ETH/USD
    
    Args:
        symbol: Normalized symbol (e.g., "BTC-USD", "AAPL")
    
    Returns:
        Symbol in Twelve Data format (e.g., "BTC/USD", "AAPL")
    """
    normalized = normalize_symbol(symbol)
    return TWELVEDATA_CRYPTO_MAP.get(normalized, normalized)


def validate_symbol(symbol: str) -> bool:
    """
    Validate that a normalized symbol looks like a valid ticker.
    
    For US equities:
    - 1-5 characters
    - Alphanumeric (may include dot for class shares like BRK.B)
    
    For crypto/FX (e.g., BTC-USD, ETH-USD):
    - Allows hyphens for crypto pairs
    - Pattern: XXX-XXX (e.g., BTC-USD)
    
    Args:
        symbol: Normalized symbol string
    
    Returns:
        True if symbol appears valid, False otherwise
    """
    if not symbol:
        return False
    
    # ISSUE 2 FIX: Allow crypto symbols with hyphens (e.g., BTC-USD, ETH-USD)
    # Pattern: 3-10 chars, alphanumeric, may include hyphen and dot
    # Examples: AAPL, MSFT, BRK.B, BTC-USD, ETH-USD
    if re.match(r'^[A-Z0-9.-]{1,10}$', symbol):
        return True
    
    return False

