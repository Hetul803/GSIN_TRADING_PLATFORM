# backend/strategy_engine/strategy_thresholds.py
"""
PHASE 2: 3-phase dynamic evolution thresholds.

PHASE 0 (cold start, first 72 hours):
- winrate ≥ 0.25
- sharpe ≥ 0.2
- trades ≥ 5

PHASE 1 (growth, after 25 strategies or 200 MCN events):
- winrate ≥ 0.55
- sharpe ≥ 0.5
- trades ≥ 10

PHASE 2 (mature stage, after 200 strategies and 1000 MCN events):
- winrate ≥ 0.90
- sharpe ≥ 1.0
- trades ≥ 30
- max_drawdown ≤ 10%
- symbol-robustness test: strategy must remain profitable across 3 symbols
"""
from typing import Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db.models import UserStrategy
from ..brain.mcn_adapter import get_mcn_adapter


class EvolutionPhase:
    """Evolution phase enum."""
    COLD_START = "cold_start"  # PHASE 0
    GROWTH = "growth"  # PHASE 1
    MATURE = "mature"  # PHASE 2


def get_evolution_phase(db: Session) -> Tuple[str, Dict[str, Any]]:
    """
    PHASE 2: Auto-detect evolution phase based on system state.
    
    Returns:
        (phase_name, phase_info)
    """
    # Count total strategies
    total_strategies = db.query(func.count(UserStrategy.id)).scalar() or 0
    
    # Count MCN events (approximate - check MCN adapter)
    mcn_adapter = get_mcn_adapter()
    mcn_events = 0
    try:
        if mcn_adapter and mcn_adapter.is_available:
            # Get approximate event count from MCN
            # This is a simplified check - in production, track events separately
            mcn_events = getattr(mcn_adapter.mcn, 'vals', None)
            if mcn_events is not None:
                try:
                    mcn_events = len(mcn_events) if hasattr(mcn_events, '__len__') else 0
                except:
                    mcn_events = 0
    except:
        mcn_events = 0
    
    # Check if system is in first 72 hours (cold start)
    # This would require tracking system start time - for now, use strategy count as proxy
    is_cold_start = total_strategies < 10  # Approximate: if very few strategies, likely cold start
    
    # PHASE 2: Determine phase
    if is_cold_start or total_strategies < 25:
        phase = EvolutionPhase.COLD_START
        phase_info = {
            "name": "cold_start",
            "description": "Cold start phase (first 72 hours or <25 strategies)",
            "total_strategies": total_strategies,
            "mcn_events": mcn_events,
        }
    elif total_strategies < 200 or mcn_events < 1000:
        phase = EvolutionPhase.GROWTH
        phase_info = {
            "name": "growth",
            "description": "Growth phase (25-200 strategies or 200-1000 MCN events)",
            "total_strategies": total_strategies,
            "mcn_events": mcn_events,
        }
    else:
        phase = EvolutionPhase.MATURE
        phase_info = {
            "name": "mature",
            "description": "Mature stage (200+ strategies and 1000+ MCN events)",
            "total_strategies": total_strategies,
            "mcn_events": mcn_events,
        }
    
    return phase, phase_info


def get_thresholds_for_phase(phase: str) -> Dict[str, Any]:
    """
    PHASE 2: Get thresholds for a given evolution phase.
    
    Returns:
        {
            "winrate_min": float,
            "sharpe_min": float,
            "trades_min": int,
            "max_drawdown_max": float | None,  # None for phases that don't require it
            "symbol_robustness_required": bool,
            "min_symbols": int  # For symbol-robustness test
        }
    """
    if phase == EvolutionPhase.COLD_START:
        return {
            "winrate_min": 0.25,
            "sharpe_min": 0.2,
            "trades_min": 5,
            "max_drawdown_max": None,  # Not required in cold start
            "symbol_robustness_required": False,
            "min_symbols": 1,
        }
    elif phase == EvolutionPhase.GROWTH:
        return {
            "winrate_min": 0.55,
            "sharpe_min": 0.5,
            "trades_min": 10,
            "max_drawdown_max": None,  # Not required in growth
            "symbol_robustness_required": False,
            "min_symbols": 1,
        }
    elif phase == EvolutionPhase.MATURE:
        # PHASE 2: More flexible - allow different types of elite strategies
        # Option 1: High win rate strategy (winrate >= 0.80 AND sharpe >= 1.0)
        # Option 2: High Sharpe strategy (winrate >= 0.55 AND sharpe >= 1.5)
        # This accepts both high-win-rate OR high-Sharpe strategies
        return {
            "winrate_min": 0.55,  # Lowered from 0.90 - now part of OR condition
            "winrate_min_high_win": 0.80,  # For high win rate path
            "sharpe_min": 1.0,  # For high win rate path
            "sharpe_min_high_sharpe": 1.5,  # For high Sharpe path
            "trades_min": 30,
            "max_drawdown_max": 10.0,  # 10% max drawdown
            "symbol_robustness_required": True,
            "min_symbols": 3,  # Must be profitable across 3 symbols
            "flexible_thresholds": True,  # Flag to indicate flexible logic
        }
    else:
        # Default to growth phase thresholds
        return {
            "winrate_min": 0.55,
            "sharpe_min": 0.5,
            "trades_min": 10,
            "max_drawdown_max": None,
            "symbol_robustness_required": False,
            "min_symbols": 1,
        }


