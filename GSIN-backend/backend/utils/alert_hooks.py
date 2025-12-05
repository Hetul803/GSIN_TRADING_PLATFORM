# backend/utils/alert_hooks.py
"""
Alert hooks for critical events.
Currently logs; can be wired to PagerDuty/Slack in the future.
"""
import os
from typing import Dict, Any, Optional
from datetime import datetime
from .logger import log


def notify_ops_critical(event: Dict[str, Any]):
    """
    Notify operations team of critical event.
    
    Currently logs; can be wired to PagerDuty/Slack later.
    
    Args:
        event: Event dictionary with:
            - type: Event type (e.g., "broker_failure", "rate_limit_issue", "mcn_init_failure")
            - severity: "critical", "warning", "info"
            - message: Human-readable message
            - details: Additional context
    """
    severity = event.get("severity", "info")
    event_type = event.get("type", "unknown")
    message = event.get("message", "")
    details = event.get("details", {})
    
    log_msg = f"🚨 CRITICAL ALERT [{event_type}]: {message}"
    if details:
        log_msg += f" | Details: {details}"
    
    if severity == "critical":
        log(f"🔴 {log_msg}", level="ERROR")
    elif severity == "warning":
        log(f"⚠️  {log_msg}", level="WARNING")
    else:
        log(f"ℹ️  {log_msg}", level="INFO")
    
    # TODO: Wire to external alerting (PagerDuty, Slack, etc.)
    # if severity == "critical":
    #     send_pagerduty_alert(event)
    #     send_slack_alert(event)


def notify_broker_failure(broker_name: str, error: str, user_id: Optional[str] = None):
    """Notify of broker API failure."""
    notify_ops_critical({
        "type": "broker_failure",
        "severity": "critical",
        "message": f"Broker API failure: {broker_name}",
        "details": {
            "broker": broker_name,
            "error": error,
            "user_id": user_id,
        }
    })


def notify_rate_limit_issue(provider: str, endpoint: str, retry_count: int):
    """Notify of repeated rate limit issues."""
    severity = "critical" if retry_count > 5 else "warning"
    notify_ops_critical({
        "type": "rate_limit_issue",
        "severity": severity,
        "message": f"Rate limit issue: {provider} - {endpoint} (retries: {retry_count})",
        "details": {
            "provider": provider,
            "endpoint": endpoint,
            "retry_count": retry_count,
        }
    })


def notify_mcn_init_failure(error: str):
    """Notify of MCN initialization failure in production."""
    notify_ops_critical({
        "type": "mcn_init_failure",
        "severity": "critical",
        "message": f"MCN initialization failed in production",
        "details": {
            "error": error,
            "environment": os.getenv("ENVIRONMENT", "unknown"),
        }
    })

