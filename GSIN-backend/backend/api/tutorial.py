# backend/api/tutorial.py
"""
PHASE 5: Onboarding tutorial API.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud

router = APIRouter(prefix="/tutorial", tags=["tutorial"])


class TutorialStatusResponse(BaseModel):
    has_seen_tutorial: bool


class MarkTutorialCompleteRequest(BaseModel):
    completed: bool = True


@router.get("/status", response_model=TutorialStatusResponse)
async def get_tutorial_status(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get tutorial completion status for the current user.
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return TutorialStatusResponse(
        has_seen_tutorial=user.has_seen_tutorial if hasattr(user, 'has_seen_tutorial') else False
    )


@router.post("/complete")
async def mark_tutorial_complete(
    request: MarkTutorialCompleteRequest = MarkTutorialCompleteRequest(),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Mark tutorial as completed for the current user.
    """
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.has_seen_tutorial = request.completed
    db.commit()
    db.refresh(user)
    
    return {"success": True, "has_seen_tutorial": user.has_seen_tutorial}

