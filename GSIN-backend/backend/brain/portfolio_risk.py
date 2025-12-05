# backend/brain/portfolio_risk.py
"""
Portfolio-level risk management.
Enforces maximum exposure, sector limits, leverage, and correlation penalties.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..db import crud
from ..db.models import Trade, UserStrategy, TradeStatus
from ..broker.paper_broker import PaperBroker
from ..market_data.market_data_provider import get_provider_with_fallback
from ..market_data.sector_cache import SectorCache


class PortfolioRiskManager:
    """Manages portfolio-level risk constraints."""
    
    def __init__(self):
        # Default risk limits (can be configured per user)
        self.max_exposure_per_symbol = 0.20  # 20% of portfolio per symbol
        self.max_exposure_per_sector = 0.40  # 40% of portfolio per sector
        self.max_leverage = 1.0  # No leverage (1.0 = 100% capital)
        self.correlation_threshold = 0.7  # Block if correlation > 0.7
    
    def evaluate_portfolio_risk(
        self,
        user_id: str,
        proposed_trade: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """
        Evaluate portfolio risk for a proposed trade.
        
        Args:
            user_id: User ID
            proposed_trade: {
                "symbol": str,
                "side": "BUY" | "SELL",
                "position_size": float,
                "entry_price": float,
                "sector": Optional[str]  # Will be fetched if not provided
            }
            db: Database session
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "adjustment": float (0-1),  # Confidence adjustment factor
                "risk_factors": {
                    "symbol_exposure": float,
                    "sector_exposure": float,
                    "correlation_risk": float,
                    "leverage_risk": float
                }
            }
        """
        try:
            symbol = proposed_trade.get("symbol", "").upper()
            side = proposed_trade.get("side", "BUY")
            position_size = proposed_trade.get("position_size", 0.0)
            entry_price = proposed_trade.get("entry_price", 0.0)
            
            # Get user's current portfolio
            portfolio = self._get_user_portfolio(user_id, db)
            
            # Get account balance
            paper_broker = PaperBroker(db)
            balance_info = paper_broker.get_account_balance(user_id)
            total_capital = balance_info.get("paper_balance", 0.0)
            
            if total_capital <= 0:
                return {
                    "allowed": False,
                    "reason": "Insufficient capital",
                    "adjustment": 0.0,
                    "risk_factors": {},
                }
            
            # Calculate proposed position value
            proposed_value = position_size * entry_price
            
            # Risk factor 1: Symbol exposure
            symbol_exposure = self._calculate_symbol_exposure(
                symbol, portfolio, total_capital, proposed_value, side
            )
            
            # Risk factor 2: Sector exposure
            # PHASE 4: Fetch sector from Alpaca API (cached)
            sector = proposed_trade.get("sector") or self._get_symbol_sector(symbol)
            sector_exposure = self._calculate_sector_exposure(
                sector, portfolio, total_capital, proposed_value, side
            )
            
            # Risk factor 3: Correlation risk
            correlation_risk = self._calculate_correlation_risk(
                symbol, portfolio, side
            )
            
            # Risk factor 4: Leverage risk
            leverage_risk = self._calculate_leverage_risk(
                portfolio, total_capital, proposed_value, side
            )
            
            # Determine if trade is allowed
            allowed = True
            reasons = []
            adjustment = 1.0
            
            # Check symbol exposure
            if symbol_exposure > self.max_exposure_per_symbol:
                allowed = False
                reasons.append(
                    f"Symbol exposure ({symbol_exposure:.1%}) exceeds limit ({self.max_exposure_per_symbol:.1%})"
                )
            elif symbol_exposure > self.max_exposure_per_symbol * 0.8:
                # Warning zone (80% of limit)
                adjustment *= 0.8
                reasons.append(
                    f"Symbol exposure ({symbol_exposure:.1%}) approaching limit"
                )
            
            # Check sector exposure
            if sector_exposure > self.max_exposure_per_sector:
                allowed = False
                reasons.append(
                    f"Sector exposure ({sector_exposure:.1%}) exceeds limit ({self.max_exposure_per_sector:.1%})"
                )
            elif sector_exposure > self.max_exposure_per_sector * 0.8:
                adjustment *= 0.8
                reasons.append(
                    f"Sector exposure ({sector_exposure:.1%}) approaching limit"
                )
            
            # Check correlation
            if correlation_risk > self.correlation_threshold:
                allowed = False
                reasons.append(
                    f"High correlation risk ({correlation_risk:.2f}) exceeds threshold ({self.correlation_threshold:.2f})"
                )
            elif correlation_risk > self.correlation_threshold * 0.8:
                adjustment *= 0.7
                reasons.append(
                    f"Moderate correlation risk ({correlation_risk:.2f})"
                )
            
            # Check leverage
            if leverage_risk > self.max_leverage:
                allowed = False
                reasons.append(
                    f"Leverage ({leverage_risk:.2f}) exceeds limit ({self.max_leverage:.2f})"
                )
            
            reason = "; ".join(reasons) if reasons else "No risk constraints violated"
            
            return {
                "allowed": allowed,
                "reason": reason,
                "adjustment": max(0.0, min(1.0, adjustment)),
                "risk_factors": {
                    "symbol_exposure": symbol_exposure,
                    "sector_exposure": sector_exposure,
                    "correlation_risk": correlation_risk,
                    "leverage_risk": leverage_risk,
                },
            }
        except Exception as e:
            print(f"Error evaluating portfolio risk: {e}")
            import traceback
            traceback.print_exc()
            return {
                "allowed": False,
                "reason": f"Error evaluating risk: {str(e)}",
                "adjustment": 0.0,
                "risk_factors": {},
            }
    
    def _get_user_portfolio(self, user_id: str, db: Session) -> List[Dict[str, Any]]:
        """Get user's current open positions."""
        try:
            # Get open trades
            open_trades = db.query(Trade).filter(
                Trade.user_id == user_id,
                Trade.status == TradeStatus.OPEN
            ).all()
            
            portfolio = []
            for trade in open_trades:
                portfolio.append({
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "entry_price": trade.entry_price,
                    "current_value": trade.quantity * (trade.exit_price or trade.entry_price),
                    "sector": self._get_symbol_sector(trade.symbol),
                })
            
            return portfolio
        except Exception as e:
            print(f"Error getting user portfolio: {e}")
            return []
    
    def _calculate_symbol_exposure(
        self,
        symbol: str,
        portfolio: List[Dict[str, Any]],
        total_capital: float,
        proposed_value: float,
        side: str
    ) -> float:
        """Calculate exposure to a specific symbol."""
        if total_capital <= 0:
            return 0.0
        
        # Current exposure
        current_exposure = sum(
            pos["current_value"] for pos in portfolio
            if pos["symbol"] == symbol
        )
        
        # Proposed exposure
        if side == "BUY":
            new_exposure = current_exposure + proposed_value
        else:  # SELL
            # Selling reduces exposure
            new_exposure = max(0.0, current_exposure - proposed_value)
        
        return new_exposure / total_capital if total_capital > 0 else 0.0
    
    def _calculate_sector_exposure(
        self,
        sector: Optional[str],
        portfolio: List[Dict[str, Any]],
        total_capital: float,
        proposed_value: float,
        side: str
    ) -> float:
        """Calculate exposure to a specific sector."""
        if not sector or total_capital <= 0:
            return 0.0
        
        # Current sector exposure
        current_exposure = sum(
            pos["current_value"] for pos in portfolio
            if pos.get("sector") == sector
        )
        
        # Proposed exposure
        if side == "BUY":
            new_exposure = current_exposure + proposed_value
        else:
            new_exposure = max(0.0, current_exposure - proposed_value)
        
        return new_exposure / total_capital if total_capital > 0 else 0.0
    
    def _calculate_correlation_risk(
        self,
        symbol: str,
        portfolio: List[Dict[str, Any]],
        side: str
    ) -> float:
        """
        Calculate correlation risk.
        
        Simplified: Count positions in same sector/industry.
        Higher count = higher correlation risk.
        """
        if not portfolio:
            return 0.0
        
        # Get sector of proposed symbol
        proposed_sector = self._get_symbol_sector(symbol)
        
        # Count positions in same sector
        same_sector_count = sum(
            1 for pos in portfolio
            if pos.get("sector") == proposed_sector and pos["side"] == side
        )
        
        # Normalize to [0, 1] (assume max 5 correlated positions = risk 1.0)
        return min(1.0, same_sector_count / 5.0)
    
    def _calculate_leverage_risk(
        self,
        portfolio: List[Dict[str, Any]],
        total_capital: float,
        proposed_value: float,
        side: str
    ) -> float:
        """Calculate leverage risk."""
        if total_capital <= 0:
            return 0.0
        
        # Current total exposure
        current_exposure = sum(pos["current_value"] for pos in portfolio)
        
        # Proposed total exposure
        if side == "BUY":
            new_exposure = current_exposure + proposed_value
        else:
            new_exposure = max(0.0, current_exposure - proposed_value)
        
        # Leverage = total_exposure / capital
        leverage = new_exposure / total_capital if total_capital > 0 else 0.0
        
        return leverage
    
    def _get_symbol_sector(self, symbol: str) -> Optional[str]:
        """
        Get sector for a symbol.
        
        PHASE 4: Uses Alpaca API with caching.
        
        Returns:
            Sector name if available, None otherwise
        """
        # Check cache first
        cached_sector = SectorCache.get(symbol)
        if cached_sector is not None:
            return cached_sector
        
        # Fetch from provider
        try:
            provider = get_provider_with_fallback()
            if provider and hasattr(provider, 'get_asset_details'):
                details = provider.get_asset_details(symbol)
                sector = details.get("sector") if details else None
                
                # Cache the result (even if None, to avoid repeated API calls)
                SectorCache.set(symbol, sector)
                
                return sector
        except Exception as e:
            # Log error but don't fail
            print(f"Warning: Could not fetch sector for {symbol}: {e}")
            # Cache None to avoid repeated failures
            SectorCache.set(symbol, None)
        
        return None

