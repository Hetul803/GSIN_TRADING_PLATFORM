# backend/strategy_engine/strategy_models.py
"""
Pydantic models for Strategy Engine API requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from ..db.models import AssetType
from .strategy_schema import StrategyBuilderRequest


class StrategyCreateRequest(BaseModel):
    """Request model for creating a new strategy (legacy format - accepts both builder and raw)."""
    name: str = Field(..., min_length=1, max_length=255, description="Strategy name")
    description: Optional[str] = Field(None, description="Strategy description")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Strategy parameters (e.g., {'rsi_period': 14})")
    ruleset: Optional[Dict[str, Any]] = Field(None, description="Trading ruleset with conditions, indicators, timeframe")
    asset_type: AssetType = Field(AssetType.STOCK, description="Asset type (STOCK, CRYPTO, FOREX, OTHER)")
    
    # PHASE 3: Support for builder format
    builder_request: Optional[StrategyBuilderRequest] = Field(None, description="Structured builder request (preferred)")


class StrategyUpdateRequest(BaseModel):
    """Request model for updating a strategy."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    ruleset: Optional[Dict[str, Any]] = None
    asset_type: Optional[AssetType] = None
    is_active: Optional[bool] = None


class StrategyResponse(BaseModel):
    """Response model for strategy data."""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    parameters: Dict[str, Any]
    ruleset: Dict[str, Any]
    asset_type: str
    score: Optional[float]
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="PHASE 2: Strategy confidence score (0-1)")
    brain_reason: Optional[str] = Field(None, description="PHASE 2: Brain-generated explanation for recommendation")
    explanation_human: Optional[str] = Field(None, description="PHASE 1: Human-readable explanation of strategy")
    risk_note: Optional[str] = Field(None, description="PHASE 1: Risk warning/note for users")
    last_backtest_at: Optional[datetime]
    last_backtest_results: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    """Request model for running a backtest."""
    symbol: str = Field(..., description="Symbol to test (e.g., 'AAPL')")
    timeframe: str = Field("1d", description="Timeframe (e.g., '1d', '1h', '15m')")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")


class BacktestResponse(BaseModel):
    """Response model for backtest results."""
    id: str
    strategy_id: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    total_return: float
    win_rate: float
    max_drawdown: float
    avg_pnl: float
    total_trades: int
    sharpe_ratio: Optional[float]
    results: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class MutationResponse(BaseModel):
    """Response model for strategy mutation."""
    parent_strategy_id: str
    mutated_strategies: List[StrategyResponse]
    lineage_ids: List[str]


class SignalResponse(BaseModel):
    """Response model for trading signal."""
    strategy_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    entry: float
    exit: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    reasoning: Optional[str] = None
    timestamp: datetime