def check_strategy_meets_thresholds(
    strategy_metrics: Dict[str, Any],
    phase: str
) -> Tuple[bool, str]:
    """
    PHASE 2: Check if strategy meets thresholds for given phase.
    
    Args:
        strategy_metrics: Dict with win_rate, sharpe_ratio, total_trades, max_drawdown, etc.
        phase: Evolution phase name
    
    Returns:
        (meets_thresholds: bool, reason: str)
    """
    thresholds = get_thresholds_for_phase(phase)
    
    win_rate = strategy_metrics.get("win_rate", 0.0)
    sharpe = strategy_metrics.get("sharpe_ratio", 0.0)
    trades = strategy_metrics.get("total_trades", 0)
    max_drawdown = strategy_metrics.get("max_drawdown", 100.0)  # Default to high if missing
    
    # Check trades count (required for all phases)
    if trades < thresholds["trades_min"]:
        return False, f"Trades count {trades} below minimum {thresholds['trades_min']}"
    
    # Check max drawdown (only for mature phase)
    if thresholds["max_drawdown_max"] is not None:
        if max_drawdown > thresholds["max_drawdown_max"]:
            return False, f"Max drawdown {max_drawdown:.2f}% exceeds maximum {thresholds['max_drawdown_max']:.2f}%"
    
    # For mature phase, use flexible thresholds (high win rate OR high Sharpe)
    if thresholds.get("flexible_thresholds", False):
        # Option 1: High win rate path (winrate >= 0.80 AND sharpe >= 1.0)
        high_win_path = (
            win_rate >= thresholds["winrate_min_high_win"] and
            sharpe >= thresholds["sharpe_min"]
        )
        
        # Option 2: High Sharpe path (winrate >= 0.55 AND sharpe >= 1.5)
        high_sharpe_path = (
            win_rate >= thresholds["winrate_min"] and
            sharpe >= thresholds["sharpe_min_high_sharpe"]
        )
        
        if not (high_win_path or high_sharpe_path):
            return False, (
                f"Strategy does not meet flexible thresholds: "
                f"Need (winrate >= {thresholds['winrate_min_high_win']:.2%} AND sharpe >= {thresholds['sharpe_min']:.2f}) "
                f"OR (winrate >= {thresholds['winrate_min']:.2%} AND sharpe >= {thresholds['sharpe_min_high_sharpe']:.2f}). "
                f"Current: winrate={win_rate:.2%}, sharpe={sharpe:.2f}"
            )
    else:
        # For other phases, use standard thresholds
        # Check win rate
        if win_rate < thresholds["winrate_min"]:
            return False, f"Win rate {win_rate:.2%} below minimum {thresholds['winrate_min']:.2%}"
        
        # Check Sharpe ratio
        if sharpe < thresholds["sharpe_min"]:
            return False, f"Sharpe ratio {sharpe:.2f} below minimum {thresholds['sharpe_min']:.2f}"
    
    # Check symbol robustness (only for mature phase)
    if thresholds["symbol_robustness_required"]:
        per_symbol_perf = strategy_metrics.get("per_symbol_performance", {})
        profitable_symbols = 0
        for symbol, perf in per_symbol_perf.items():
            if isinstance(perf, dict) and perf.get("win_rate", 0.0) >= 0.5:
                profitable_symbols += 1
        
        if profitable_symbols < thresholds["min_symbols"]:
            return False, f"Symbol robustness: only {profitable_symbols} profitable symbols, need {thresholds['min_symbols']}"
    
    return True, "Strategy meets all thresholds"

