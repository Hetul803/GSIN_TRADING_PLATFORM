#!/usr/bin/env python3
"""
Test runner for all GSIN backend tests.
Runs unit, integration, and E2E tests and prints summary.
"""
import sys
import subprocess
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def run_tests(test_type: str, verbose: bool = False) -> tuple[bool, str]:
    """Run tests of a specific type."""
    test_path = ROOT / "tests" / test_type
    if not test_path.exists():
        return False, f"Test directory not found: {test_path}"
    
    cmd = ["python", "-m", "pytest", str(test_path)]
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Tests timed out after 5 minutes"
    except Exception as e:
        return False, f"Error running tests: {str(e)}"


def main():
    """Run all tests and print summary."""
    print("=" * 60)
    print("GSIN Backend Test Suite")
    print("=" * 60)
    print()
    
    results = {}
    
    # Run unit tests
    print("Running UNIT tests...")
    unit_passed, unit_output = run_tests("unit", verbose=False)
    results["UNIT"] = unit_passed
    if not unit_passed:
        print("❌ UNIT tests FAILED")
        print(unit_output[-500:])  # Last 500 chars
    else:
        print("✅ UNIT tests PASSED")
    print()
    
    # Run integration tests
    print("Running INTEGRATION tests...")
    integration_passed, integration_output = run_tests("integration", verbose=False)
    results["INTEGRATION"] = integration_passed
    if not integration_passed:
        print("❌ INTEGRATION tests FAILED")
        print(integration_output[-500:])
    else:
        print("✅ INTEGRATION tests PASSED")
    print()
    
    # Run E2E tests
    print("Running E2E tests...")
    e2e_passed, e2e_output = run_tests("e2e", verbose=False)
    results["E2E"] = e2e_passed
    if not e2e_passed:
        print("❌ E2E tests FAILED")
        print(e2e_output[-500:])
    else:
        print("✅ E2E tests PASSED")
    print()
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"UNIT:        {'✅ PASSED' if results['UNIT'] else '❌ FAILED'}")
    print(f"INTEGRATION: {'✅ PASSED' if results['INTEGRATION'] else '❌ FAILED'}")
    print(f"E2E:         {'✅ PASSED' if results['E2E'] else '❌ FAILED'}")
    print()
    
    all_passed = all(results.values())
    print(f"READY_FOR_PRODUCTION: {'✅ TRUE' if all_passed else '❌ FALSE'}")
    print()
    
    if not all_passed:
        print("⚠️  Some tests failed. Please fix issues before deploying.")
        sys.exit(1)
    else:
        print("✅ All tests passed! System is ready for production.")
        sys.exit(0)


if __name__ == "__main__":
    main()

