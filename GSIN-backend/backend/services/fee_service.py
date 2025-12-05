# backend/services/fee_service.py
"""
FIX 4 & 5: Fee service for calculating platform fees and creator royalties.

Fee Rules:
- Users owe platform fees only when their monthly PNL exceeds $1000 (REAL mode only)
- Platform fee: 5% general, 3% for creators (admin configurable)
- Strategy creators receive 5% of profits made by users who executed their strategies
- Grace logic: if user has been paying for 3+ months, allow up to 2 months delayed payments before soft-freeze
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func

from ..db.models import Trade, User, SubscriptionPlan, RoyaltyLedger, TradeMode
from ..db import crud


class FeeService:
    """Service for calculating platform fees and creator royalties."""
    
    # FIX 4: Platform fee thresholds
    MONTHLY_PNL_THRESHOLD = 1000.0  # Users only pay fees if monthly PNL > $1000
    DEFAULT_PLATFORM_FEE_RATE = 0.05  # 5% general
    CREATOR_PLATFORM_FEE_RATE = 0.03  # 3% for creators
    ROYALTY_RATE = 0.05  # 5% to strategy creators
    
    # FIX 4: Grace period logic
    GRACE_MONTHS_REQUIRED = 3  # Must have paid for 3+ months
    GRACE_DELAYED_MONTHS = 2  # Allow up to 2 months delayed payments
    
    def calculate_monthly_pnl(
        self,
        user_id: str,
        db: Session,
        month: Optional[int] = None,
        year: Optional[int] = None,
        mode: TradeMode = TradeMode.REAL
    ) -> float:
        """
        FIX 4: Calculate monthly PNL for a user (REAL mode only).
        
        Returns:
            Total PNL for the month (positive = profit, negative = loss)
        """
        now = datetime.now(timezone.utc)
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        # Calculate month boundaries
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        
        # FIX 4: Only calculate for REAL trades
        trades = db.query(Trade).filter(
            and_(
                Trade.user_id == user_id,
                Trade.mode == mode,  # Only REAL mode
                Trade.status == "CLOSED",
                Trade.realized_pnl.isnot(None),
                Trade.closed_at >= month_start,
                Trade.closed_at <= month_end
            )
        ).all()
        
        total_pnl = sum(trade.realized_pnl for trade in trades if trade.realized_pnl)
        return total_pnl
    
    def calculate_platform_fee(
        self,
        user_id: str,
        db: Session,
        month: Optional[int] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        FIX 4: Calculate platform fee for a user.
        
        Rules:
        - Only applies if monthly PNL > $1000 (REAL mode)
        - Fee rate: 5% general, 3% for creators (admin configurable)
        - Returns 0 if PNL <= $1000 or PAPER mode
        
        Returns:
            Dictionary with fee details
        """
        # FIX 4: Only calculate for REAL mode
        monthly_pnl = self.calculate_monthly_pnl(user_id, db, month, year, mode=TradeMode.REAL)
        
        if monthly_pnl <= self.MONTHLY_PNL_THRESHOLD:
            return {
                "user_id": user_id,
                "monthly_pnl": monthly_pnl,
                "platform_fee": 0.0,
                "platform_fee_rate": 0.0,
                "reason": "Monthly PNL below threshold ($1000)"
            }
        
        # Get user's subscription plan to determine fee rate
        user = crud.get_user_by_id(db, user_id)
        if not user:
            return {
                "user_id": user_id,
                "monthly_pnl": monthly_pnl,
                "platform_fee": 0.0,
                "platform_fee_rate": 0.0,
                "reason": "User not found"
            }
        
        # FIX 4: Get platform fee rate from subscription plan (admin configurable)
        platform_fee_rate = self.DEFAULT_PLATFORM_FEE_RATE  # Default 5%
        if user.current_plan_id:
            plan = crud.get_subscription_plan(db, user.current_plan_id)
            if plan and plan.platform_fee_percent is not None:
                platform_fee_rate = plan.platform_fee_percent / 100.0
            elif plan and plan.is_creator_plan:
                # Creator plan gets 3% default
                platform_fee_rate = self.CREATOR_PLATFORM_FEE_RATE
        
        # Calculate fee on PNL above threshold
        taxable_pnl = monthly_pnl - self.MONTHLY_PNL_THRESHOLD
        platform_fee = taxable_pnl * platform_fee_rate
        
        return {
            "user_id": user_id,
            "monthly_pnl": monthly_pnl,
            "taxable_pnl": taxable_pnl,
            "platform_fee": platform_fee,
            "platform_fee_rate": platform_fee_rate,
            "threshold": self.MONTHLY_PNL_THRESHOLD
        }
    
    def check_payment_grace_period(
        self,
        user_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        FIX 4: Check if user qualifies for grace period (delayed payment allowance).
        
        Rules:
        - User must have paid for 3+ months
        - Allow up to 2 months delayed payments before soft-freeze
        
        Returns:
            Dictionary with grace status
        """
        # Check payment history (from RoyaltyLedger or future payment tracking)
        # For now, we'll check if user has been active for 3+ months
        user = crud.get_user_by_id(db, user_id)
        if not user:
            return {
                "user_id": user_id,
                "has_grace": False,
                "reason": "User not found"
            }
        
        # FIX 4: Check if user has subscription for 3+ months
        from ..db.models import UserSubscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active"
        ).order_by(UserSubscription.created_at.asc()).first()
        
        if not subscription:
            return {
                "user_id": user_id,
                "has_grace": False,
                "reason": "No active subscription"
            }
        
        months_active = (datetime.now(timezone.utc) - subscription.created_at).days / 30.0
        
        has_grace = months_active >= self.GRACE_MONTHS_REQUIRED
        
        return {
            "user_id": user_id,
            "has_grace": has_grace,
            "months_active": months_active,
            "grace_delayed_months_allowed": self.GRACE_DELAYED_MONTHS if has_grace else 0,
            "reason": "Qualifies for grace period" if has_grace else "Less than 3 months active"
        }
    
    def get_creator_royalties(
        self,
        user_id: str,
        db: Session,
        month: Optional[int] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        FIX 4: Get royalties owed to a strategy creator.
        
        Returns:
            Dictionary with total royalties for the month
        """
        now = datetime.now(timezone.utc)
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        # Calculate month boundaries
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        
        # Get royalties for this user (as strategy creator)
        royalties = db.query(RoyaltyLedger).filter(
            and_(
                RoyaltyLedger.user_id == user_id,
                RoyaltyLedger.created_at >= month_start,
                RoyaltyLedger.created_at <= month_end
            )
        ).all()
        
        total_royalty = sum(r.royalty_amount for r in royalties)
        total_platform_fee = sum(r.platform_fee for r in royalties)
        total_net = sum(r.net_amount for r in royalties)
        
        return {
            "user_id": user_id,
            "month": month,
            "year": year,
            "total_royalty": total_royalty,
            "total_platform_fee": total_platform_fee,
            "total_net": total_net,
            "count": len(royalties)
        }


# Singleton instance
fee_service = FeeService()

