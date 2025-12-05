# backend/utils/correlation_id.py
"""
Correlation ID utilities for request tracking.
"""
import uuid
from contextvars import ContextVar
from typing import Optional

# Context variable for correlation ID
_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return _correlation_id.get()


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID (generate if not provided)."""
    if cid is None:
        cid = str(uuid.uuid4())
    _correlation_id.set(cid)
    return cid


def clear_correlation_id():
    """Clear correlation ID."""
    _correlation_id.set(None)

