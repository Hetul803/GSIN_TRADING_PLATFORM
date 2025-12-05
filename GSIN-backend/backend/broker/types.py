# backend/broker/types.py
"""
Type definitions for broker layer.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TradeMode(str, Enum):
    PAPER = "PAPER"
    REAL = "REAL"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeSource(str, Enum):
    MANUAL = "MANUAL"
    BRAIN = "BRAIN"
    GROUP_PROPOSAL = "GROUP_PROPOSAL"


class PlaceOrderRequest(BaseModel):
    """Request to place a market order."""
    symbol: str = Field(..., description="Symbol to trade (e.g., AAPL)")
    side: TradeSide = Field(..., description="BUY or SELL")
    quantity: float = Field(..., gt=0, description="Quantity to trade")
    mode: TradeMode = Field(..., description="PAPER or REAL")
    source: TradeSource = Field(TradeSource.MANUAL, description="Trade source")
    group_id: Optional[str] = Field(None, description="Group ID if from group proposal")
    strategy_id: Optional[str] = Field(None, description="Strategy ID if from Brain")
    stop_loss: Optional[float] = Field(None, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")


class OrderResponse(BaseModel):
    """Response from placing an order."""
    order_id: str
    trade_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    mode: str
    status: str
    timestamp: datetime


class PositionResponse(BaseModel):
    """Position information."""
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    mode: str


class AccountBalanceResponse(BaseModel):
    """Account balance information."""
    user_id: str
    paper_balance: float
    real_balance: Optional[float] = None
    paper_equity: float
    real_equity: Optional[float] = None
    buying_power_paper: float
    buying_power_real: Optional[float] = None

