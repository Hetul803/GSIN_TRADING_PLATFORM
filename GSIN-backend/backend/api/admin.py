# backend/api/admin.py
"""
Admin API endpoints for managing subscription plans, prices, and royalties.
Only accessible to admin users (patelhetul803@gmail.com).
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from ..db.models import UserRole, User, UserStrategy, Trade, Group, SubscriptionTier, TradeStatus, SubscriptionPlan, RoyaltyLedger
from sqlalchemy import func, or_, desc

router = APIRouter(prefix="/admin", tags=["admin"])

# Admin email (hardcoded for security)
ADMIN_EMAIL = "patelhetul803@gmail.com"

# PHASE 4: JWT-only authentication - use dependency directly

def verify_admin(db: Session, user_id: str) -> None:
    """Verify that the user is an admin."""
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user is admin by email or role
    if user.email.lower() != ADMIN_EMAIL.lower() and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

class UpdatePlanPriceRequest(BaseModel):
    priceMonthly: int  # in cents

class UpdatePlanRoyaltyRequest(BaseModel):
    defaultRoyaltyPercent: float

class UpdatePlanPlatformFeeRequest(BaseModel):
    platformFeePercent: float

class UpdatePlanRequest(BaseModel):
    name: Optional[str] = None
    priceMonthly: Optional[int] = None
    defaultRoyaltyPercent: Optional[float] = None
    platformFeePercent: Optional[float] = None
    description: Optional[str] = None
    isActive: Optional[bool] = None

@router.get("/plans")
async def list_all_plans(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """List all subscription plans (admin only)."""
    verify_admin(db, user_id)
    
    plans = crud.list_subscription_plans(db, active_only=False)
    # Ensure all plans have platformFeePercent
    for plan in plans:
        if "platformFeePercent" not in plan:
            plan["platformFeePercent"] = 5.0  # Default
    return {"plans": plans}

@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    request: UpdatePlanRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Update subscription plan (admin only)."""
    verify_admin(db, user_id)
    
    # Get old plan values for notification
    old_plan = crud.get_subscription_plan(db, plan_id)
    if not old_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    plan = crud.update_subscription_plan(
        db=db,
        plan_id=plan_id,
        name=request.name,
        price_monthly=request.priceMonthly,
        default_royalty_percent=request.defaultRoyaltyPercent,
        platform_fee_percent=request.platformFeePercent,
        description=request.description,
        is_active=request.isActive,
    )
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Create notification about the change
    changes = []
    if request.priceMonthly is not None and request.priceMonthly != old_plan.price_monthly:
        old_price = old_plan.price_monthly / 100
        new_price = request.priceMonthly / 100
        changes.append(f"Price: ${old_price:.2f} → ${new_price:.2f}/month")
    if request.defaultRoyaltyPercent is not None and request.defaultRoyaltyPercent != old_plan.default_royalty_percent:
        changes.append(f"Default Royalty: {old_plan.default_royalty_percent}% → {request.defaultRoyaltyPercent}%")
    if request.platformFeePercent is not None and request.platformFeePercent != old_plan.platform_fee_percent:
        changes.append(f"Platform Fee: {old_plan.platform_fee_percent}% → {request.platformFeePercent}%")
    
    if changes:
        notification_title = f"Subscription Plan Updated: {plan.name}"
        notification_message = f"The {plan.name} plan has been updated:\n\n" + "\n".join(f"• {change}" for change in changes)
        notification_message += "\n\nNote: Current subscribers will continue at their current rate until their next billing cycle."
        
        # Create admin notification
        crud.create_admin_notification(
            db=db,
            title=notification_title,
            message=notification_message,
            notification_type="update"
        )
        
        # Also create a regular notification for all users
        from ..db.models import Notification
        import uuid
        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=None,  # None = all users
            title=notification_title,
            body=notification_message,
            read_flag=False,
            created_by=user_id,
        )
        db.add(notification)
        db.commit()
        crud.create_admin_notification(
            db=db,
            title=notification_title,
            message=notification_message,
            notification_type="update"
        )
    
    return {
        "id": plan.id,
        "planCode": plan.plan_code,
        "name": plan.name,
        "priceMonthly": plan.price_monthly,
        "defaultRoyaltyPercent": plan.default_royalty_percent,
        "platformFeePercent": plan.platform_fee_percent,
        "description": plan.description,
        "isActive": plan.is_active,
    }

