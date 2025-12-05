from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel

Mode = Literal["PAPER", "REAL"]
Side = Literal["BUY", "SELL"]


class BrainSignal(BaseModel):
    id: str
    user_id: str
    symbol: str
    side: Side
    mode: Mode
    entry_price: float
    take_profit: float
    stop_loss: float
    confidence: float  # 0.0 - 1.0
    expected_profit: float
    expected_loss: float
    timeframe: str  # e.g. "1h", "4h", "1d"
    explanation: str
    created_at: datetime


def get_signals_for_user(user_id: str, mode: Mode = "PAPER") -> List[BrainSignal]:
    """
    v0 implementation: return mock signals in the exact shape
    the real MCN-powered Brain will use.

    Later, this function will:
    - query recent market data
    - query user profile and risk prefs
    - query MCN memory clusters
    - generate signals using MemoryClusterNetworks

    For now, we just return a fixed list for testing.
    """
    now = datetime.utcnow()

    signals: List[BrainSignal] = [
        BrainSignal(
            id="sig-1",
            user_id=user_id,
            symbol="AAPL",
            side="BUY",
            mode=mode,
            entry_price=190.0,
            take_profit=200.0,
            stop_loss=185.0,
            confidence=0.82,
            expected_profit=10.0,
            expected_loss=5.0,
            timeframe="1d",
            explanation="Mock GSIN Brain: AAPL in strong uptrend with bullish sentiment.",
            created_at=now,
        ),
        BrainSignal(
            id="sig-2",
            user_id=user_id,
            symbol="TSLA",
            side="SELL",
            mode=mode,
            entry_price=250.0,
            take_profit=230.0,
            stop_loss=260.0,
            confidence=0.76,
            expected_profit=20.0,
            expected_loss=10.0,
            timeframe="4h",
            explanation="Mock GSIN Brain: TSLA overextended after news spike.",
            created_at=now,
        ),
        BrainSignal(
            id="sig-3",
            user_id=user_id,
            symbol="BTC-USD",
            side="BUY",
            mode=mode,
            entry_price=65000.0,
            take_profit=68000.0,
            stop_loss=64000.0,
            confidence=0.79,
            expected_profit=3000.0,
            expected_loss=1000.0,
            timeframe="1h",
            explanation="Mock GSIN Brain: BTC momentum with positive funding and sentiment.",
            created_at=now,
        ),
    ]

    return signals
