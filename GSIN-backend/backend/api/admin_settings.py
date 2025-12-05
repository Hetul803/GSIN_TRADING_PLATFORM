# backend/api/admin_settings.py
"""
PHASE 2: Admin Settings API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db.models import AdminSettings, UserRole
from ..db import crud

router = APIRouter(prefix="/admin/settings", tags=["admin"])


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


class AdminSettingsResponse(BaseModel):
    platform_fee_percent: float
    creator_fee_percent: float
    pnl_fee_threshold_usd: float
    grace_months_for_good_users: int
    basic_price: float
    pro_price: float
    creator_price: float
    max_concurrent_backtests: int
    updated_at: str
    updated_by: Optional[str] = None


class AdminSettingsUpdateRequest(BaseModel):
    platform_fee_percent: Optional[float] = None
    creator_fee_percent: Optional[float] = None
    pnl_fee_threshold_usd: Optional[float] = None
    grace_months_for_good_users: Optional[int] = None
    basic_price: Optional[float] = None
    pro_price: Optional[float] = None
    creator_price: Optional[float] = None
    max_concurrent_backtests: Optional[int] = None


@router.get("", response_model=AdminSettingsResponse)
async def get_admin_settings(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get current admin settings."""
    verify_admin(db, user_id)
    
    settings = db.query(AdminSettings).filter(AdminSettings.id == "default").first()
    if not settings:
        # Create default settings
        settings = AdminSettings(id="default")
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return AdminSettingsResponse(
        platform_fee_percent=settings.platform_fee_percent,
        creator_fee_percent=settings.creator_fee_percent,
        pnl_fee_threshold_usd=settings.pnl_fee_threshold_usd,
        grace_months_for_good_users=settings.grace_months_for_good_users,
        basic_price=settings.basic_price,
        pro_price=settings.pro_price,
        creator_price=settings.creator_price,
        max_concurrent_backtests=getattr(settings, 'max_concurrent_backtests', 3),
        updated_at=settings.updated_at.isoformat() if settings.updated_at else "",
        updated_by=settings.updated_by,
    )


@router.put("", response_model=AdminSettingsResponse)
async def update_admin_settings(
    request: AdminSettingsUpdateRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Update admin settings."""
    verify_admin(db, user_id)
    
    settings = db.query(AdminSettings).filter(AdminSettings.id == "default").first()
    if not settings:
        settings = AdminSettings(id="default")
        db.add(settings)
    
    if request.platform_fee_percent is not None:
        settings.platform_fee_percent = request.platform_fee_percent
    if request.creator_fee_percent is not None:
        settings.creator_fee_percent = request.creator_fee_percent
    if request.pnl_fee_threshold_usd is not None:
        settings.pnl_fee_threshold_usd = request.pnl_fee_threshold_usd
    if request.grace_months_for_good_users is not None:
        settings.grace_months_for_good_users = request.grace_months_for_good_users
    if request.basic_price is not None:
        settings.basic_price = request.basic_price
    if request.pro_price is not None:
        settings.pro_price = request.pro_price
    if request.creator_price is not None:
        settings.creator_price = request.creator_price
    if request.max_concurrent_backtests is not None:
        if request.max_concurrent_backtests < 1 or request.max_concurrent_backtests > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="max_concurrent_backtests must be between 1 and 20"
            )
        settings.max_concurrent_backtests = request.max_concurrent_backtests
        # Update the backtest worker with new max_workers
        from ..workers.backtest_worker import get_backtest_worker
        worker = get_backtest_worker()
        worker.update_max_workers(request.max_concurrent_backtests)
    
    settings.updated_by = user_id
    from datetime import datetime, timezone
    settings.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(settings)
    
    return AdminSettingsResponse(
        platform_fee_percent=settings.platform_fee_percent,
        creator_fee_percent=settings.creator_fee_percent,
        pnl_fee_threshold_usd=settings.pnl_fee_threshold_usd,
        grace_months_for_good_users=settings.grace_months_for_good_users,
        basic_price=settings.basic_price,
        pro_price=settings.pro_price,
        creator_price=settings.creator_price,
        max_concurrent_backtests=getattr(settings, 'max_concurrent_backtests', 3),
        updated_at=settings.updated_at.isoformat() if settings.updated_at else "",
        updated_by=settings.updated_by,
    )

