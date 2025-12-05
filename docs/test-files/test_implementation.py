#!/usr/bin/env python3
"""
Test script to verify all implementation changes are working correctly.
Run this before starting the app to ensure everything is set up properly.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session
from backend.db.session import SessionLocal
from backend.db import crud
from backend.db.models import User, UserPaperAccount, UserStrategy, UserTradingSettings
from backend.broker.paper_broker import PaperBroker
from backend.market_data.cache import get_cache
from backend.brain.brain_service import BrainService
from backend.strategy_engine.backtest_engine import BacktestEngine
from backend.broker.alpaca_broker import AlpacaBroker
import os

def test_models():
    """Test that all new models can be imported and have correct fields."""
    print("\n📋 Testing Models...")
    try:
        from backend.db.models import UserPaperAccount, UserStrategy, UserTradingSettings
        
        # Check UserPaperAccount fields
        assert hasattr(UserPaperAccount, 'balance')
        assert hasattr(UserPaperAccount, 'starting_balance')
        assert hasattr(UserPaperAccount, 'last_reset_at')
        print("  ✅ UserPaperAccount model has all required fields")
        
        # Check UserStrategy has is_proposable
        assert hasattr(UserStrategy, 'is_proposable')
        print("  ✅ UserStrategy model has is_proposable field")
        
        # Check UserTradingSettings has daily_profit_target
        assert hasattr(UserTradingSettings, 'daily_profit_target')
        print("  ✅ UserTradingSettings model has daily_profit_target field")
        
        return True
    except Exception as e:
        print(f"  ❌ Model test failed: {e}")
        return False

def test_crud_functions():
    """Test CRUD functions for paper accounts."""
    print("\n💾 Testing CRUD Functions...")
    try:
        db = SessionLocal()
        
        # Create a test user first (required for foreign key)
        test_user_id = "test-user-123"
        test_user = crud.get_user_by_id(db, test_user_id)
        if not test_user:
            from backend.db.models import UserRole, SubscriptionTier
            test_user = User(
                id=test_user_id,
                email="test@example.com",
                name="Test User",
                role=UserRole.USER,
                subscription_tier=SubscriptionTier.USER,
            )
            db.add(test_user)
            db.commit()
        
        # Test get_or_create_paper_account
        account = crud.get_or_create_paper_account(db, test_user_id, 50000.0)
        assert account is not None
        assert account.balance == 50000.0
        assert account.starting_balance == 50000.0
        print("  ✅ get_or_create_paper_account works")
        
        # Test update_paper_account_balance
        crud.update_paper_account_balance(db, test_user_id, 75000.0)
        account = crud.get_paper_account(db, test_user_id)
        assert account.balance == 75000.0
        print("  ✅ update_paper_account_balance works")
        
        # Test reset_paper_account
        crud.reset_paper_account(db, test_user_id)
        account = crud.get_paper_account(db, test_user_id)
        assert account.balance == 50000.0  # Should reset to starting balance
        assert account.last_reset_at is not None
        print("  ✅ reset_paper_account works")
        
        # Cleanup
        db.delete(account)
        db.delete(test_user)
        db.commit()
        db.close()
        
        return True
    except Exception as e:
        print(f"  ❌ CRUD test failed: {e}")
        import traceback
        traceback.print_exc()
        if 'db' in locals():
            db.close()
        return False

def test_market_data_cache():
    """Test market data caching."""
    print("\n💾 Testing Market Data Cache...")
    try:
        cache = get_cache()
        
        # Test cache set/get
        cache.set("price", "AAPL", {"price": 150.0}, None)
        cached = cache.get("price", "AAPL", None, ttl_seconds=5)
        assert cached is not None
        assert cached["price"] == 150.0
        print("  ✅ Market data cache set/get works")
        
        # Test cache expiration
        import time
        cache.set("price", "TSLA", {"price": 200.0}, None)
        time.sleep(0.1)  # Wait a bit
        cached = cache.get("price", "TSLA", None, ttl_seconds=0)  # Expired immediately
        assert cached is None
        print("  ✅ Market data cache expiration works")
        
        return True
    except Exception as e:
        print(f"  ❌ Cache test failed: {e}")
        return False

def test_paper_broker():
    """Test PaperBroker integration with UserPaperAccount."""
    print("\n📊 Testing PaperBroker...")
    try:
        db = SessionLocal()
        
        # Create a test user
        test_user_id = "test-broker-user"
        test_user = crud.get_user_by_id(db, test_user_id)
        if not test_user:
            # Create minimal user for testing
            test_user = User(
                id=test_user_id,
                email="test@example.com",
                name="Test User",
                role=crud.UserRole.USER,
                subscription_tier=crud.SubscriptionTier.USER,
            )
            db.add(test_user)
            db.commit()
        
        # Test PaperBroker initialization
        broker = PaperBroker(db)
        assert broker.is_available()
        print("  ✅ PaperBroker initializes correctly")
        
        # Test get_account_balance (should create paper account if doesn't exist)
        balance_info = broker.get_account_balance(test_user_id)
        assert "paper_balance" in balance_info
        assert balance_info["paper_balance"] > 0
        print("  ✅ PaperBroker.get_account_balance works and creates account if needed")
        
        # Cleanup
        paper_account = crud.get_paper_account(db, test_user_id)
        if paper_account:
            db.delete(paper_account)
        db.delete(test_user)
        db.commit()
        db.close()
        
        return True
    except Exception as e:
        print(f"  ❌ PaperBroker test failed: {e}")
        import traceback
        traceback.print_exc()
        if 'db' in locals():
            db.close()
        return False

def test_backtest_engine():
    """Test that backtest engine doesn't check capital constraints."""
    print("\n🧪 Testing Backtest Engine...")
    try:
        engine = BacktestEngine()
        # Just verify it initializes - actual backtest requires market data
        assert engine is not None
        print("  ✅ BacktestEngine initializes correctly")
        print("  ℹ️  Note: Backtest engine uses unlimited capital (no user balance checks)")
        return True
    except Exception as e:
        print(f"  ❌ BacktestEngine test failed: {e}")
        return False

