# backend/api/feedback.py
"""
Feedback API - User feedback and suggestions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import uuid

from ..utils.jwt_deps import get_current_user_id_dep, get_current_user_id_optional
from ..db.session import get_db
from ..db import crud

router = APIRouter(prefix="/feedback", tags=["feedback"])
# PHASE 4: JWT-only authentication (optional for anonymous feedback)


class FeedbackCreateRequest(BaseModel):
    page_or_context: str
    category: str  # "bug", "feature", "idea", "other"
    message: str


class FeedbackResponse(BaseModel):
    id: str
    user_id: Optional[str]
    page_or_context: str
    category: str
    message: str
    created_at: datetime


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    feedback_data: FeedbackCreateRequest,
    user_id: Optional[str] = Depends(get_current_user_id_optional),
    db: Session = Depends(get_db)
):
    """
    Create a feedback entry.
    
    User can be logged in (user_id attached) or anonymous (user_id is None).
    """
    # Validate category
    valid_categories = ["bug", "feature", "idea", "other"]
    if feedback_data.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )
    
    # Create feedback
    feedback = crud.create_feedback(
        db=db,
        user_id=user_id,
        page_or_context=feedback_data.page_or_context,
        category=feedback_data.category,
        message=feedback_data.message,
    )
    
    return FeedbackResponse(
        id=feedback.id,
        user_id=feedback.user_id,
        page_or_context=feedback.page_or_context,
        category=feedback.category,
        message=feedback.message,
        created_at=feedback.created_at,
    )

