# backend/brain/user_risk_profile.py
"""
MCN-based User Risk Profile.
PHASE 4: Tracks user trading behavior and infers risk profile (conservative/moderate/aggressive).
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import numpy as np

from ..db import crud
from ..db.models import Trade, TradeStatus
from .mcn_adapter import get_mcn_adapter


class UserRiskProfile:
    """
    Infers user risk profile from trading behavior using MCN.
    
    Risk profiles:
    - conservative: Low position sizes, high win rate, long holding periods
    - moderate: Balanced approach
    - aggressive: Large position sizes, higher volatility tolerance, shorter holding periods
    """
    
    def __init__(self):
        self.mcn_adapter = get_mcn_adapter()
    
    def get_user_risk_profile(
        self,
        user_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Get user risk profile based on trading history.
        
        Returns:
            {
                "risk_tendency": "conservative" | "moderate" | "aggressive",
                "confidence": float (0-1),
                "factors": {
                    "avg_position_size_pct": float,
                    "win_rate": float,
                    "avg_holding_period_days": float,
                    "volatility_tolerance": float,
                    "max_drawdown_tolerance": float
                },
                "trade_count": int,
                "last_updated": str (ISO datetime)
            }
        """
        # Get user's closed trades
        closed_trades = crud.list_user_trades(
            db, user_id, status=TradeStatus.CLOSED, limit=100
        )
        
        if len(closed_trades) < 5:
            # Not enough data - return default moderate profile
            return {
                "risk_tendency": "moderate",
                "confidence": 0.3,
                "factors": {},
                "trade_count": len(closed_trades),
                "last_updated": datetime.now().isoformat(),
                "reason": "Insufficient trade history (need at least 5 closed trades)"
            }
        
        # Calculate risk factors
        factors = self._calculate_risk_factors(closed_trades, db, user_id)
        
        # Infer risk tendency
        risk_tendency, confidence = self._infer_risk_tendency(factors)
        
        # Record to MCN for learning
        self._record_to_mcn(user_id, factors, risk_tendency, db)
        
        return {
            "risk_tendency": risk_tendency,
            "confidence": confidence,
            "factors": factors,
            "trade_count": len(closed_trades),
            "last_updated": datetime.now().isoformat()
        }
    
    def _calculate_risk_factors(
        self,
        trades: List[Trade],
        db: Session,
        user_id: str
    ) -> Dict[str, float]:
        """Calculate risk factors from trade history."""
        if not trades:
            return {}
        
        # Get account balance for position size calculation
        from ..broker.paper_broker import PaperBroker
        broker = PaperBroker(db)
        balance_info = broker.get_account_balance(user_id)
        avg_balance = balance_info.get("paper_balance", 100000.0)  # Default if not available
        
        # Factor 1: Average position size as % of portfolio
        position_sizes = []
        for trade in trades:
            position_value = trade.quantity * trade.entry_price
            if avg_balance > 0:
                position_sizes.append(position_value / avg_balance)
        
        avg_position_size_pct = np.mean(position_sizes) if position_sizes else 0.0
        
        # Factor 2: Win rate
        winning_trades = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
        win_rate = len(winning_trades) / len(trades) if trades else 0.0
        
        # Factor 3: Average holding period
        holding_periods = []
        for trade in trades:
            if trade.closed_at and trade.opened_at:
                delta = trade.closed_at - trade.opened_at
                holding_periods.append(delta.total_seconds() / 86400)  # Convert to days
        
        avg_holding_period_days = np.mean(holding_periods) if holding_periods else 0.0
        
        # Factor 4: Volatility tolerance (std dev of returns)
        returns = []
        for trade in trades:
            if trade.realized_pnl and trade.entry_price > 0:
                pct_return = trade.realized_pnl / (trade.quantity * trade.entry_price)
                returns.append(pct_return)
        
        volatility_tolerance = np.std(returns) if len(returns) > 1 else 0.0
        
        # Factor 5: Max drawdown tolerance (largest single loss)
        losses = [t.realized_pnl for t in trades if t.realized_pnl and t.realized_pnl < 0]
        max_drawdown_tolerance = abs(min(losses)) if losses else 0.0
        if avg_balance > 0:
            max_drawdown_tolerance = max_drawdown_tolerance / avg_balance
        
        return {
            "avg_position_size_pct": avg_position_size_pct,
            "win_rate": win_rate,
            "avg_holding_period_days": avg_holding_period_days,
            "volatility_tolerance": volatility_tolerance,
            "max_drawdown_tolerance": max_drawdown_tolerance
        }
    
    def _infer_risk_tendency(
        self,
        factors: Dict[str, float]
    ) -> tuple[str, float]:
        """
        Infer risk tendency from factors.
        
        Returns:
            (risk_tendency, confidence)
        """
        avg_position_size = factors.get("avg_position_size_pct", 0.0)
        win_rate = factors.get("win_rate", 0.5)
        avg_holding_period = factors.get("avg_holding_period_days", 0.0)
        volatility_tolerance = factors.get("volatility_tolerance", 0.0)
        max_drawdown = factors.get("max_drawdown_tolerance", 0.0)
        
        # Scoring system
        conservative_score = 0.0
        moderate_score = 0.0
        aggressive_score = 0.0
        
        # Position size scoring
        if avg_position_size < 0.05:  # < 5% of portfolio
            conservative_score += 0.3
        elif avg_position_size < 0.15:  # 5-15%
            moderate_score += 0.3
        else:  # > 15%
            aggressive_score += 0.3
        
        # Win rate scoring (higher win rate = more conservative)
        if win_rate > 0.7:
            conservative_score += 0.2
        elif win_rate > 0.5:
            moderate_score += 0.2
        else:
            aggressive_score += 0.2
        
        # Holding period scoring (longer = more conservative)
        if avg_holding_period > 7:  # > 7 days
            conservative_score += 0.2
        elif avg_holding_period > 2:  # 2-7 days
            moderate_score += 0.2
        else:  # < 2 days
            aggressive_score += 0.2
        
        # Volatility tolerance scoring
        if volatility_tolerance < 0.02:  # Low volatility
            conservative_score += 0.15
        elif volatility_tolerance < 0.05:  # Medium
            moderate_score += 0.15
        else:  # High
            aggressive_score += 0.15
        
        # Drawdown tolerance scoring
        if max_drawdown < 0.05:  # < 5% max loss
            conservative_score += 0.15
        elif max_drawdown < 0.15:  # 5-15%
            moderate_score += 0.15
        else:  # > 15%
            aggressive_score += 0.15
        
        # Determine winner
        scores = {
            "conservative": conservative_score,
            "moderate": moderate_score,
            "aggressive": aggressive_score
        }
        
        max_score = max(scores.values())
        risk_tendency = max(scores.items(), key=lambda x: x[1])[0]
        
        # Confidence based on score difference
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) > 1:
            confidence = (sorted_scores[0] - sorted_scores[1]) / max(sorted_scores[0], 0.01)
        else:
            confidence = 0.5
        
        confidence = max(0.3, min(1.0, confidence))
        
        return risk_tendency, confidence
    
    def _record_to_mcn(
        self,
        user_id: str,
        factors: Dict[str, float],
        risk_tendency: str,
        db: Session
    ):
        """Record user risk profile to MCN for learning."""
        if not self.mcn_adapter.is_available:
            return
        
        try:
            self.mcn_adapter.record_event(
                event_type="user_risk_profile_updated",
                payload={
                    "user_id": user_id,
                    "risk_tendency": risk_tendency,
                    "factors": factors,
                    "timestamp": datetime.now().isoformat(),
                },
                user_id=user_id,
            )
        except Exception as e:
            print(f"Warning: Failed to record risk profile to MCN: {e}")