@router.put("/plans/{plan_id}/price")
async def update_plan_price(
    plan_id: str,
    request: UpdatePlanPriceRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Update subscription plan price (admin only)."""
    verify_admin(db, user_id)
    
    plan = crud.update_subscription_plan(
        db=db,
        plan_id=plan_id,
        price_monthly=request.priceMonthly,
    )
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    return {
        "id": plan.id,
        "planCode": plan.plan_code,
        "name": plan.name,
        "priceMonthly": plan.price_monthly,
    }

@router.put("/plans/{plan_id}/royalty")
async def update_plan_royalty(
    plan_id: str,
    request: UpdatePlanRoyaltyRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Update subscription plan default royalty percent (admin only)."""
    verify_admin(db, user_id)
    
    plan = crud.update_subscription_plan(
        db=db,
        plan_id=plan_id,
        default_royalty_percent=request.defaultRoyaltyPercent,
    )
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    return {
        "id": plan.id,
        "planCode": plan.plan_code,
        "name": plan.name,
        "defaultRoyaltyPercent": plan.default_royalty_percent,
    }

@router.put("/plans/{plan_id}/platform-fee")
async def update_plan_platform_fee(
    plan_id: str,
    request: UpdatePlanPlatformFeeRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Update subscription plan platform fee percent (admin only)."""
    verify_admin(db, user_id)
    
    plan = crud.update_subscription_plan(
        db=db,
        plan_id=plan_id,
        platform_fee_percent=request.platformFeePercent,
    )
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    return {
        "id": plan.id,
        "planCode": plan.plan_code,
        "name": plan.name,
        "platformFeePercent": plan.platform_fee_percent,
    }

@router.get("/royalties")
async def get_all_royalties(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get all royalties (admin only)."""
    verify_admin(db, user_id)
    
    from ..db.models import RoyaltyLedger
    from sqlalchemy import func
    
    royalties = db.query(RoyaltyLedger).order_by(
        RoyaltyLedger.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    total_royalties = db.query(func.sum(RoyaltyLedger.royalty_amount)).scalar() or 0.0
    total_platform_fees = db.query(func.sum(RoyaltyLedger.platform_fee)).scalar() or 0.0
    total_net = db.query(func.sum(RoyaltyLedger.net_amount)).scalar() or 0.0
    
    return {
        "royalties": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "strategy_id": r.strategy_id,
                "trade_id": r.trade_id,
                "royalty_amount": r.royalty_amount,
                "platform_fee": r.platform_fee,
                "net_amount": r.net_amount,
                "trade_profit": r.trade_profit,
                "created_at": r.created_at.isoformat()
            }
            for r in royalties
        ],
        "summary": {
            "total_royalties": float(total_royalties),
            "total_platform_fees": float(total_platform_fees),
            "total_net_paid": float(total_net),
            "count": len(royalties)
        }
    }


@router.get("/stats")
async def get_admin_stats(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get platform-wide statistics (admin only)."""
    verify_admin(db, user_id)
    
    # Total users
    total_users = db.query(func.count(User.id)).scalar() or 0
    
    # Active users (updated profile within last 30 days - proxy for activity)
    # Note: User model doesn't have last_login_at, using updated_at as proxy
    from datetime import datetime, timedelta, timezone
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_users = db.query(func.count(User.id)).filter(
        User.updated_at >= thirty_days_ago
    ).scalar() or 0
    
    # Users by subscription plan
    users_by_plan = {}
    plans = db.query(SubscriptionPlan).all()
    for plan in plans:
        count = db.query(func.count(User.id)).filter(
            User.current_plan_id == plan.id
        ).scalar() or 0
        users_by_plan[plan.plan_code] = {
            "plan_name": plan.name,
            "user_count": count
        }
    
    # Legacy tier counts (for backward compatibility)
    user_tier = db.query(func.count(User.id)).filter(
        User.subscription_tier == SubscriptionTier.USER
    ).scalar() or 0
    
    pro_tier = db.query(func.count(User.id)).filter(
        User.subscription_tier == SubscriptionTier.PRO
    ).scalar() or 0
    
    creator_tier = db.query(func.count(User.id)).filter(
        User.subscription_tier == SubscriptionTier.CREATOR
    ).scalar() or 0
    
    # Total strategies
    total_strategies = db.query(func.count(UserStrategy.id)).scalar() or 0
    
    # Total trades
    total_trades = db.query(func.count(Trade.id)).scalar() or 0
    
    # Total P&L (sum of all realized P&L)
    total_pnl_result = db.query(func.sum(Trade.realized_pnl)).filter(
        Trade.status == TradeStatus.CLOSED
    ).scalar()
    total_pnl = float(total_pnl_result) if total_pnl_result else 0.0
    
    # Total royalties and platform fees from RoyaltyLedger
    total_royalties_result = db.query(func.sum(RoyaltyLedger.royalty_amount)).scalar()
    total_royalties = float(total_royalties_result) if total_royalties_result else 0.0
    
    total_platform_fees_result = db.query(func.sum(RoyaltyLedger.platform_fee)).scalar()
    total_platform_fees = float(total_platform_fees_result) if total_platform_fees_result else 0.0
    
    total_net_royalties = db.query(func.sum(RoyaltyLedger.net_amount)).scalar()
    total_net_royalties = float(total_net_royalties) if total_net_royalties else 0.0
    
    # Groups created
    groups_created = db.query(func.count(Group.id)).scalar() or 0
    
    # Revenue (from subscription plans - estimate based on active subscriptions)
    # This is a simplified calculation - in production, you'd track actual payments
    revenue_today = 0.0  # Would need to track actual payments
    revenue_week = 0.0
    revenue_month = 0.0
    
    # FINAL ALIGNMENT: Per-strategy performance
    from sqlalchemy import desc
    strategy_performance = db.query(
        UserStrategy.id,
        UserStrategy.name,
        func.count(Trade.id).label("trade_count"),
        func.sum(Trade.realized_pnl).label("total_pnl"),
        func.avg(Trade.realized_pnl).label("avg_pnl")
    ).join(
        Trade, UserStrategy.id == Trade.strategy_id, isouter=True
    ).group_by(
        UserStrategy.id, UserStrategy.name
    ).order_by(desc("total_pnl")).limit(10).all()
    
    strategy_perf_list = [
        {
            "strategy_id": s.id,
            "strategy_name": s.name,
            "trade_count": s.trade_count or 0,
            "total_pnl": float(s.total_pnl) if s.total_pnl else 0.0,
            "avg_pnl": float(s.avg_pnl) if s.avg_pnl else 0.0
        }
        for s in strategy_performance
    ]
    
    # FINAL ALIGNMENT: Flagged users (users with blocked status or suspicious activity)
    flagged_users = db.query(User).filter(
        or_(
            User.role == UserRole.BLOCKED,
            User.email_verified == False
        )
    ).count()
    
    return {
        "totalUsers": total_users,
        "activeUsers": active_users,
        "usersByPlan": users_by_plan,
        "userTier": user_tier,  # Legacy
        "proTier": pro_tier,  # Legacy
        "creatorTier": creator_tier,  # Legacy
        "totalStrategies": total_strategies,
        "activeStrategies": db.query(func.count(UserStrategy.id)).filter(
            UserStrategy.is_active == True
        ).scalar() or 0,
        "totalTrades": total_trades,
        "openTrades": db.query(func.count(Trade.id)).filter(
            Trade.status == TradeStatus.OPEN
        ).scalar() or 0,
        "closedTrades": db.query(func.count(Trade.id)).filter(
            Trade.status == TradeStatus.CLOSED
        ).scalar() or 0,
        "totalPnl": total_pnl,
        "totalRoyalties": total_royalties,
        "totalPlatformFees": total_platform_fees,
        "totalNetRoyalties": total_net_royalties,
        "groupsCreated": groups_created,
        "flaggedUsers": flagged_users,
        "strategyPerformance": strategy_perf_list,
        "revenue": {
            "today": revenue_today,
            "week": revenue_week,
            "month": revenue_month,
        }
    }


class SendMessageRequest(BaseModel):
    title: str
    message: str


@router.post("/send-message")
async def send_message_to_all_users(
    request: SendMessageRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Send a message to all users (admin only)."""
    verify_admin(db, user_id)
    
    from ..db.models import Notification
    import uuid
    
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=None,  # None = all users
        title=request.title,
        body=request.message,
        read_flag=False,
        created_by=user_id,
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    return {
        "id": notification.id,
        "title": notification.title,
        "message": notification.body,
        "created_at": notification.created_at.isoformat() if notification.created_at else "",
    }

