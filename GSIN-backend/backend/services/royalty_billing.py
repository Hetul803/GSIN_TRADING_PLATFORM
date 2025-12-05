# backend/services/royalty_billing.py
"""
PHASE 4: Monthly billing cycle for royalties.
Handles automatic Stripe charges for outstanding royalties.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func
import uuid

from ..db.models import RoyaltyLedger, User, Trade
from ..db import crud
from .stripe_service import charge_customer_for_royalties


class RoyaltyBillingService:
    """Service for managing monthly royalty billing cycles."""
    
    def get_outstanding_royalties(
        self,
        user_id: str,
        db: Session,
        billing_cycle_start: Optional[datetime] = None,
        billing_cycle_end: Optional[datetime] = None
    ) -> List[RoyaltyLedger]:
        """
        Get all outstanding (unpaid) royalties for a user within a billing cycle.
        
        Args:
            user_id: User ID (strategy creator)
            db: Database session
            billing_cycle_start: Start of billing cycle (defaults to start of current month)
            billing_cycle_end: End of billing cycle (defaults to end of current month)
        
        Returns:
            List of RoyaltyLedger entries that are unpaid
        """
        # Default to current month if not specified
        now = datetime.now(timezone.utc)
        if not billing_cycle_start:
            billing_cycle_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not billing_cycle_end:
            # End of current month
            if now.month == 12:
                billing_cycle_end = now.replace(year=now.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                billing_cycle_end = now.replace(month=now.month + 1, day=1) - timedelta(seconds=1)
        
        # Query unpaid royalties within the billing cycle
        # NOTE: We'll add a 'paid' field to RoyaltyLedger in a migration
        # For now, we'll assume all royalties are unpaid if they don't have a payment_id
        outstanding = db.query(RoyaltyLedger).filter(
            and_(
                RoyaltyLedger.user_id == user_id,
                RoyaltyLedger.created_at >= billing_cycle_start,
                RoyaltyLedger.created_at <= billing_cycle_end,
                # TODO: Add paid_at IS NULL filter once migration is added
            )
        ).all()
        
        return outstanding
    
    def calculate_monthly_total(
        self,
        user_id: str,
        db: Session,
        month: Optional[int] = None,
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate total outstanding royalties for a user in a given month.
        
        Args:
            user_id: User ID (strategy creator)
            db: Database session
            month: Month number (1-12), defaults to current month
            year: Year, defaults to current year
        
        Returns:
            Dictionary with total amounts and count
        """
        now = datetime.now(timezone.utc)
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        billing_cycle_start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            billing_cycle_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        else:
            billing_cycle_end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        
        outstanding = self.get_outstanding_royalties(user_id, db, billing_cycle_start, billing_cycle_end)
        
        total_royalty = sum(r.royalty_amount for r in outstanding)
        total_platform_fee = sum(r.platform_fee for r in outstanding)
        total_net = sum(r.net_amount for r in outstanding)
        
        return {
            "user_id": user_id,
            "month": month,
            "year": year,
            "billing_cycle_start": billing_cycle_start.isoformat(),
            "billing_cycle_end": billing_cycle_end.isoformat(),
            "outstanding_count": len(outstanding),
            "total_royalty_amount": total_royalty,
            "total_platform_fee": total_platform_fee,
            "total_net_amount": total_net,
            "entries": [r.id for r in outstanding]
        }
    
    def process_monthly_billing(
        self,
        user_id: str,
        db: Session,
        month: Optional[int] = None,
        year: Optional[int] = None,
        admin_override: bool = False
    ) -> Dict[str, Any]:
        """
        Process monthly billing for a user's outstanding royalties.
        Attempts to charge via Stripe and records the payment.
        
        Args:
            user_id: User ID (strategy creator)
            db: Database session
            month: Month number (1-12), defaults to current month
            year: Year, defaults to current year
            admin_override: If True, skip payment and mark as paid (admin override)
        
        Returns:
            Dictionary with billing result
        """
        user = crud.get_user_by_id(db, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        monthly_total = self.calculate_monthly_total(user_id, db, month, year)
        
        if monthly_total["outstanding_count"] == 0:
            return {
                "success": True,
                "message": "No outstanding royalties for this billing cycle",
                "amount_charged": 0.0,
                "monthly_total": monthly_total
            }
        
        amount_to_charge = monthly_total["total_net_amount"]
        
        # Admin override: mark as paid without charging
        if admin_override:
            # TODO: Mark all entries as paid (add paid_at field in migration)
            return {
                "success": True,
                "message": "Admin override: royalties marked as paid without charge",
                "amount_charged": 0.0,
                "monthly_total": monthly_total,
                "admin_override": True
            }
        
        # Attempt Stripe charge
        try:
            charge_result = charge_customer_for_royalties(
                user_id=user_id,
                user_email=user.email,
                amount_cents=int(amount_to_charge * 100),  # Convert to cents
                description=f"Royalties for {monthly_total['month']}/{monthly_total['year']}",
                metadata={
                    "billing_cycle": f"{monthly_total['year']}-{monthly_total['month']:02d}",
                    "royalty_entries": ",".join(monthly_total["entries"])
                }
            )
            
            # TODO: Update RoyaltyLedger entries with payment_id and paid_at
            # For now, we'll just return the charge result
            
            return {
                "success": True,
                "message": "Monthly billing processed successfully",
                "amount_charged": amount_to_charge,
                "monthly_total": monthly_total,
                "stripe_charge_id": charge_result.get("charge_id"),
                "charge_result": charge_result
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to process billing: {str(e)}",
                "amount_charged": 0.0,
                "monthly_total": monthly_total,
                "error": str(e)
            }
    
    def check_payment_status(
        self,
        user_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Check if a user has unpaid royalties that would trigger a hard lock.
        
        Args:
            user_id: User ID
            db: Database session
        
        Returns:
            Dictionary with payment status and lock information
        """
        # Get current month's outstanding royalties
        monthly_total = self.calculate_monthly_total(user_id, db)
        
        # Hard lock threshold: if user has > $10 unpaid royalties
        HARD_LOCK_THRESHOLD = 10.0
        has_unpaid = monthly_total["total_net_amount"] > 0
        should_lock = monthly_total["total_net_amount"] >= HARD_LOCK_THRESHOLD
        
        return {
            "user_id": user_id,
            "has_unpaid_royalties": has_unpaid,
            "outstanding_amount": monthly_total["total_net_amount"],
            "should_lock": should_lock,
            "lock_threshold": HARD_LOCK_THRESHOLD,
            "monthly_total": monthly_total
        }


# Singleton instance
royalty_billing_service = RoyaltyBillingService()

