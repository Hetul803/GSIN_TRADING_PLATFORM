#!/usr/bin/env python3
"""
Script to delete all users and create admin accounts.
Run with: python scripts/setup_admin_accounts.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from backend.db.session import SessionLocal
from backend.db import crud
from backend.db.models import User, UserRole, SubscriptionTier
from backend.utils.auth import hash_password
from backend.db.crud import get_subscription_plan_by_code

def setup_admin_accounts():
    """Delete all users and create admin accounts."""
    db: Session = SessionLocal()
    
    try:
        # Delete all users (cascade will handle related data)
        print("Deleting all existing users...")
        db.query(User).delete()
        db.commit()
        print("✅ All users deleted")
        
        # Get the PRO/CREATOR plan (USER_PLUS_UPLOAD or CREATOR)
        # Let's use CREATOR plan for the main account
        creator_plan = get_subscription_plan_by_code(db, "CREATOR")
        if not creator_plan:
            # If CREATOR plan doesn't exist, try USER_PLUS_UPLOAD
            creator_plan = get_subscription_plan_by_code(db, "USER_PLUS_UPLOAD")
        
        # Create main account (hetul803@gmail.com) - PRO/CREATOR + ADMIN
        print("\nCreating main account (hetul803@gmail.com)...")
        main_password_hash = hash_password("Hetul7698676686")
        main_user = crud.create_user(
            db,
            email="hetul803@gmail.com",
            password_hash=main_password_hash,
            name="Hetul Patel (Creator)",
            role=UserRole.ADMIN,
            subscription_tier=SubscriptionTier.CREATOR if creator_plan else SubscriptionTier.PRO
        )
        
        # Set subscription plan if available
        if creator_plan:
            crud.update_user_subscription(
                db,
                main_user.id,
                creator_plan.id,
                royalty_percent=creator_plan.default_royalty_percent
            )
            print(f"✅ Set subscription plan to: {creator_plan.name}")
        
        print(f"✅ Main account created:")
        print(f"   Email: hetul803@gmail.com")
        print(f"   Password: Hetul7698676686")
        print(f"   Role: ADMIN")
        print(f"   Subscription: {main_user.subscription_tier.value}")
        print(f"   User ID: {main_user.id}")
        
        # Create admin account (patelhetul803@gmail.com) - ADMIN
        print("\nCreating admin account (patelhetul803@gmail.com)...")
        admin_password_hash = hash_password("Hetul7698676686")
        admin_user = crud.create_user(
            db,
            email="patelhetul803@gmail.com",
            password_hash=admin_password_hash,
            name="Hetul Patel (Admin)",
            role=UserRole.ADMIN,
            subscription_tier=SubscriptionTier.CREATOR if creator_plan else SubscriptionTier.PRO
        )
        
        # Set subscription plan if available
        if creator_plan:
            crud.update_user_subscription(
                db,
                admin_user.id,
                creator_plan.id,
                royalty_percent=creator_plan.default_royalty_percent
            )
            print(f"✅ Set subscription plan to: {creator_plan.name}")
        
        print(f"✅ Admin account created:")
        print(f"   Email: patelhetul803@gmail.com")
        print(f"   Password: Hetul7698676686")
        print(f"   Role: ADMIN")
        print(f"   Subscription: {admin_user.subscription_tier.value}")
        print(f"   User ID: {admin_user.id}")
        
        db.commit()
        print("\n✅ Setup complete! Both accounts are ready to use.")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    setup_admin_accounts()

