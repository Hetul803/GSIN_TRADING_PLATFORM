# backend/api/admin_health.py
"""
PHASE 2: System Health Check API endpoint.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db.models import UserRole
from ..db import crud
from ..market_data.market_data_provider import get_provider

router = APIRouter(prefix="/admin/health", tags=["admin"])


def verify_admin(db: Session, user_id: str) -> None:
    """Verify that the user is an admin."""
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


class HealthCheckResponse(BaseModel):
    status: str  # "ok" | "degraded" | "down"
    details: Dict[str, Any]


@router.get("", response_model=HealthCheckResponse)
async def get_system_health(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Check system health (admin only)."""
    verify_admin(db, user_id)
    
    health_details = {}
    overall_status = "ok"
    
    # Check database
    db_status = "ok"
    try:
        db.execute("SELECT 1")
        health_details["database"] = {"status": "ok", "message": "Connected"}
    except Exception as e:
        db_status = "down"
        health_details["database"] = {"status": "down", "message": str(e)}
        overall_status = "down"
    
    # Check Twelve Data
    twelve_data_status = "ok"
    try:
        provider = get_provider()
        if provider:
            test_price = provider.get_price("AAPL")
            if test_price:
                health_details["twelve_data"] = {"status": "ok", "message": "API responding"}
            else:
                twelve_data_status = "degraded"
                health_details["twelve_data"] = {"status": "degraded", "message": "API returned no data"}
                if overall_status == "ok":
                    overall_status = "degraded"
        else:
            twelve_data_status = "degraded"
            health_details["twelve_data"] = {"status": "degraded", "message": "Provider not available"}
            if overall_status == "ok":
                overall_status = "degraded"
    except Exception as e:
        twelve_data_status = "down"
        health_details["twelve_data"] = {"status": "down", "message": str(e)}
        if overall_status == "ok":
            overall_status = "degraded"
    
    # Check Alpaca (paper only - simplified)
    alpaca_status = "ok"
    try:
        # Just check if env vars are set (simplified check)
        import os
        if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
            health_details["alpaca"] = {"status": "ok", "message": "Credentials configured"}
        else:
            alpaca_status = "degraded"
            health_details["alpaca"] = {"status": "degraded", "message": "Credentials not configured"}
    except Exception as e:
        alpaca_status = "degraded"
        health_details["alpaca"] = {"status": "degraded", "message": str(e)}
    
    # Check evolution worker (simplified - would need heartbeat tracking)
    evolution_status = "unknown"
    health_details["evolution_worker"] = {
        "status": "unknown",
        "message": "Heartbeat tracking not implemented"
    }
    
    return HealthCheckResponse(
        status=overall_status,
        details=health_details,
    )

