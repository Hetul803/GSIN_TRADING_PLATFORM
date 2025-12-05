# backend/strategy_engine/constants.py
"""
Constants for strategy engine.
"""
# Default symbols for multi-asset testing
DEFAULT_SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT", "SPY", "QQQ", "BTCUSD", "ETHUSD"]

# Minimum number of assets a strategy must perform well on to be considered "generalized"
MIN_ASSETS_FOR_GENERALIZATION = 2

# Performance thresholds for generalization
GENERALIZATION_WINRATE_THRESHOLD = 0.55  # Minimum winrate on an asset
GENERALIZATION_MIN_ASSETS = 2  # Must perform well on at least 2 assets

