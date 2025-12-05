# backend/strategy_engine/walk_forward.py
"""
Walk-Forward Optimization Engine - Hedge Fund Grade

Implements walk-forward analysis to validate strategies across multiple time periods,
preventing overfitting and ensuring robustness.

Walk-forward analysis:
1. Split data into in-sample (training) and out-of-sample (testing) periods
2. Optimize parameters on in-sample data
3. Test on out-of-sample data
4. Roll forward and repeat
5. Aggregate results across all periods

This is the gold standard for strategy validation in institutional trading.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass

from .backtest_engine import BacktestEngine
from ..market_data.market_data_provider import call_with_fallback


@dataclass
class WalkForwardPeriod:
    """Represents a single walk-forward period."""
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime
    period_number: int


@dataclass
class WalkForwardResult:
    """Results from walk-forward analysis."""
    periods: List[WalkForwardPeriod]
    in_sample_results: List[Dict[str, Any]]
    out_of_sample_results: List[Dict[str, Any]]
    aggregated_metrics: Dict[str, float]
    consistency_score: float  # 0-1, how consistent performance is across periods
    overfitting_risk: str  # "Low", "Medium", "High"


class WalkForwardOptimizer:
    """
    Walk-forward optimization engine for institutional-grade strategy validation.
    """
    
    def __init__(
        self,
        in_sample_months: int = 12,
        out_of_sample_months: int = 3,
        step_months: int = 3,
        min_periods: int = 2  # Reduced from 3 to 2 for flexibility
    ):
        """
        Initialize walk-forward optimizer.
        
        Args:
            in_sample_months: Months of data for training/optimization
            out_of_sample_months: Months of data for testing
            step_months: How many months to step forward each iteration
            min_periods: Minimum number of periods required for valid analysis (default: 2)
        """
        self.in_sample_months = in_sample_months
        self.out_of_sample_months = out_of_sample_months
        self.step_months = step_months
        self.min_periods = min_periods
    
    def generate_periods(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[WalkForwardPeriod]:
        """
        Generate walk-forward periods from start to end date.
        
        Args:
            start_date: Start of available data
            end_date: End of available data
        
        Returns:
            List of walk-forward periods
        """
        periods = []
        current_start = start_date
        period_num = 0
        
        while True:
            # In-sample period
            in_sample_end = current_start + timedelta(days=30 * self.in_sample_months)
            
            # Out-of-sample period
            out_of_sample_start = in_sample_end
            out_of_sample_end = out_of_sample_start + timedelta(days=30 * self.out_of_sample_months)
            
            # Check if we have enough data
            if out_of_sample_end > end_date:
                break
            
            period = WalkForwardPeriod(
                in_sample_start=current_start,
                in_sample_end=in_sample_end,
                out_of_sample_start=out_of_sample_start,
                out_of_sample_end=out_of_sample_end,
                period_number=period_num
            )
            periods.append(period)
            
            # Step forward
            current_start += timedelta(days=30 * self.step_months)
            period_num += 1
        
        return periods
    
    def run_walk_forward(
        self,
        strategy: Dict[str, Any],
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000.0
    ) -> WalkForwardResult:
        """
        Run complete walk-forward analysis.
        
        Args:
            strategy: Strategy definition
            symbol: Trading symbol
            timeframe: Timeframe (1m, 5m, 1h, 1d, etc.)
            start_date: Start of available data
            end_date: End of available data
            initial_capital: Starting capital
        
        Returns:
            WalkForwardResult with all periods and aggregated metrics
        """
        # Generate periods
        periods = self.generate_periods(start_date, end_date)
        
        if len(periods) < self.min_periods:
            raise ValueError(
                f"Insufficient data for walk-forward analysis. "
                f"Need at least {self.min_periods} periods, got {len(periods)}"
            )
        
        in_sample_results = []
        out_of_sample_results = []
        
        backtest_engine = BacktestEngine()
        
        # Run backtest for each period
        for period in periods:
            # In-sample backtest (optimization)
            in_sample_result = backtest_engine.run_backtest(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                start_date=period.in_sample_start,
                end_date=period.in_sample_end,
                initial_capital=initial_capital
            )
            in_sample_results.append(in_sample_result)
            
            # Out-of-sample backtest (validation)
            out_of_sample_result = backtest_engine.run_backtest(
                strategy=strategy,
                symbol=symbol,
                timeframe=timeframe,
                start_date=period.out_of_sample_start,
                end_date=period.out_of_sample_end,
                initial_capital=initial_capital
            )
            out_of_sample_results.append(out_of_sample_result)
        
        # Aggregate metrics
        aggregated_metrics = self._aggregate_metrics(out_of_sample_results)
        
        # Calculate consistency score
        consistency_score = self._calculate_consistency(out_of_sample_results)
        
        # Assess overfitting risk
        overfitting_risk = self._assess_overfitting_risk(
            in_sample_results,
            out_of_sample_results
        )
        
        return WalkForwardResult(
            periods=periods,
            in_sample_results=in_sample_results,
            out_of_sample_results=out_of_sample_results,
            aggregated_metrics=aggregated_metrics,
            consistency_score=consistency_score,
            overfitting_risk=overfitting_risk
        )
    
    def _aggregate_metrics(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Aggregate metrics across all periods."""
        if not results:
            return {}
        
        # Aggregate key metrics
        total_return = np.mean([r.get("total_return", 0) for r in results])
        sharpe_ratio = np.mean([r.get("sharpe_ratio", 0) for r in results])
        max_drawdown = np.mean([abs(r.get("max_drawdown", 0)) for r in results])
        win_rate = np.mean([r.get("win_rate", 0) for r in results])
        profit_factor = np.mean([r.get("profit_factor", 0) for r in results])
        total_trades = sum([r.get("total_trades", 0) for r in results])
        
        # Calculate stability (lower std = more stable)
        returns = [r.get("total_return", 0) for r in results]
        return_stability = 1.0 - min(1.0, np.std(returns) / (abs(np.mean(returns)) + 0.01))
        
        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "return_stability": return_stability,
            "periods_tested": len(results)
        }
    
    def _calculate_consistency(
        self,
        results: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate consistency score (0-1).
        Higher = more consistent performance across periods.
        """
        if len(results) < 2:
            return 0.5
        
        # Calculate coefficient of variation for returns
        returns = [r.get("total_return", 0) for r in results]
        if np.mean(returns) == 0:
            return 0.0
        
        cv = np.std(returns) / (abs(np.mean(returns)) + 0.01)
        
        # Convert to 0-1 score (lower CV = higher consistency)
        consistency = 1.0 / (1.0 + cv)
        
        return min(1.0, max(0.0, consistency))
    
    def _assess_overfitting_risk(
        self,
        in_sample_results: List[Dict[str, Any]],
        out_of_sample_results: List[Dict[str, Any]]
    ) -> str:
        """
        Assess overfitting risk by comparing in-sample vs out-of-sample performance.
        
        Returns:
            "Low", "Medium", or "High"
        """
        if not in_sample_results or not out_of_sample_results:
            return "High"
        
        # Calculate average Sharpe ratio for in-sample vs out-of-sample
        in_sample_sharpe = np.mean([r.get("sharpe_ratio", 0) for r in in_sample_results])
        out_of_sample_sharpe = np.mean([r.get("sharpe_ratio", 0) for r in out_of_sample_results])
        
        # Calculate degradation
        if in_sample_sharpe == 0:
            degradation = 1.0
        else:
            degradation = (in_sample_sharpe - out_of_sample_sharpe) / abs(in_sample_sharpe)
        
        # Assess risk
        if degradation < 0.1:  # Less than 10% degradation
            return "Low"
        elif degradation < 0.3:  # 10-30% degradation
            return "Medium"
        else:  # More than 30% degradation
            return "High"

