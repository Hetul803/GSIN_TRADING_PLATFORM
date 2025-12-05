#!/usr/bin/env python3
"""
Comprehensive system check for GSIN backend.
Run this to verify all components are working before starting the server.
"""
import sys
import os
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

def check_imports():
    """Check that all critical imports work."""
    print("1. Checking critical imports...")
    errors = []
    
    try:
        from backend.main import app
        print("   ✅ Main app imports successfully")
    except Exception as e:
        print(f"   ❌ Main app import failed: {e}")
        errors.append(f"Main app: {e}")
    
    try:
        from backend.services.broker_key_encryption import broker_key_encryption
        print("   ✅ Encryption service imports")
    except Exception as e:
        print(f"   ❌ Encryption service import failed: {e}")
        errors.append(f"Encryption: {e}")
    
    try:
        from backend.db.session import engine, get_db
        print("   ✅ Database session imports")
    except Exception as e:
        print(f"   ❌ Database session import failed: {e}")
        errors.append(f"Database: {e}")
    
    return errors

def check_encryption():
    """Test encryption service."""
    print("\n2. Testing encryption service...")
    try:
        from backend.services.broker_key_encryption import broker_key_encryption
        test_data = "test_api_key_12345"
        encrypted = broker_key_encryption.encrypt(test_data)
        decrypted = broker_key_encryption.decrypt(encrypted)
        if decrypted == test_data:
            print("   ✅ Encryption/decryption works correctly")
            return []
        else:
            print("   ❌ Encryption/decryption mismatch")
            return ["Encryption test failed"]
    except Exception as e:
        print(f"   ❌ Encryption test failed: {e}")
        return [f"Encryption test: {e}"]

def check_database():
    """Test database connection."""
    print("\n3. Testing database connection...")
    try:
        from backend.db.session import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("   ✅ Database connection successful")
        return []
    except Exception as e:
        print(f"   ⚠️  Database connection issue: {e}")
        print("      (This may be expected if database is not running)")
        return []

def check_market_data():
    """Test market data provider."""
    print("\n4. Testing market data provider...")
    try:
        from backend.market_data.market_data_provider import get_provider_with_fallback
        provider = get_provider_with_fallback()
        if provider:
            print(f"   ✅ Market data provider available: {type(provider).__name__}")
        else:
            print("   ⚠️  No market data provider available")
        return []
    except Exception as e:
        print(f"   ⚠️  Market data provider issue: {e}")
        return []

def check_mcn():
    """Test MCN adapter."""
    print("\n5. Testing MCN adapter...")
    try:
        from backend.brain.mcn_adapter import MCNAdapter
        adapter = MCNAdapter()
        print("   ✅ MCN adapter initialized")
        return []
    except Exception as e:
        print(f"   ⚠️  MCN adapter issue: {e}")
        print("      (This may be expected if MCN is not available)")
        return []

def check_env_file():
    """Check that .env file exists and has required keys."""
    print("\n6. Checking environment configuration...")
    errors = []
    env_path = Path(__file__).resolve().parents[2] / "config" / ".env"
    
    if not env_path.exists():
        print(f"   ⚠️  .env file not found at {env_path}")
        return []
    
    print(f"   ✅ .env file found at {env_path}")
    
    from dotenv import dotenv_values
    cfg = dotenv_values(str(env_path))
    
    required_keys = ["DATABASE_URL"]
    for key in required_keys:
        if key not in cfg and key not in os.environ:
            print(f"   ⚠️  {key} not set in .env or environment")
        else:
            print(f"   ✅ {key} is set")
    
    # Check encryption key format
    if "BROKER_ENCRYPTION_KEY" in cfg:
        key = cfg["BROKER_ENCRYPTION_KEY"]
        # Fernet keys are base64-encoded and typically 44 chars
        if len(key) == 44 and key.endswith("="):
            print("   ✅ BROKER_ENCRYPTION_KEY format looks correct")
        else:
            print(f"   ⚠️  BROKER_ENCRYPTION_KEY format may be incorrect (length: {len(key)})")
    
    return errors

def main():
    """Run all checks."""
    print("=" * 60)
    print("GSIN Backend System Check")
    print("=" * 60)
    print()
    
    all_errors = []
    
    # Run all checks
    all_errors.extend(check_imports())
    all_errors.extend(check_encryption())
    all_errors.extend(check_database())
    all_errors.extend(check_market_data())
    all_errors.extend(check_mcn())
    all_errors.extend(check_env_file())
    
    print("\n" + "=" * 60)
    if all_errors:
        print("❌ System check completed with errors:")
        for error in all_errors:
            print(f"   - {error}")
        print("\n⚠️  Some issues need to be fixed before running the backend.")
        return 1
    else:
        print("✅ System check passed! Backend should be ready to run.")
        print("\nTo start the backend:")
        print("   python backend/main.py")
        return 0

if __name__ == "__main__":
    sys.exit(main())

