# backend/api/subscriptions.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Body, Query, status, Request
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json

from ..db.session import get_db
from ..db import crud
from ..db.models import SubscriptionPlan
from ..services.stripe_service import create_checkout_session, verify_webhook_signature
from ..utils.jwt_deps import get_current_user_id_dep

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Response models
class PlanResponse(BaseModel):
    id: str
    planCode: str
    name: str
    priceMonthly: int  # in cents
    defaultRoyaltyPercent: float
    platformFeePercent: float  # GSIN platform fee %
    description: str
    isCreatorPlan: bool
    isActive: bool
    createdAt: str
    updatedAt: str

    class Config:
        from_attributes = True

class SubscriptionResponse(BaseModel):
    userId: str
    planId: Optional[str]
    planCode: Optional[str]
    planName: Optional[str]
    royaltyPercent: float
    canUploadStrategies: bool
    isCreator: bool

class UpdateSubscriptionRequest(BaseModel):
    planId: str
    royaltyPercent: Optional[float] = None  # Optional override, otherwise uses plan's default

# GET /api/plans (or /subscriptions/plans)
@router.get("/plans", response_model=Dict[str, Any])
def get_plans(
    active_only: bool = Query(True, description="Only return active plans"),
    db: Session = Depends(get_db)
):
    """
    Get all available subscription plans.
    Returns plans with plan_code, default_royalty_percent, and all other fields.
    """
    # Query plans directly from database
    query = db.query(SubscriptionPlan)
    if active_only:
        query = query.filter(SubscriptionPlan.is_active == True)
    plan_objects = query.order_by(SubscriptionPlan.price_monthly.asc()).all()
    
    if not plan_objects:
        # Return default plans if none exist in database (for initial setup)
        default_plans = [
            {
                "id": "default-user",
                "planCode": "USER",
                "name": "User",
                "priceMonthly": 3999,
                "defaultRoyaltyPercent": 5.0,
                "platformFeePercent": 7.0,
                "description": "Perfect for individual traders. Can use strategies and signals.",
                "isCreatorPlan": False,
                "isActive": True,
                "createdAt": "",
                "updatedAt": "",
            },
            {
                "id": "default-user-upload",
                "planCode": "USER_PLUS_UPLOAD",
                "name": "User + Upload",
                "priceMonthly": 4999,
                "defaultRoyaltyPercent": 5.0,
                "platformFeePercent": 5.0,
                "description": "Everything in User plan, plus upload strategies and earn royalties.",
                "isCreatorPlan": False,
                "isActive": True,
                "createdAt": "",
                "updatedAt": "",
            },
            {
                "id": "default-creator",
                "planCode": "CREATOR",
                "name": "Creator",
                "priceMonthly": 9999,
                "defaultRoyaltyPercent": 3.0,
                "platformFeePercent": 3.0,
                "description": "Content creator account with better royalty rates and all features.",
                "isCreatorPlan": True,
                "isActive": True,
                "createdAt": "",
                "updatedAt": "",
            },
        ]
        return {"plans": default_plans, "isMock": True}
    
    plan_responses = [
        PlanResponse(
            id=plan.id,
            planCode=plan.plan_code,
            name=plan.name,
            priceMonthly=plan.price_monthly,
            defaultRoyaltyPercent=plan.default_royalty_percent,
            platformFeePercent=plan.platform_fee_percent,
            description=plan.description,
            isCreatorPlan=plan.is_creator_plan,
            isActive=plan.is_active,
            createdAt=plan.created_at.isoformat() if plan.created_at else "",
            updatedAt=plan.updated_at.isoformat() if plan.updated_at else "",
        )
        for plan in plan_objects
    ]
    
    return {"plans": [p.dict() for p in plan_responses], "isMock": False}

