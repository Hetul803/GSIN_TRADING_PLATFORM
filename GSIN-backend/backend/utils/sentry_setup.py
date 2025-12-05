# backend/utils/sentry_setup.py
"""
Sentry error monitoring setup.
"""
import os
from pathlib import Path
from dotenv import dotenv_values

# Try to import Sentry
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.httpx import HttpxIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    sentry_sdk = None
    SENTRY_AVAILABLE = False
    # Only show warning if SENTRY_DSN is set (user wants Sentry but SDK not installed)
    import os
    from pathlib import Path
    from dotenv import dotenv_values
    CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
    cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
    if os.getenv("SENTRY_DSN") or cfg.get("SENTRY_DSN"):
        print("WARNING: sentry-sdk not installed. Error monitoring disabled. Install with: pip install sentry-sdk")


def init_sentry():
    """Initialize Sentry error monitoring."""
    if not SENTRY_AVAILABLE:
        return False
    
    # Load config
    CFG_PATH = Path(__file__).resolve().parents[3] / "config" / ".env"
    cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}
    
    sentry_dsn = os.environ.get("SENTRY_DSN") or cfg.get("SENTRY_DSN")
    
    if not sentry_dsn:
        print("⚠️  SENTRY_DSN not set. Error monitoring disabled.")
        return False
    
    try:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                HttpxIntegration(),
            ],
            traces_sample_rate=0.1,  # 10% of transactions
            profiles_sample_rate=0.1,  # 10% of transactions
            environment=os.environ.get("ENVIRONMENT", "development"),
            release=os.environ.get("APP_VERSION", "0.3.0"),
        )
        print("✅ Sentry error monitoring initialized")
        return True
    except Exception as e:
        print(f"⚠️  Failed to initialize Sentry: {e}")
        return False


def capture_exception(error: Exception, **context):
    """Capture an exception with context."""
    if SENTRY_AVAILABLE and sentry_sdk:
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_context(key, value)
            sentry_sdk.capture_exception(error)
    else:
        # Fallback to logging
        import traceback
        print(f"Error: {error}")
        traceback.print_exc()


def capture_message(message: str, level: str = "info", **context):
    """Capture a message with context."""
    if SENTRY_AVAILABLE and sentry_sdk:
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_context(key, value)
            sentry_sdk.capture_message(message, level=level)
    else:
        print(f"[{level.upper()}] {message}")

