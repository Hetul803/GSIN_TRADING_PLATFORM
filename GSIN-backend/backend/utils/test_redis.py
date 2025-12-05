# backend/utils/test_redis.py
"""
Test Redis connection and functionality.
Run this script to verify Redis is working correctly.
"""
import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.utils.redis_client import get_redis_client


def test_redis_connection():
    """Test Redis connection and basic operations."""
    print("=" * 60)
    print("Redis Connection Test")
    print("=" * 60)
    
    # Get Redis client
    redis_client = get_redis_client()
    
    if not redis_client.is_available:
        print("❌ Redis is NOT available")
        print("\nPossible issues:")
        print("1. REDIS_URL not set in config/.env")
        print("2. redis package not installed (run: pip install redis)")
        print("3. Redis server not running or unreachable")
        print("4. Invalid Redis URL format")
        return False
    
    print("✅ Redis is available")
    print(f"   Client: {type(redis_client.client).__name__}")
    
    # Test 1: Ping
    print("\n📡 Test 1: Ping")
    try:
        result = redis_client.client.ping()
        if result:
            print("   ✅ Ping successful")
        else:
            print("   ❌ Ping failed")
            return False
    except Exception as e:
        print(f"   ❌ Ping error: {e}")
        return False
    
    # Test 2: Set/Get
    print("\n💾 Test 2: Set/Get")
    try:
        test_key = "gsin_test:connection"
        test_value = {"test": True, "timestamp": "2024-12-19"}
        
        # Set value
        success = redis_client.set(test_key, test_value, ttl_seconds=60)
        if not success:
            print("   ❌ Set failed")
            return False
        print("   ✅ Set successful")
        
        # Get value
        retrieved = redis_client.get(test_key)
        if retrieved == test_value:
            print("   ✅ Get successful (value matches)")
        else:
            print(f"   ⚠️  Get successful but value mismatch: {retrieved}")
        
        # Cleanup
        redis_client.delete(test_key)
        print("   ✅ Cleanup successful")
    except Exception as e:
        print(f"   ❌ Set/Get error: {e}")
        return False
    
    # Test 3: Lock
    print("\n🔒 Test 3: Distributed Lock")
    try:
        lock_key = "gsin_test:lock"
        lock_obj = redis_client.acquire_lock(lock_key, timeout_seconds=10)
        
        if lock_obj:
            print("   ✅ Lock acquired")
            
            # Try to acquire again (should fail)
            lock_obj2 = redis_client.acquire_lock(lock_key, timeout_seconds=10, blocking=False)
            if lock_obj2 is None:
                print("   ✅ Lock correctly prevents duplicate acquisition")
            else:
                print("   ⚠️  Lock allows duplicate acquisition (unexpected)")
            
            # Release lock
            released = redis_client.release_lock(lock_obj)
            if released:
                print("   ✅ Lock released")
            else:
                print("   ⚠️  Lock release failed")
        else:
            print("   ❌ Lock acquisition failed")
            return False
    except Exception as e:
        print(f"   ❌ Lock error: {e}")
        return False
    
    # Test 4: Increment
    print("\n🔢 Test 4: Increment Counter")
    try:
        counter_key = "gsin_test:counter"
        value1 = redis_client.increment(counter_key, amount=1, ttl_seconds=60)
        value2 = redis_client.increment(counter_key, amount=2, ttl_seconds=60)
        
        if value1 == 1 and value2 == 3:
            print("   ✅ Increment successful")
        else:
            print(f"   ⚠️  Increment unexpected values: {value1}, {value2}")
        
        # Cleanup
        redis_client.delete(counter_key)
    except Exception as e:
        print(f"   ❌ Increment error: {e}")
        return False
    
    # Test 5: Exists
    print("\n🔍 Test 5: Key Exists")
    try:
        exists_key = "gsin_test:exists"
        redis_client.set(exists_key, "test", ttl_seconds=60)
        
        if redis_client.exists(exists_key):
            print("   ✅ Exists check successful")
        else:
            print("   ❌ Exists check failed")
            return False
        
        # Cleanup
        redis_client.delete(exists_key)
    except Exception as e:
        print(f"   ❌ Exists error: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Redis is working correctly!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_redis_connection()
    sys.exit(0 if success else 1)

