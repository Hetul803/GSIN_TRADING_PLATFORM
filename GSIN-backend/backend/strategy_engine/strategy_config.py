# backend/strategy_engine/strategy_config.py
"""
Centralized configuration for all strategy thresholds and evolution parameters.

This file consolidates all thresholds to avoid contradictions between:
- Evolution Worker
- Monitoring Worker
- Status Manager
- Phase thresholds
"""
import os

# ============================================================================
# PHASE 0: Cold Start Thresholds
# ============================================================================
COLD_START_WINRATE_MIN = 0.25  # 25%
COLD_START_SHARPE_MIN = 0.2
COLD_START_TRADES_MIN = 5

# ============================================================================
# PHASE 1: Growth Thresholds
# ============================================================================
GROWTH_WINRATE_MIN = 0.55  # 55%
GROWTH_SHARPE_MIN = 0.5
GROWTH_TRADES_MIN = 10

# ============================================================================
# PHASE 2: Mature Thresholds (Flexible - High Win Rate OR High Sharpe)
# ============================================================================
MATURE_WINRATE_MIN = 0.55  # For high Sharpe path
MATURE_WINRATE_MIN_HIGH_WIN = 0.80  # For high win rate path
MATURE_SHARPE_MIN = 1.0  # For high win rate path
MATURE_SHARPE_MIN_HIGH_SHARPE = 1.5  # For high Sharpe path
MATURE_TRADES_MIN = 30
MATURE_MAX_DRAWDOWN_MAX = 10.0  # 10%

# ============================================================================
# Status Transition Thresholds
# ============================================================================

# Experiment → Candidate
# PERMANENT CHANGE: Reduced from 50 to 20 for swing trading strategies (trade once a week)
# Do not change back to 50 unless you only want scalpers
MIN_TRADES_FOR_CANDIDATE = 20
# PERMANENT CHANGE: Reduced from 0.75 to 0.40 for trend following strategies (40% win rate but big wins)
# Keep this low, BUT ensure profit_factor > 1.2 is checked alongside it
WIN_RATE_THRESHOLD_CANDIDATE = 0.40  # 40% (was 75%)
MAX_DRAWDOWN_FOR_CANDIDATE = 0.30  # 30%

# Candidate → Proposable (Base Requirements)
# FIXED: Use flexible thresholds to ensure profitability while being realistic
# Path 1: High win rate (80%+) with moderate Sharpe (1.0+)
# Path 2: Moderate win rate (60%+) with high Sharpe (1.5+) - ensures profitability via risk-adjusted returns
MIN_TRADES_FOR_PROPOSABLE = 50
WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_WIN = 0.80  # 80% win rate (Path 1)
WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_SHARPE = 0.60  # 60% win rate (Path 2)
# TEMPORARY CHANGE: Reduced from 1.0 to 0.7 to verify pipeline works
# Change back to 1.0 or 1.2 after ~1 week when you have too many strategies and need to filter harder
MIN_SHARPE_FOR_PROPOSABLE_HIGH_WIN = 0.7  # Sharpe for Path 1 (was 1.0, temporary)
MIN_SHARPE_FOR_PROPOSABLE_HIGH_SHARPE = 1.5  # Sharpe for Path 2 (higher to ensure profitability)
MIN_PROFIT_FACTOR_FOR_PROPOSABLE = 1.2  # Unified profit factor (ensures profitability: avg win > avg loss)
MAX_DRAWDOWN_FOR_PROPOSABLE = 0.20  # 20%
# TEMPORARY CHANGE: Reduced from 0.70 to 0.60 because strategies are getting 0.66
# Change back to 0.70 once the AI gets smarter and starts producing 0.75+ strategies naturally
MIN_SCORE_FOR_PROPOSABLE = 0.60  # (was 0.70, temporary)
MIN_TEST_WIN_RATE = 0.70  # Anti-overfitting (lowered from 0.75 to be more realistic)

# Candidate → Proposable (MCN Robustness Requirements)
MCN_REGIME_STABILITY_SCORE_MIN = 0.75  # Must pass 3 out of 4 regimes
MCN_OVERFITTING_RISK_REQUIRED = "Low"

