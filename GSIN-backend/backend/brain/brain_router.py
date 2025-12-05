# backend/brain/brain_router.py
"""
Brain Router (L3) - API endpoints for Brain layer.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
import os

from ..db.session import get_db
from ..db import crud
from ..db.models import StrategyLineage, StrategyBacktest
from .brain_service import BrainService
from .explanation_engine import ExplanationEngine
from .recommended_strategies import RecommendedStrategiesService
from .types import (
    BrainSignalResponse,
    BrainBacktestResponse,
    BrainMutationResponse,
    BrainContextResponse,
)
from .mcn_adapter import get_mcn_adapter
from ..utils.jwt_deps import get_current_user_id_dep

router = APIRouter(prefix="/brain", tags=["brain"])


@router.get("/signal/{strategy_id}", response_model=BrainSignalResponse)
async def get_brain_signal(
    strategy_id: str,
    symbol: str = Query(..., description="Symbol to generate signal for (e.g., AAPL)"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Generate an MCN-enhanced trading signal.
    
    Combines Strategy Engine (L2) + Market Data (L1) + MCN (L3) to produce
    an enhanced signal with confidence, reasoning, and market context.
    """
    service = BrainService()
    try:
        signal = await service.generate_signal(
            strategy_id=strategy_id,
            user_id=user_id,
            symbol=symbol,
            db=db,
        )
        return signal
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signal generation failed: {str(e)}"
        )


@router.post("/backtest/{strategy_id}", response_model=BrainBacktestResponse)
async def run_brain_backtest(
    strategy_id: str,
    symbol: str = Query(..., description="Symbol to backtest (e.g., AAPL)"),
    timeframe: str = Query("1d", description="Timeframe (e.g., 1d, 1h)"),
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Run an MCN-enhanced backtest.
    
    Combines basic backtest (L2) with MCN memory adjustments (L3) to produce
    enhanced metrics including regime fit and historical pattern matching.
    """
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}"
        )
    
    service = BrainService()
    try:
        backtest = service.backtest_with_memory(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start,
            end_date=end,
            db=db,
        )
        return backtest
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {str(e)}"
        )


@router.post("/mutate/{strategy_id}", response_model=BrainMutationResponse)
async def run_brain_mutation(
    strategy_id: str,
    num_mutations: int = Query(3, ge=1, le=3, description="Number of mutations to create (1-3)"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Create MCN-enhanced strategy mutations.
    
    Combines basic mutation (L2) with MCN-guided refinements (L3) to produce
    improved mutated strategies with parameter adjustments.
    """
    service = BrainService()
    try:
        mutation = service.mutate_with_memory(
            strategy_id=strategy_id,
            num_mutations=num_mutations,
            db=db,
        )
        return mutation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mutation failed: {str(e)}"
        )


