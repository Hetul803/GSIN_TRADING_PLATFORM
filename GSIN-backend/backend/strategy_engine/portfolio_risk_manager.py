# backend/strategy_engine/portfolio_risk_manager.py
"""
Portfolio Risk Manager - Hedge Fund Grade

Manages risk at the portfolio level, not just individual strategies.
Implements:
- Position sizing based on portfolio risk
- Correlation analysis
- Portfolio-level drawdown limits
- Risk budgeting
- Diversification metrics
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np
from datetime import datetime


@dataclass
class PortfolioPosition:
    """Represents a position in the portfolio."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    notional: float
    strategy_id: Optional[str] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""
    total_notional: float
    total_exposure: float
    portfolio_var_95: float  # Portfolio Value at Risk (95%)
    portfolio_var_99: float  # Portfolio Value at Risk (99%)
    max_portfolio_drawdown: float
    correlation_risk: float  # 0-1, higher = more correlated (riskier)
    diversification_score: float  # 0-1, higher = more diversified
    concentration_risk: float  # 0-1, higher = more concentrated (riskier)
    leverage_ratio: float
    risk_budget_utilization: Dict[str, float]  # Per-strategy risk budget usage


class PortfolioRiskManager:
    """
    Manages portfolio-level risk for institutional-grade trading.
    """
    
    def __init__(
        self,
        max_portfolio_risk: float = 0.20,  # 20% max portfolio drawdown
        max_position_size: float = 0.10,  # 10% max per position
        max_correlation: float = 0.70,  # Max correlation between positions
        risk_free_rate: float = 0.02  # 2% risk-free rate
    ):
        """
        Initialize portfolio risk manager.
        
        Args:
            max_portfolio_risk: Maximum acceptable portfolio drawdown (0-1)
            max_position_size: Maximum position size as % of portfolio (0-1)
            max_correlation: Maximum correlation between positions (0-1)
            risk_free_rate: Risk-free rate for Sharpe calculation
        """
        self.max_portfolio_risk = max_portfolio_risk
        self.max_position_size = max_position_size
        self.max_correlation = max_correlation
        self.risk_free_rate = risk_free_rate
    
    def calculate_position_size(
        self,
        account_balance: float,
        strategy_risk: float,  # Strategy's risk per trade (e.g., 0.02 for 2%)
        symbol: str,
        entry_price: float,
        portfolio_positions: List[PortfolioPosition],
        max_risk_per_trade: float = 0.02  # 2% max risk per trade
    ) -> float:
        """
        Calculate optimal position size based on portfolio risk management.
        
        Uses Kelly Criterion and risk budgeting:
        - Limits risk per trade
        - Ensures diversification
        - Respects position size limits
        - Accounts for correlation
        
        Args:
            account_balance: Total account balance
            strategy_risk: Strategy's historical risk (volatility)
            symbol: Trading symbol
            entry_price: Entry price
            portfolio_positions: Current portfolio positions
            max_risk_per_trade: Maximum risk per trade as % of account
        
        Returns:
            Optimal number of shares
        """
        # Base position size from risk
        risk_amount = account_balance * min(max_risk_per_trade, strategy_risk)
        
        # Adjust for stop loss (assume 2% stop loss)
        stop_loss_percent = 0.02
        position_value = risk_amount / stop_loss_percent
        
        # Calculate shares
        base_shares = position_value / entry_price
        
        # Apply position size limit
        max_position_value = account_balance * self.max_position_size
        max_shares = max_position_value / entry_price
        
        shares = min(base_shares, max_shares)
        
        # Check correlation with existing positions
        if portfolio_positions:
            correlation_penalty = self._calculate_correlation_penalty(
                symbol,
                portfolio_positions
            )
            shares *= (1.0 - correlation_penalty)
        
        # Ensure minimum viable position (at least 1 share if affordable)
        if shares < 1.0 and position_value >= entry_price:
            shares = 1.0
        
        return max(0.0, shares)
    
    def _calculate_correlation_penalty(
        self,
        symbol: str,
        portfolio_positions: List[PortfolioPosition]
    ) -> float:
        """
        Calculate position size reduction based on correlation with existing positions.
        
        Returns:
            Penalty factor (0-1), higher = more correlated = reduce size more
        """
        # Simplified: assume higher correlation if same sector/type
        # In production, would use actual correlation matrix
        
        # For now, reduce size if we already have positions in similar symbols
        existing_symbols = [p.symbol for p in portfolio_positions]
        
        if symbol in existing_symbols:
            return 0.5  # 50% reduction if exact match
        
        # Check for similar symbols (same prefix, e.g., "AAPL" vs "AAPL2")
        symbol_prefix = symbol[:3]
        similar_count = sum(1 for s in existing_symbols if s.startswith(symbol_prefix))
        
        if similar_count > 0:
            return 0.3 * similar_count  # 30% per similar symbol
        
        return 0.0  # No penalty if uncorrelated
    
    def calculate_portfolio_metrics(
        self,
        positions: List[PortfolioPosition],
        account_balance: float,
        historical_returns: Optional[Dict[str, List[float]]] = None
    ) -> PortfolioRiskMetrics:
        """
        Calculate portfolio-level risk metrics.
        
        Args:
            positions: Current portfolio positions
            account_balance: Total account balance
            historical_returns: Historical returns per symbol (for correlation)
        
        Returns:
            PortfolioRiskMetrics
        """
        if not positions:
            return PortfolioRiskMetrics(
                total_notional=0.0,
                total_exposure=0.0,
                portfolio_var_95=0.0,
                portfolio_var_99=0.0,
                max_portfolio_drawdown=0.0,
                correlation_risk=0.0,
                diversification_score=1.0,
                concentration_risk=0.0,
                leverage_ratio=1.0,
                risk_budget_utilization={}
            )
        
        # Total notional
        total_notional = sum(p.notional for p in positions)
        
        # Total exposure (long + short)
        total_exposure = sum(abs(p.notional) for p in positions)
        
        # Leverage ratio
        leverage_ratio = total_exposure / account_balance if account_balance > 0 else 1.0
        
        # Concentration risk (Herfindahl index)
        position_weights = [abs(p.notional) / total_exposure for p in positions if total_exposure > 0]
        concentration_risk = sum(w ** 2 for w in position_weights)
        
        # Diversification score (inverse of concentration)
        diversification_score = 1.0 - min(1.0, concentration_risk)
        
        # Correlation risk (simplified)
        correlation_risk = self._estimate_correlation_risk(positions, historical_returns)
        
        # Portfolio VaR (simplified - would use full correlation matrix in production)
        portfolio_var_95 = self._calculate_portfolio_var(positions, 0.95)
        portfolio_var_99 = self._calculate_portfolio_var(positions, 0.99)
        
        # Max portfolio drawdown (from current positions)
        max_portfolio_drawdown = abs(min((p.pnl_percent for p in positions), default=0.0))
        
        # Risk budget utilization
        risk_budget_utilization = self._calculate_risk_budget_utilization(positions, account_balance)
        
        return PortfolioRiskMetrics(
            total_notional=total_notional,
            total_exposure=total_exposure,
            portfolio_var_95=portfolio_var_95,
            portfolio_var_99=portfolio_var_99,
            max_portfolio_drawdown=max_portfolio_drawdown,
            correlation_risk=correlation_risk,
            diversification_score=diversification_score,
            concentration_risk=concentration_risk,
            leverage_ratio=leverage_ratio,
            risk_budget_utilization=risk_budget_utilization
        )
    
    def _estimate_correlation_risk(
        self,
        positions: List[PortfolioPosition],
        historical_returns: Optional[Dict[str, List[float]]]
    ) -> float:
        """Estimate correlation risk (simplified)."""
        if not historical_returns or len(positions) < 2:
            return 0.0
        
        # In production, would calculate actual correlation matrix
        # For now, assume higher risk if many positions in similar symbols
        symbols = [p.symbol for p in positions]
        unique_symbols = len(set(symbols))
        
        # Lower unique symbols = higher correlation risk
        correlation_risk = 1.0 - (unique_symbols / len(symbols)) if symbols else 0.0
        
        return correlation_risk
    
    def _calculate_portfolio_var(
        self,
        positions: List[PortfolioPosition],
        confidence: float
    ) -> float:
        """Calculate portfolio Value at Risk."""
        # Simplified VaR calculation
        # In production, would use full correlation matrix and historical data
        
        total_notional = sum(abs(p.notional) for p in positions)
        if total_notional == 0:
            return 0.0
        
        # Assume 2% daily volatility per position (simplified)
        daily_volatility = 0.02
        
        # Z-score for confidence level
        if confidence == 0.95:
            z_score = 1.65
        elif confidence == 0.99:
            z_score = 2.33
        else:
            z_score = 1.65
        
        # Portfolio VaR (simplified - doesn't account for correlation)
        portfolio_var = total_notional * daily_volatility * z_score
        
        return portfolio_var
    
    def _calculate_risk_budget_utilization(
        self,
        positions: List[PortfolioPosition],
        account_balance: float
    ) -> Dict[str, float]:
        """Calculate risk budget utilization per strategy."""
        utilization = {}
        
        for position in positions:
            if position.strategy_id:
                strategy_id = position.strategy_id
                risk_used = abs(position.notional) / account_balance if account_balance > 0 else 0.0
                utilization[strategy_id] = utilization.get(strategy_id, 0.0) + risk_used
        
        return utilization
    
    def validate_new_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        account_balance: float,
        portfolio_positions: List[PortfolioPosition],
        strategy_id: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if a new position can be added without exceeding risk limits.
        
        Returns:
            (is_valid, error_message)
        """
        new_notional = quantity * entry_price
        
        # Check position size limit
        if new_notional > account_balance * self.max_position_size:
            return False, f"Position size ({new_notional:.2f}) exceeds max ({account_balance * self.max_position_size:.2f})"
        
        # Check total exposure
        total_exposure = sum(abs(p.notional) for p in portfolio_positions) + new_notional
        if total_exposure > account_balance * 2.0:  # Max 2x leverage
            return False, f"Total exposure ({total_exposure:.2f}) exceeds max leverage"
        
        # Check portfolio risk
        test_positions = portfolio_positions + [
            PortfolioPosition(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
                notional=new_notional,
                strategy_id=strategy_id
            )
        ]
        
        metrics = self.calculate_portfolio_metrics(test_positions, account_balance)
        
        if metrics.max_portfolio_drawdown > self.max_portfolio_risk:
            return False, f"Portfolio drawdown risk ({metrics.max_portfolio_drawdown:.2%}) exceeds max ({self.max_portfolio_risk:.2%})"
        
        return True, None

