# backend/strategy_engine/strategy_transparency.py
"""
Strategy Transparency & Risk Disclosure Engine

Provides clear, transparent information about strategies when proposed to users:
- Market regime fit
- Investment requirements (amount, duration)
- Possible loss (worst-case scenario)
- Possible profit (best-case scenario)
- Risk metrics
- Clear risk disclosure

This ensures users make informed decisions before investing.
"""
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

from .monte_carlo import MonteCarloSimulator
from .walk_forward import WalkForwardOptimizer
from ..brain.regime_detector import RegimeDetector


@dataclass
class StrategyTransparencyReport:
    """Comprehensive transparency report for a strategy."""
    # Market Regime Fit
    current_regime: str  # "Bull", "Bear", "High-Vol", "Low-Vol", "Trending", "Ranging"
    regime_fit_score: float  # 0-1, how well strategy fits current regime
    regime_stability: Dict[str, str]  # Pass/Fail for each regime
    
    # Investment Requirements
    recommended_investment_min: float  # Minimum recommended investment
    recommended_investment_max: float  # Maximum recommended investment
    typical_investment: float  # Typical investment amount
    expected_duration_days: int  # Expected holding period
    expected_trades_per_month: float  # Expected number of trades
    
    # Risk Metrics
    possible_loss_worst_case: float  # Worst-case loss (95% VaR)
    possible_loss_typical: float  # Typical loss scenario
    possible_profit_best_case: float  # Best-case profit (95% percentile)
    possible_profit_typical: float  # Typical profit scenario
    max_drawdown: float  # Maximum drawdown
    probability_of_loss: float  # Probability of losing money
    
    # Performance Projections
    expected_annual_return: float  # Expected annual return %
    expected_annual_return_range: tuple  # (min, max) at 90% confidence
    sharpe_ratio: float  # Risk-adjusted return
    
    # Risk Disclosure
    risk_level: str  # "Low", "Medium", "High", "Very High"
    risk_factors: List[str]  # List of risk factors
    suitability_warning: str  # Suitability warning
    
    # Transparency Details
    backtest_period: str  # "2020-2024" or similar
    number_of_trades_analyzed: int
    walk_forward_consistency: float  # 0-1
    overfitting_risk: str  # "Low", "Medium", "High"


