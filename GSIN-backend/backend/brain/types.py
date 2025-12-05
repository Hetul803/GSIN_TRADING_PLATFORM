# backend/brain/types.py
"""
Type definitions for Brain Layer (L3).
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """Types of events that can be recorded in MCN."""
    TRADE_EXECUTED = "trade_executed"
    STRATEGY_BACKTEST = "strategy_backtest"
    STRATEGY_MUTATED = "strategy_mutated"
    SIGNAL_GENERATED = "signal_generated"
    MARKET_SNAPSHOT = "market_snapshot"
    USER_ACTION = "user_action"


class MarketRegime(str, Enum):
    """Market regime classifications."""
    BULL = "bull"
    BEAR = "bear"
    VOLATILE = "volatile"
    TRENDING = "trending"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class BrainSignalResponse(BaseModel):
    """Enhanced signal response from Brain (L3)."""
    strategy_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    entry: float
    exit: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    position_size: Optional[float] = None  # Recommended position size
    volatility: Optional[float] = None  # Market volatility
    sentiment: Optional[str] = None  # "bullish", "bearish", "neutral"
    reasoning: Optional[str] = None
    explanation: Optional[str] = None  # MCN-generated explanation
    market_regime: Optional[str] = None
    volatility_context: Optional[float] = None
    sentiment_context: Optional[float] = None
    mode_recommendation: Optional[str] = None  # "PAPER" or "REAL"
    risk_level: Optional[str] = None  # "low", "moderate", "high", "very_high"
    mcn_adjustments: Optional[Dict[str, Any]] = None  # MCN-specific adjustments
    target_alignment: Optional[Dict[str, Any]] = None  # Daily profit target alignment with risk explanation
    timestamp: datetime


class BrainBacktestResponse(BaseModel):
    """Enhanced backtest response with MCN memory."""
    strategy_id: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    # Standard backtest metrics
    total_return: float
    win_rate: float
    max_drawdown: float
    avg_pnl: float
    total_trades: int
    sharpe_ratio: Optional[float]
    # MCN-enhanced metrics
    regime_fit_score: Optional[float] = None  # How well strategy fits current regime
    memory_adjusted_score: Optional[float] = None  # Score adjusted by MCN memory
    historical_pattern_match: Optional[float] = None  # Match to historical patterns
    results: Dict[str, Any]
    created_at: datetime


class BrainMutationResponse(BaseModel):
    """Enhanced mutation response with MCN guidance."""
    parent_strategy_id: str
    mutated_strategies: List[Dict[str, Any]]
    lineage_ids: List[str]
    mcn_recommendations: Optional[List[Dict[str, Any]]] = None  # MCN-suggested improvements


class BrainContextResponse(BaseModel):
    """Brain context summary for a user."""
    user_id: str
    market_regime: str
    user_risk_profile: Optional[Dict[str, Any]] = None
    relevant_strategy_clusters: Optional[List[Dict[str, Any]]] = None
    sentiment_cluster_summary: Optional[Dict[str, Any]] = None
    recommended_actions: Optional[List[str]] = None
    timestamp: datetime


class EventPayload(BaseModel):
    """Payload for recording events in MCN."""
    event_type: EventType
    user_id: Optional[str] = None
    strategy_id: Optional[str] = None
    trade_id: Optional[str] = None
    symbol: Optional[str] = None
    data: Dict[str, Any]  # Event-specific data
    timestamp: datetime = Field(default_factory=datetime.now)

