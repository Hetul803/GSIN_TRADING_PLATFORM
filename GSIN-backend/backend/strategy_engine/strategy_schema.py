# backend/strategy_engine/strategy_schema.py
"""
Canonical Strategy Input Schema - Defines the structured format for user-submitted strategies.

This schema enforces a no-code, builder-based approach to strategy creation,
preventing raw code/script uploads that could break the engine.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal, Union
from enum import Enum

from ..db.models import AssetType


class Timeframe(str, Enum):
    """Supported timeframes."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"


class Direction(str, Enum):
    """Trading direction."""
    LONG = "long"
    SHORT = "short"
    BOTH = "both"


class IntendedRegime(str, Enum):
    """Intended market regime for strategy."""
    BULL = "bull"
    BEAR = "bear"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    ANY = "any"


class IndicatorType(str, Enum):
    """Supported indicator types."""
    RSI = "rsi"
    SMA = "sma"
    EMA = "ema"
    MACD = "macd"
    BOLLINGER = "bollinger"
    STOCHASTIC = "stochastic"
    ADX = "adx"
    ATR = "atr"
    VOLUME = "volume"
    PRICE = "price"


class Operator(str, Enum):
    """Comparison operators."""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    EQUALS = "=="
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    BETWEEN = "between"


class EntryRule(BaseModel):
    """A single entry condition rule."""
    indicator: IndicatorType = Field(..., description="Indicator type")
    operator: Operator = Field(..., description="Comparison operator")
    value: Union[float, str, List[float]] = Field(..., description="Threshold value(s)")
    lookback: Optional[int] = Field(None, description="Lookback period for indicator")
    period: Optional[int] = Field(None, description="Period for indicator (alias for lookback)")
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v, info):
        """Validate value based on operator."""
        operator = info.data.get('operator')
        if operator == Operator.BETWEEN:
            if not isinstance(v, list) or len(v) != 2:
                raise ValueError("BETWEEN operator requires a list of exactly 2 values")
        return v


class ExitRule(BaseModel):
    """Exit rule configuration."""
    stop_loss_percent: float = Field(..., ge=0.01, le=50.0, description="Stop loss percentage (required)")
    take_profit_percent: float = Field(..., ge=0.01, le=100.0, description="Take profit percentage (required)")
    trailing_stop_percent: Optional[float] = Field(None, ge=0.01, le=50.0, description="Trailing stop percentage (optional)")


class PositionSizing(BaseModel):
    """Position sizing configuration."""
    max_risk_per_trade_percent: float = Field(..., ge=0.1, le=10.0, description="Maximum risk per trade as % of equity")
    position_size_percent: Optional[float] = Field(None, ge=0.1, le=100.0, description="Fixed position size as % of equity (optional)")


class StrategyBuilderRequest(BaseModel):
    """Canonical request model for strategy creation via Builder UI."""
    
    # Required fields
    name: str = Field(..., min_length=1, max_length=255, description="Strategy name")
    asset_type: AssetType = Field(..., description="Asset type")
    symbols: List[str] = Field(..., min_length=1, description="List of symbols to trade (at least one)")
    timeframe: Timeframe = Field(..., description="Trading timeframe")
    direction: Direction = Field(..., description="Trading direction")
    entry_rules: List[EntryRule] = Field(..., min_length=1, description="Entry conditions (at least one)")
    exit_rules: ExitRule = Field(..., description="Exit rules")
    position_sizing: PositionSizing = Field(..., description="Position sizing configuration")
    
    # Optional fields (for MCN and explanations)
    description: Optional[str] = Field(None, max_length=2000, description="Strategy description/hypothesis")
    tags: Optional[List[str]] = Field(None, description="Strategy tags (e.g., 'trend-following', 'breakout')")
    intended_regime: Optional[IntendedRegime] = Field(IntendedRegime.ANY, description="Intended market regime")
    max_concurrent_positions: Optional[int] = Field(None, ge=1, le=10, description="Maximum concurrent positions")
    cooldown_bars: Optional[int] = Field(None, ge=0, description="Cooldown bars between trades")
    
    def to_ruleset(self) -> dict:
        """Convert builder request to internal ruleset format."""
        return {
            "ticker": self.symbols[0] if len(self.symbols) == 1 else self.symbols,
            "symbols": self.symbols,
            "timeframe": self.timeframe.value,
            "direction": self.direction.value,
            "entry_conditions": [
                {
                    "indicator": rule.indicator.value,
                    "operator": rule.operator.value,
                    "value": rule.value,
                    "lookback": rule.lookback or rule.period,
                }
                for rule in self.entry_rules
            ],
            "exit_rules": {
                "stop_loss_percent": self.exit_rules.stop_loss_percent,
                "take_profit_percent": self.exit_rules.take_profit_percent,
                "trailing_stop_percent": self.exit_rules.trailing_stop_percent,
            },
            "position_sizing": {
                "max_risk_per_trade_percent": self.position_sizing.max_risk_per_trade_percent,
                "position_size_percent": self.position_sizing.position_size_percent,
            },
            "max_concurrent_positions": self.max_concurrent_positions,
            "cooldown_bars": self.cooldown_bars,
            "intended_regime": self.intended_regime.value if self.intended_regime else "any",
            "tags": self.tags or [],
        }
    
    def to_parameters(self) -> dict:
        """Extract parameters from entry rules for storage."""
        params = {}
        for rule in self.entry_rules:
            if rule.lookback or rule.period:
                params[f"{rule.indicator.value}_period"] = rule.lookback or rule.period
        return params

