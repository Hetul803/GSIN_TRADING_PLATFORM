# backend/api/admin_promo.py
"""
PHASE 2: Promo Code API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db.models import PromoCode, UserRole
from ..db import crud

router = APIRouter(prefix="/admin/promo", tags=["admin"])


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


class PromoCodeCreateRequest(BaseModel):
    code: str
    discount_percent: Optional[float] = None
    discount_amount: Optional[float] = None
    applicable_tiers: List[str] = []
    max_uses: Optional[int] = None
    expiry_date: Optional[str] = None  # ISO format


class PromoCodeResponse(BaseModel):
    id: str
    code: str
    discount_percent: Optional[float]
    discount_amount: Optional[float]
    applicable_tiers: List[str]
    max_uses: Optional[int]
    current_uses: int
    expiry_date: Optional[str]
    is_active: bool
    created_at: str
    created_by: Optional[str]


@router.post("", response_model=PromoCodeResponse)
async def create_promo_code(
    request: PromoCodeCreateRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Create a new promo code."""
    verify_admin(db, user_id)
    
    # Check if code already exists
    existing = db.query(PromoCode).filter(PromoCode.code == request.code.upper()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promo code already exists"
        )
    
    # Validate discount
    if request.discount_percent is None and request.discount_amount is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either discount_percent or discount_amount must be provided"
        )
    
    # Parse expiry date
    expiry_date = None
    if request.expiry_date:
        try:
            expiry_date = datetime.fromisoformat(request.expiry_date.replace("Z", "+00:00"))
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid expiry_date format. Use ISO format."
            )
    
    promo = PromoCode(
        id=str(uuid.uuid4()),
        code=request.code.upper(),
        discount_percent=request.discount_percent,
        discount_amount=request.discount_amount,
        applicable_tiers=request.applicable_tiers or [],
        max_uses=request.max_uses,
        expiry_date=expiry_date,
        is_active=True,
        created_by=user_id,
    )
    
    db.add(promo)
    db.commit()
    db.refresh(promo)
    
    return PromoCodeResponse(
        id=promo.id,
        code=promo.code,
        discount_percent=promo.discount_percent,
        discount_amount=promo.discount_amount,
        applicable_tiers=promo.applicable_tiers or [],
        max_uses=promo.max_uses,
        current_uses=promo.current_uses,
        expiry_date=promo.expiry_date.isoformat() if promo.expiry_date else None,
        is_active=promo.is_active,
        created_at=promo.created_at.isoformat() if promo.created_at else "",
        created_by=promo.created_by,
    )


@router.get("", response_model=List[PromoCodeResponse])
async def list_promo_codes(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    active_only: bool = Query(False, description="Filter to active codes only")
):
    """List all promo codes."""
    verify_admin(db, user_id)
    
    query = db.query(PromoCode)
    if active_only:
        query = query.filter(PromoCode.is_active == True)
    
    promos = query.order_by(PromoCode.created_at.desc()).all()
    
    return [
        PromoCodeResponse(
            id=p.id,
            code=p.code,
            discount_percent=p.discount_percent,
            discount_amount=p.discount_amount,
            applicable_tiers=p.applicable_tiers or [],
            max_uses=p.max_uses,
            current_uses=p.current_uses,
            expiry_date=p.expiry_date.isoformat() if p.expiry_date else None,
            is_active=p.is_active,
            created_at=p.created_at.isoformat() if p.created_at else "",
            created_by=p.created_by,
        )
        for p in promos
    ]


@router.delete("/{promo_id}")
async def delete_promo_code(
    promo_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Delete a promo code."""
    verify_admin(db, user_id)
    
    promo = db.query(PromoCode).filter(PromoCode.id == promo_id).first()
    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promo code not found"
        )
    
    db.delete(promo)
    db.commit()
    
    return {"message": "Promo code deleted"}

