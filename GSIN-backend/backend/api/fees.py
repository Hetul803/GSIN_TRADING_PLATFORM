# backend/api/fees.py
"""
FIX 5: Fee calculation and payment endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..db.session import get_db
from ..db.models import User  # FIX 5: Import User model
from ..utils.jwt_deps import get_current_user_id_dep
from ..services.fee_service import fee_service
from ..services.stripe_service import charge_customer_for_fees  # FIX 5: Import function directly

router = APIRouter(prefix="/fees", tags=["fees"])


@router.get("/calculate")
async def calculate_fees(
    user_id: str = Depends(get_current_user_id_dep),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12), defaults to current month"),
    year: Optional[int] = Query(None, description="Year, defaults to current year"),
    db: Session = Depends(get_db)
):
    """
    FIX 5: Calculate platform fees for a user.
    
    Rules:
    - Only applies if monthly PNL > $1000 (REAL mode)
    - Fee rate: 5% general, 3% for creators (admin configurable)
    - Returns 0 if PNL <= $1000 or PAPER mode
    
    Returns:
        Dictionary with fee calculation details
    """
    try:
        fee_calculation = fee_service.calculate_platform_fee(user_id, db, month, year)
        return fee_calculation
    except Exception as e:
        print(f"⚠️  Error calculating fees: {e}")
        return {
            "user_id": user_id,
            "monthly_pnl": 0.0,
            "platform_fee": 0.0,
            "platform_fee_rate": 0.0,
            "reason": f"Error: {str(e)}"
        }


@router.post("/pay")
async def pay_fees(
    user_id: str = Depends(get_current_user_id_dep),
    amount: float = Query(..., ge=0, description="Amount to pay"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month being paid for"),
    year: Optional[int] = Query(None, description="Year being paid for"),
    db: Session = Depends(get_db)
):
    """
    FIX 5: Process fee payment via Stripe.
    
    Only applies to REAL mode fees.
    """
    try:
        # Calculate fees
        fee_calculation = fee_service.calculate_platform_fee(user_id, db, month, year)
        
        if fee_calculation["platform_fee"] <= 0:
            return {
                "success": False,
                "message": "No fees to pay",
                "fee_calculation": fee_calculation
            }
        
        # FIX 5: Process Stripe payment
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # FIX 5: Create or get Stripe customer (use imported function directly)
        payment_intent = charge_customer_for_fees(
            user_id=user_id,
            user_email=user.email,
            amount_cents=int(amount * 100),  # Convert to cents
            description=f"Platform fee for {month or datetime.now().month}/{year or datetime.now().year}",
            metadata={"type": "platform_fee"}
        )
        
        return {
            "success": True,
            "payment_intent_id": payment_intent.get("id") or payment_intent.get("payment_intent_id"),
            "amount": amount,
            "fee_calculation": fee_calculation,
            "client_secret": payment_intent.get("client_secret")  # FIX 5: Include client secret for frontend
        }
    except Exception as e:
        print(f"⚠️  Error processing fee payment: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Payment processing failed: {str(e)}"
        )


@router.get("/creator-royalties")
async def get_creator_royalties(
    user_id: str = Depends(get_current_user_id_dep),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12), defaults to current month"),
    year: Optional[int] = Query(None, description="Year, defaults to current year"),
    db: Session = Depends(get_db)
):
    """
    FIX 5: Get royalties owed to a strategy creator.
    
    Shows royalties from users who executed their strategies.
    """
    try:
        royalties = fee_service.get_creator_royalties(user_id, db, month, year)
        return royalties
    except Exception as e:
        print(f"⚠️  Error getting creator royalties: {e}")
        return {
            "user_id": user_id,
            "month": month or datetime.now().month,
            "year": year or datetime.now().year,
            "total_royalty": 0.0,
            "total_platform_fee": 0.0,
            "total_net": 0.0,
            "count": 0,
            "error": str(e)
        }


@router.get("/grace-period")
async def check_grace_period(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    FIX 4: Check if user qualifies for grace period (delayed payment allowance).
    """
    try:
        grace_status = fee_service.check_payment_grace_period(user_id, db)
        return grace_status
    except Exception as e:
        print(f"⚠️  Error checking grace period: {e}")
        return {
            "user_id": user_id,
            "has_grace": False,
            "reason": f"Error: {str(e)}"
        }

