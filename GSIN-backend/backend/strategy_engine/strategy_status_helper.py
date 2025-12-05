# backend/strategy_engine/strategy_status_helper.py
"""
Centralized Strategy Status Management with Notification Hooks.

This module provides a single point of control for strategy status changes,
ensuring all status transitions trigger appropriate notifications.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..db import crud
from ..db.models import UserStrategy
from .status_manager import StrategyStatus
from ..utils.logger import log


def set_strategy_status(
    db: Session,
    strategy: UserStrategy,
    new_status: str,
    reason: Optional[str] = None,
    triggered_by: str = "system",
    update_is_active: Optional[bool] = None,
    **kwargs
) -> bool:
    """
    Centralized function to update strategy status and send notifications.
    
    Args:
        db: Database session
        strategy: Strategy to update
        new_status: New status (from StrategyStatus enum)
        reason: Optional reason for status change
        triggered_by: "system" or "user"
        update_is_active: Optional override for is_active flag
        **kwargs: Additional fields to update (e.g., score, is_proposable)
    
    Returns:
        True if update was successful
    """
    old_status = strategy.status or StrategyStatus.EXPERIMENT
    
    # Don't do anything if status hasn't changed
    if old_status == new_status:
        return True
    
    try:
        # Determine is_active based on status if not explicitly provided
        if update_is_active is None:
            update_is_active = new_status not in [
                StrategyStatus.DISCARDED,
                StrategyStatus.REJECTED,
                StrategyStatus.DUPLICATE,
                StrategyStatus.PENDING_REVIEW
            ]
        
        # Determine is_proposable
        is_proposable = new_status == StrategyStatus.PROPOSABLE
        
        # Update strategy
        update_data = {
            "status": new_status,
            "is_active": update_is_active,
            "is_proposable": is_proposable,
            **kwargs
        }
        
        crud.update_user_strategy(
            db=db,
            strategy_id=strategy.id,
            **update_data
        )
        
        # Send notification
        _send_strategy_notification(
            db=db,
            user_id=strategy.user_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            old_status=old_status,
            new_status=new_status,
            reason=reason
        )
        
        log(f"✅ Strategy {strategy.id} status changed: {old_status} → {new_status} (triggered by: {triggered_by})")
        
        return True
    
    except Exception as e:
        log(f"❌ Failed to update strategy status: {e}")
        import traceback
        traceback.print_exc()
        return False


def _send_strategy_notification(
    db: Session,
    user_id: str,
    strategy_id: str,
    strategy_name: str,
    old_status: str,
    new_status: str,
    reason: Optional[str] = None
) -> bool:
    """Send a notification to the user about strategy status change."""
    try:
        from ..db.models import Notification
        import uuid
        
        # Map status to notification title/body
        notification_templates = {
            StrategyStatus.PENDING_REVIEW: {
                "title": "Strategy Under Review",
                "body": f"Your strategy '{strategy_name}' was received and is under review."
            },
            StrategyStatus.DUPLICATE: {
                "title": "Strategy Marked as Duplicate",
                "body": f"Your strategy '{strategy_name}' matches an existing strategy and was marked as duplicate. You will not receive royalties for this one."
            },
            StrategyStatus.REJECTED: {
                "title": "Strategy Rejected",
                "body": f"Your strategy '{strategy_name}' was rejected. {reason or 'Reason: Strategy failed initial validation checks.'}"
            },
            StrategyStatus.EXPERIMENT: {
                "title": "Strategy Accepted",
                "body": f"Your strategy '{strategy_name}' passed initial checks and is now being backtested by the Brain."
            },
            StrategyStatus.CANDIDATE: {
                "title": "Strategy Promoted to Candidate",
                "body": f"Your strategy '{strategy_name}' is showing promising results and moved to candidate status."
            },
            StrategyStatus.PROPOSABLE: {
                "title": "Strategy Now Live!",
                "body": f"Your strategy '{strategy_name}' has passed robustness checks and is now available for other users to run. You are now eligible for royalties according to your plan."
            },
            StrategyStatus.DISCARDED: {
                "title": "Strategy Deprecated",
                "body": f"Your strategy '{strategy_name}' has been deprecated based on new performance data."
            },
        }
        
        # Only send notification if status changed to a new status that has a template
        if new_status not in notification_templates:
            return False
        
        # Don't send notification if transitioning from pending_review to experiment (already handled)
        if old_status == StrategyStatus.PENDING_REVIEW and new_status == StrategyStatus.EXPERIMENT:
            # This notification is already sent by Monitoring Worker
            return True
        
        template = notification_templates[new_status]
        
        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=template["title"],
            body=template["body"],
            read_flag=False,
        )
        
        db.add(notification)
        db.commit()
        
        return True
    
    except Exception as e:
        log(f"⚠️  Failed to send notification: {e}")
        return False

