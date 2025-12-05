#!/usr/bin/env python3
"""
Test script to verify Supabase database connection.
Run this to test different connection string formats.
"""
import sys
from pathlib import Path
from dotenv import dotenv_values

# Load .env
cfg_path = Path(__file__).parent / "config" / ".env"
cfg = dotenv_values(str(cfg_path)) if cfg_path.exists() else {}
db_url = cfg.get("DATABASE_URL", "")

print("=" * 60)
print("Database Connection Test")
print("=" * 60)
print(f"\nCurrent DATABASE_URL: {db_url[:60]}...\n")

# Test connection
try:
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print("✅ SUCCESS! Database connection working!")
        print(f"PostgreSQL version: {version[:60]}...")
        sys.exit(0)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\n" + "=" * 60)
    print("TROUBLESHOOTING:")
    print("=" * 60)
    print("\n1. Get the correct connection string from Supabase:")
    print("   - Go to: https://supabase.com/dashboard/project/hprlgsbhqmhfljqetfpw")
    print("   - Navigate to: Settings > Database")
    print("   - Copy the 'Connection string' under 'Connection pooling'")
    print("   - Or use 'Direct connection' if pooler doesn't work")
    print("\n2. Update config/.env with the correct DATABASE_URL")
    print("\n3. Common formats:")
    print("   Direct: postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres")
    print("   Pooler: postgresql://postgres.[PROJECT]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres")
    print("\n4. Make sure:")
    print("   - Password is URL-encoded (special chars like @ become %40)")
    print("   - Database is not paused in Supabase dashboard")
    print("   - Your IP is allowed (if IP restrictions are enabled)")
    sys.exit(1)

