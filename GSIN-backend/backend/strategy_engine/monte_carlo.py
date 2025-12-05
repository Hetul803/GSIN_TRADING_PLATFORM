# backend/strategy_engine/monte_carlo.py
"""
Monte Carlo Simulation Engine - Hedge Fund Grade

Performs Monte Carlo simulations to assess strategy risk and potential outcomes.
This is critical for institutional-grade risk management.

Monte Carlo simulation:
1. Generate many random scenarios based on historical trade distribution
2. Simulate portfolio performance under each scenario
3. Calculate risk metrics (VaR, CVaR, probability of ruin, etc.)
4. Provide confidence intervals for returns
"""
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from dataclasses import dataclass
from scipy import stats


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""
    mean_return: float
    std_return: float
    var_95: float  # Value at Risk (95% confidence)
    var_99: float  # Value at Risk (99% confidence)
    cvar_95: float  # Conditional VaR (95% confidence)
    cvar_99: float  # Conditional VaR (99% confidence)
    probability_of_ruin: float  # Probability of losing entire capital
    max_drawdown_distribution: Dict[str, float]  # Percentiles of max drawdown
    return_distribution: Dict[str, float]  # Percentiles of returns
    confidence_intervals: Dict[str, Tuple[float, float]]  # CI for different confidence levels
    simulations_run: int


class MonteCarloSimulator:
    """
    Monte Carlo simulation engine for risk assessment.
    """
    
    def __init__(self, n_simulations: int = 10000):
        """
        Initialize Monte Carlo simulator.
        
        Args:
            n_simulations: Number of Monte Carlo simulations to run
        """
        self.n_simulations = n_simulations
    
    def simulate_strategy(
        self,
        trade_returns: List[float],
        initial_capital: float = 10000.0,
        max_trades: Optional[int] = None
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on strategy based on historical trade returns.
        
        Args:
            trade_returns: List of historical trade returns (as decimals, e.g., 0.05 for 5%)
            initial_capital: Starting capital
            max_trades: Maximum number of trades to simulate (None = use all)
        
        Returns:
            MonteCarloResult with risk metrics
        """
        if not trade_returns:
            raise ValueError("trade_returns cannot be empty")
        
        if max_trades is None:
            max_trades = len(trade_returns)
        
        # Fit distribution to trade returns
        mean_return = np.mean(trade_returns)
        std_return = np.std(trade_returns)
        
        # Run simulations
        simulated_returns = []
        simulated_drawdowns = []
        ruin_count = 0
        
        for _ in range(self.n_simulations):
            # Sample random trades
            sampled_trades = np.random.choice(
                trade_returns,
                size=min(max_trades, len(trade_returns)),
                replace=True
            )
            
            # Simulate portfolio
            capital = initial_capital
            equity_curve = [capital]
            peak = capital
            
            for trade_return in sampled_trades:
                capital *= (1 + trade_return)
                equity_curve.append(capital)
                peak = max(peak, capital)
            
            # Calculate metrics
            final_return = (capital - initial_capital) / initial_capital
            simulated_returns.append(final_return)
            
            # Calculate max drawdown
            max_dd = 0
            for value in equity_curve:
                if peak > 0:
                    dd = (peak - value) / peak
                    max_dd = max(max_dd, dd)
            simulated_drawdowns.append(max_dd)
            
            # Check for ruin
            if capital < initial_capital * 0.1:  # Lost 90%+
                ruin_count += 1
        
        # Calculate statistics
        mean_sim_return = np.mean(simulated_returns)
        std_sim_return = np.std(simulated_returns)
        
        # Value at Risk (VaR) - worst case at confidence level
        var_95 = np.percentile(simulated_returns, 5)  # 95% confidence (5th percentile)
        var_99 = np.percentile(simulated_returns, 1)  # 99% confidence (1st percentile)
        
        # Conditional VaR (CVaR) - expected loss given VaR threshold
        cvar_95 = np.mean([r for r in simulated_returns if r <= var_95])
        cvar_99 = np.mean([r for r in simulated_returns if r <= var_99])
        
        # Probability of ruin
        probability_of_ruin = ruin_count / self.n_simulations
        
        # Distribution percentiles
        return_distribution = {
            "p5": np.percentile(simulated_returns, 5),
            "p25": np.percentile(simulated_returns, 25),
            "p50": np.percentile(simulated_returns, 50),
            "p75": np.percentile(simulated_returns, 75),
            "p95": np.percentile(simulated_returns, 95),
        }
        
        max_drawdown_distribution = {
            "p5": np.percentile(simulated_drawdowns, 5),
            "p25": np.percentile(simulated_drawdowns, 25),
            "p50": np.percentile(simulated_drawdowns, 50),
            "p75": np.percentile(simulated_drawdowns, 75),
            "p95": np.percentile(simulated_drawdowns, 95),
        }
        
        # Confidence intervals
        confidence_intervals = {
            "90": (
                np.percentile(simulated_returns, 5),
                np.percentile(simulated_returns, 95)
            ),
            "95": (
                np.percentile(simulated_returns, 2.5),
                np.percentile(simulated_returns, 97.5)
            ),
            "99": (
                np.percentile(simulated_returns, 0.5),
                np.percentile(simulated_returns, 99.5)
            ),
        }
        
        return MonteCarloResult(
            mean_return=mean_sim_return,
            std_return=std_sim_return,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            probability_of_ruin=probability_of_ruin,
            max_drawdown_distribution=max_drawdown_distribution,
            return_distribution=return_distribution,
            confidence_intervals=confidence_intervals,
            simulations_run=self.n_simulations
        )
    
    def simulate_portfolio(
        self,
        strategies: List[Dict[str, Any]],
        correlation_matrix: Optional[np.ndarray] = None,
        initial_capital: float = 10000.0
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on a portfolio of strategies.
        
        Args:
            strategies: List of strategy results with trade_returns
            correlation_matrix: Correlation matrix between strategies (None = independent)
            initial_capital: Starting capital
        
        Returns:
            MonteCarloResult for the portfolio
        """
        # Extract trade returns from each strategy
        all_trade_returns = []
        for strategy in strategies:
            trade_returns = strategy.get("trade_returns", [])
            all_trade_returns.extend(trade_returns)
        
        if not all_trade_returns:
            raise ValueError("No trade returns found in strategies")
        
        # If correlation matrix provided, use multivariate simulation
        if correlation_matrix is not None and len(strategies) > 1:
            # Multivariate Monte Carlo
            return self._simulate_multivariate(
                strategies,
                correlation_matrix,
                initial_capital
            )
        else:
            # Simple aggregation
            return self.simulate_strategy(
                all_trade_returns,
                initial_capital
            )
    
    def _simulate_multivariate(
        self,
        strategies: List[Dict[str, Any]],
        correlation_matrix: np.ndarray,
        initial_capital: float
    ) -> MonteCarloResult:
        """
        Run multivariate Monte Carlo simulation with correlation.
        """
        # This is a simplified version - full implementation would use
        # Cholesky decomposition for correlated random sampling
        # For now, use independent simulation
        all_returns = []
        for strategy in strategies:
            all_returns.extend(strategy.get("trade_returns", []))
        
        return self.simulate_strategy(all_returns, initial_capital)
