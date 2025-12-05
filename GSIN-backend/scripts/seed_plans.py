#!/usr/bin/env python3
"""
Seed the database with default subscription plans.
Run this after migrations to populate initial plans.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db.session import SessionLocal
from backend.db import crud

def seed_plans():
    """Create the three default subscription plans if they don't exist."""
    db = SessionLocal()
    try:
        # Check if plans already exist
        existing_plans = crud.list_subscription_plans(db, active_only=False)
        if existing_plans:
            print(f"Found {len(existing_plans)} existing plans. Skipping seed.")
            for plan in existing_plans:
                print(f"  - {plan.plan_code}: {plan.name} (${plan.price_monthly/100:.2f}/month)")
            return
        
        print("Creating default subscription plans...")
        
        # Plan 1: USER/STARTER (View-Only Strategies)
        user_plan = crud.create_subscription_plan(
            db,
            plan_code="USER",
            name="Starter",
            price_monthly=3999,  # $39.99
            default_royalty_percent=0.0,  # Starter: 0% royalties
            description="Perfect for individual traders. Can use strategies and signals in the app. Cannot upload strategies or run backtests.",
            is_creator_plan=False,
            platform_fee_percent=7.0,  # Starter: 7% platform fee
        )
        print(f"✅ Created plan: {user_plan.plan_code} - {user_plan.name} (${user_plan.price_monthly/100:.2f}/month, {user_plan.default_royalty_percent}% royalty, {user_plan.platform_fee_percent}% platform fee)")
        
        # Plan 2: USER_PLUS_UPLOAD/PRO (User + Upload Strategies)
        upload_plan = crud.create_subscription_plan(
            db,
            plan_code="USER_PLUS_UPLOAD",
            name="Pro",
            price_monthly=4999,  # $49.99
            default_royalty_percent=0.0,  # Pro: 0% royalties (admin sets per strategy)
            description="Everything in Starter plan, plus upload strategies that others may use. Earn royalties (set by admin). Cannot create groups.",
            is_creator_plan=False,
            platform_fee_percent=5.0,  # Pro: 5% platform fee
        )
        print(f"✅ Created plan: {upload_plan.plan_code} - {upload_plan.name} (${upload_plan.price_monthly/100:.2f}/month, {upload_plan.default_royalty_percent}% royalty, {upload_plan.platform_fee_percent}% platform fee)")
        
        # Plan 3: CREATOR (Creator Account)
        creator_plan = crud.create_subscription_plan(
            db,
            plan_code="CREATOR",
            name="Creator",
            price_monthly=9999,  # $99.99
            default_royalty_percent=5.0,  # Creator: 5% royalties
            description="Content creator account with 5% royalties. Access to everything including private groups.",
            is_creator_plan=True,
            platform_fee_percent=3.0,  # Creator: 3% platform fee
        )
        print(f"✅ Created plan: {creator_plan.plan_code} - {creator_plan.name} (${creator_plan.price_monthly/100:.2f}/month, {creator_plan.default_royalty_percent}% royalty, {creator_plan.platform_fee_percent}% platform fee)")
        
        print("\n✅ All default plans created successfully!")
        
    except Exception as e:
        print(f"❌ Error seeding plans: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_plans()