# Proposable → Candidate (Demotion with Buffer Zone)
WIN_RATE_DEMOTION_PROPOSABLE = 0.70  # Buffer: 0.90 -> 0.70
SHARPE_DEMOTION_PROPOSABLE = 0.5  # Buffer: 1.0 -> 0.5
SCORE_DEMOTION_PROPOSABLE = 0.60  # Buffer: 0.70 -> 0.60
MAX_DRAWDOWN_DEMOTION_PROPOSABLE = 0.30  # Buffer: 0.20 -> 0.30
MIN_TRADES_DEMOTION_PROPOSABLE = 50

# ============================================================================
# Monitoring Worker Thresholds
# ============================================================================

# Sanity Check (Fast Validation for New Strategies)
# FIXED: Increased from 3 to 10 trades to reduce gap with full backtest (50 trades)
SANITY_CHECK_MIN_TRADES = 10  # Increased from 3 to reduce gap with full backtest
SANITY_CHECK_MAX_DRAWDOWN = 0.70  # 70% - very lenient
SANITY_CHECK_REQUIRE_NO_NAN = True

# Robustness Score Calculation
ROBUSTNESS_MIN_REGIMES_TESTED = 2  # At least 2 different volatility regimes
ROBUSTNESS_WALK_FORWARD_SPLIT = 0.5  # First half vs second half
ROBUSTNESS_PARAMETER_SENSITIVITY_TESTS = 2  # Number of small perturbations to test

# Candidate → Proposable (Monitoring Worker)
# FIXED: Unified profit factor to 1.2 (same as status_manager) to avoid contradictions
MONITORING_ROBUSTNESS_SCORE_MIN = 70  # 0-100 scale
# TEMPORARY CHANGE: Reduced from 1.0 to 0.7 to match MIN_SHARPE_FOR_PROPOSABLE_HIGH_WIN
# Change back to 1.0 after ~1 week when you have too many strategies and need to filter harder
MONITORING_SHARPE_MIN = 0.7  # (was 1.0, temporary)
MONITORING_PROFIT_FACTOR_MIN = 1.2  # Unified to 1.2 (was 1.3) - ensures profitability
MONITORING_MAX_DRAWDOWN_MAX = 0.25  # 25%

# Experiment → Discard (Monitoring Worker)
MONITORING_DISCARD_ROBUSTNESS_THRESHOLD = 40  # Below this = discard
MONITORING_DISCARD_MIN_TRADES = 20  # Must have at least this many trades
MONITORING_DISCARD_MIN_EVALUATION_CYCLES = 3  # Must have been tested for this many cycles

# ============================================================================
# Evolution Worker Thresholds
# ============================================================================
MAX_EVOLUTION_ATTEMPTS = 10  # After this many failed attempts, discard
EVOLUTION_INTERVAL_SECONDS = int(os.environ.get("EVOLUTION_INTERVAL_SECONDS", "480"))  # Default: 8 minutes
MAX_STRATEGIES_TO_MAINTAIN = 100

# Fail-Fast Discard Rules
DISCARD_NEGATIVE_SHARPE_MIN_TRADES = 50  # If sharpe < 0 and trades >= this, discard
DISCARD_NOT_LEARNING_ATTEMPTS = 5  # If attempts >= this and score < threshold, discard
DISCARD_NOT_LEARNING_SCORE_THRESHOLD = 0.20

# ============================================================================
# Monitoring Worker Configuration
# ============================================================================
MONITORING_WORKER_INTERVAL_SECONDS = int(os.environ.get("MONITORING_WORKER_INTERVAL_SECONDS", "900"))  # Default: 15 minutes

# ============================================================================
# Strategy Fingerprinting
# ============================================================================
# Fields used for duplicate detection
FINGERPRINT_FIELDS = [
    "primary_symbols",  # Normalized list of symbols
    "timeframe",
    "direction",  # long/short/both
    "entry_rules_hash",  # Hash of normalized entry rules
    "exit_rules_hash",  # Hash of normalized exit rules
]

