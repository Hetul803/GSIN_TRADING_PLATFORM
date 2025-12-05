#!/usr/bin/env python3
"""Test different Supabase connection string formats"""
import psycopg2
from urllib.parse import quote

password = "Hetul@7698676686"
password_encoded = quote(password, safe='')
project_ref = "hprlgsbhqmhfljqetfpw"

# Try different formats
formats = [
    f"postgresql://postgres:{password_encoded}@db.{project_ref}.supabase.co:5432/postgres",
    f"postgresql://postgres:{password_encoded}@{project_ref}.supabase.co:5432/postgres",
    f"postgresql://postgres.{project_ref}:{password_encoded}@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
    f"postgresql://postgres.{project_ref}:{password_encoded}@aws-0-us-west-1.pooler.supabase.com:6543/postgres",
]

print("Testing connection string formats...\n")
for i, conn_str in enumerate(formats, 1):
    print(f"Format {i}: {conn_str[:60]}...")
    try:
        conn = psycopg2.connect(conn_str, connect_timeout=5)
        print(f"  ✅ SUCCESS! This format works!")
        conn.close()
        print(f"\n✅ Use this DATABASE_URL in config/.env:")
        print(f"   DATABASE_URL={conn_str}\n")
        break
    except Exception as e:
        print(f"  ❌ Failed: {str(e)[:60]}...")
        if i == len(formats):
            print("\n❌ None of the formats worked.")
            print("\nPlease get the connection string from Supabase dashboard:")
            print("1. Go to: https://supabase.com/dashboard/project/hprlgsbhqmhfljqetfpw")
            print("2. Settings > Database")
            print("3. Copy the 'Connection string' (URI format)")