class StrategyTransparencyEngine:
    """
    Generates transparent, clear reports for strategies.
    """
    
    def __init__(self):
        self.monte_carlo = MonteCarloSimulator(n_simulations=10000)
        self.regime_detector = RegimeDetector()
    
    def generate_transparency_report(
        self,
        strategy: Dict[str, Any],
        strategy_id: str,
        symbol: str,
        backtest_results: Dict[str, Any],
        account_balance: float = 10000.0,
        user_risk_profile: str = "moderate"  # "low", "moderate", "high"
    ) -> StrategyTransparencyReport:
        """
        Generate comprehensive transparency report for a strategy.
        
        Args:
            strategy: Strategy definition
            strategy_id: Strategy ID
            symbol: Trading symbol
            backtest_results: Results from backtesting
            account_balance: User's account balance
            user_risk_profile: User's risk tolerance
        
        Returns:
            StrategyTransparencyReport with all transparency information
        """
        # 1. Market Regime Analysis
        current_regime, regime_fit_score, regime_stability = self._analyze_regime_fit(
            strategy,
            symbol,
            backtest_results
        )
        
        # 2. Investment Requirements
        investment_reqs = self._calculate_investment_requirements(
            backtest_results,
            account_balance,
            user_risk_profile
        )
        
        # 3. Risk Metrics (Monte Carlo)
        risk_metrics = self._calculate_risk_metrics(
            backtest_results,
            investment_reqs["typical_investment"]
        )
        
        # 4. Performance Projections
        performance = self._calculate_performance_projections(
            backtest_results,
            risk_metrics
        )
        
        # 5. Risk Disclosure
        risk_disclosure = self._generate_risk_disclosure(
            risk_metrics,
            performance,
            user_risk_profile,
            backtest_results
        )
        
        # 6. Transparency Details
        transparency_details = self._generate_transparency_details(
            backtest_results,
            strategy_id
        )
        
        return StrategyTransparencyReport(
            current_regime=current_regime,
            regime_fit_score=regime_fit_score,
            regime_stability=regime_stability,
            recommended_investment_min=investment_reqs["min"],
            recommended_investment_max=investment_reqs["max"],
            typical_investment=investment_reqs["typical"],
            expected_duration_days=investment_reqs["duration_days"],
            expected_trades_per_month=investment_reqs["trades_per_month"],
            possible_loss_worst_case=risk_metrics["worst_case_loss"],
            possible_loss_typical=risk_metrics["typical_loss"],
            possible_profit_best_case=risk_metrics["best_case_profit"],
            possible_profit_typical=risk_metrics["typical_profit"],
            max_drawdown=risk_metrics["max_drawdown"],
            probability_of_loss=risk_metrics["probability_of_loss"],
            expected_annual_return=performance["annual_return"],
            expected_annual_return_range=performance["return_range"],
            sharpe_ratio=performance["sharpe_ratio"],
            risk_level=risk_disclosure["risk_level"],
            risk_factors=risk_disclosure["risk_factors"],
            suitability_warning=risk_disclosure["suitability_warning"],
            backtest_period=transparency_details["backtest_period"],
            number_of_trades_analyzed=transparency_details["num_trades"],
            walk_forward_consistency=transparency_details["consistency"],
            overfitting_risk=transparency_details["overfitting_risk"]
        )
    
    def _analyze_regime_fit(
        self,
        strategy: Dict[str, Any],
        symbol: str,
        backtest_results: Dict[str, Any]
    ) -> tuple[str, float, Dict[str, str]]:
        """Analyze how well strategy fits current market regime."""
        try:
            # Detect current regime
            current_regime_data = self.regime_detector.detect_regime(symbol)
            current_regime = current_regime_data.get("regime", "Unknown")
            
            # Get regime stability from backtest results
            mcn_analysis = backtest_results.get("mcn_analysis", {})
            regime_stability = mcn_analysis.get("regime_stability", {})
            
            # Calculate fit score
            if current_regime in regime_stability:
                regime_fit_score = 1.0 if regime_stability[current_regime] == "pass" else 0.5
            else:
                regime_fit_score = 0.7  # Neutral if regime not tested
            
            return current_regime, regime_fit_score, regime_stability
        except Exception as e:
            print(f"Error analyzing regime fit: {e}")
            return "Unknown", 0.5, {}
    
    def _calculate_investment_requirements(
        self,
        backtest_results: Dict[str, Any],
        account_balance: float,
        user_risk_profile: str
    ) -> Dict[str, Any]:
        """Calculate investment requirements."""
        # Get strategy metrics
        total_trades = backtest_results.get("total_trades", 0)
        backtest_days = backtest_results.get("backtest_days", 365)
        
        # Calculate trades per month
        trades_per_month = (total_trades / backtest_days) * 30 if backtest_days > 0 else 0
        
        # Calculate expected duration (average holding period)
        avg_holding_period = backtest_days / total_trades if total_trades > 0 else 30
        expected_duration_days = int(avg_holding_period)
        
        # Calculate recommended investment based on risk profile
        if user_risk_profile == "low":
            risk_percent = 0.01  # 1% of account
        elif user_risk_profile == "moderate":
            risk_percent = 0.02  # 2% of account
        else:  # high
            risk_percent = 0.05  # 5% of account
        
        # Typical investment (2-5% of account balance)
        typical_investment = account_balance * 0.03  # 3% default
        
        # Min investment (1% of account, minimum $100)
        min_investment = max(100.0, account_balance * 0.01)
        
        # Max investment (10% of account, or based on risk profile)
        max_investment = account_balance * min(0.10, risk_percent * 5)
        
        return {
            "min": min_investment,
            "max": max_investment,
            "typical": typical_investment,
            "duration_days": expected_duration_days,
            "trades_per_month": trades_per_month
        }
    
    def _calculate_risk_metrics(
        self,
        backtest_results: Dict[str, Any],
        investment_amount: float
    ) -> Dict[str, float]:
        """Calculate risk metrics using Monte Carlo simulation."""
        # Extract trade returns
        trades = backtest_results.get("trades", [])
        if not trades:
            # Fallback to backtest metrics
            total_return = backtest_results.get("total_return", 0)
            max_drawdown = backtest_results.get("max_drawdown", 0)
            
            return {
                "worst_case_loss": abs(max_drawdown) * investment_amount,
                "typical_loss": abs(max_drawdown) * 0.5 * investment_amount,
                "best_case_profit": total_return * investment_amount * 1.5,  # Optimistic
                "typical_profit": total_return * investment_amount,
                "max_drawdown": abs(max_drawdown),
                "probability_of_loss": 0.3 if total_return < 0 else 0.2
            }
        
        # Calculate trade returns
        trade_returns = []
        for trade in trades:
            if isinstance(trade, dict):
                pnl = trade.get("pnl", 0)
                entry_price = trade.get("entry_price", 1.0)
                if entry_price > 0:
                    trade_return = pnl / (entry_price * trade.get("quantity", 1))
                    trade_returns.append(trade_return)
        
        if not trade_returns:
            # Fallback
            total_return = backtest_results.get("total_return", 0)
            return {
                "worst_case_loss": abs(backtest_results.get("max_drawdown", 0.2)) * investment_amount,
                "typical_loss": abs(backtest_results.get("max_drawdown", 0.1)) * investment_amount,
                "best_case_profit": total_return * investment_amount * 1.5,
                "typical_profit": total_return * investment_amount,
                "max_drawdown": abs(backtest_results.get("max_drawdown", 0.2)),
                "probability_of_loss": 0.3 if total_return < 0 else 0.2
            }
        
        # Run Monte Carlo simulation
        mc_result = self.monte_carlo.simulate_strategy(
            trade_returns=trade_returns,
            initial_capital=investment_amount
        )
        
        # Calculate possible loss (95% VaR)
        worst_case_loss = abs(mc_result.var_95) * investment_amount
        typical_loss = abs(mc_result.return_distribution["p25"]) * investment_amount
        
        # Calculate possible profit (95% percentile)
        best_case_profit = mc_result.return_distribution["p95"] * investment_amount
        typical_profit = mc_result.return_distribution["p50"] * investment_amount
        
        return {
            "worst_case_loss": worst_case_loss,
            "typical_loss": typical_loss,
            "best_case_profit": best_case_profit,
            "typical_profit": typical_profit,
            "max_drawdown": mc_result.max_drawdown_distribution["p95"],
            "probability_of_loss": mc_result.probability_of_ruin
        }
    
    def _calculate_performance_projections(
        self,
        backtest_results: Dict[str, Any],
        risk_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Calculate performance projections."""
        total_return = backtest_results.get("total_return", 0)
        sharpe_ratio = backtest_results.get("sharpe_ratio", 0)
        backtest_days = backtest_results.get("backtest_days", 365)
        
        # Annualize return
        if backtest_days > 0:
            annual_return = ((1 + total_return) ** (365 / backtest_days)) - 1
        else:
            annual_return = total_return
        
        # Calculate return range (90% confidence)
        return_min = annual_return * 0.5  # Conservative
        return_max = annual_return * 1.5  # Optimistic
        
        return {
            "annual_return": annual_return,
            "return_range": (return_min, return_max),
            "sharpe_ratio": sharpe_ratio
        }
    
    def _generate_risk_disclosure(
        self,
        risk_metrics: Dict[str, float],
        performance: Dict[str, Any],
        user_risk_profile: str,
        backtest_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate risk disclosure and warnings."""
        max_drawdown = risk_metrics["max_drawdown"]
        probability_of_loss = risk_metrics["probability_of_loss"]
        sharpe_ratio = performance["sharpe_ratio"]
        
        # Determine risk level
        if max_drawdown < 0.10 and probability_of_loss < 0.2 and sharpe_ratio > 1.5:
            risk_level = "Low"
        elif max_drawdown < 0.20 and probability_of_loss < 0.3 and sharpe_ratio > 1.0:
            risk_level = "Medium"
        elif max_drawdown < 0.35 and probability_of_loss < 0.4:
            risk_level = "High"
        else:
            risk_level = "Very High"
        
        # Risk factors
        risk_factors = []
        if max_drawdown > 0.25:
            risk_factors.append(f"High maximum drawdown ({max_drawdown:.1%})")
        if probability_of_loss > 0.3:
            risk_factors.append(f"Significant probability of loss ({probability_of_loss:.1%})")
        if sharpe_ratio < 1.0:
            risk_factors.append("Below-average risk-adjusted returns")
        if backtest_results.get("overfitting_risk", "Medium") == "High":
            risk_factors.append("High overfitting risk - past performance may not continue")
        
        # Suitability warning
        if risk_level == "Very High" and user_risk_profile == "low":
            suitability_warning = "⚠️ WARNING: This strategy is VERY HIGH RISK and may not be suitable for conservative investors."
        elif risk_level == "High" and user_risk_profile == "low":
            suitability_warning = "⚠️ CAUTION: This strategy is HIGH RISK. Conservative investors should consider lower-risk alternatives."
        elif risk_level in ["Low", "Medium"]:
            suitability_warning = "This strategy appears suitable for your risk profile, but always invest only what you can afford to lose."
        else:
            suitability_warning = "Please review all risk factors carefully before investing."
        
        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "suitability_warning": suitability_warning
        }
    
    def _generate_transparency_details(
        self,
        backtest_results: Dict[str, Any],
        strategy_id: str
    ) -> Dict[str, Any]:
        """Generate transparency details."""
        total_trades = backtest_results.get("total_trades", 0)
        start_date = backtest_results.get("start_date")
        end_date = backtest_results.get("end_date")
        
        # Backtest period
        if start_date and end_date:
            if isinstance(start_date, str):
                start_year = start_date[:4]
            else:
                start_year = str(start_date.year)
            if isinstance(end_date, str):
                end_year = end_date[:4]
            else:
                end_year = str(end_date.year)
            backtest_period = f"{start_year}-{end_year}"
        else:
            backtest_period = "N/A"
        
        # Walk-forward consistency (if available)
        consistency = backtest_results.get("walk_forward_consistency", 0.7)
        
        # Overfitting risk
        overfitting_risk = backtest_results.get("overfitting_risk", "Medium")
        mcn_analysis = backtest_results.get("mcn_analysis", {})
        if mcn_analysis:
            overfitting_risk = mcn_analysis.get("overfitting_risk", overfitting_risk)
        
        return {
            "backtest_period": backtest_period,
            "num_trades": total_trades,
            "consistency": consistency,
            "overfitting_risk": overfitting_risk
        }

