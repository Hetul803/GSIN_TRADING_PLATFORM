# backend/utils/env_validator.py
"""
Environment variable validation on startup.
Ensures all required environment variables are set.
"""
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import dotenv_values

# Load .env file before validation
# Go up from backend/utils/env_validator.py -> backend/utils -> backend -> GSIN-backend -> gsin_new_git (repo root)
CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
if CFG_PATH.exists():
    cfg = dotenv_values(str(CFG_PATH))
    # Set environment variables from .env file if not already set
    for key, value in cfg.items():
        if value and not os.getenv(key):
            os.environ[key] = value

# Note: REQUIRED_ENV_VARS moved below to include all required vars

# Required environment variables (must be set)
REQUIRED_ENV_VARS = [
    "DATABASE_URL",  # PostgreSQL connection (Supabase)
    "JWT_SECRET_KEY",  # Authentication (min 32 chars)
    "TWELVEDATA_API_KEY",  # Market data (377 credits/min)
    "ALPACA_API_KEY",  # Broker integration
    "ALPACA_SECRET_KEY",  # Broker integration
]

# Optional but recommended environment variables
RECOMMENDED_ENV_VARS = [
    "SENTRY_DSN",  # Error tracking
    "ALLOWED_ORIGINS",  # CORS configuration
    "REDIS_URL",  # Caching (optional)
    "QDRANT_URL",  # MCN embeddings (optional)
    "QDRANT_API_KEY",  # MCN embeddings (optional)
]

# Environment variable descriptions
ENV_VAR_DESCRIPTIONS: Dict[str, str] = {
    "DATABASE_URL": "PostgreSQL database connection string",
    "SENTRY_DSN": "Sentry error tracking DSN (optional but recommended)",
    "JWT_SECRET_KEY": "Secret key for JWT token signing",
    "TWELVEDATA_API_KEY": "Twelve Data API key for market data",
    "ALPACA_API_KEY": "Alpaca API key for broker integration",
    "ALPACA_SECRET_KEY": "Alpaca secret key for broker integration",
    "MCN_STORAGE_PATH": "Path to MCN storage directory (default: ./mcn_store)",
    "EVOLUTION_INTERVAL_SECONDS": "Evolution Worker interval in seconds (default: 480)",
    "MONITORING_WORKER_INTERVAL_SECONDS": "Monitoring Worker interval in seconds (default: 900)",
    "MAX_CONCURRENT_BACKTESTS": "Maximum concurrent backtests (default: 3)",
    "REDIS_URL": "Redis connection URL for caching and distributed locks (optional but recommended)",
}


def validate_env_vars() -> Dict[str, Any]:
    """
    Validate environment variables on startup.
    
    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "missing_required": List[str],
            "missing_recommended": List[str],
            "warnings": List[str]
        }
    """
    result = {
        "valid": True,
        "missing_required": [],
        "missing_recommended": [],
        "warnings": []
    }
    
    # Check required variables
    for var in REQUIRED_ENV_VARS:
        if not os.getenv(var):
            result["missing_required"].append(var)
            result["valid"] = False
    
    # Check recommended variables
    for var in RECOMMENDED_ENV_VARS:
        if not os.getenv(var):
            result["missing_recommended"].append(var)
    
    # Additional validation checks
    # Check if DATABASE_URL is set or if we're using Supabase connection
    if not os.getenv("DATABASE_URL") and not os.getenv("SUPABASE_DB_URL"):
        result["warnings"].append(
            "DATABASE_URL or SUPABASE_DB_URL not set. "
            "Database connection might fail if not configured via Supabase."
        )
    
    # Check JWT_SECRET_KEY strength
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if jwt_secret and len(jwt_secret) < 32:
        result["warnings"].append(
            "JWT_SECRET_KEY is too short (minimum 32 characters recommended for security)"
        )
    
    return result


def print_env_validation(validation_result: Dict[str, Any]) -> None:
    """Print environment variable validation results."""
    if not validation_result["valid"]:
        print("❌ ENVIRONMENT VALIDATION FAILED")
        print(f"   Missing required variables: {', '.join(validation_result['missing_required'])}")
    else:
        print("✅ Environment validation passed")
    
    if validation_result["missing_recommended"]:
        print("⚠️  Missing recommended variables:")
        for var in validation_result["missing_recommended"]:
            desc = ENV_VAR_DESCRIPTIONS.get(var, "No description")
            print(f"   - {var}: {desc}")
    
    if validation_result["warnings"]:
        print("⚠️  Warnings:")
        for warning in validation_result["warnings"]:
            print(f"   - {warning}")


def get_env_summary() -> Dict[str, Any]:
    """Get summary of environment configuration (without sensitive values)."""
    summary = {
        "database_configured": bool(os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")),
        "sentry_configured": bool(os.getenv("SENTRY_DSN")),
        "jwt_configured": bool(os.getenv("JWT_SECRET_KEY")),
        "market_data_configured": {
            "twelvedata": bool(os.getenv("TWELVEDATA_API_KEY")),
            "alpaca": bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY")),
        },
        "mcn_storage_path": os.getenv("MCN_STORAGE_PATH", "./mcn_store"),
        "evolution_interval": int(os.getenv("EVOLUTION_INTERVAL_SECONDS", "480")),
        "monitoring_interval": int(os.getenv("MONITORING_WORKER_INTERVAL_SECONDS", "900")),
        "max_concurrent_backtests": int(os.getenv("MAX_CONCURRENT_BACKTESTS", "3")),
    }
    return summary

