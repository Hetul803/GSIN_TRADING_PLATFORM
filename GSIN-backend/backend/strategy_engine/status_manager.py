# backend/strategy_engine/status_manager.py
"""
Strategy Status Manager - Handles promotion/demotion logic for strategies.

Status transitions:
- experiment → candidate: When sample size >= threshold and basic metrics pass
- candidate → proposable: When test metrics meet elite thresholds
- proposable → candidate: If metrics degrade
- any → discarded: After N failed evolution attempts

Business Rules:
- Only "proposable" strategies can be used for live signals
- "experiment" and "discarded" strategies are never proposed
- Status transitions are based on explicit thresholds
"""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Import centralized config
from .strategy_config import (
    MIN_TRADES_FOR_CANDIDATE,
    MIN_TRADES_FOR_PROPOSABLE,
    WIN_RATE_THRESHOLD_CANDIDATE,
    WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_WIN,
    WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_SHARPE,
    MIN_SHARPE_FOR_PROPOSABLE_HIGH_WIN,
    MIN_SHARPE_FOR_PROPOSABLE_HIGH_SHARPE,
    MIN_PROFIT_FACTOR_FOR_PROPOSABLE,
    MAX_DRAWDOWN_FOR_PROPOSABLE,
    MIN_SCORE_FOR_PROPOSABLE,
    MIN_TEST_WIN_RATE,
    MCN_REGIME_STABILITY_SCORE_MIN,
    MCN_OVERFITTING_RISK_REQUIRED,
    MAX_EVOLUTION_ATTEMPTS,
)

# Keep these for backward compatibility (will be removed later)
MIN_TRADES_FOR_EVAL = MIN_TRADES_FOR_CANDIDATE
WIN_RATE_THRESHOLD_PROPOSABLE = WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_WIN  # Default to high win path
MIN_SHARPE_FOR_PROPOSABLE = MIN_SHARPE_FOR_PROPOSABLE_HIGH_WIN

# Demotion thresholds (lower than promotion to create buffer zone)
WIN_RATE_DEMOTION_CANDIDATE = 0.70  # Demote from candidate if win_rate < 0.70 (buffer: 0.75 -> 0.70)
WIN_RATE_DEMOTION_PROPOSABLE = 0.70  # Demote from proposable if win_rate < 0.70
SHARPE_DEMOTION_PROPOSABLE = 0.5  # Demote from proposable if sharpe < 0.5
SCORE_DEMOTION_PROPOSABLE = 0.60  # Demote from proposable if score < 0.60
MAX_DRAWDOWN_DEMOTION_PROPOSABLE = 0.30  # Demote if drawdown > 30%
MIN_TRADES_DEMOTION_PROPOSABLE = 50  # Demote if trades < 50

# MCN thresholds for Candidate → Proposable promotion
MCN_REGIME_STABILITY_SCORE_MIN = 0.75  # Must pass 3 out of 4 regimes (0.75 = 75%)
MCN_OVERFITTING_RISK_REQUIRED = "Low"  # Must have low overfitting risk


class StrategyStatus:
    """Strategy status values."""
    PENDING_REVIEW = "pending_review"  # New user upload, awaiting Monitoring Worker review
    DUPLICATE = "duplicate"  # Matches existing strategy fingerprint
    REJECTED = "rejected"  # Failed sanity check
    EXPERIMENT = "experiment"
    CANDIDATE = "candidate"
    PROPOSABLE = "proposable"
    DISCARDED = "discarded"


