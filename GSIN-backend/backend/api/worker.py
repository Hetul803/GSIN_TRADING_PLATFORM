# backend/api/worker.py
"""
Evolution Worker Status API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ..db.session import get_db
from ..db.models import UserStrategy, StrategyLineage, StrategyBacktest
from ..strategy_engine.status_manager import StrategyStatus

router = APIRouter(prefix="/worker", tags=["worker"])


@router.get("/status")
def get_worker_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get evolution worker status and metrics.
    
    Returns:
        - is_running: Whether worker is running (estimated from last activity)
        - last_cycle_at: Last evolution cycle timestamp
        - next_cycle_at: Estimated next cycle timestamp
        - total_strategies: Total active strategies
        - strategies_by_status: Count by status
        - recent_activity: Recent mutations and backtests
    """
    # Check for recent activity (within last 2 hours = worker likely running)
    two_hours_ago = datetime.now() - timedelta(hours=2)
    
    # Get most recent mutation
    recent_mutation = db.query(StrategyLineage).order_by(
        StrategyLineage.created_at.desc()
    ).first()
    
    # Get most recent backtest
    recent_backtest = db.query(StrategyBacktest).order_by(
        StrategyBacktest.created_at.desc()
    ).first()
    
    # Determine if worker is running (has activity in last 2 hours)
    last_activity = None
    if recent_mutation and recent_backtest:
        last_activity = max(recent_mutation.created_at, recent_backtest.created_at)
    elif recent_mutation:
        last_activity = recent_mutation.created_at
    elif recent_backtest:
        last_activity = recent_backtest.created_at
    
    is_running = last_activity and last_activity >= two_hours_ago if last_activity else False
    
    # Calculate next cycle (if worker is running, estimate based on interval)
    import os
    interval_hours = int(os.environ.get("EVOLUTION_WORKER_INTERVAL_HOURS", "24"))
    next_cycle_at = None
    if last_activity:
        next_cycle_at = last_activity + timedelta(hours=interval_hours)
    
    # Count strategies by status
    all_strategies = db.query(UserStrategy).filter(
        UserStrategy.is_active == True
    ).all()
    
    strategies_by_status = {
        "experiment": len([s for s in all_strategies if s.status == StrategyStatus.EXPERIMENT]),
        "candidate": len([s for s in all_strategies if s.status == StrategyStatus.CANDIDATE]),
        "proposable": len([s for s in all_strategies if s.status == StrategyStatus.PROPOSABLE]),
        "discarded": len([s for s in all_strategies if s.status == StrategyStatus.DISCARDED]),
    }
    
    return {
        "is_running": is_running,
        "last_cycle_at": last_activity.isoformat() if last_activity else None,
        "next_cycle_at": next_cycle_at.isoformat() if next_cycle_at else None,
        "total_strategies": len(all_strategies),
        "strategies_by_status": strategies_by_status,
        "worker_interval_hours": interval_hours,
    }


