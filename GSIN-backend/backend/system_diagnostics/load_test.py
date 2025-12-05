#!/usr/bin/env python3
"""
PHASE 6: Load Testing Script
Simulates 10,000 concurrent users across major endpoints.

Usage:
    python backend/system_diagnostics/load_test.py

Output:
    - Average latency
    - P95 latency
    - Error rates
    - Overload signs
"""

import sys
import asyncio
import aiohttp
import time
from pathlib import Path
from typing import List, Dict, Any
from statistics import mean, median
import json
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CONCURRENT_USERS = 10000
REQUESTS_PER_USER = 5  # Each user makes 5 requests
TOTAL_REQUESTS = CONCURRENT_USERS * REQUESTS_PER_USER

# Test endpoints (without authentication for now - would need JWT tokens in production)
ENDPOINTS = [
    ("GET", "/health"),
    ("GET", "/api/market/price?symbol=AAPL"),
    ("GET", "/api/market/candles?symbol=AAPL&interval=1d&limit=100"),
    ("GET", "/api/market/volatility?symbol=AAPL"),
    ("GET", "/api/market/sentiment?symbol=AAPL"),
]


class LoadTestResults:
    """Container for load test results."""
    
    def __init__(self):
        self.latencies: List[float] = []
        self.errors: List[Dict[str, Any]] = []
        self.status_codes: Dict[int, int] = {}
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def add_result(self, latency: float, status_code: int, error: Optional[str] = None):
        """Add a test result."""
        self.latencies.append(latency)
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
        if error or status_code >= 400:
            self.errors.append({
                "status_code": status_code,
                "error": error,
                "latency_ms": latency * 1000
            })
    
    def calculate_stats(self) -> Dict[str, Any]:
        """Calculate statistics from results."""
        if not self.latencies:
            return {"error": "No results collected"}
        
        sorted_latencies = sorted(self.latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p99_index = int(len(sorted_latencies) * 0.99)
        
        total_time = (self.end_time - self.start_time) if self.end_time and self.start_time else 0
        
        return {
            "total_requests": len(self.latencies),
            "total_errors": len(self.errors),
            "error_rate": len(self.errors) / len(self.latencies) if self.latencies else 0,
            "average_latency_ms": mean(self.latencies) * 1000,
            "median_latency_ms": median(self.latencies) * 1000,
            "p95_latency_ms": sorted_latencies[p95_index] * 1000 if p95_index < len(sorted_latencies) else 0,
            "p99_latency_ms": sorted_latencies[p99_index] * 1000 if p99_index < len(sorted_latencies) else 0,
            "min_latency_ms": min(self.latencies) * 1000,
            "max_latency_ms": max(self.latencies) * 1000,
            "requests_per_second": len(self.latencies) / total_time if total_time > 0 else 0,
            "status_codes": self.status_codes,
            "total_time_seconds": total_time
        }


async def make_request(session: aiohttp.ClientSession, method: str, endpoint: str) -> Dict[str, Any]:
    """Make a single HTTP request."""
    url = f"{BASE_URL}{endpoint}"
    start_time = time.time()
    
    try:
        async with session.request(method, url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            latency = time.time() - start_time
            status_code = response.status
            
            # Try to read response (may fail for large responses)
            try:
                await response.read()
            except:
                pass
            
            return {
                "latency": latency,
                "status_code": status_code,
                "error": None
            }
    except asyncio.TimeoutError:
        return {
            "latency": time.time() - start_time,
            "status_code": 0,
            "error": "Timeout"
        }
    except Exception as e:
        return {
            "latency": time.time() - start_time,
            "status_code": 0,
            "error": str(e)
        }


async def simulate_user(user_id: int, results: LoadTestResults, semaphore: asyncio.Semaphore):
    """Simulate a single user making requests."""
    async with semaphore:
        async with aiohttp.ClientSession() as session:
            # Each user makes requests to different endpoints
            for i, (method, endpoint) in enumerate(ENDPOINTS):
                if i >= REQUESTS_PER_USER:
                    break
                
                result = await make_request(session, method, endpoint)
                results.add_result(
                    result["latency"],
                    result["status_code"],
                    result["error"]
                )
                
                # Small delay between requests
                await asyncio.sleep(0.1)


async def run_load_test():
    """Run the load test."""
    print(f"🚀 Starting load test...")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Concurrent Users: {CONCURRENT_USERS}")
    print(f"   Requests per User: {REQUESTS_PER_USER}")
    print(f"   Total Requests: {CONCURRENT_USERS * REQUESTS_PER_USER}")
    print()
    
    results = LoadTestResults()
    results.start_time = time.time()
    
    # Limit concurrent connections to avoid overwhelming the server
    semaphore = asyncio.Semaphore(100)  # Max 100 concurrent connections
    
    # Create tasks for all users
    tasks = [
        simulate_user(i, results, semaphore)
        for i in range(CONCURRENT_USERS)
    ]
    
    # Run all tasks
    print("⏳ Running load test (this may take a while)...")
    await asyncio.gather(*tasks, return_exceptions=True)
    
    results.end_time = time.time()
    
    # Calculate and print statistics
    stats = results.calculate_stats()
    
    print("\n" + "="*80)
    print("LOAD TEST RESULTS")
    print("="*80)
    print(f"Total Requests: {stats['total_requests']}")
    print(f"Total Errors: {stats['total_errors']}")
    print(f"Error Rate: {stats['error_rate']:.2%}")
    print()
    print("LATENCY STATISTICS:")
    print(f"  Average: {stats['average_latency_ms']:.2f}ms")
    print(f"  Median:  {stats['median_latency_ms']:.2f}ms")
    print(f"  P95:     {stats['p95_latency_ms']:.2f}ms")
    print(f"  P99:     {stats['p99_latency_ms']:.2f}ms")
    print(f"  Min:     {stats['min_latency_ms']:.2f}ms")
    print(f"  Max:     {stats['max_latency_ms']:.2f}ms")
    print()
    print(f"Requests per Second: {stats['requests_per_second']:.2f}")
    print(f"Total Time: {stats['total_time_seconds']:.2f}s")
    print()
    print("STATUS CODES:")
    for code, count in sorted(stats['status_codes'].items()):
        print(f"  {code}: {count}")
    
    # Check for overload signs
    print()
    print("OVERLOAD ANALYSIS:")
    overload_signs = []
    
    if stats['error_rate'] > 0.05:  # >5% error rate
        overload_signs.append(f"High error rate: {stats['error_rate']:.2%}")
    
    if stats['p95_latency_ms'] > 5000:  # >5s P95
        overload_signs.append(f"High P95 latency: {stats['p95_latency_ms']:.2f}ms")
    
    if stats['requests_per_second'] < 10:  # <10 req/s
        overload_signs.append(f"Low throughput: {stats['requests_per_second']:.2f} req/s")
    
    if overload_signs:
        print("  ⚠️  OVERLOAD SIGNS DETECTED:")
        for sign in overload_signs:
            print(f"     - {sign}")
    else:
        print("  ✅ No overload signs detected")
    
    print("\n" + "="*80)
    
    # Save results to file
    output_file = Path(__file__).parent / "load_test_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "config": {
                "base_url": BASE_URL,
                "concurrent_users": CONCURRENT_USERS,
                "requests_per_user": REQUESTS_PER_USER
            },
            "results": stats,
            "overload_signs": overload_signs
        }, f, indent=2)
    
    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    import os
    asyncio.run(run_load_test())

