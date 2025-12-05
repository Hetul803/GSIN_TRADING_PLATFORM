# backend/api/monitoring.py
"""
Monitoring and metrics endpoints for system observability.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from ..db.models import UserRole
from ..utils.performance_monitor import get_performance_monitor
from ..utils.response_cache import get_cache
from ..workers.evolution_worker import EvolutionWorker
from ..workers.monitoring_worker import MonitoringWorker

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def verify_admin(user_id: str, db: Session):
    """Verify user is admin."""
    user = crud.get_user_by_id(db, user_id)
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/metrics")
async def get_metrics(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get system performance metrics (admin only)."""
    verify_admin(user_id, db)
    
    monitor = get_performance_monitor()
    cache = get_cache()
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "performance": monitor.get_all_stats(),
        "cache": {
            "size": cache.size(),
            "operations": {
                "cleanup_expired": cache.cleanup_expired()
            }
        },
        "workers": {
            "evolution": {
                "status": "running",  # Would need to check actual worker status
                "last_run": None  # Would need to track this
            },
            "monitoring": {
                "status": "running",
                "last_run": None
            }
        }
    }


@router.get("/health/detailed")
async def get_detailed_health(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get detailed health information (admin only)."""
    verify_admin(user_id, db)
    
    from ..db.session import engine
    from ..market_data.market_data_provider import get_provider
    
    health = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {"status": "unknown"},
        "market_data": {"status": "unknown"},
        "cache": {"status": "unknown"},
        "workers": {"status": "unknown"}
    }
    
    # Database health
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        health["database"] = {"status": "healthy", "connection": "ok"}
    except Exception as e:
        health["database"] = {"status": "unhealthy", "error": str(e)}
    
    # Market data health
    try:
        provider = get_provider()
        if provider:
            health["market_data"] = {"status": "healthy", "provider": provider.__class__.__name__}
        else:
            health["market_data"] = {"status": "degraded", "message": "No provider available"}
    except Exception as e:
        health["market_data"] = {"status": "unhealthy", "error": str(e)}
    
    # Cache health
    try:
        cache = get_cache()
        health["cache"] = {
            "status": "healthy",
            "size": cache.size(),
            "operations": cache.cleanup_expired()
        }
    except Exception as e:
        health["cache"] = {"status": "unhealthy", "error": str(e)}
    
    # Workers health
    health["workers"] = {
        "evolution": {"status": "running"},  # Would need actual status tracking
        "monitoring": {"status": "running"}
    }
    
    return health

