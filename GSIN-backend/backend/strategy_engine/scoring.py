# backend/strategy_engine/scoring.py
"""
Strategy scoring engine - Unified composite score for Brain decision-making.

This module computes a single unified score that the Brain uses to rank and decide
which strategies to propose. The score combines multiple metrics with explicit weights
that can be easily tweaked.

Formula:
    score = a1 * win_rate
          + a2 * risk_adjusted_return
          - a3 * max_drawdown
          + a4 * stability
          + a5 * sharpe_bonus

Where:
    - win_rate: Percentage of profitable trades (0-1)
    - risk_adjusted_return: CAGR normalized by volatility
    - max_drawdown: Maximum peak-to-trough decline (penalized)
    - stability: Low variance in monthly returns (consistency)
    - sharpe_bonus: Sharpe or Sortino ratio bonus

Business Logic:
    - High win rate is critical (weight: 0.35)
    - Risk-adjusted returns matter more than raw returns (weight: 0.25)
    - Drawdowns are penalized heavily (weight: -0.20)
    - Stability indicates robustness (weight: 0.15)
    - Sharpe ratio provides risk-adjusted quality signal (weight: 0.05)
"""
from typing import Dict, Any, Optional
import math
import statistics


# Configuration constants - easily tweakable
# Updated weights to include WFA and Monte Carlo (will be normalized in formula)
WIN_RATE_WEIGHT = 0.30  # Reduced from 0.35 to make room for WFA/MC
RISK_ADJUSTED_RETURN_WEIGHT = 0.20  # Reduced from 0.25
DRAWDOWN_PENALTY_WEIGHT = 0.20
STABILITY_WEIGHT = 0.15
SHARPE_BONUS_WEIGHT = 0.05
# WFA_WEIGHT and MC_WEIGHT defined in score_strategy function

# Thresholds for normalization
MAX_REASONABLE_DRAWDOWN = 0.50  # 50% drawdown = score of 0
MAX_REASONABLE_SHARPE = 3.0
MIN_TRADES_FOR_STABILITY = 10


