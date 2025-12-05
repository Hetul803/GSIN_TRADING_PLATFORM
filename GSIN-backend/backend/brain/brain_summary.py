# backend/brain/brain_summary.py
"""
Brain summary endpoint - provides high-level stats about strategies and evolution.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from ..db.session import get_db
from ..db.models import UserStrategy, StrategyLineage, StrategyBacktest
from ..db import crud
from .mcn_adapter import get_mcn_adapter, get_mcn_instance

router = APIRouter(prefix="/brain", tags=["brain"])


class TopStrategy(BaseModel):
    """Top performing strategy info."""
    strategy_id: str
    name: str
    score: float
    win_rate: float
    avg_return: float
    total_trades: int


class BrainSummaryResponse(BaseModel):
    """Brain summary with strategy stats."""
    total_strategies: int
    active_strategies: int
    mutated_strategies: int
    top_strategies: List[TopStrategy]
    last_evolution_run_at: str | None


@router.get("/summary", response_model=BrainSummaryResponse)
def get_brain_summary(
    db: Session = Depends(get_db)
):
    """
    Get high-level Brain summary with strategy statistics.
    """
    # PHASE 5: Always return valid JSON, never raise errors
    try:
        # Get all strategies
        all_strategies = db.query(UserStrategy).all()
        total_strategies = len(all_strategies) if all_strategies else 0
        
        # Get active strategies
        active_strategies = db.query(UserStrategy).filter(
            UserStrategy.is_active == True
        ).count() if all_strategies else 0
        
        # Get mutated strategies (those with lineage as children)
        try:
            mutated_strategy_ids = db.query(StrategyLineage.child_strategy_id).distinct().all()
            mutated_strategies = len(mutated_strategy_ids) if mutated_strategy_ids else 0
        except Exception:
            mutated_strategies = 0
        
        # Get top strategies (by score, with backtests)
        top_strategies = []
        try:
            top_strategies_query = db.query(UserStrategy).filter(
                UserStrategy.score.isnot(None),
                UserStrategy.is_active == True
            ).order_by(UserStrategy.score.desc()).limit(10).all()
            
            for strategy in top_strategies_query:
                try:
                    # Get latest backtest for win_rate and avg_return
                    latest_backtest = db.query(StrategyBacktest).filter(
                        StrategyBacktest.strategy_id == strategy.id
                    ).order_by(StrategyBacktest.created_at.desc()).first()
                    
                    # PHASE 5: Use last_backtest_results if StrategyBacktest model doesn't exist
                    if not latest_backtest and strategy.last_backtest_results:
                        results = strategy.last_backtest_results
                        win_rate = results.get("win_rate", 0.0)
                        avg_return = results.get("total_return", 0.0)
                        total_trades = results.get("total_trades", 0)
                    else:
                        win_rate = latest_backtest.win_rate if latest_backtest else 0.0
                        avg_return = latest_backtest.total_return if latest_backtest else 0.0
                        total_trades = latest_backtest.total_trades if latest_backtest else 0
                    
                    top_strategies.append(TopStrategy(
                        strategy_id=strategy.id,
                        name=strategy.name or "Unknown",
                        score=strategy.score or 0.0,
                        win_rate=win_rate,
                        avg_return=avg_return,
                        total_trades=total_trades,
                    ))
                except Exception as e:
                    # Skip this strategy if there's an error
                    print(f"⚠️  Error processing strategy {strategy.id}: {e}")
                    continue
        except Exception as e:
            print(f"⚠️  Error getting top strategies: {e}")
            top_strategies = []
        
        # Get last evolution run (from most recent backtest or mutation)
        last_evolution_run_at = None
        try:
            last_backtest = db.query(StrategyBacktest).order_by(
                StrategyBacktest.created_at.desc()
            ).first()
            last_lineage = db.query(StrategyLineage).order_by(
                StrategyLineage.created_at.desc()
            ).first()
            
            if last_backtest and last_lineage:
                if last_backtest.created_at > last_lineage.created_at:
                    last_evolution_run_at = last_backtest.created_at.isoformat()
                else:
                    last_evolution_run_at = last_lineage.created_at.isoformat()
            elif last_backtest:
                last_evolution_run_at = last_backtest.created_at.isoformat()
            elif last_lineage:
                last_evolution_run_at = last_lineage.created_at.isoformat()
        except Exception:
            # If StrategyBacktest model doesn't exist, try to get from UserStrategy
            try:
                latest_strategy = db.query(UserStrategy).filter(
                    UserStrategy.last_backtest_at.isnot(None)
                ).order_by(UserStrategy.last_backtest_at.desc()).first()
                if latest_strategy and latest_strategy.last_backtest_at:
                    last_evolution_run_at = latest_strategy.last_backtest_at.isoformat()
            except Exception:
                pass
        
        # PHASE 5: Always return valid response (never raise errors)
        return BrainSummaryResponse(
            total_strategies=total_strategies,
            active_strategies=active_strategies,
            mutated_strategies=mutated_strategies,
            top_strategies=top_strategies,  # Can be empty list
            last_evolution_run_at=last_evolution_run_at,
        )
    except Exception as e:
        # PHASE 5: Return default values instead of raising error
        print(f"⚠️  Error generating brain summary: {e}")
        import traceback
        traceback.print_exc()
        return BrainSummaryResponse(
            total_strategies=0,
            active_strategies=0,
            mutated_strategies=0,
            top_strategies=[],
            last_evolution_run_at=None,
        )


class MCNStatsResponse(BaseModel):
    """MCN statistics and debug info."""
    total_events: int
    num_trade_events: int
    num_backtest_events: int
    num_mutation_events: int
    num_signal_events: int
    num_strategies_in_memory: int
    num_users_in_memory: int
    last_update_at: str | None
    mcn_available: bool
    storage_path: str | None


@router.get("/mcn-stats", response_model=MCNStatsResponse)
def get_mcn_stats(
    db: Session = Depends(get_db)
):
    """
    Get MCN statistics and debug information.
    
    Returns counts of events, strategies, users, and last update timestamp.
    """
    try:
        mcn_adapter = get_mcn_adapter()
        mcn_instance = get_mcn_instance()
        
        if not mcn_adapter.is_available or not mcn_instance:
            return MCNStatsResponse(
                total_events=0,
                num_trade_events=0,
                num_backtest_events=0,
                num_mutation_events=0,
                num_signal_events=0,
                num_strategies_in_memory=0,
                num_users_in_memory=0,
                last_update_at=None,
                mcn_available=False,
                storage_path=mcn_adapter.storage_path if mcn_adapter else None,
            )
        
        # Count events by type from MCN store
        total_events = 0
        num_trade_events = 0
        num_backtest_events = 0
        num_mutation_events = 0
        num_signal_events = 0
        strategies_in_memory = set()
        users_in_memory = set()
        last_update_at = None
        
        if hasattr(mcn_instance, 'store') and hasattr(mcn_instance.store, 'meta'):
            meta_list = mcn_instance.store.meta
            total_events = len(meta_list)
            
            for meta in meta_list:
                event_type = meta.get("event_type", "")
                if "trade" in event_type.lower():
                    num_trade_events += 1
                elif "backtest" in event_type.lower():
                    num_backtest_events += 1
                elif "mutat" in event_type.lower():
                    num_mutation_events += 1
                elif "signal" in event_type.lower():
                    num_signal_events += 1
                
                # Extract strategy and user IDs
                strategy_id = meta.get("strategy_id")
                if strategy_id:
                    strategies_in_memory.add(strategy_id)
                
                user_id = meta.get("user_id")
                if user_id:
                    users_in_memory.add(user_id)
                
                # Track latest timestamp
                timestamp = meta.get("timestamp")
                if timestamp:
                    try:
                        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        if last_update_at is None or ts > datetime.fromisoformat(last_update_at.replace("Z", "+00:00")):
                            last_update_at = timestamp
                    except:
                        pass
        
        # If no timestamp found, use current time
        if last_update_at is None:
            last_update_at = datetime.now().isoformat()
        
        return MCNStatsResponse(
            total_events=total_events,
            num_trade_events=num_trade_events,
            num_backtest_events=num_backtest_events,
            num_mutation_events=num_mutation_events,
            num_signal_events=num_signal_events,
            num_strategies_in_memory=len(strategies_in_memory),
            num_users_in_memory=len(users_in_memory),
            last_update_at=last_update_at,
            mcn_available=True,
            storage_path=mcn_adapter.storage_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting MCN stats: {str(e)}"
        )

