# backend/api/royalties.py
"""
PHASE 5: Royalty API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from ..db.models import RoyaltyLedger

router = APIRouter(prefix="/royalties", tags=["royalties"])


class RoyaltyResponse(BaseModel):
    id: str
    user_id: str
    strategy_id: Optional[str]
    trade_id: str
    royalty_amount: float
    royalty_rate: float
    platform_fee: float
    platform_fee_rate: float
    net_amount: float
    trade_profit: float
    created_at: str
    
    class Config:
        from_attributes = True


@router.get("/me", response_model=List[RoyaltyResponse])
async def get_my_royalties(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get royalties received by the current user (as strategy owner).
    """
    royalties = db.query(RoyaltyLedger).filter(
        RoyaltyLedger.user_id == user_id
    ).order_by(RoyaltyLedger.created_at.desc()).offset(offset).limit(limit).all()
    
    return [
        RoyaltyResponse(
            id=r.id,
            user_id=r.user_id,
            strategy_id=r.strategy_id,
            trade_id=r.trade_id,
            royalty_amount=r.royalty_amount,
            royalty_rate=r.royalty_rate,
            platform_fee=r.platform_fee,
            platform_fee_rate=r.platform_fee_rate,
            net_amount=r.net_amount,
            trade_profit=r.trade_profit,
            created_at=r.created_at.isoformat()
        )
        for r in royalties
    ]


@router.get("/summary")
async def get_royalty_summary(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get royalty summary for the current user.
    """
    from sqlalchemy import func
    
    total_royalties = db.query(func.sum(RoyaltyLedger.royalty_amount)).filter(
        RoyaltyLedger.user_id == user_id
    ).scalar() or 0.0
    
    total_platform_fees = db.query(func.sum(RoyaltyLedger.platform_fee)).filter(
        RoyaltyLedger.user_id == user_id
    ).scalar() or 0.0
    
    total_net = db.query(func.sum(RoyaltyLedger.net_amount)).filter(
        RoyaltyLedger.user_id == user_id
    ).scalar() or 0.0
    
    count = db.query(func.count(RoyaltyLedger.id)).filter(
        RoyaltyLedger.user_id == user_id
    ).scalar() or 0
    
    return {
        "total_royalties": float(total_royalties),
        "total_platform_fees": float(total_platform_fees),
        "total_net_paid": float(total_net),  # Changed from total_net_amount to match frontend
        "count": count  # Changed from total_trades to match frontend
    }


# PHASE 4: Monthly billing endpoints
@router.get("/billing/status")
async def get_billing_status(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    month: Optional[int] = None,
    year: Optional[int] = None
):
    """
    Get billing status for the current user (outstanding royalties, payment status).
    """
    from ..services.royalty_billing import royalty_billing_service
    
    payment_status = royalty_billing_service.check_payment_status(user_id, db)
    monthly_total = royalty_billing_service.calculate_monthly_total(user_id, db, month, year)
    
    return {
        "payment_status": payment_status,
        "monthly_total": monthly_total
    }


@router.post("/billing/process")
async def process_billing(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    month: Optional[int] = None,
    year: Optional[int] = None
):
    """
    Process monthly billing for the current user (attempts Stripe charge).
    """
    from ..services.royalty_billing import royalty_billing_service
    
    result = royalty_billing_service.process_monthly_billing(user_id, db, month, year)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to process billing")
        )
    
    return result


# PHASE 4: Admin override endpoints
@router.post("/billing/admin-override")
async def admin_override_billing(
    target_user_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Admin-only: Override billing for a user (mark as paid without charge).
    """
    from ..db.models import UserRole
    from ..db import crud
    
    # Check if user is admin
    user = crud.get_user_by_id(db, user_id)
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    from ..services.royalty_billing import royalty_billing_service
    
    result = royalty_billing_service.process_monthly_billing(
        target_user_id, db, month, year, admin_override=True
    )
    
    return result