def score_strategy(
    backtest_results: Dict[str, Any],
    use_test_metrics: bool = False
) -> float:
    """
    Compute unified strategy score from backtest results.
    
    Uses train metrics by default, but can use test metrics for validation.
    
    Args:
        backtest_results: Dictionary with backtest metrics
        use_test_metrics: If True, use test set metrics (for overfitting detection)
    
    Returns:
        Score between 0.0 and 1.0, where:
        - 0.9+ = Elite strategy (highly proposable)
        - 0.7-0.9 = Good strategy (proposable with caution)
        - 0.5-0.7 = Acceptable (needs improvement)
        - <0.5 = Poor (should be discarded or heavily mutated)
    """
    # Select metrics source (train or test)
    if use_test_metrics and "test_metrics" in backtest_results:
        metrics = backtest_results["test_metrics"]
    else:
        metrics = backtest_results
    
    win_rate = metrics.get("win_rate", 0.0)
    max_drawdown = abs(metrics.get("max_drawdown", 0.0))
    total_return = metrics.get("total_return", 0.0)
    sharpe_ratio = metrics.get("sharpe_ratio", 0.0)
    sortino_ratio = metrics.get("sortino_ratio", sharpe_ratio)  # Prefer Sortino if available
    total_trades = metrics.get("total_trades", 0)
    
    # Calculate CAGR if period info available
    start_date = metrics.get("start_date")
    end_date = metrics.get("end_date")
    if start_date and end_date:
        try:
            from datetime import datetime
            if isinstance(start_date, str):
                start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            else:
                start = start_date
            if isinstance(end_date, str):
                end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            else:
                end = end_date
            years = (end - start).days / 365.25
            if years > 0 and total_return > -1.0:
                cagr = ((1 + total_return / 100.0) ** (1 / years) - 1) * 100.0
            else:
                cagr = total_return
        except:
            cagr = total_return
    else:
        cagr = total_return
    
    # Component 1: Win Rate (0-1, already normalized)
    # High win rate is critical for reliability
    win_rate_score = win_rate
    
    # Component 2: Risk-Adjusted Return
    # Use CAGR normalized by volatility (if available)
    volatility = metrics.get("volatility", 0.0)
    if volatility > 0:
        risk_adjusted_return = cagr / (volatility * 100.0)  # Normalize
        risk_adjusted_score = min(1.0, max(0.0, (risk_adjusted_return / 2.0) + 0.5))
    else:
        # Fallback: use raw return normalized
        risk_adjusted_score = min(1.0, max(0.0, (cagr / 100.0) + 0.5))
    
    # Component 3: Drawdown Penalty
    # Exponential penalty: 0% drawdown = 1.0, 50%+ drawdown ≈ 0.0
    drawdown_score = math.exp(-max_drawdown * 2.0) if max_drawdown > 0 else 1.0
    drawdown_score = max(0.0, min(1.0, drawdown_score))
    
    # Component 4: Stability (consistency of returns)
    # Calculate from equity curve or monthly returns if available
    equity_curve = metrics.get("equity_curve", [])
    stability_score = _calculate_stability(equity_curve, total_trades)
    
    # Component 5: Sharpe/Sortino Bonus
    # Use Sortino if available (penalizes downside volatility only)
    risk_adjusted_ratio = sortino_ratio if sortino_ratio else sharpe_ratio
    if risk_adjusted_ratio:
        sharpe_score = min(1.0, max(0.0, (risk_adjusted_ratio / MAX_REASONABLE_SHARPE) + 0.5))
    else:
        sharpe_score = 0.5  # Neutral if not available
    
    # Component 6: Walk-Forward Analysis consistency
    # Higher consistency = strategy is robust across different time periods
    wfa_results = backtest_results.get("wfa_results", {})
    wfa_consistency = wfa_results.get("consistency_score", 0.0)
    # FIX: If WFA results are missing, use a neutral score based on train/test split
    if not wfa_results or wfa_consistency == 0.0:
        # Use train/test metrics to estimate consistency
        train_metrics = backtest_results.get("train_metrics", {})
        test_metrics = backtest_results.get("test_metrics", {})
        if train_metrics and test_metrics:
            train_winrate = train_metrics.get("win_rate", 0.0)
            test_winrate = test_metrics.get("win_rate", 0.0)
            # Consistency = how close test is to train (closer = more consistent)
            consistency = 1.0 - abs(train_winrate - test_winrate)
            wfa_consistency = consistency - 0.5  # Convert to -1 to 1 range
        else:
            wfa_consistency = 0.0  # Neutral if no train/test split
    
    wfa_score = max(0.0, min(1.0, (wfa_consistency + 1.0) / 2.0))  # Normalize -1 to 1 -> 0 to 1
    WFA_WEIGHT = 0.10  # 10% weight for WFA consistency
    
    # Component 7: Monte Carlo robustness
    # Lower variance in MC simulations = more robust strategy
    mc_results = backtest_results.get("monte_carlo_results", {})
    # FIX: If MC results are missing, use a neutral score based on drawdown and volatility
    if not mc_results or not mc_results.get("std_return"):
        # Estimate MC robustness from available metrics
        volatility = metrics.get("volatility", 0.0)
        if volatility > 0:
            # Lower volatility = higher robustness estimate
            mc_robustness = max(0.3, min(0.7, 1.0 - (volatility / 0.5)))  # Normalize volatility
        else:
            mc_robustness = 0.5  # Neutral
        mc_score = mc_robustness
    else:
        mc_mean_return = mc_results.get("mean_return", 0.0)
        mc_std_return = mc_results.get("std_return", 100.0)  # High std = fragile
        mc_percentile_5 = mc_results.get("percentile_5", -100.0)  # Worst case scenario
        
        # Monte Carlo score: penalize high variance and negative worst-case
        if mc_std_return > 0:
            mc_robustness = 1.0 / (1.0 + (mc_std_return / 50.0))  # Lower std = higher score
        else:
            mc_robustness = 0.5
        
        # Penalize negative worst-case (5th percentile)
        if mc_percentile_5 < 0:
            mc_robustness *= 0.7  # Reduce score if worst case is negative
        
        mc_score = max(0.0, min(1.0, mc_robustness))
    
    MC_WEIGHT = 0.10  # 10% weight for Monte Carlo robustness
    
    # Weighted combination
    # Formula: score = a1*win_rate + a2*risk_adj_return - a3*drawdown + a4*stability + a5*sharpe + a6*wfa + a7*mc
    # Adjust weights to sum to 1.0
    total_weight = (
        WIN_RATE_WEIGHT +
        RISK_ADJUSTED_RETURN_WEIGHT +
        (1.0 - DRAWDOWN_PENALTY_WEIGHT) +
        STABILITY_WEIGHT +
        SHARPE_BONUS_WEIGHT +
        WFA_WEIGHT +
        MC_WEIGHT
    )
    
    # Normalize weights
    final_score = (
        win_rate_score * (WIN_RATE_WEIGHT / total_weight) +
        risk_adjusted_score * (RISK_ADJUSTED_RETURN_WEIGHT / total_weight) +
        drawdown_score * ((1.0 - DRAWDOWN_PENALTY_WEIGHT) / total_weight) +
        stability_score * (STABILITY_WEIGHT / total_weight) +
        sharpe_score * (SHARPE_BONUS_WEIGHT / total_weight) +
        wfa_score * (WFA_WEIGHT / total_weight) +
        mc_score * (MC_WEIGHT / total_weight)
    )
    
    # Clamp to 0-1
    return max(0.0, min(1.0, final_score))


