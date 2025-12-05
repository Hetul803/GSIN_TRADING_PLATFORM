# backend/api/notifications.py
"""
PHASE 2: Notifications API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timezone
import uuid

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db.models import Notification, UserRole
from ..db import crud

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: str
    user_id: Optional[str]
    title: str
    body: str
    read_flag: bool
    created_at: str
    created_by: Optional[str] = None


class NotificationCreateRequest(BaseModel):
    user_id: Optional[str] = None  # None = all users
    title: str
    body: str


@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db),
    unread_only: bool = Query(False, description="Filter to unread only")
):
    """Get notifications for the current user."""
    # FIX: Use SQLAlchemy's or_() instead of Python's | operator
    from sqlalchemy import or_
    query = db.query(Notification).filter(
        or_(
            Notification.user_id == user_id,
            Notification.user_id.is_(None)
        )
    )
    
    if unread_only:
        query = query.filter(Notification.read_flag == False)
    
    notifications = query.order_by(Notification.created_at.desc()).all()
    
    return [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            title=n.title,
            body=n.body,
            read_flag=n.read_flag,
            created_at=n.created_at.isoformat() if n.created_at else "",
            created_by=n.created_by,
        )
        for n in notifications
    ]


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Check ownership (user-specific notifications only)
    if notification.user_id and notification.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark your own notifications as read"
        )
    
    notification.read_flag = True
    db.commit()
    
    return {"message": "Notification marked as read"}


# Admin endpoints for creating notifications
def verify_admin(db: Session, user_id: str) -> None:
    """Verify that the user is an admin."""
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


@router.post("/admin", response_model=NotificationResponse)
async def create_notification(
    request: NotificationCreateRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Create a notification (admin only)."""
    verify_admin(db, user_id)
    
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=request.user_id,
        title=request.title,
        body=request.body,
        read_flag=False,
        created_by=user_id,
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        title=notification.title,
        body=notification.body,
        read_flag=notification.read_flag,
        created_at=notification.created_at.isoformat() if notification.created_at else "",
        created_by=notification.created_by,
    )


@router.get("/unread/count")
async def get_unread_count(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get count of unread notifications for the current user."""
    count = db.query(Notification).filter(
        ((Notification.user_id == user_id) | (Notification.user_id.is_(None))) &
        (Notification.read_flag == False)
    ).count()
    
    return {"count": count}
