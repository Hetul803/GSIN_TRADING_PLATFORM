# backend/api/trades.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Body, Query, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..db import crud
from ..db.models import Trade, TradeSide, TradeMode, TradeStatus, TradeSource, AssetType
from ..utils.jwt_deps import get_current_user_id_dep

router = APIRouter(prefix="/trades", tags=["trades"])

# Request/Response models
class CreateTradeRequest(BaseModel):
    symbol: str
    asset_type: Optional[str] = "STOCK"  # STOCK, CRYPTO, FOREX, OTHER
    side: str  # BUY or SELL
    quantity: float
    entry_price: float
    mode: Optional[str] = "PAPER"  # For now always PAPER
    source: Optional[str] = "MANUAL"  # MANUAL or BRAIN
    strategy_id: Optional[str] = None  # For later royalties feature
    group_id: Optional[str] = None  # For later group-based trading

class CloseTradeRequest(BaseModel):
    exit_price: float

class TradeResponse(BaseModel):
    id: str
    user_id: str
    symbol: str
    asset_type: str
    side: str
    quantity: float
    entry_price: float
    exit_price: Optional[float]
    status: str
    mode: str
    source: str
    opened_at: str
    closed_at: Optional[str]
    realized_pnl: Optional[float]
    strategy_id: Optional[str]
    group_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

class TradeSummaryResponse(BaseModel):
    total_trades: int
    open_trades: int
    closed_trades: int
    win_rate: float  # As decimal (0.67 = 67%)
    total_realized_pnl: float
    avg_realized_pnl: float

# POST /api/trades
@router.post("", response_model=TradeResponse)
async def create_trade(
    trade_data: CreateTradeRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Open a new PAPER trade.
    For now, all trades are PAPER mode. Later, REAL mode will integrate with broker APIs.
    TODO: Later, attach market data snapshot, sentiment, volatility at entry.
    """
    
    # Validate required fields
    if not trade_data.symbol or not trade_data.symbol.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Symbol is required"
        )
    
    if trade_data.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be positive"
        )
    
    if trade_data.entry_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entry price must be positive"
        )
    
    # Validate enums
    try:
        side = TradeSide(trade_data.side.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid side: {trade_data.side}. Must be BUY or SELL"
        )
    
    try:
        asset_type = AssetType(trade_data.asset_type.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid asset_type: {trade_data.asset_type}. Must be STOCK, CRYPTO, FOREX, or OTHER"
        )
    
    mode = TradeMode.PAPER  # For now, always PAPER
    if trade_data.mode and trade_data.mode.upper() != "PAPER":
        # TODO: Later, implement REAL mode with broker integration
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="REAL mode is not yet supported. Only PAPER trades are allowed."
        )
    
    try:
        source = TradeSource(trade_data.source.upper()) if trade_data.source else TradeSource.MANUAL
    except ValueError:
        source = TradeSource.MANUAL  # Default to MANUAL if invalid
    
    # Create trade
    try:
        trade = crud.create_trade(
            db,
            user_id=user_id,
            symbol=trade_data.symbol.strip(),
            side=side,
            quantity=trade_data.quantity,
            entry_price=trade_data.entry_price,
            asset_type=asset_type,
            mode=mode,
            source=source,
            strategy_id=trade_data.strategy_id,
            group_id=trade_data.group_id,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create trade: {str(e)}"
        )
    
    return TradeResponse(
        id=trade.id,
        user_id=trade.user_id,
        symbol=trade.symbol,
        asset_type=trade.asset_type.value,
        side=trade.side.value,
        quantity=trade.quantity,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        status=trade.status.value,
        mode=trade.mode.value,
        source=trade.source.value,
        opened_at=trade.opened_at.isoformat(),
        closed_at=trade.closed_at.isoformat() if trade.closed_at else None,
        realized_pnl=trade.realized_pnl,
        strategy_id=trade.strategy_id,
        group_id=trade.group_id,
        created_at=trade.created_at.isoformat(),
    )

# PATCH /api/trades/{trade_id}/close
@router.patch("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: str,
    close_data: CloseTradeRequest = Body(...),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Close an open trade and compute realized P&L.
    """
    
    if close_data.exit_price <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exit price must be positive"
        )
    
    trade = crud.close_trade(db, trade_id, user_id, close_data.exit_price)
    
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found or already closed"
        )
    
    return TradeResponse(
        id=trade.id,
        user_id=trade.user_id,
        symbol=trade.symbol,
        asset_type=trade.asset_type.value,
        side=trade.side.value,
        quantity=trade.quantity,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        status=trade.status.value,
        mode=trade.mode.value,
        source=trade.source.value,
        opened_at=trade.opened_at.isoformat(),
        closed_at=trade.closed_at.isoformat() if trade.closed_at else None,
        realized_pnl=trade.realized_pnl,
        strategy_id=trade.strategy_id,
        group_id=trade.group_id,
        created_at=trade.created_at.isoformat(),
    )

# GET /api/trades
@router.get("", response_model=List[TradeResponse])
async def list_trades(
    status: Optional[str] = Query(None, description="Filter by status: OPEN, CLOSED, or ALL"),
    mode: Optional[str] = Query("PAPER", description="Filter by mode: PAPER or REAL"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    List the user's trades with optional filters.
    Returns most recent first.
    """
    
    # Parse status filter
    status_filter = None
    if status and status.upper() != "ALL":
        try:
            status_filter = TradeStatus(status.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}. Must be OPEN, CLOSED, or ALL"
            )
    
    # Parse mode filter
    mode_filter = None
    if mode:
        try:
            mode_filter = TradeMode(mode.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode: {mode}. Must be PAPER or REAL"
            )
    
    trades = crud.list_user_trades(db, user_id, status=status_filter, mode=mode_filter)
    
    return [
        TradeResponse(
            id=trade.id,
            user_id=trade.user_id,
            symbol=trade.symbol,
            asset_type=trade.asset_type.value,
            side=trade.side.value,
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            status=trade.status.value,
            mode=trade.mode.value,
            source=trade.source.value,
            opened_at=trade.opened_at.isoformat(),
            closed_at=trade.closed_at.isoformat() if trade.closed_at else None,
            realized_pnl=trade.realized_pnl,
            strategy_id=trade.strategy_id,
            group_id=trade.group_id,
            created_at=trade.created_at.isoformat(),
        )
        for trade in trades
    ]

# GET /api/trades/summary
@router.get("/summary", response_model=TradeSummaryResponse)
async def get_trade_summary(
    mode: Optional[str] = Query("PAPER", description="Filter by mode: PAPER or REAL"),
    user_id: str = Depends(get_current_user_id_dep),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics for the user's PAPER trades.
    TODO: Later, add time-based filtering (e.g., last 30 days, all-time).
    TODO: Later, add group-based filtering.
    """
    
    # Parse mode filter
    mode_filter = None
    if mode:
        try:
            mode_filter = TradeMode(mode.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode: {mode}. Must be PAPER or REAL"
            )
    
    summary = crud.get_trade_summary(db, user_id, mode=mode_filter)
    
    return TradeSummaryResponse(**summary)

