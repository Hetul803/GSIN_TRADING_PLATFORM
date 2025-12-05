# backend/api/dev.py
"""
FINAL ALIGNMENT: Development endpoints for seeding strategies.
DEV MODE ONLY - protected by ENV check.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pathlib import Path

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..seed_strategies.load_into_mcn import load_seed_strategies_into_mcn

router = APIRouter(prefix="/dev", tags=["dev"])


def check_dev_mode():
    """Verify that we're not in production."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in development mode"
        )


@router.post("/seed-strategies")
async def seed_strategies(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    FINAL ALIGNMENT: Seed proven strategies from JSON into database and MCN.
    
    DEV MODE ONLY - checks ENV != production.
    Seeds if not already seeded.
    """
    check_dev_mode()
    
    try:
        seed_file = Path(__file__).resolve().parents[2] / "seed_strategies" / "proven_strategies.json"
        count = load_seed_strategies_into_mcn(db, seed_file)
        
        return {
            "success": True,
            "message": f"Seeded {count} strategies into database and MCN",
            "count": count
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed strategies: {str(e)}"
        )

