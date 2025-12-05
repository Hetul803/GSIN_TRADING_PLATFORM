#!/usr/bin/env python3
"""Test different Supabase regions"""
import psycopg2
from urllib.parse import quote

password = "Hetul@7698676686"
password_encoded = quote(password, safe='')
project_ref = "hprlgsbhqmhfljqetfpw"

# Common Supabase regions
regions = [
    "us-east-1",
    "us-west-1", 
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-central-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
]

print("Testing different Supabase regions...\n")
for region in regions:
    conn_str = f"postgresql://postgres.{project_ref}:{password_encoded}@aws-0-{region}.pooler.supabase.com:6543/postgres"
    print(f"Testing {region}...", end=" ")
    try:
        conn = psycopg2.connect(conn_str, connect_timeout=5)
        print(f"✅ SUCCESS!")
        conn.close()
        print(f"\n✅ Working connection string:")
        print(f"   DATABASE_URL={conn_str}\n")
        break
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        if "Tenant or user not found" in error_msg:
            print("❌ Wrong region (tenant not found)")
        elif "could not translate host" in error_msg:
            print("❌ DNS failed")
        else:
            print(f"❌ {error_msg[:50]}...")
    except Exception as e:
        print(f"❌ {str(e)[:50]}...")
else:
    print("\n❌ None of the regions worked.")
    print("\nThe database might be:")
    print("1. Paused - Check Supabase dashboard")
    print("2. Using a different connection format")
    print("3. Have IP restrictions enabled")
    print("\nPlease get the exact connection string from:")
    print("   Supabase Dashboard > Settings > Database > Connection string")
