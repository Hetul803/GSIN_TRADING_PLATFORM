# backend/brain/recommended_strategies.py
"""
Brain Recommended Strategies Service
Generates personalized strategy recommendations based on MCN, regime, and user profile.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import json
from pathlib import Path

from ..db import crud
from ..db.models import UserStrategy, Trade, TradeStatus
from .mcn_adapter import get_mcn_adapter
from .regime_detector import RegimeDetector
from .user_risk_profile import UserRiskProfile
from ..market_data.market_data_provider import get_provider
from ..strategy_engine.backtest_engine import BacktestEngine


class RecommendedStrategiesService:
    """Service for generating strategy recommendations."""
    
    def __init__(self):
        self.mcn_adapter = get_mcn_adapter()
        self.regime_detector = RegimeDetector()
        self.user_risk_profile = UserRiskProfile()
        self.market_provider = get_provider()
        self.backtest_engine = BacktestEngine()
    
    def get_recommended_strategies(
        self,
        user_id: str,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        limit: int = 10,
        db: Session = None
    ) -> List[Dict[str, Any]]:
        """
        Get recommended strategies for a user.
        
        Combines:
        - Seeded proven strategies (40+)
        - User's own strategies
        - MCN regime compatibility
        - User risk profile
        - Recent backtest performance
        
        Returns:
            List of recommended strategies with:
            - strategy_id
            - name
            - description
            - recent_backtest_metrics (winrate, avg_rr, sample_size)
            - regime_compatibility_score
            - confidence (0-1)
            - estimated_profit_range (with disclaimer)
            - why_recommended (explanation)
        """
        recommendations = []
        
        # 1. Load seeded strategies
        seeded_strategies = self._load_seeded_strategies()
        
        # 2. Get user's own strategies
        user_strategies = crud.get_user_strategies(db, user_id) if db else []
        
        # 3. Get current market regime
        current_regime = None
        if symbol:
            try:
                from ..market_data.market_data_provider import call_with_fallback
                price_data = call_with_fallback("get_price", symbol)
                market_data = {
                    "price": price_data.price if price_data and hasattr(price_data, 'price') else 0.0,
                    "volatility": 0.0,
                    "sentiment": 0.0,
                } if price_data else None
                regime_result = self.regime_detector.get_market_regime(symbol, market_data)
                current_regime = regime_result.get("regime", "unknown")
            except Exception as e:
                print(f"Error detecting regime: {e}")
        
        # 4. Get user risk profile
        user_profile = self.user_risk_profile.get_user_risk_profile(user_id, db) if db else {}
        
        # 5. Process seeded strategies
        for seed_strategy in seeded_strategies[:20]:  # Top 20 seeded
            rec = self._evaluate_strategy_for_recommendation(
                strategy_data=seed_strategy,
                strategy_id=None,  # Seeded strategies don't have DB IDs
                user_id=user_id,
                current_regime=current_regime,
                user_profile=user_profile,
                symbol=symbol,
                timeframe=timeframe,
                db=db,
                is_seeded=True
            )
            if rec:
                recommendations.append(rec)
        
        # IMPROVEMENT 3: Process user's own strategies - ONLY proposable with successful backtests
        for user_strategy in user_strategies:
            # IMPROVEMENT 3: Only include strategies that are proposable AND have successful backtest results
            if user_strategy.status == "proposable" and user_strategy.is_proposable:
                # IMPROVEMENT 3: Check that strategy has valid backtest results
                has_valid_backtest = False
                if user_strategy.last_backtest_results:
                    results = user_strategy.last_backtest_results
                    total_trades = results.get("total_trades", 0)
                    win_rate = results.get("win_rate", 0.0)
                    # Only include if has trades and reasonable winrate
                    if total_trades >= 10 and win_rate > 0.4:
                        has_valid_backtest = True
                
                # IMPROVEMENT 3: Also check StrategyBacktest table if last_backtest_results is missing
                if not has_valid_backtest and db:
                    try:
                        from ..db.models import StrategyBacktest
                        latest_backtest = db.query(StrategyBacktest).filter(
                            StrategyBacktest.strategy_id == user_strategy.id
                        ).order_by(StrategyBacktest.created_at.desc()).first()
                        
                        if latest_backtest and latest_backtest.total_trades >= 10 and latest_backtest.win_rate > 0.4:
                            has_valid_backtest = True
                    except Exception:
                        pass
                
                # IMPROVEMENT 3: Only recommend if has valid backtest
                if has_valid_backtest:
                    strategy_data = {
                        "name": user_strategy.name,
                        "description": user_strategy.description or "",
                        "ruleset": user_strategy.ruleset,
                        "parameters": user_strategy.parameters,
                        "score": user_strategy.score,
                    }
                    rec = self._evaluate_strategy_for_recommendation(
                        strategy_data=strategy_data,
                        strategy_id=user_strategy.id,
                        user_id=user_id,
                        current_regime=current_regime,
                        user_profile=user_profile,
                        symbol=symbol,
                        timeframe=timeframe,
                        db=db,
                        is_seeded=False
                    )
                    if rec:
                        recommendations.append(rec)
        
        # 7. Sort by confidence and return top N
        recommendations.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        result = recommendations[:limit]
        
        # IMPROVEMENT 3: Return empty list with message if no recommendations (don't return placeholder)
        # Frontend should handle empty list gracefully
        return result  # Can be empty list - frontend should handle this
    
    def _load_seeded_strategies(self) -> List[Dict[str, Any]]:
        """Load seeded strategies from JSON file."""
        try:
            seed_file = Path(__file__).resolve().parents[2] / "seed_strategies" / "proven_strategies.json"
            if seed_file.exists():
                with open(seed_file) as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading seeded strategies: {e}")
        return []
    
    def _evaluate_strategy_for_recommendation(
        self,
        strategy_data: Dict[str, Any],
        strategy_id: Optional[str],
        user_id: str,
        current_regime: Optional[str],
        user_profile: Dict[str, Any],
        symbol: Optional[str],
        timeframe: Optional[str],
        db: Optional[Session],
        is_seeded: bool
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a strategy and create recommendation if suitable."""
        
        # Get backtest metrics
        backtest_metrics = self._get_backtest_metrics(strategy_id, strategy_data, db)
        
        # Calculate regime compatibility
        regime_compatibility = self._calculate_regime_compatibility(
            strategy_data, current_regime, db
        )
        
        # Get MCN similarity score
        mcn_similarity = self._get_mcn_similarity_score(
            strategy_data, user_id, current_regime, db
        )
        
        # Calculate confidence
        confidence = self._calculate_recommendation_confidence(
            backtest_metrics=backtest_metrics,
            regime_compatibility=regime_compatibility,
            mcn_similarity=mcn_similarity,
            user_profile=user_profile,
        )
        
        # FIX 1: Only recommend if winrate >= 0.9 AND sharpe > 1.0 AND trades >= MIN_TRADES
        sample_size = backtest_metrics.get("sample_size", 0)
        winrate = backtest_metrics.get("winrate", 0.0)
        sharpe = backtest_metrics.get("sharpe_ratio", 0.0) or backtest_metrics.get("sharpe", 0.0)
        
        # FIX 1: Require winrate >= 0.9 AND sharpe > 1.0 AND trades >= 50
        if sample_size < 50:  # Need at least 50 trades (MIN_TRADES_FOR_PROPOSABLE)
            return None
        
        if winrate < 0.9:  # FIX 1: Changed from 0.4 to 0.9
            return None
        
        if sharpe <= 1.0:  # FIX 1: New requirement - sharpe must be > 1.0
            return None
        
        if confidence < 0.6:
            return None
        
        # Estimate profit range (with strong disclaimer)
        estimated_profit_range = self._estimate_profit_range(backtest_metrics)
        
        # Generate explanation
        why_recommended = self._generate_explanation(
            strategy_data=strategy_data,
            backtest_metrics=backtest_metrics,
            regime_compatibility=regime_compatibility,
            current_regime=current_regime,
            mcn_similarity=mcn_similarity,
            strategy_id=strategy_id,
            db=db,
        )
        
        # PHASE 8: Include mutation lineage if available
        mutation_lineage = None
        if strategy_id and db:
            from ..db.models import StrategyLineage
            lineage = db.query(StrategyLineage).filter(
                StrategyLineage.child_strategy_id == strategy_id
            ).first()
            if lineage:
                mutation_lineage = {
                    "parent_strategy_id": lineage.parent_strategy_id,
                    "mutation_type": lineage.mutation_type,
                    "created_at": lineage.created_at.isoformat() if lineage.created_at else None
                }
        
        # PHASE 1: Get explanation_human and risk_note from strategy if available
        explanation_human = None
        risk_note = None
        if strategy_id and db:
            user_strategy = crud.get_user_strategy(db, strategy_id)
            if user_strategy:
                explanation_human = user_strategy.explanation_human
                risk_note = user_strategy.risk_note
                # Generate if missing
                if not explanation_human:
                    from ..strategy_engine.strategy_explanation import generate_human_explanation
                    stats = user_strategy.last_backtest_results or {}
                    explanation_human, risk_note = generate_human_explanation(
                        {"name": user_strategy.name, "ruleset": user_strategy.ruleset, "asset_type": user_strategy.asset_type.value},
                        stats
                    )
        
        return {
            "strategy_id": strategy_id or f"seeded_{strategy_data.get('name', 'unknown')}",
            "name": strategy_data.get("name", "Unknown Strategy"),
            "description": strategy_data.get("description", ""),
            "is_seeded": is_seeded,
            "recent_backtest_metrics": backtest_metrics,
            "regime_compatibility_score": regime_compatibility,
            "confidence": confidence,
            "estimated_profit_range": estimated_profit_range,
            "why_recommended": why_recommended,
            "mutation_lineage": mutation_lineage,  # PHASE 8: Include lineage
            "explanation_human": explanation_human,  # PHASE 1: Added
            "risk_note": risk_note,  # PHASE 1: Added
        }
    
    def _get_backtest_metrics(
        self,
        strategy_id: Optional[str],
        strategy_data: Dict[str, Any],
        db: Optional[Session]
    ) -> Dict[str, Any]:
        """Get recent backtest metrics for a strategy."""
        if strategy_id and db:
            # Try to get from user strategy
            user_strategy = crud.get_user_strategy(db, strategy_id)
            if user_strategy and user_strategy.last_backtest_results:
                results = user_strategy.last_backtest_results
                total_trades = results.get("total_trades", 0)
                winning_trades = results.get("winning_trades", 0)
                winrate = winning_trades / total_trades if total_trades > 0 else 0.0
                avg_return = results.get("avg_return", 0.0)
                
                return {
                    "winrate": winrate,
                    "avg_rr": results.get("avg_rr", 2.0),
                    "sample_size": total_trades,
                    "avg_return": avg_return,
                }
        
        # Fallback to seeded strategy defaults
        return {
            "winrate": strategy_data.get("historical_winrate", 0.55),
            "avg_rr": strategy_data.get("expected_rr", 2.0),
            "sample_size": 100,  # Estimated
            "avg_return": 0.05,
        }
    
    def _calculate_regime_compatibility(
        self,
        strategy_data: Dict[str, Any],
        current_regime: Optional[str],
        db: Optional[Session]
    ) -> float:
        """Calculate how well strategy fits current regime."""
        if not current_regime or current_regime == "unknown":
            return 0.7  # Neutral
        
        # Check if strategy has regime-specific performance data
        # For now, use simple heuristics
        strategy_market = strategy_data.get("market", "stocks")
        strategy_timeframe = strategy_data.get("timeframe", "1d")
        
        # Simple compatibility scoring
        compatibility = 0.7  # Base
        
        # Adjust based on regime
        if current_regime in ["bull_trend", "bear_trend"]:
            # Trend-following strategies work well
            if "trend" in strategy_data.get("name", "").lower():
                compatibility = 0.85
        elif current_regime == "ranging":
            # Mean reversion strategies work well
            if "reversion" in strategy_data.get("name", "").lower() or "mean" in strategy_data.get("name", "").lower():
                compatibility = 0.85
        
        return compatibility
    
    def _get_mcn_similarity_score(
        self,
        strategy_data: Dict[str, Any],
        user_id: str,
        current_regime: Optional[str],
        db: Optional[Session]
    ) -> float:
        """Get MCN similarity score for strategy."""
        if not self.mcn_adapter.is_available:
            return 0.7  # Neutral if MCN unavailable
        
        try:
            # Get user profile memory
            user_memory = self.mcn_adapter.get_user_profile_memory(user_id)
            
            # Check if user has performed well with similar strategies
            best_strategies = user_memory.get("best_performing_strategies", [])
            if best_strategies:
                # Simple similarity: if user has good performance, boost score
                avg_winrate = sum(s.get("win_rate", 0.5) for s in best_strategies) / len(best_strategies)
                return min(1.0, 0.7 + (avg_winrate - 0.5) * 0.6)
            
            return 0.7
        except Exception as e:
            print(f"Error getting MCN similarity: {e}")
            return 0.7
    
    def _calculate_recommendation_confidence(
        self,
        backtest_metrics: Dict[str, Any],
        regime_compatibility: float,
        mcn_similarity: float,
        user_profile: Dict[str, Any],
    ) -> float:
        """Calculate overall recommendation confidence."""
        winrate = backtest_metrics.get("winrate", 0.5)
        sample_size = backtest_metrics.get("sample_size", 0)
        avg_rr = backtest_metrics.get("avg_rr", 1.0)
        
        # Base confidence from winrate and RR
        base_confidence = (winrate * 0.6) + (min(avg_rr / 3.0, 1.0) * 0.4)
        
        # Adjust for sample size (more samples = more reliable)
        sample_adjustment = min(1.0, sample_size / 100.0)
        base_confidence = base_confidence * (0.5 + 0.5 * sample_adjustment)
        
        # Apply regime compatibility
        base_confidence = base_confidence * (0.7 + 0.3 * regime_compatibility)
        
        # Apply MCN similarity
        base_confidence = base_confidence * (0.7 + 0.3 * mcn_similarity)
        
        # Adjust for user risk profile
        user_risk_tendency = user_profile.get("risk_tendency", "moderate")
        if user_risk_tendency == "low":
            # Slightly reduce confidence for risk-averse users
            base_confidence = base_confidence * 0.95
        elif user_risk_tendency == "high":
            # Slightly increase for risk-tolerant users
            base_confidence = min(1.0, base_confidence * 1.05)
        
        return min(1.0, max(0.0, base_confidence))
    
    def _estimate_profit_range(
        self,
        backtest_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Estimate profit range based on backtest metrics (WITH DISCLAIMER)."""
        winrate = backtest_metrics.get("winrate", 0.5)
        avg_rr = backtest_metrics.get("avg_rr", 2.0)
        avg_return = backtest_metrics.get("avg_return", 0.05)
        
        # Conservative estimate: assume 10 trades
        num_trades = 10
        expected_wins = int(num_trades * winrate)
        expected_losses = num_trades - expected_wins
        
        # Estimate profit per win (assuming avg_rr)
        profit_per_win = avg_return * avg_rr / (1 + avg_rr)
        loss_per_loss = avg_return / (1 + avg_rr)
        
        # Expected profit
        expected_profit = (expected_wins * profit_per_win) - (expected_losses * loss_per_loss)
        
        # Range: ±30% of expected
        min_profit = expected_profit * 0.7
        max_profit = expected_profit * 1.3
        
        return {
            "min_pct": min_profit,
            "max_pct": max_profit,
            "expected_pct": expected_profit,
            "disclaimer": "This is based on historical backtests and is NOT guaranteed. Markets can behave differently. Past performance does not guarantee future results.",
        }
    
    def _generate_explanation(
        self,
        strategy_data: Dict[str, Any],
        backtest_metrics: Dict[str, Any],
        regime_compatibility: float,
        current_regime: Optional[str],
        mcn_similarity: float,
        strategy_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> str:
        """Generate human-readable explanation for recommendation."""
        name = strategy_data.get("name", "this strategy")
        winrate = backtest_metrics.get("winrate", 0.5)
        avg_rr = backtest_metrics.get("avg_rr", 2.0)
        
        parts = []
        
        # Performance
        parts.append(f"{name} has shown strong historical performance")
        parts.append(f"with a {winrate:.1%} win rate and {avg_rr:.1f}x risk-reward ratio")
        
        # Cross-asset performance (if strategy is generalized)
        if strategy_id and db:
            user_strategy = crud.get_user_strategy(db, strategy_id)
            if user_strategy and user_strategy.generalized and user_strategy.per_symbol_performance:
                well_performing = list(user_strategy.per_symbol_performance.keys())
                if well_performing:
                    if len(well_performing) >= 3:
                        top_symbols = sorted(
                            well_performing,
                            key=lambda s: user_strategy.per_symbol_performance[s].get("winrate", 0.0),
                            reverse=True
                        )[:3]
                        parts.append(f"This strategy historically performs best on {', '.join(top_symbols)}")
                    else:
                        parts.append(f"This strategy performs well across multiple assets: {', '.join(well_performing)}")
        
        # Regime
        if current_regime and regime_compatibility > 0.75:
            parts.append(f"and is well-suited for the current {current_regime} market regime")
        
        # MCN
        if mcn_similarity > 0.75:
            parts.append("with patterns similar to your successful trades")
        
        return ". ".join(parts) + "."

