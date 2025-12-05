#!/usr/bin/env python3
"""
Run performance tests on the API.
"""
import asyncio
import time
import httpx
from typing import List, Dict, Any


async def test_endpoint(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict = None,
    json: dict = None
) -> Dict[str, Any]:
    """Test a single endpoint."""
    start = time.time()
    try:
        if method == "GET":
            response = await client.get(url, headers=headers)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=json)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        duration = time.time() - start
        return {
            "url": url,
            "method": method,
            "status_code": response.status_code,
            "duration": duration,
            "success": 200 <= response.status_code < 300
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "url": url,
            "method": method,
            "error": str(e),
            "duration": duration,
            "success": False
        }


async def run_performance_tests(base_url: str = "http://localhost:8000"):
    """Run performance tests."""
    print("=" * 60)
    print("GSIN Performance Tests")
    print("=" * 60)
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        tests = [
            ("GET", f"{base_url}/health"),
            ("GET", f"{base_url}/ready"),
            ("GET", f"{base_url}/api/strategies"),
        ]
        
        results = []
        for method, url in tests:
            print(f"Testing {method} {url}...")
            result = await test_endpoint(client, method, url)
            results.append(result)
            if result.get("success"):
                print(f"  ✅ {result['duration']:.3f}s - Status {result['status_code']}")
            else:
                print(f"  ❌ {result.get('error', 'Failed')}")
        
        print()
        print("=" * 60)
        print("Performance Summary")
        print("=" * 60)
        
        successful = [r for r in results if r.get("success")]
        if successful:
            durations = [r["duration"] for r in successful]
            print(f"Successful requests: {len(successful)}/{len(results)}")
            print(f"Average duration: {sum(durations)/len(durations):.3f}s")
            print(f"Min duration: {min(durations):.3f}s")
            print(f"Max duration: {max(durations):.3f}s")
        else:
            print("No successful requests")


if __name__ == "__main__":
    asyncio.run(run_performance_tests())