# GET /api/subscription (or /subscriptions/me)
@router.get("/me", response_model=SubscriptionResponse)
async def get_current_subscription(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get current user's subscription information.
    Returns plan details, royalty percent, and permissions.
    PHASE 4: JWT-only authentication.
    """
    sub_info = crud.get_user_subscription_info(db, user_id)
    
    if not sub_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get plan from sub_info (it's already a dict, not an object)
    plan_code = sub_info.get("plan_code", "USER")
    
    return SubscriptionResponse(
        userId=sub_info["user_id"],
        planId=sub_info.get("plan_id"),
        planCode=plan_code,
        planName=sub_info.get("plan_name", "User"),
        royaltyPercent=sub_info.get("royalty_percent", 0.0),
        canUploadStrategies=sub_info.get("can_upload_strategies", False),
        isCreator=sub_info.get("is_creator", False),
    )

# PUT /api/subscription (or /subscriptions/me)
@router.put("/me", response_model=SubscriptionResponse)
async def update_subscription(
    update_data: UpdateSubscriptionRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Update current user's subscription plan.
    NOTE: This endpoint now requires payment via Stripe checkout.
    Use POST /subscriptions/checkout to create a payment session first.
    PHASE 4: JWT-only authentication.
    """
    
    # Verify plan exists
    plan = crud.get_subscription_plan(db, update_data.planId)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Update user's subscription
    updated_user = crud.update_user_subscription(
        db,
        user_id=user_id,
        plan_id=update_data.planId,
        royalty_percent=update_data.royaltyPercent
    )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get updated subscription info
    sub_info = crud.get_user_subscription_info(db, user_id)
    plan = sub_info["plan"]
    
    return SubscriptionResponse(
        userId=sub_info["user_id"],
        planId=plan.id if plan else None,
        planCode=plan.plan_code if plan else None,
        planName=plan.name if plan else None,
        royaltyPercent=sub_info["royalty_percent"] or 0.0,
        canUploadStrategies=sub_info["can_upload_strategies"],
        isCreator=sub_info["is_creator"],
    )

# Stripe Checkout
class CreateCheckoutRequest(BaseModel):
    planId: str

@router.post("/checkout", response_model=Dict[str, Any])
async def create_checkout(
    checkout_data: CreateCheckoutRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe Checkout Session for subscription payment.
    Returns checkout URL that user should be redirected to.
    PHASE 4: JWT-only authentication.
    """
    
    # Get user
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get plan
    plan = crud.get_subscription_plan(db, checkout_data.planId)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Build redirect URLs
    # TODO: Make these configurable via environment variables
    base_url = "http://localhost:3000"  # Frontend URL
    success_url = f"{base_url}/subscriptions/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/subscriptions?canceled=true"
    
    # Handle free plans ($0) - activate directly without Stripe
    if plan.price_monthly == 0:
        # Update user subscription directly for free plans
        updated_user = crud.update_user_subscription(
            db=db,
            user_id=user_id,
            plan_id=plan.id,
            royalty_percent=None  # Use plan's default
        )
        
        if updated_user:
            return {
                "checkout_url": f"{base_url}/subscriptions?success=true&plan={plan.name}",
                "session_id": "free_plan_activated",
                "is_free": True
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate free plan"
            )
    
    try:
        # Create Stripe checkout session for paid plans
        checkout = create_checkout_session(
            plan_id=plan.id,
            plan_name=plan.name,
            price_cents=plan.price_monthly,  # Uses current price from database
            user_id=user_id,
            user_email=user.email,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        return {
            "checkout_url": checkout["url"],
            "session_id": checkout["session_id"],
            "is_free": False
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )

# Stripe Webhook
@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events (payment success, subscription updates, etc.).
    This endpoint should be configured in Stripe Dashboard.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )
    
    try:
        event = verify_webhook_signature(payload, signature)
        if not event:
            # In development, you might want to parse without verification
            # In production, always verify!
            event = json.loads(payload.decode('utf-8'))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook signature verification failed: {str(e)}"
        )
    
    # Handle different event types
    event_type = event.get("type")
    event_data = event.get("data", {}).get("object", {})
    
    if event_type == "checkout.session.completed":
        # Payment successful - update user's subscription
        session = event_data
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_id = metadata.get("plan_id")
        
        if user_id and plan_id:
            # Update user's subscription
            updated_user = crud.update_user_subscription(
                db,
                user_id=user_id,
                plan_id=plan_id,
                royalty_percent=None  # Use plan's default
            )
            
            if updated_user:
                return {"status": "success", "message": "Subscription updated"}
            else:
                return {"status": "error", "message": "Failed to update subscription"}
    
    elif event_type == "customer.subscription.updated":
        # Subscription updated (e.g., plan changed, renewed)
        subscription = event_data
        customer_id = subscription.get("customer")
        # You might want to store customer_id in user table for future lookups
        return {"status": "success", "message": "Subscription updated"}
    
    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled
        subscription = event_data
        customer_id = subscription.get("customer")
        # Handle subscription cancellation
        return {"status": "success", "message": "Subscription cancelled"}
    
    # Return 200 for unhandled events (Stripe will retry if we return error)
    return {"status": "received", "message": f"Event {event_type} received"}

# ========== ADMIN ENDPOINTS ==========
# These endpoints allow admins to manage plans (update prices, etc.)

class CreatePlanRequest(BaseModel):
    planCode: str
    name: str
    priceMonthly: int
    defaultRoyaltyPercent: float
    description: str
    isCreatorPlan: bool = False

class UpdatePlanRequest(BaseModel):
    name: Optional[str] = None
    priceMonthly: Optional[int] = None
    defaultRoyaltyPercent: Optional[float] = None
    description: Optional[str] = None
    isActive: Optional[bool] = None

@router.post("/plans", response_model=PlanResponse)
def create_plan(
    plan_data: CreatePlanRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create a new subscription plan (Admin only).
    TODO: Add admin authentication check.
    """
    # Check if plan_code already exists
    existing = crud.get_subscription_plan_by_code(db, plan_data.planCode)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan with code '{plan_data.planCode}' already exists"
        )
    
    plan = crud.create_subscription_plan(
        db,
        plan_code=plan_data.planCode,
        name=plan_data.name,
        price_monthly=plan_data.priceMonthly,
        default_royalty_percent=plan_data.defaultRoyaltyPercent,
        description=plan_data.description,
        is_creator_plan=plan_data.isCreatorPlan,
        platform_fee_percent=getattr(plan_data, 'platformFeePercent', None),
    )
    
    return PlanResponse(
        id=plan.id,
        planCode=plan.plan_code,
        name=plan.name,
        priceMonthly=plan.price_monthly,
        defaultRoyaltyPercent=plan.default_royalty_percent,
        platformFeePercent=plan.platform_fee_percent,
        description=plan.description,
        isCreatorPlan=plan.is_creator_plan,
        isActive=plan.is_active,
        createdAt=plan.created_at.isoformat(),
        updatedAt=plan.updated_at.isoformat(),
    )

@router.put("/plans/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: str,
    update_data: UpdatePlanRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update a subscription plan (Admin only).
    Allows changing prices, royalty percentages, descriptions, etc.
    TODO: Add admin authentication check.
    """
    plan = crud.update_subscription_plan(
        db,
        plan_id=plan_id,
        name=update_data.name,
        price_monthly=update_data.priceMonthly,
        default_royalty_percent=update_data.defaultRoyaltyPercent,
        description=update_data.description,
        is_active=update_data.isActive,
    )
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    return PlanResponse(
        id=plan.id,
        planCode=plan.plan_code,
        name=plan.name,
        priceMonthly=plan.price_monthly,
        defaultRoyaltyPercent=plan.default_royalty_percent,
        description=plan.description,
        isCreatorPlan=plan.is_creator_plan,
        isActive=plan.is_active,
        createdAt=plan.created_at.isoformat(),
        updatedAt=plan.updated_at.isoformat(),
    )
