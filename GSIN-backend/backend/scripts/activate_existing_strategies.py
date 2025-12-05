# backend/scripts/activate_existing_strategies.py
"""
Script to activate existing strategies in the database.

This script:
1. Finds seed strategies (created by system/admin user) that are discarded/inactive
2. Reactivates them with experiment status and marks them for backtesting
3. Ensures they can be picked up by the evolution worker
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.db.session import SessionLocal
from backend.db.models import UserStrategy, User, UserRole
from backend.strategy_engine.status_manager import StrategyStatus


def activate_existing_strategies():
    """Activate seed strategies that were previously discarded or inactive."""
    db = SessionLocal()
    try:
        # Identify system user (seed strategies are created by system/admin user)
        system_user_id = os.getenv("SEED_STRATEGIES_USER_ID")
        system_user_ids = []
        
        if system_user_id:
            # Check if user exists
            system_user = db.query(User).filter(User.id == system_user_id).first()
            if system_user:
                system_user_ids.append(system_user_id)
        
        # Also find admin/system users (seed strategies might be created by them)
        admin_users = db.query(User).filter(
            (User.role == UserRole.ADMIN) | (User.email.like("%system%")) | (User.email.like("%admin%"))
        ).all()
        for admin_user in admin_users:
            if admin_user.id not in system_user_ids:
                system_user_ids.append(admin_user.id)
        
        if not system_user_ids:
            print("⚠️  No system user found. Skipping seed strategy activation.")
            return 0
        
        # Find seed strategies where:
        # 1. user_id matches system/admin user
        # 2. AND status in ["discarded", "inactive", "none", null, ""]
        # OR is_active = False
        strategies_to_reactivate = db.query(UserStrategy).filter(
            UserStrategy.user_id.in_(system_user_ids),
            (
                (UserStrategy.status.in_(["discarded", "inactive", "none", ""])) |
                (UserStrategy.status == None) |
                (UserStrategy.is_active == False)
            )
        ).all()
        
        if not strategies_to_reactivate:
            print("✅ No seed strategies need reactivation. All seed strategies are already active.")
            return 0
        
        print(f"📊 Found {len(strategies_to_reactivate)} seed strategies to activate:")
        
        activated_count = 0
        for strategy in strategies_to_reactivate:
            # Reactivate seed strategy
            strategy.is_active = True
            strategy.status = StrategyStatus.EXPERIMENT  # Reset to experiment status
            strategy.last_backtest_at = None  # Mark as needing backtest
            strategy.evolution_attempts = 0  # Reset evolution attempts
            
            print(f"🌱 Activated seed strategy: {strategy.name}")
            activated_count += 1
        
        db.commit()
        print(f"\n✅ Activated {activated_count} seed strategies")
        return activated_count
        
    except Exception as e:
        print(f"❌ Error activating seed strategies: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    count = activate_existing_strategies()
    sys.exit(0 if count >= 0 else 1)

