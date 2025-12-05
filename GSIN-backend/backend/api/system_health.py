# backend/api/system_health.py
"""
PHASE 6: System health check endpoint.

Returns:
{
  "websocket_ok": true,
  "market_data_ok": true,
  "strategy_engine_ok": true,
  "evolution_phase": "growth",
  "mcn_vectors": 213,
  "twelvedata_credits_remaining": 311
}

Endpoint never fails, always returns diagnostic.
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..utils.jwt_deps import get_current_user_id_dep
from ..strategy_engine.strategy_thresholds import get_evolution_phase
from ..brain.mcn_adapter import get_mcn_adapter
from ..market_data.market_data_provider import get_historical_provider

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health-check")
def health_check(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    PHASE 6: System health check endpoint.
    Never fails, always returns diagnostic.
    """
    result: Dict[str, Any] = {
        "websocket_ok": False,
        "market_data_ok": False,
        "strategy_engine_ok": False,
        "evolution_phase": "unknown",
        "mcn_vectors": 0,
        "twelvedata_credits_remaining": 0,
    }
    
    # Check WebSocket (simplified - just check if manager exists)
    try:
        from ..api.websocket import manager
        result["websocket_ok"] = manager is not None
    except Exception as e:
        result["websocket_error"] = str(e)
    
    # Check market data provider
    try:
        provider = get_historical_provider()
        result["market_data_ok"] = provider is not None
        if provider:
            result["market_data_provider"] = provider.__class__.__name__
    except Exception as e:
        result["market_data_error"] = str(e)
    
    # Check strategy engine (simplified - just check if BacktestEngine can be imported)
    try:
        from ..strategy_engine.backtest_engine import BacktestEngine
        engine = BacktestEngine()
        result["strategy_engine_ok"] = engine is not None
    except Exception as e:
        result["strategy_engine_error"] = str(e)
    
    # Get evolution phase
    try:
        phase, phase_info = get_evolution_phase(db)
        result["evolution_phase"] = phase_info["name"]
        result["evolution_phase_info"] = phase_info
    except Exception as e:
        result["evolution_phase_error"] = str(e)
    
    # PHASE E: Get MCN vector count from all 5 MCN categories with robust error handling
    try:
        mcn_adapter = get_mcn_adapter()
        mcn_category_stats = {}
        total_vectors = 0
        
        if mcn_adapter and mcn_adapter.is_available:
            # PHASE E: Count vectors in each MCN category
            mcn_categories = {
                "regime": mcn_adapter.mcn_regime,
                "strategy": mcn_adapter.mcn_strategy,
                "user": mcn_adapter.mcn_user,
                "market": mcn_adapter.mcn_market,
                "trade": mcn_adapter.mcn_trade,
            }
            
            for category, mcn_instance in mcn_categories.items():
                if mcn_instance:
                    try:
                        mcn_vals = None
                        if hasattr(mcn_instance, 'vals'):
                            mcn_vals = getattr(mcn_instance, 'vals', None)
                        
                        if mcn_vals is not None:
                            try:
                                if hasattr(mcn_vals, '__len__'):
                                    category_count = len(mcn_vals)
                                elif hasattr(mcn_vals, 'shape'):
                                    category_count = mcn_vals.shape[0] if len(mcn_vals.shape) > 0 else 0
                                else:
                                    category_count = 0
                                total_vectors += category_count
                                mcn_category_stats[category] = category_count
                            except (AttributeError, TypeError, ValueError, MemoryError):
                                mcn_category_stats[category] = 0
                        else:
                            mcn_category_stats[category] = 0
                    except (AttributeError, TypeError, ValueError, MemoryError) as mcn_err:
                        mcn_category_stats[category] = 0
        
        result["mcn_vectors"] = total_vectors
        result["mcn_category_stats"] = mcn_category_stats
    except (Exception, MemoryError, AttributeError) as e:
        result["mcn_vectors"] = 0
        result["mcn_error"] = f"MCN error (non-fatal): {type(e).__name__}"
    
    # Get Twelve Data credits (simplified - would need API call in production)
    # For now, return a placeholder
    try:
        # In production, this would call Twelve Data API to get remaining credits
        # For now, return a reasonable estimate based on rate limits
        result["twelvedata_credits_remaining"] = 377  # Per minute for Grow plan
        result["twelvedata_note"] = "Estimated based on plan limits"
    except Exception as e:
        result["twelvedata_error"] = str(e)
    
    return result

