# backend/brain/explanation_engine.py
"""
"Why This Trade?" Explanation Engine.
PHASE 4: Provides detailed explanations for trading signals.
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from .types import BrainSignalResponse
from ..db import crud
from ..db.models import UserStrategy


class ExplanationEngine:
    """
    Generates detailed explanations for trading signals.
    
    Explains:
    - Market regime and why it matters
    - Volume confirmation
    - Trend alignment across timeframes
    - Risk checks (portfolio, correlation, leverage)
    - MCN context (historical patterns, similarity)
    - Confidence breakdown
    - Strategy lineage information
    """
    
    def explain_signal(
        self,
        signal: BrainSignalResponse,
        strategy: UserStrategy,
        context: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """
        Generate comprehensive explanation for a trading signal.
        
        Args:
            signal: BrainSignalResponse from generate_signal()
            strategy: UserStrategy object
            context: Additional context (regime, volume, trends, etc.)
            db: Database session
        
        Returns:
            {
                "regime": {
                    "label": str,
                    "confidence": float,
                    "explanation": str,
                    "why_it_matters": str
                },
                "volume": {
                    "trend": str,
                    "strength": float,
                    "recommendation": str,
                    "explanation": str
                },
                "trend_alignment": {
                    "short": str,
                    "medium": str,
                    "long": str,
                    "alignment_score": float,
                    "explanation": str
                },
                "risk_checks": {
                    "portfolio_risk": Dict,
                    "symbol_exposure": float,
                    "sector_exposure": float,
                    "correlation_risk": float,
                    "leverage_risk": float,
                    "all_passed": bool
                },
                "mcn_context": {
                    "similar_patterns": int,
                    "historical_performance": Dict,
                    "regime_fit": float,
                    "explanation": str
                },
                "confidence_breakdown": {
                    "raw_confidence": float,
                    "calibrated_confidence": float,
                    "factors": Dict,
                    "explanation": str
                },
                "lineage_info": {
                    "ancestor_count": int,
                    "ancestor_stability": float,
                    "has_overfit_ancestors": bool,
                    "explanation": str
                },
                "strategy_info": {
                    "name": str,
                    "score": float,
                    "status": str,
                    "win_rate": float,
                    "total_trades": int
                }
            }
        """
        mcn_adjustments = signal.mcn_adjustments or {}
        
        # Extract context data
        regime_result = mcn_adjustments.get("market_regime_detected", {})
        volume_confirmation = mcn_adjustments.get("volume_confirmation", {})
        mtn_trend = mcn_adjustments.get("multi_timeframe_trend", {})
        portfolio_risk = mcn_adjustments.get("portfolio_risk", {})
        confidence_calibration = mcn_adjustments.get("confidence_calibration", {})
        lineage_memory = mcn_adjustments.get("lineage_memory", {})
        regime_context = mcn_adjustments.get("regime_context", {})
        
        # Build explanation
        explanation = {
            "regime": self._explain_regime(regime_result),
            "volume": self._explain_volume(volume_confirmation),
            "trend_alignment": self._explain_trend_alignment(mtn_trend),
            "risk_checks": self._explain_risk_checks(portfolio_risk),
            "mcn_context": self._explain_mcn_context(regime_context, mcn_adjustments),
            "confidence_breakdown": self._explain_confidence(confidence_calibration, signal.confidence),
            "lineage_info": self._explain_lineage(lineage_memory),
            "strategy_info": self._explain_strategy(strategy),
        }
        
        return explanation
    
    def _explain_regime(self, regime_result: Dict[str, Any]) -> Dict[str, Any]:
        """Explain market regime."""
        regime_label = regime_result.get("regime", "unknown")
        confidence = regime_result.get("confidence", 0.0)
        
        regime_descriptions = {
            "bull_trend": "Strong upward momentum with consistent buying pressure",
            "bear_trend": "Strong downward momentum with consistent selling pressure",
            "ranging": "Sideways movement with no clear directional bias",
            "high_vol": "Elevated volatility indicating uncertainty or major events",
            "low_vol": "Low volatility indicating stability or consolidation",
            "mixed": "Conflicting signals across different indicators",
            "unknown": "Unable to determine market regime"
        }
        
        why_it_matters = {
            "bull_trend": "Trend-following strategies perform best in trending markets",
            "bear_trend": "Short strategies or defensive positions may be preferred",
            "ranging": "Mean-reversion strategies typically outperform in range-bound markets",
            "high_vol": "Requires wider stops and position sizing adjustments",
            "low_vol": "Tighter stops possible, but may indicate upcoming breakout",
            "mixed": "Caution advised - market signals are conflicting",
            "unknown": "Limited historical context available"
        }
        
        return {
            "label": regime_label,
            "confidence": confidence,
            "explanation": regime_descriptions.get(regime_label, "Unknown market regime"),
            "why_it_matters": why_it_matters.get(regime_label, "Market regime context unavailable")
        }
    
    def _explain_volume(self, volume_confirmation: Dict[str, Any]) -> Dict[str, Any]:
        """Explain volume confirmation."""
        volume_trend = volume_confirmation.get("volume_trend", "normal")
        volume_strength = volume_confirmation.get("volume_strength", 0.0)
        recommendation = volume_confirmation.get("recommendation", "caution")
        
        explanations = {
            "increasing": "Volume is rising, indicating strong interest and potential continuation",
            "decreasing": "Volume is declining, suggesting weakening momentum",
            "normal": "Volume is at typical levels, no strong signal",
            "low": "Volume is extremely low, indicating lack of market interest or liquidity risk"
        }
        
        return {
            "trend": volume_trend,
            "strength": volume_strength,
            "recommendation": recommendation,
            "explanation": explanations.get(volume_trend, "Volume analysis unavailable")
        }
    
    def _explain_trend_alignment(self, mtn_trend: Dict[str, Any]) -> Dict[str, Any]:
        """Explain multi-timeframe trend alignment."""
        trend_short = mtn_trend.get("trend_short", "flat")
        trend_medium = mtn_trend.get("trend_medium", "flat")
        trend_long = mtn_trend.get("trend_long", "flat")
        alignment_score = mtn_trend.get("alignment_score", 0.0)
        
        if alignment_score > 0.8:
            explanation = "Strong alignment across all timeframes - high confidence in direction"
        elif alignment_score > 0.5:
            explanation = "Moderate alignment - some timeframes agree, others neutral"
        else:
            explanation = "Weak alignment - conflicting signals across timeframes, caution advised"
        
        return {
            "short": trend_short,
            "medium": trend_medium,
            "long": trend_long,
            "alignment_score": alignment_score,
            "explanation": explanation
        }
    
    def _explain_risk_checks(self, portfolio_risk: Dict[str, Any]) -> Dict[str, Any]:
        """Explain risk checks."""
        risk_factors = portfolio_risk.get("risk_factors", {})
        allowed = portfolio_risk.get("allowed", True)
        reason = portfolio_risk.get("reason", "All checks passed")
        
        return {
            "portfolio_risk": portfolio_risk,
            "symbol_exposure": risk_factors.get("symbol_exposure", 0.0),
            "sector_exposure": risk_factors.get("sector_exposure", 0.0),
            "correlation_risk": risk_factors.get("correlation_risk", 0.0),
            "leverage_risk": risk_factors.get("leverage_risk", 0.0),
            "all_passed": allowed,
            "explanation": reason
        }
    
    def _explain_mcn_context(
        self,
        regime_context: Dict[str, Any],
        mcn_adjustments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Explain MCN context."""
        strategy_perf = regime_context.get("strategy_perf_in_regime", {})
        similar_patterns = len(mcn_adjustments.get("historical_patterns", []))
        
        return {
            "similar_patterns": similar_patterns,
            "historical_performance": strategy_perf,
            "regime_fit": strategy_perf.get("win_rate", 0.0),
            "explanation": (
                f"Found {similar_patterns} similar historical patterns. "
                f"Strategy win rate in this regime: {strategy_perf.get('win_rate', 0.0):.1%}"
            )
        }
    
    def _explain_confidence(
        self,
        confidence_calibration: Dict[str, Any],
        final_confidence: float
    ) -> Dict[str, Any]:
        """Explain confidence breakdown."""
        contributions = confidence_calibration.get("contributions", {})
        raw_confidence = confidence_calibration.get("raw_confidence", final_confidence)
        calibrated = confidence_calibration.get("calibrated_confidence", final_confidence)
        
        # Build factor explanations
        factor_explanations = {}
        for factor_name, factor_data in contributions.items():
            value = factor_data.get("value", 0.0)
            weight = factor_data.get("weight", 0.0)
            contribution = factor_data.get("contribution", 0.0)
            
            factor_explanations[factor_name] = {
                "value": value,
                "weight": weight,
                "contribution": contribution,
                "impact": "positive" if contribution > 0.05 else ("negative" if contribution < -0.05 else "neutral")
            }
        
        return {
            "raw_confidence": raw_confidence,
            "calibrated_confidence": calibrated,
            "factors": factor_explanations,
            "explanation": (
                f"Base confidence: {raw_confidence:.1%}, "
                f"Calibrated confidence: {calibrated:.1%} "
                f"after adjusting for regime, trends, volume, and risk factors"
            )
        }
    
    def _explain_lineage(self, lineage_memory: Dict[str, Any]) -> Dict[str, Any]:
        """Explain strategy lineage."""
        ancestor_count = lineage_memory.get("ancestor_count", 0)
        ancestor_stability = lineage_memory.get("ancestor_stability", 0.5)
        has_overfit = lineage_memory.get("has_overfit_ancestors", False)
        
        if has_overfit:
            explanation = "Some ancestor strategies showed signs of overfitting - confidence reduced"
        elif ancestor_stability > 0.8:
            explanation = "Strong lineage with stable ancestors - high confidence"
        elif ancestor_stability > 0.5:
            explanation = "Moderate lineage stability - acceptable confidence"
        else:
            explanation = "Weak lineage stability - lower confidence"
        
        return {
            "ancestor_count": ancestor_count,
            "ancestor_stability": ancestor_stability,
            "has_overfit_ancestors": has_overfit,
            "explanation": explanation
        }
    
    def _explain_strategy(self, strategy: UserStrategy) -> Dict[str, Any]:
        """Explain strategy information."""
        backtest_results = strategy.last_backtest_results or {}
        
        return {
            "name": strategy.name,
            "score": strategy.score or 0.0,
            "status": strategy.status,
            "win_rate": backtest_results.get("win_rate", 0.0),
            "total_trades": backtest_results.get("total_trades", 0),
            "explanation": (
                f"Strategy '{strategy.name}' (score: {strategy.score or 0.0:.2f}, "
                f"status: {strategy.status}, win rate: {backtest_results.get('win_rate', 0.0):.1%})"
            )
        }
    
    def explain_strategy_recommendation(
        self,
        strategy_name: str,
        winrate: float,
        sharpe: float,
        sample_size: int,
        avg_rr: float
    ) -> str:
        """
        PHASE 2: Generate Brain explanation for strategy recommendation.
        
        Returns a human-readable explanation of why this strategy is recommended.
        """
        parts = []
        
        # Performance summary
        if winrate >= 0.7:
            parts.append(f"{strategy_name} has excellent historical performance with {winrate:.1%} win rate")
        elif winrate >= 0.6:
            parts.append(f"{strategy_name} shows strong performance with {winrate:.1%} win rate")
        else:
            parts.append(f"{strategy_name} has {winrate:.1%} win rate")
        
        # Risk-reward
        if avg_rr >= 2.5:
            parts.append(f"excellent {avg_rr:.1f}x risk-reward ratio")
        elif avg_rr >= 2.0:
            parts.append(f"strong {avg_rr:.1f}x risk-reward ratio")
        else:
            parts.append(f"{avg_rr:.1f}x risk-reward ratio")
        
        # Sharpe ratio
        if sharpe >= 2.0:
            parts.append(f"and exceptional risk-adjusted returns (Sharpe: {sharpe:.2f})")
        elif sharpe >= 1.5:
            parts.append(f"and good risk-adjusted returns (Sharpe: {sharpe:.2f})")
        
        # Sample size
        if sample_size >= 100:
            parts.append(f"based on {sample_size} trades")
        elif sample_size >= 50:
            parts.append(f"based on {sample_size} trades (moderate sample size)")
        else:
            parts.append(f"based on {sample_size} trades (limited sample)")
        
        return ". ".join(parts) + "."