@router.get("/metrics")
def get_worker_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get detailed evolution worker metrics.
    
    Returns:
        - backtest_queue_size: Strategies waiting for backtest
        - mutated_strategies_count: Total mutated strategies
        - discarded_strategies_count: Total discarded strategies
        - promotion_rate: Rate of strategies promoted to proposable
        - mutation_rate: Rate of strategies mutated
        - average_evolution_attempts: Average attempts before success/discard
    """
    # Get all active strategies
    all_strategies = db.query(UserStrategy).filter(
        UserStrategy.is_active == True
    ).all()
    
    # Count strategies needing backtest (experiment or candidate, no recent backtest)
    one_day_ago = datetime.now() - timedelta(days=1)
    backtest_queue = [
        s for s in all_strategies
        if s.status in [StrategyStatus.EXPERIMENT, StrategyStatus.CANDIDATE]
        and (not s.last_backtest_at or s.last_backtest_at < one_day_ago)
    ]
    
    # Count mutated strategies (have lineage as children)
    mutated_count = db.query(StrategyLineage).distinct(
        StrategyLineage.child_strategy_id
    ).count()
    
    # Count discarded strategies
    discarded_count = len([s for s in all_strategies if s.status == StrategyStatus.DISCARDED])
    
    # Count proposable strategies
    proposable_count = len([s for s in all_strategies if s.status == StrategyStatus.PROPOSABLE])
    
    # Calculate rates
    total_processed = len(all_strategies)
    promotion_rate = (proposable_count / total_processed * 100) if total_processed > 0 else 0.0
    mutation_rate = (mutated_count / total_processed * 100) if total_processed > 0 else 0.0
    
    # Calculate average evolution attempts
    attempts_list = [s.evolution_attempts or 0 for s in all_strategies]
    avg_attempts = sum(attempts_list) / len(attempts_list) if attempts_list else 0.0
    
    return {
        "backtest_queue_size": len(backtest_queue),
        "mutated_strategies_count": mutated_count,
        "discarded_strategies_count": discarded_count,
        "proposable_strategies_count": proposable_count,
        "promotion_rate": round(promotion_rate, 2),
        "mutation_rate": round(mutation_rate, 2),
        "average_evolution_attempts": round(avg_attempts, 2),
    }


@router.get("/recent-activity")
def get_recent_activity(
    limit: int = 20,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get recent evolution worker activity.
    
    Returns:
        - mutations: Recent strategy mutations
        - backtests: Recent backtests
        - promotions: Recent status promotions
        - discards: Recent strategy discards
    """
    # Get recent mutations
    recent_mutations = db.query(StrategyLineage).order_by(
        StrategyLineage.created_at.desc()
    ).limit(limit).all()
    
    mutations = [
        {
            "id": m.id,
            "parent_strategy_id": m.parent_strategy_id,
            "child_strategy_id": m.child_strategy_id,
            "mutation_type": m.mutation_type,
            "created_at": m.created_at.isoformat(),
        }
        for m in recent_mutations
    ]
    
    # Get recent backtests
    recent_backtests = db.query(StrategyBacktest).order_by(
        StrategyBacktest.created_at.desc()
    ).limit(limit).all()
    
    backtests = [
        {
            "id": b.id,
            "strategy_id": b.strategy_id,
            "symbol": b.symbol,
            "timeframe": b.timeframe,
            "total_return": b.total_return,
            "win_rate": b.win_rate,
            "created_at": b.created_at.isoformat(),
        }
        for b in recent_backtests
    ]
    
    # Get recent promotions (strategies that became proposable)
    # This is estimated from strategies with proposable status and recent backtest
    one_week_ago = datetime.now() - timedelta(days=7)
    recent_proposable = db.query(UserStrategy).filter(
        UserStrategy.status == StrategyStatus.PROPOSABLE,
        UserStrategy.last_backtest_at >= one_week_ago
    ).order_by(UserStrategy.last_backtest_at.desc()).limit(limit).all()
    
    promotions = [
        {
            "strategy_id": s.id,
            "strategy_name": s.name,
            "score": s.score,
            "promoted_at": s.last_backtest_at.isoformat() if s.last_backtest_at else None,
        }
        for s in recent_proposable
    ]
    
    # Get recent discards
    recent_discarded = db.query(UserStrategy).filter(
        UserStrategy.status == StrategyStatus.DISCARDED,
        UserStrategy.updated_at >= one_week_ago
    ).order_by(UserStrategy.updated_at.desc()).limit(limit).all()
    
    discards = [
        {
            "strategy_id": s.id,
            "strategy_name": s.name,
            "evolution_attempts": s.evolution_attempts,
            "discarded_at": s.updated_at.isoformat(),
        }
        for s in recent_discarded
    ]
    
    return {
        "mutations": mutations,
        "backtests": backtests,
        "promotions": promotions,
        "discards": discards,
    }