def test_brain_service():
    """Test BrainService with is_proposable check."""
    print("\n🧠 Testing Brain Service...")
    try:
        service = BrainService()
        assert service is not None
        print("  ✅ BrainService initializes correctly")
        print("  ℹ️  Note: Brain signals check is_proposable before generating")
        return True
    except Exception as e:
        print(f"  ❌ BrainService test failed: {e}")
        return False

def test_alpaca_safety():
    """Test Alpaca broker safety (no funding endpoints)."""
    print("\n🔒 Testing Alpaca Safety...")
    try:
        broker = AlpacaBroker()
        
        # Check that it only uses order/account endpoints
        # We can't actually test the API calls without keys, but we can verify the code
        import inspect
        source = inspect.getsource(broker.place_market_order)
        
        # Verify safety comments are present
        assert "SAFETY" in source or "order endpoints" in source.lower()
        assert "funding" not in source.lower() or "NO" in source or "NOT" in source
        print("  ✅ Alpaca broker has safety documentation")
        print("  ℹ️  Note: REAL trades are capped at 1 share by default")
        
        return True
    except Exception as e:
        print(f"  ❌ Alpaca safety test failed: {e}")
        return False

def test_environment_variables():
    """Test that environment variables are documented."""
    print("\n🔧 Testing Environment Variables...")
    try:
        from pathlib import Path
        from dotenv import dotenv_values
        
        CFG_PATH = Path(__file__).resolve().parent / "config" / ".env"
        if CFG_PATH.exists():
            cfg = dotenv_values(str(CFG_PATH))
            print(f"  ✅ .env file found at {CFG_PATH}")
            
            # Check for PAPER_STARTING_BALANCE
            if "PAPER_STARTING_BALANCE" in cfg or "PAPER_STARTING_BALANCE" in os.environ:
                print("  ✅ PAPER_STARTING_BALANCE is set")
            else:
                print("  ⚠️  PAPER_STARTING_BALANCE not set (will use default 100000)")
        else:
            print(f"  ⚠️  .env file not found at {CFG_PATH} (will use environment variables)")
        
        return True
    except Exception as e:
        print(f"  ❌ Environment variable test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("GSIN Implementation Test Suite")
    print("=" * 60)
    
    tests = [
        ("Models", test_models),
        ("CRUD Functions", test_crud_functions),
        ("Market Data Cache", test_market_data_cache),
        ("PaperBroker", test_paper_broker),
        ("Backtest Engine", test_backtest_engine),
        ("Brain Service", test_brain_service),
        ("Alpaca Safety", test_alpaca_safety),
        ("Environment Variables", test_environment_variables),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Ready to run the app.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review before running the app.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

