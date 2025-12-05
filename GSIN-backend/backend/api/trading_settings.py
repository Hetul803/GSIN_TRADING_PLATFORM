# backend/api/trading_settings.py
"""
API endpoints for user trading settings.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..utils.jwt_deps import get_current_user_id_dep
from ..db.session import get_db
from ..db import crud
from ..db.models import UserTradingSettings

router = APIRouter(prefix="/user/settings", tags=["trading-settings"])


# PHASE 4: JWT-only authentication - use dependency directly


class TradingSettingsRequest(BaseModel):
    min_balance: Optional[float] = None
    max_auto_trade_amount: Optional[float] = None
    max_risk_percent: Optional[float] = None
    capital_range_min: Optional[float] = None
    capital_range_max: Optional[float] = None
    auto_execution_enabled: Optional[bool] = None
    stop_under_balance: Optional[float] = None
    daily_profit_target: Optional[float] = None


class TradingSettingsResponse(BaseModel):
    id: str
    user_id: str
    min_balance: float
    max_auto_trade_amount: float
    max_risk_percent: float
    capital_range_min: Optional[float]
    capital_range_max: Optional[float]
    auto_execution_enabled: bool
    stop_under_balance: Optional[float]
    
    class Config:
        from_attributes = True


@router.get("/trading", response_model=TradingSettingsResponse)
def get_trading_settings(
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Get user's trading settings."""
    settings = crud.get_user_trading_settings(db, user_id)
    if not settings:
        # Create default settings
        settings = crud.create_user_trading_settings(db, user_id)
    
    return TradingSettingsResponse.from_orm(settings)


@router.post("/trading", response_model=TradingSettingsResponse)
async def update_trading_settings(
    settings_data: TradingSettingsRequest,
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """Update user's trading settings."""
    settings = crud.update_user_trading_settings(
        db=db,
        user_id=user_id,
        min_balance=settings_data.min_balance,
        max_auto_trade_amount=settings_data.max_auto_trade_amount,
        max_risk_percent=settings_data.max_risk_percent,
        capital_range_min=settings_data.capital_range_min,
        capital_range_max=settings_data.capital_range_max,
        auto_execution_enabled=settings_data.auto_execution_enabled,
        stop_under_balance=settings_data.stop_under_balance,
        daily_profit_target=settings_data.daily_profit_target,
    )
    
    if not settings:
        # Create if doesn't exist
        settings = crud.create_user_trading_settings(
            db=db,
            user_id=user_id,
            min_balance=settings_data.min_balance or 0.0,
            max_auto_trade_amount=settings_data.max_auto_trade_amount or 1000.0,
            max_risk_percent=settings_data.max_risk_percent or 2.0,
            capital_range_min=settings_data.capital_range_min,
            capital_range_max=settings_data.capital_range_max,
            auto_execution_enabled=settings_data.auto_execution_enabled or False,
            stop_under_balance=settings_data.stop_under_balance,
        )
    
    return TradingSettingsResponse.from_orm(settings)

