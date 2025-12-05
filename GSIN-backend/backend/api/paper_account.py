# backend/api/paper_account.py
"""
API endpoints for paper account management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud

router = APIRouter(prefix="/user/paper", tags=["paper-account"])


# PHASE 4: JWT-only authentication - use dependency directly


class PaperAccountResponse(BaseModel):
    id: str
    user_id: str
    balance: float
    starting_balance: float
    last_reset_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/account", response_model=PaperAccountResponse)
async def get_paper_account(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get user's paper account."""
    account = crud.get_user_paper_account(db, user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Paper account not found")
    
    return PaperAccountResponse.from_orm(account)


@router.post("/reset", response_model=PaperAccountResponse)
async def reset_paper_account(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Reset user's paper account to starting balance."""
    account = crud.reset_user_paper_account(db, user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Paper account not found")
    
    return PaperAccountResponse.from_orm(account)