@router.get("/context/{user_id}", response_model=BrainContextResponse)
async def get_brain_context(
    user_id: str,
    current_user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get Brain context summary for a user.
    
    Returns market regime, user risk profile, relevant strategy clusters,
    and sentiment summary.
    """
    # Check that user is requesting their own context
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own context"
        )
    
    service = BrainService()
    try:
        context = service.context_summary(
            user_id=user_id,
            db=db,
        )
        return context
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Context retrieval failed: {str(e)}"
        )


@router.get("/health")
def brain_health():
    """
    PHASE 7: Check Brain/MCN health status with detailed diagnostics.
    """
    mcn_adapter = get_mcn_adapter()
    
    # PHASE 7: Enhanced health check
    health_info = {
        "mcn_available": mcn_adapter.is_available,
        "status": "healthy" if mcn_adapter.is_available else "degraded",
        "message": "MCN is available" if mcn_adapter.is_available else "MCN is not available - using fallback mode",
        "storage_path": mcn_adapter.storage_path if mcn_adapter else None,
        "is_stub_mode": mcn_adapter.is_stub_mode if mcn_adapter else True,
        "embedder_available": mcn_adapter.embedder is not None if mcn_adapter else False,
    }
    
    # Check if storage file exists
    if mcn_adapter and mcn_adapter.storage_path:
        storage_file = os.path.join(mcn_adapter.storage_path, "mcn_state.npz")
        health_info["storage_file_exists"] = os.path.exists(storage_file)
        if os.path.exists(storage_file):
            try:
                file_size = os.path.getsize(storage_file)
                health_info["storage_file_size"] = file_size
            except:
                pass
    
    return health_info


@router.get("/explain/{strategy_id}")
async def explain_signal(
    strategy_id: str,
    symbol: str = Query(..., description="Symbol to explain signal for (e.g., AAPL)"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    PHASE 4: Get detailed explanation for a trading signal.
    
    Returns comprehensive breakdown of:
    - Market regime and why it matters
    - Volume confirmation
    - Trend alignment
    - Risk checks
    - MCN context
    - Confidence breakdown
    - Strategy lineage
    """
    service = BrainService()
    explanation_engine = ExplanationEngine()
    
    try:
        # Generate signal first
        signal = await service.generate_signal(
            strategy_id=strategy_id,
            user_id=user_id,
            symbol=symbol,
            db=db,
        )
        
        # Get strategy
        strategy = crud.get_user_strategy(db, strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        # Generate explanation
        context = signal.mcn_adjustments or {}
        explanation = explanation_engine.explain_signal(
            signal=signal,
            strategy=strategy,
            context=context,
            db=db
        )
        
        return {
            "signal": signal,
            "explanation": explanation
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Explanation generation failed: {str(e)}"
        )


@router.get("/recommended-strategies")
async def get_recommended_strategies(
    symbol: Optional[str] = Query(None, description="Optional symbol to filter by (e.g., AAPL)"),
    timeframe: Optional[str] = Query(None, description="Optional timeframe to filter by (e.g., 1d)"),
    limit: int = Query(10, ge=1, le=20, description="Maximum number of recommendations (1-20)"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get Brain-recommended strategies for the current user.
    
    Combines:
    - Seeded proven strategies (40+)
    - User's own strategies
    - MCN regime compatibility
    - User risk profile
    - Recent backtest performance
    
    Returns a list of recommended strategies with:
    - strategy_id
    - name
    - description
    - recent_backtest_metrics (winrate, avg_rr, sample_size)
    - regime_compatibility_score
    - confidence (0-1)
    - estimated_profit_range (with disclaimer)
    - why_recommended (explanation)
    """
    # Cache expensive recommendation calculation (2 minute TTL - recommendations can change with market)
    from ..utils.response_cache import get_cache
    cache = get_cache()
    
    cache_key = f"recommended_strategies:{user_id}:{symbol or 'all'}:{timeframe or 'all'}:{limit}"
    cached_result = cache.get("recommended_strategies", user_id, symbol or "", timeframe or "", limit, ttl_seconds=120)
    if cached_result is not None:
        return cached_result
    
    # PHASE 5: Always return valid JSON, never raise errors
    service = RecommendedStrategiesService()
    try:
        recommendations = service.get_recommended_strategies(
            user_id=user_id,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            db=db,
        )
        # PHASE 5: Ensure recommendations is never None
        if recommendations is None:
            recommendations = []
        
        result = {
            "recommendations": recommendations,
            "count": len(recommendations),
            "disclaimer": "These recommendations are based on historical backtests and are NOT guaranteed. Markets can behave differently. Past performance does not guarantee future results.",
        }
        
        # Cache the result
        cache.set("recommended_strategies", result, user_id, symbol or "", timeframe or "", limit, ttl_seconds=120)
        
        return result
    except Exception as e:
        # PHASE 5: Return empty recommendations instead of raising error
        print(f"⚠️  Error getting recommended strategies: {e}")
        import traceback
        traceback.print_exc()
        return {
            "recommendations": [{
                "strategy_id": "error",
                "name": "Unable to load recommendations",
                "description": "The Brain is temporarily unavailable. Please try again later.",
                "is_seeded": False,
                "recent_backtest_metrics": {
                    "winrate": 0.0,
                    "avg_rr": 0.0,
                    "sample_size": 0,
                    "avg_return": 0.0
                },
                "regime_compatibility_score": 0.0,
                "confidence": 0.0,
                "estimated_profit_range": {
                    "min_pct": 0.0,
                    "max_pct": 0.0,
                    "expected_pct": 0.0,
                    "disclaimer": "No data available."
                },
                "why_recommended": "Service temporarily unavailable."
            }],
            "count": 1,
            "disclaimer": "These recommendations are based on historical backtests and are NOT guaranteed. Markets can behave differently. Past performance does not guarantee future results.",
        }


@router.get("/summary")
async def get_brain_summary(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    IMPROVEMENT 2: Get Brain/Evolution summary showing strategy evolution and performance.
    
    NEVER returns 500 - always returns safe defaults if no data exists.
    
    Returns:
    {
        "total_strategies": int,
        "active_strategies": int,
        "mutated_strategies": int,
        "proposable_strategies": int,
        "top_strategies": [...],
        "last_evolution_run_at": str (ISO datetime) | null,
        "message": str (optional message if no strategies)
    }
    """
    # IMPROVEMENT 2: Always return valid JSON, never raise errors
    try:
        # Get all strategies for user (with error handling)
        try:
            all_strategies = crud.list_user_strategies(db, user_id, active_only=False)
            total_strategies = len(all_strategies) if all_strategies else 0
        except Exception as e:
            print(f"⚠️  Error listing strategies: {e}")
            all_strategies = []
            total_strategies = 0
        
        # Count active strategies
        try:
            active_strategies = len([s for s in all_strategies if s.is_active]) if all_strategies else 0
        except Exception:
            active_strategies = 0
        
        # Count proposable strategies (IMPROVEMENT 2: Add this metric)
        try:
            proposable_strategies = len([s for s in all_strategies if s.is_proposable and s.status == "proposable"]) if all_strategies else 0
        except Exception:
            proposable_strategies = 0
        
        # Count mutated strategies (those with lineage as children)
        mutated_count = 0
        try:
            from ..db.models import StrategyLineage
            if all_strategies:
                mutated_count = db.query(StrategyLineage).filter(
                    StrategyLineage.child_strategy_id.in_([s.id for s in all_strategies])
                ).count()
        except Exception as e:
            print(f"⚠️  Error counting mutated strategies: {e}")
            mutated_count = 0
        
        # Get top strategies (by score, limit to top 10)
        top_strategies = []
        try:
            if all_strategies:
                top_strategies_list = sorted(
                    [s for s in all_strategies if s.score is not None],
                    key=lambda x: x.score or 0.0,
                    reverse=True
                )[:10]
                
                # Format top strategies
                for strategy in top_strategies_list:
                    try:
                        # Extract win_rate and avg_return from last_backtest_results
                        win_rate = 0.0
                        avg_return = 0.0
                        
                        if strategy.last_backtest_results:
                            win_rate = strategy.last_backtest_results.get("win_rate", 0.0) or 0.0
                            avg_return = strategy.last_backtest_results.get("total_return", 0.0) or 0.0
                        
                        top_strategies.append({
                            "strategy_id": strategy.id,
                            "name": strategy.name or "Unknown",
                            "score": strategy.score or 0.0,
                            "win_rate": win_rate,
                            "avg_return": avg_return
                        })
                    except Exception as e:
                        print(f"⚠️  Error formatting strategy {strategy.id}: {e}")
                        continue
        except Exception as e:
            print(f"⚠️  Error getting top strategies: {e}")
            top_strategies = []
        
        # Get last evolution run time (from most recent mutation or backtest)
        last_evolution = None
        try:
            from ..db.models import StrategyLineage, StrategyBacktest
            
            # Check for most recent mutation
            recent_mutation = None
            if all_strategies:
                recent_mutation = db.query(StrategyLineage).filter(
                    StrategyLineage.child_strategy_id.in_([s.id for s in all_strategies])
                ).order_by(StrategyLineage.created_at.desc()).first()
            
            # Check for most recent backtest
            recent_backtest = None
            if all_strategies:
                recent_backtest = db.query(StrategyBacktest).filter(
                    StrategyBacktest.strategy_id.in_([s.id for s in all_strategies])
                ).order_by(StrategyBacktest.created_at.desc()).first()
            
            if recent_mutation and recent_backtest:
                last_evolution = max(recent_mutation.created_at, recent_backtest.created_at)
            elif recent_mutation:
                last_evolution = recent_mutation.created_at
            elif recent_backtest:
                last_evolution = recent_backtest.created_at
        except Exception as e:
            print(f"⚠️  Error getting last evolution time: {e}")
            last_evolution = None
        
        # IMPROVEMENT 2: Add message if no strategies
        message = None
        if total_strategies == 0:
            message = "No strategies yet. The Brain is ready to evolve strategies once they are created."
        elif active_strategies == 0:
            message = "No active strategies. Strategies will become active after backtesting."
        
        # Always return valid JSON
        return {
            "total_strategies": total_strategies,
            "active_strategies": active_strategies,
            "mutated_strategies": mutated_count,
            "proposable_strategies": proposable_strategies,  # IMPROVEMENT 2: New field
            "top_strategies": top_strategies,
            "last_evolution_run_at": last_evolution.isoformat() if last_evolution else None,
            "message": message  # IMPROVEMENT 2: Optional message
        }
    except Exception as e:
        # IMPROVEMENT 2: Return safe defaults, never raise
        print(f"⚠️  Error getting brain summary: {e}")
        import traceback
        traceback.print_exc()
        return {
            "total_strategies": 0,
            "active_strategies": 0,
            "mutated_strategies": 0,
            "proposable_strategies": 0,
            "top_strategies": [],
            "last_evolution_run_at": None,
            "message": "Unable to load summary. Please try again later."
        }

