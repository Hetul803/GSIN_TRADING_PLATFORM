#!/usr/bin/env python3
"""
Run security audit on the codebase.
"""
import sys
from pathlib import Path

# Add backend to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from backend.utils.security_audit import run_security_audit


def main():
    """Run security audit."""
    print("=" * 60)
    print("GSIN Security Audit")
    print("=" * 60)
    print()
    
    results = run_security_audit(str(ROOT))
    
    print("Security Audit Results:")
    print(f"Total Issues: {results['total_issues']}")
    print(f"High Severity: {results['high_severity']}")
    print()
    
    for category, issues in results['results'].items():
        if issues:
            print(f"\n{category.upper().replace('_', ' ')}:")
            for issue in issues:
                severity = issue.get('severity', 'UNKNOWN')
                file = issue.get('file', 'unknown')
                message = issue.get('message', 'No message')
                print(f"  [{severity}] {file}: {message}")
    
    print()
    print("=" * 60)
    print(f"Status: {results['summary']['status']}")
    print(results['summary']['message'])
    print("=" * 60)
    
    if results['high_severity'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