def determine_strategy_status(
    strategy: Dict[str, Any],
    backtest_results: Dict[str, Any],
    current_status: str = "experiment",
    db: Optional[Any] = None  # Optional DB session for MCN queries
) -> tuple[str, bool]:
    """
    Determine new strategy status based on backtest results.
    
    Args:
        strategy: Strategy data (with evolution_attempts, etc.)
        backtest_results: Backtest results with train/test metrics
        current_status: Current strategy status
        db: Optional database session for MCN queries (required for Candidate → Proposable)
    
    Returns:
        Tuple of (new_status, is_proposable)
    """
    # If already discarded, stay discarded
    if current_status == StrategyStatus.DISCARDED:
        return (StrategyStatus.DISCARDED, False)
    
    # Get metrics (prefer test metrics if available for validation)
    metrics = backtest_results.get("test_metrics") or backtest_results
    train_metrics = backtest_results.get("train_metrics", {})
    
    total_trades = metrics.get("total_trades", 0)
    win_rate = metrics.get("win_rate", 0.0)
    score = backtest_results.get("score", 0.0)  # Unified score
    max_drawdown = abs(metrics.get("max_drawdown", 0.0))
    sharpe_ratio = metrics.get("sharpe_ratio", 0.0) or backtest_results.get("sharpe_ratio", 0.0)
    overfitting_detected = backtest_results.get("overfitting_detected", False)
    evolution_attempts = strategy.get("evolution_attempts", 0)
    strategy_id = strategy.get("id")
    
    # Check for overfitting - if detected, don't promote
    if overfitting_detected:
        # If overfit and already tried many times, discard
        if evolution_attempts >= MAX_EVOLUTION_ATTEMPTS:
            return (StrategyStatus.DISCARDED, False)
        # Otherwise, keep in current status (don't promote)
        if current_status == StrategyStatus.EXPERIMENT:
            return (StrategyStatus.EXPERIMENT, False)
        elif current_status == StrategyStatus.CANDIDATE:
            return (StrategyStatus.CANDIDATE, False)
        else:
            # If proposable but overfit, demote to candidate
            return (StrategyStatus.CANDIDATE, False)
    
    # Transition: experiment → candidate
    if current_status == StrategyStatus.EXPERIMENT:
        # PERMANENT CHANGE: Win rate lowered to 0.40 for trend following strategies
        # Must check profit_factor > 1.2 alongside low win rate to ensure profitability
        profit_factor = metrics.get("profit_factor", 0.0) or backtest_results.get("profit_factor", 0.0)
        if (
            total_trades >= MIN_TRADES_FOR_EVAL and
            win_rate >= WIN_RATE_THRESHOLD_CANDIDATE and
            max_drawdown <= 0.30 and  # Allow up to 30% drawdown for candidates
            profit_factor >= 1.2  # Ensure profitability even with low win rate (trend following)
        ):
            return (StrategyStatus.CANDIDATE, False)
        else:
            return (StrategyStatus.EXPERIMENT, False)
    
    # PHASE C: Transition: candidate → proposable with specific thresholds + MCN checks
    elif current_status == StrategyStatus.CANDIDATE:
        test_win_rate = metrics.get("win_rate", 0.0)
        profit_factor = metrics.get("profit_factor", 0.0) or backtest_results.get("profit_factor", 0.0)
        
        # Get MCN robustness data if DB is available
        mcn_regime_stability_score = 0.0
        mcn_overfitting_risk = "Unknown"
        
        if db and strategy_id:
            try:
                from ..brain.mcn_adapter import get_mcn_adapter
                mcn_adapter = get_mcn_adapter()
                
                # Get lineage memory for robustness and overfitting checks
                lineage_memory = mcn_adapter.get_strategy_lineage_memory(strategy_id, db)
                if lineage_memory:
                    # Calculate regime stability score from lineage memory
                    # Check if strategy has been tested across different regimes
                    # For now, use ancestor_stability as proxy, but ideally would test in bull/bear/highVol/lowVol
                    ancestor_stability = lineage_memory.get("ancestor_stability", 0.5)
                    has_overfit = lineage_memory.get("has_overfit_ancestors", False)
                    
                    # If we have per_symbol_performance, calculate regime stability
                    per_symbol_perf = strategy.get("per_symbol_performance", {})
                    if per_symbol_perf:
                        # Count how many symbols are profitable (proxy for regime stability)
                        profitable_symbols = sum(1 for perf in per_symbol_perf.values() 
                                               if isinstance(perf, dict) and perf.get("win_rate", 0.0) >= 0.5)
                        total_symbols = len(per_symbol_perf)
                        if total_symbols > 0:
                            mcn_regime_stability_score = profitable_symbols / total_symbols
                        else:
                            mcn_regime_stability_score = ancestor_stability
                    else:
                        mcn_regime_stability_score = ancestor_stability
                    
                    mcn_overfitting_risk = "High" if has_overfit else "Low"
            except Exception as e:
                # If MCN check fails, default to allowing promotion (fail-open)
                print(f"Warning: MCN check failed for strategy {strategy_id}: {e}")
                mcn_regime_stability_score = 0.75  # Default to passing
                mcn_overfitting_risk = "Low"  # Default to low risk
        
        # PHASE C: Candidate → Proposable with flexible thresholds + MCN robustness checks
        # FIXED: Use flexible thresholds - Path 1 (High Win Rate) OR Path 2 (High Sharpe)
        # Path 1: High win rate (80%+) with moderate Sharpe (1.0+) - ensures profitability via high win rate
        # Path 2: Moderate win rate (60%+) with high Sharpe (1.5+) - ensures profitability via risk-adjusted returns
        test_win_rate = metrics.get("win_rate", win_rate)  # Use test metrics if available
        
        path1_met = (
            total_trades >= MIN_TRADES_FOR_PROPOSABLE and
            win_rate >= WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_WIN and  # 80%
            sharpe_ratio >= MIN_SHARPE_FOR_PROPOSABLE_HIGH_WIN and  # 1.0
            profit_factor >= MIN_PROFIT_FACTOR_FOR_PROPOSABLE and  # 1.2
            max_drawdown <= MAX_DRAWDOWN_FOR_PROPOSABLE and  # 20%
            score >= MIN_SCORE_FOR_PROPOSABLE and  # 0.70
            test_win_rate >= MIN_TEST_WIN_RATE  # 0.70 (anti-overfitting)
        )
        
        path2_met = (
            total_trades >= MIN_TRADES_FOR_PROPOSABLE and
            win_rate >= WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_SHARPE and  # 60%
            sharpe_ratio >= MIN_SHARPE_FOR_PROPOSABLE_HIGH_SHARPE and  # 1.5
            profit_factor >= MIN_PROFIT_FACTOR_FOR_PROPOSABLE and  # 1.2
            max_drawdown <= MAX_DRAWDOWN_FOR_PROPOSABLE and  # 20%
            score >= MIN_SCORE_FOR_PROPOSABLE and  # 0.70
            test_win_rate >= MIN_TEST_WIN_RATE  # 0.70 (anti-overfitting)
        )
        
        # Base requirements: Either path must be met
        base_requirements_met = path1_met or path2_met
        
        # MCN robustness requirements (only if DB available)
        mcn_requirements_met = True
        if db and strategy_id:
            mcn_requirements_met = (
                mcn_regime_stability_score >= MCN_REGIME_STABILITY_SCORE_MIN and
                mcn_overfitting_risk == MCN_OVERFITTING_RISK_REQUIRED
            )
        
        if base_requirements_met and mcn_requirements_met:
            return (StrategyStatus.PROPOSABLE, True)
        else:
            # Check if should demote (metrics degraded significantly, with buffer zone)
            if win_rate < WIN_RATE_DEMOTION_CANDIDATE or max_drawdown > 0.40:
                return (StrategyStatus.EXPERIMENT, False)
            return (StrategyStatus.CANDIDATE, False)
    
    # Transition: proposable → (maintain or demote) with buffer zone
    elif current_status == StrategyStatus.PROPOSABLE:
        # Check if still meets proposable criteria (with buffer zone for demotion)
        test_win_rate = metrics.get("win_rate", 0.0)
        
        # Use demotion thresholds (requested values create explicit buffer)
        if (
            total_trades >= MIN_TRADES_DEMOTION_PROPOSABLE and
            win_rate >= WIN_RATE_DEMOTION_PROPOSABLE and  # Demote if win_rate < 70%
            sharpe_ratio >= SHARPE_DEMOTION_PROPOSABLE and  # Demote if sharpe < 0.5
            test_win_rate >= MIN_TEST_WIN_RATE and
            score >= SCORE_DEMOTION_PROPOSABLE and  # Demote if score < 0.60
            max_drawdown <= MAX_DRAWDOWN_DEMOTION_PROPOSABLE  # Demote if drawdown > 30%
        ):
            return (StrategyStatus.PROPOSABLE, True)
        else:
            # Demote to candidate if metrics degraded below buffer thresholds
            return (StrategyStatus.CANDIDATE, False)
    
    # Default: maintain current status
    return (current_status, current_status == StrategyStatus.PROPOSABLE)