def _calculate_stability(equity_curve: list, total_trades: int) -> float:
    """
    Calculate stability score from equity curve.
    
    Stability = low variance in period-over-period returns.
    Higher stability = more consistent performance.
    
    Returns:
        Score between 0.0 and 1.0
    """
    if not equity_curve or len(equity_curve) < MIN_TRADES_FOR_STABILITY:
        return 0.5  # Neutral if insufficient data
    
    try:
        # Calculate period-over-period returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1].get("equity", 0) if isinstance(equity_curve[i-1], dict) else equity_curve[i-1]
            curr_equity = equity_curve[i].get("equity", 0) if isinstance(equity_curve[i], dict) else equity_curve[i]
            if prev_equity > 0:
                period_return = (curr_equity - prev_equity) / prev_equity
                returns.append(period_return)
        
        if len(returns) < 2:
            return 0.5
        
        # Calculate coefficient of variation (std / mean)
        mean_return = statistics.mean(returns)
        if abs(mean_return) < 1e-6:
            return 0.5  # Neutral if mean is near zero
        
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0.0
        cv = abs(std_return / mean_return) if mean_return != 0 else 1.0
        
        # Lower CV = higher stability
        # CV of 0 = perfect stability (score 1.0)
        # CV of 1.0+ = high volatility (score approaches 0)
        stability_score = math.exp(-cv)
        return max(0.0, min(1.0, stability_score))
    except:
        return 0.5  # Neutral on error


def calculate_sortino_ratio(returns: list, risk_free_rate: float = 0.0) -> Optional[float]:
    """
    Calculate Sortino ratio (Sharpe-like but only penalizes downside volatility).
    
    Sortino = (Mean Return - Risk Free Rate) / Downside Deviation
    
    Args:
        returns: List of period returns
        risk_free_rate: Risk-free rate (default 0.0)
    
    Returns:
        Sortino ratio or None if insufficient data
    """
    if not returns or len(returns) < 2:
        return None
    
    try:
        mean_return = statistics.mean(returns)
        excess_return = mean_return - risk_free_rate
        
        # Calculate downside deviation (std of negative returns only)
        downside_returns = [r for r in returns if r < 0]
        if len(downside_returns) < 2:
            # If no downside, return high ratio
            return 10.0 if excess_return > 0 else 0.0
        
        downside_std = statistics.stdev(downside_returns)
        if downside_std == 0:
            return 10.0 if excess_return > 0 else 0.0
        
        sortino = excess_return / downside_std
        return sortino
    except:
        return None

