# backend/utils/security_audit.py
"""
Security audit utilities for checking common vulnerabilities.
"""
import os
import re
from typing import Dict, List, Any
from pathlib import Path


class SecurityAuditor:
    """Security audit tool for codebase."""
    
    def __init__(self, root_path: str = None):
        self.root_path = Path(root_path) if root_path else Path(__file__).parent.parent.parent
        self.issues: List[Dict[str, Any]] = []
    
    def check_hardcoded_secrets(self) -> List[Dict[str, Any]]:
        """Check for hardcoded secrets in code."""
        issues = []
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
            (r'private_key\s*=\s*["\'][^"\']+["\']', "Hardcoded private key"),
            (r'JWT_SECRET\s*=\s*["\'][^"\']+["\']', "Hardcoded JWT secret"),
        ]
        
        for py_file in self.root_path.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                for pattern, issue_type in secret_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        issues.append({
                            "type": issue_type,
                            "file": str(py_file.relative_to(self.root_path)),
                            "line": content[:match.start()].count('\n') + 1,
                            "severity": "HIGH",
                            "message": f"Potential hardcoded secret found"
                        })
            except Exception:
                pass
        
        return issues
    
    def check_sql_injection(self) -> List[Dict[str, Any]]:
        """Check for potential SQL injection vulnerabilities."""
        issues = []
        
        for py_file in self.root_path.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                # Check for string formatting in SQL queries
                if re.search(r'execute\s*\([^)]*%[^)]*\)', content):
                    issues.append({
                        "type": "SQL Injection Risk",
                        "file": str(py_file.relative_to(self.root_path)),
                        "severity": "HIGH",
                        "message": "Potential SQL injection via string formatting"
                    })
            except Exception:
                pass
        
        return issues
    
    def check_weak_crypto(self) -> List[Dict[str, Any]]:
        """Check for weak cryptographic implementations."""
        issues = []
        
        for py_file in self.root_path.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                # Check for MD5 or SHA1 usage
                if re.search(r'hashlib\.(md5|sha1)', content):
                    issues.append({
                        "type": "Weak Cryptography",
                        "file": str(py_file.relative_to(self.root_path)),
                        "severity": "MEDIUM",
                        "message": "MD5 or SHA1 detected - use SHA256 or better"
                    })
            except Exception:
                pass
        
        return issues
    
    def check_cors_config(self) -> List[Dict[str, Any]]:
        """Check CORS configuration."""
        issues = []
        
        main_py = self.root_path / "backend" / "main.py"
        if main_py.exists():
            content = main_py.read_text()
            # Check for overly permissive CORS
            if 'allow_origins=["*"]' in content or "allow_origins=['*']" in content:
                issues.append({
                    "type": "CORS Configuration",
                    "file": "backend/main.py",
                    "severity": "MEDIUM",
                    "message": "CORS allows all origins - restrict in production"
                })
        
        return issues
    
    def check_env_vars(self) -> List[Dict[str, Any]]:
        """Check environment variable usage."""
        issues = []
        
        # Check if sensitive env vars are being logged
        for py_file in self.root_path.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                # Check for logging of sensitive env vars
                sensitive_vars = ["JWT_SECRET", "API_KEY", "SECRET", "PASSWORD", "TOKEN"]
                for var in sensitive_vars:
                    if re.search(rf'log.*{var}|print.*{var}', content, re.IGNORECASE):
                        issues.append({
                            "type": "Sensitive Data Exposure",
                            "file": str(py_file.relative_to(self.root_path)),
                            "severity": "HIGH",
                            "message": f"Potential logging of sensitive variable: {var}"
                        })
            except Exception:
                pass
        
        return issues
    
    def run_full_audit(self) -> Dict[str, Any]:
        """Run full security audit."""
        results = {
            "hardcoded_secrets": self.check_hardcoded_secrets(),
            "sql_injection": self.check_sql_injection(),
            "weak_crypto": self.check_weak_crypto(),
            "cors_config": self.check_cors_config(),
            "env_vars": self.check_env_vars(),
        }
        
        total_issues = sum(len(issues) for issues in results.values())
        high_severity = sum(
            1 for issues in results.values()
            for issue in issues
            if issue.get("severity") == "HIGH"
        )
        
        return {
            "total_issues": total_issues,
            "high_severity": high_severity,
            "results": results,
            "summary": {
                "status": "PASS" if high_severity == 0 else "FAIL",
                "message": f"Found {total_issues} issues ({high_severity} high severity)"
            }
        }


def run_security_audit(root_path: str = None) -> Dict[str, Any]:
    """Run security audit and return results."""
    auditor = SecurityAuditor(root_path)
    return auditor.run_full_audit()