def should_discard_strategy(
    strategy: Dict[str, Any],
    backtest_results: Dict[str, Any]
) -> bool:
    """
    Determine if a strategy should be discarded.
    
    Discard conditions (fail-fast to save compute):
    - Too many evolution attempts without improvement
    - Consistently poor performance
    - Severe overfitting that can't be fixed
    - Proven loser (negative Sharpe with enough trades)
    - Not learning (many attempts but still very low score)
    """
    evolution_attempts = strategy.get("evolution_attempts", 0)
    metrics = backtest_results.get("test_metrics") or backtest_results
    win_rate = metrics.get("win_rate", 0.0)
    score = backtest_results.get("score", 0.0)
    sharpe_ratio = metrics.get("sharpe_ratio", 0.0) or backtest_results.get("sharpe_ratio", 0.0)
    total_trades = metrics.get("total_trades", 0)
    overfitting_detected = backtest_results.get("overfitting_detected", False)
    
    # Rule 1: Discard if too many failed attempts
    if evolution_attempts >= MAX_EVOLUTION_ATTEMPTS:
        return True
    
    # Rule 2: Fail-fast - Proven loser (negative Sharpe with enough sample size)
    # If strategy has negative Sharpe and >50 trades, it's proven to be a loser
    if sharpe_ratio < 0 and total_trades > 50:
        return True
    
    # Rule 3: Fail-fast - Not learning (many attempts but still very low score)
    # If strategy has tried 5+ times and score is still <0.20, it's not learning
    if evolution_attempts >= 5 and score < 0.20:
        return True
    
    # Rule 4: Discard if consistently poor (low win rate, low score, overfit)
    if (
        evolution_attempts >= 5 and
        win_rate < 0.50 and
        score < 0.40 and
        overfitting_detected
    ):
        return True
    
    return False

