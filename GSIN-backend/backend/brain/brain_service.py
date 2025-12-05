# backend/brain/brain_service.py
"""
Brain Service (L3) - High-level service combining:
- Strategy Engine (L2)
- Market Data Engine (L1)
- MCN Adapter (L3)
"""
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..db import crud
from ..market_data.market_data_provider import get_provider
from ..strategy_engine.strategy_service import StrategyService
from ..strategy_engine.backtest_engine import BacktestEngine
from ..strategy_engine.mutation_engine import MutationEngine
from ..strategy_engine.scoring import score_strategy
from ..strategy_engine.constants import DEFAULT_SYMBOLS, MIN_ASSETS_FOR_GENERALIZATION, GENERALIZATION_WINRATE_THRESHOLD
from .mcn_adapter import get_mcn_adapter
from .types import BrainSignalResponse, BrainBacktestResponse, BrainMutationResponse, BrainContextResponse, MarketRegime
from .regime_detector import RegimeDetector
from .confidence_calibrator import ConfidenceCalibrator
from .portfolio_risk import PortfolioRiskManager
from .user_risk_profile import UserRiskProfile
from ..market_data.multi_timeframe import MultiTimeframeAnalyzer
from ..market_data.volume_analyzer import VolumeAnalyzer


class BrainService:
    """
    Brain Service - Orchestrates L1, L2, and L3 components.
    """
    
    def __init__(self):
        self.mcn_adapter = get_mcn_adapter()
        self.strategy_service = StrategyService()
        self.backtest_engine = BacktestEngine()
        self.mutation_engine = MutationEngine()
        self.market_provider = get_provider()
        self.regime_detector = RegimeDetector()
        self.confidence_calibrator = ConfidenceCalibrator()
        self.portfolio_risk_manager = PortfolioRiskManager()
        self.user_risk_profile = UserRiskProfile()  # PHASE 4
        self.explanation_engine = ExplanationEngine()  # PHASE 4
        self.multi_timeframe_analyzer = MultiTimeframeAnalyzer()
        self.volume_analyzer = VolumeAnalyzer()
    
    async def generate_signal(
        self,
        strategy_id: str,
        user_id: str,
        symbol: str,
        db: Session
    ) -> BrainSignalResponse:
        """
        Generate an MCN-enhanced trading signal with comprehensive confidence calculation.
        
        This method combines multiple factors to produce a high-quality trading signal:
        
        **Input Factors:**
        - Regime: Current market regime (bull_trend, bear_trend, ranging, high_vol, low_vol)
        - Volatility: Market volatility (affects position sizing and confidence decay)
        - Volume: Volume confirmation (blocks trades in extremely low volume conditions)
        - Multi-timeframe trend: Alignment across multiple timeframes (1h, 4h, 1d)
        - User risk profile: User's historical risk tendency and preferences
        - MCN similarity: Pattern matching score from MemoryClusterNetworks
        - Strategy backtest stats: Historical winrate, expected RR, sample size
        
        **Confidence Calculation:**
        The confidence score (0-1) is computed using a calibrated model that:
        1. Starts with base signal confidence (60%) + MCN confidence (40%)
        2. Applies regime fit multiplier (how well strategy performs in current regime)
        3. Applies multi-timeframe alignment score
        4. Applies volume strength factor
        5. Applies user risk profile adjustment
        6. Applies ancestor stability penalty (if strategy has overfit ancestors)
        7. Applies portfolio risk adjustment
        8. Decays confidence in high-volatility, low-liquidity, or anomaly conditions
        
        **MCN Contribution:**
        MCN (MemoryClusterNetworks) contributes by:
        - Finding similar historical patterns in market conditions
        - Weighting recommendations by pattern value (successful patterns weighted higher)
        - Providing regime context and strategy performance in similar regimes
        - Learning from user's historical trading behavior
        
        **User Traits Influence:**
        - Risk-averse users: Lower position sizes, higher confidence thresholds
        - Risk-tolerant users: Higher position sizes, more aggressive signals
        - User's historical acceptance rate affects signal generation
        
        **Output:**
        Returns a BrainSignalResponse with:
        - side: "BUY" or "SELL"
        - entry, stop_loss, take_profit: Price levels
        - confidence: Calibrated confidence (0-1)
        - position_size: Recommended position size based on risk
        - explanation: Human-readable reasoning
        - market_regime: Detected regime
        - risk_level: "low", "moderate", "high", "very_high"
        
        **Raises:**
        - ValueError: If strategy not proposable, confidence too low, or risk constraints violated
        """
        # Load strategy
        strategy = crud.get_user_strategy(db, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
        
        if strategy.user_id != user_id:
            raise ValueError("Strategy does not belong to user")
        
        # STRICT GATING: Only proposable strategies can generate signals
        # Check status first (more reliable than is_proposable flag)
        from ..strategy_engine.status_manager import StrategyStatus
        
        if strategy.status != StrategyStatus.PROPOSABLE:
            status_reason = {
                StrategyStatus.EXPERIMENT: "Strategy is still in experimentation phase. Brain is testing and evolving it.",
                StrategyStatus.CANDIDATE: "Strategy is a candidate but hasn't met all proposable thresholds yet.",
                StrategyStatus.DISCARDED: "Strategy has been discarded due to poor performance or overfitting.",
            }.get(strategy.status, "Strategy status is invalid.")
            
            raise ValueError(
                f"Strategy not yet reliable (status: {strategy.status}). "
                f"{status_reason} "
                f"Please wait for the evolution worker to improve this strategy."
            )
        
        # Double-check is_proposable flag
        if not strategy.is_proposable:
            raise ValueError(
                "Strategy not yet reliable (is_proposable=False). "
                "Brain is still evolving it. Please wait for the evolution worker to improve this strategy."
            )
        
        # Check unified score threshold
        if strategy.score is None or strategy.score < 0.70:
            raise ValueError(
                f"Strategy score too low (score: {strategy.score}). "
                f"Minimum score for proposable strategies is 0.70. "
                f"Brain is still evolving this strategy."
            )
        
        # Check minimum sample size
        if strategy.last_backtest_results:
            total_trades = strategy.last_backtest_results.get("total_trades", 0)
            if total_trades < 50:
                raise ValueError(
                    f"Strategy has insufficient sample size (trades: {total_trades}, required: 50). "
                    f"Brain needs more backtest data to ensure reliability."
                )
        
        # Get market data through request queue
        from ..market_data.market_data_provider import call_with_fallback
        
        price_data = call_with_fallback("get_price", symbol)
        if not price_data:
            raise ValueError(f"Could not fetch price for {symbol}")
        
        # Get volatility and sentiment through queue
        volatility_data = call_with_fallback("get_volatility", symbol)
        sentiment_data = call_with_fallback("get_sentiment", symbol)
        
        # TWELVE DATA INTEGRATION: Get market context (news, sentiment, fundamentals)
        market_context = None
        try:
            from ..market_data.services.twelvedata_context import get_twelvedata_context_service
            context_service = get_twelvedata_context_service()
            market_context = context_service.get_market_context(symbol, include_news=True, include_sentiment=True, include_fundamentals=True)
        except Exception as e:
            # Market context is optional - don't break if unavailable
            print(f"⚠️  Could not fetch Twelve Data market context: {e}")
        
        market_data = {
            "price": price_data.price,
            "volatility": volatility_data.volatility if volatility_data else 0.0,
            "sentiment": sentiment_data.sentiment_score if sentiment_data else 0.0,
            "timestamp": price_data.timestamp,
            "market_context": market_context,  # TWELVE DATA INTEGRATION: Include news/sentiment/fundamentals
        }
        
        base_signal = self.strategy_service.generate_signal(
            strategy_id=strategy_id,
            strategy_ruleset=strategy.ruleset,
            strategy_score=strategy.score,
            symbol=symbol,
        )
        
        # Prepare strategy dict for MCN
        strategy_dict = {
            "id": strategy_id,
            "name": strategy.name,
            "ruleset": strategy.ruleset,
            "score": strategy.score,
            "status": strategy.status,
        }
        
        # ========== PHASE 3: Enhanced Intelligence ==========
        # Get MCN market regime using clustering (PHASE 3)
        market_regime_result = await self.regime_detector.get_market_regime(symbol, market_data)
        regime_label = market_regime_result.get("regime", "unknown")
        regime_confidence = market_regime_result.get("confidence", 0.0)
        
        # Get multi-timeframe trend confirmation (PHASE 3)
        mtn_trend = await self.multi_timeframe_analyzer.get_multi_timeframe_trend(symbol)
        mtn_alignment_score = mtn_trend.get("alignment_score", 0.5)
        
        # Get volume confirmation (PHASE 3)
        volume_confirmation = await self.volume_analyzer.get_volume_confirmation(symbol, strategy.ruleset.get("timeframe", "1d"))
        volume_strength = volume_confirmation.get("volume_strength", 0.5)
        volume_recommendation = volume_confirmation.get("recommendation", "caution")
        
        # Get MCN context (L3) - Regime, User Profile, Lineage
        regime_context = self.mcn_adapter.get_regime_context(symbol, strategy_id, market_data)
        
        # PHASE 4: Get user risk profile from MCN-based analysis
        user_risk_profile_data = self.user_risk_profile.get_user_risk_profile(user_id, db)
        user_profile = {
            "risk_tendency": user_risk_profile_data.get("risk_tendency", "moderate"),
            "confidence": user_risk_profile_data.get("confidence", 0.5),
            "factors": user_risk_profile_data.get("factors", {}),
            # Also get MCN memory for additional context
            "mcn_memory": self.mcn_adapter.get_user_profile_memory(user_id)
        }
        lineage_memory = self.mcn_adapter.get_strategy_lineage_memory(strategy_id, db)
        
        # Check for overfit ancestors - if ancestors were unstable, reduce confidence
        if lineage_memory.get("has_overfit_ancestors", False):
            # Reduce confidence if ancestors were overfit
            ancestor_penalty = 1.0 - (1.0 - lineage_memory.get("ancestor_stability", 0.5)) * 0.3
        else:
            ancestor_penalty = 1.0
        
        # Get MCN recommendation (L3) - uses true MCN learning
        mcn_recommendation = self.mcn_adapter.recommend_trade(
            strategy=strategy_dict,
            market_data=market_data,
            user_id=user_id,
            db=db,
        )
        
        # Check regime fit - if strategy performs poorly in current regime, reduce confidence
        regime_perf = regime_context.get("strategy_perf_in_regime", {})
        regime_win_rate = regime_perf.get("win_rate", 0.5)
        regime_fit_multiplier = min(1.0, regime_win_rate / 0.75) if regime_win_rate > 0 else 0.5
        
        # Enhance regime fit with detected regime (PHASE 3)
        # If detected regime matches strategy's best-performing regime, boost confidence
        if regime_label in ["bull_trend", "bear_trend"]:
            # Check if strategy performs well in trending markets
            if regime_win_rate > 0.7:
                regime_fit_multiplier = min(1.0, regime_fit_multiplier * 1.1)
        elif regime_label == "ranging":
            # Check if strategy performs well in ranging markets
            if regime_win_rate > 0.6:
                regime_fit_multiplier = min(1.0, regime_fit_multiplier * 1.05)
        
        # Combine base signal with MCN recommendation
        # Weight: 60% base signal, 40% MCN recommendation
        final_side = mcn_recommendation.get("side", base_signal["side"])
        final_entry = base_signal["entry"]
        final_stop_loss = mcn_recommendation.get("stop_loss") or base_signal.get("stop_loss")
        final_take_profit = mcn_recommendation.get("take_profit") or base_signal.get("take_profit")
        
        # Calculate base confidence
        base_confidence = base_signal.get("confidence", 0.5)
        mcn_confidence = mcn_recommendation.get("confidence", 0.5)
        raw_confidence = (base_confidence * 0.6) + (mcn_confidence * 0.4)
        
        # ========== PHASE 3: Volume Confirmation ==========
        # Check volume recommendation (PHASE 3)
        if volume_recommendation == "block":
            raise ValueError(
                f"Trade blocked due to extremely low volume. "
                f"Volume ratio: {volume_confirmation.get('volume_ratio', 0.0):.2f}"
            )
        
        # ========== PHASE 3: Portfolio Risk Management ==========
        # Evaluate portfolio risk (PHASE 3)
        proposed_trade = {
            "symbol": symbol,
            "side": final_side,
            "position_size": 0.0,  # Will be calculated later
            "entry_price": final_entry,
        }
        portfolio_risk = await self.portfolio_risk_manager.evaluate_portfolio_risk(
            user_id, proposed_trade, db
        )
        
        if not portfolio_risk.get("allowed", True):
            raise ValueError(
                f"Trade blocked due to portfolio risk: {portfolio_risk.get('reason', 'Unknown risk')}"
            )
        
        # ========== PHASE 3/6: Formal Confidence Calibration with Phase 6 Enhancements ==========
        # Prepare factors for confidence calibration
        factors_dict = {
            "regime_match": regime_fit_multiplier,  # How well strategy matches current regime
            "mtn_alignment_score": mtn_alignment_score,  # Multi-timeframe alignment
            "volume_strength": volume_strength,  # Volume confirmation
            "mcn_similarity": mcn_confidence,  # MCN pattern similarity
            "user_risk_tendency": user_profile.get("risk_tendency", "moderate"),
            "strategy_stability": lineage_memory.get("ancestor_stability", 0.5),
        }
        
        # PHASE 6: Prepare market conditions for dynamic weighting and confidence decay
        market_conditions = {
            "regime": regime_label.lower(),
            "volatility": market_data.get("volatility", 0.5),
            "volume_trend": volume_confirmation.get("volume_trend", "normal"),
            "spread": market_data.get("spread", 0.0),
            "volume_ratio": volume_confirmation.get("volume_ratio", 1.0),
        }
        
        # PHASE 6: Get historical stats for anomaly detection
        historical_stats = {
            "avg_volatility": market_data.get("volatility", 0.5),  # Would be calculated from history
            "avg_volume": market_data.get("volume", 0),
            "avg_price": final_entry,
        }
        
        # Calibrate confidence using enhanced model (PHASE 6)
        calibration_result = self.confidence_calibrator.calibrate_confidence(
            raw_confidence, factors_dict, market_conditions, historical_stats
        )
        
        # Extract confidence (handle both old float return and new dict return)
        if isinstance(calibration_result, dict):
            calibrated_confidence = calibration_result.get("confidence", raw_confidence)
            anomaly_detected = calibration_result.get("anomaly_detected", False)
            anomaly_info = calibration_result.get("anomaly_info")
        else:
            calibrated_confidence = calibration_result
            anomaly_detected = False
            anomaly_info = None
        
        # PHASE 6: Block signal if anomaly detected with high severity
        if anomaly_detected and anomaly_info:
            if anomaly_info.get("recommendation") == "avoid":
                raise ValueError(
                    f"Signal blocked due to market anomaly: {anomaly_info.get('anomalies', [{}])[0].get('message', 'Unknown anomaly')}"
                )
        
        # Apply portfolio risk adjustment
        portfolio_adjustment = portfolio_risk.get("adjustment", 1.0)
        final_confidence = calibrated_confidence * portfolio_adjustment
        
        # Apply ancestor stability adjustment
        final_confidence = final_confidence * ancestor_penalty
        
        # Clamp confidence
        final_confidence = max(0.0, min(1.0, final_confidence))
        
        # If confidence is too low after all adjustments, reject the signal
        if final_confidence < 0.5:
            raise ValueError(
                f"Signal confidence too low after calibration (confidence: {final_confidence:.2f}). "
                f"Regime: {regime_label}, MTN alignment: {mtn_alignment_score:.2f}, "
                f"Volume strength: {volume_strength:.2f}, Portfolio adjustment: {portfolio_adjustment:.2f}. "
                f"This strategy may not be suitable for current market conditions."
            )
        
        # Apply user risk constraints (L4 enhancement)
        position_size = self._calculate_position_size(
            user_id=user_id,
            entry_price=final_entry,
            stop_loss=final_stop_loss,
            confidence=final_confidence,
            db=db,
        )
        
        # ========== PHASE 3: Re-evaluate Portfolio Risk with Actual Position Size ==========
        # Re-evaluate portfolio risk with actual position size
        proposed_trade["position_size"] = position_size
        portfolio_risk = await self.portfolio_risk_manager.evaluate_portfolio_risk(
            user_id, proposed_trade, db
        )
        
        # Adjust position size if portfolio risk requires it
        if not portfolio_risk.get("allowed", True):
            # Reduce position size to meet risk constraints
            risk_adjustment = portfolio_risk.get("adjustment", 0.5)
            position_size = position_size * risk_adjustment
        
        # Adjust signal based on risk constraints
        if position_size <= 0:
            raise ValueError("Position size is zero after applying risk constraints")
        
        # Record event in MCN
        self.mcn_adapter.record_event(
            event_type="signal_generated",
            payload={
                "strategy_id": strategy_id,
                "symbol": symbol,
                "side": final_side,
                "entry": final_entry,
                "confidence": final_confidence,
                "position_size": position_size,
                "market_regime": regime_label,  # Use detected regime from PHASE 3
                "timestamp": datetime.now().isoformat(),
            },
            user_id=user_id,
            strategy_id=strategy_id,
        )
        
        # Determine sentiment label
        sentiment_score = market_data.get("sentiment", 0.0)
        if sentiment_score > 0.3:
            sentiment_label = "bullish"
        elif sentiment_score < -0.3:
            sentiment_label = "bearish"
        else:
            sentiment_label = "neutral"
        
        # Determine mode recommendation (default to PAPER for safety)
        mode_recommendation = "PAPER"  # Can be enhanced with user risk settings
        
        # Calculate MCN explanation from recommendation
        mcn_explanation = mcn_recommendation.get("explanation", "") or (
            f"MCN recommendation based on {len(mcn_recommendation.get('historical_patterns', []))} historical patterns. "
            f"Regime: {regime_context.get('regime_label', 'unknown')}, "
            f"Strategy performance in regime: {regime_context.get('strategy_perf_in_regime', {}).get('win_rate', 0.0):.2%}"
        )
        
        # Calculate risk level using the helper method
        risk_level = self._determine_risk_level(
            volatility=market_data.get("volatility", 0.0),
            position_size=position_size,
            entry_price=final_entry,
            user_profile=user_profile
        )
        
        # Calculate target_alignment for daily profit goal
        target_alignment = self._calculate_target_alignment(
            user_id=user_id,
            daily_profit_target=None,  # Will load from user settings
            position_size=position_size,
            entry_price=final_entry,
            stop_loss=final_stop_loss,
            take_profit=final_take_profit,
            confidence=final_confidence,
            db=db,
        )
        
        return BrainSignalResponse(
            strategy_id=strategy_id,
            symbol=symbol,
            side=final_side,
            entry=final_entry,
            exit=base_signal.get("exit"),
            stop_loss=final_stop_loss,
            take_profit=final_take_profit,
            confidence=final_confidence,
            position_size=position_size,
            volatility=market_data.get("volatility"),
            sentiment=sentiment_label,
            reasoning=base_signal.get("reasoning") or mcn_recommendation.get("explanation"),
            explanation=mcn_explanation,  # Rich MCN-based explanation
            market_regime=regime_label,  # Use detected regime from PHASE 3
            volatility_context=market_data["volatility"],
            sentiment_context=market_data["sentiment"],
            mode_recommendation=mode_recommendation,
            risk_level=risk_level,
            mcn_adjustments={
                **mcn_recommendation,
                "regime_context": regime_context,
                "user_profile": user_profile,
                "lineage_memory": lineage_memory,
                "market_regime_detected": market_regime_result,  # PHASE 3
                "multi_timeframe_trend": mtn_trend,  # PHASE 3
                "volume_confirmation": volume_confirmation,  # PHASE 3
                "portfolio_risk": portfolio_risk,  # PHASE 3
                "confidence_calibration": self.confidence_calibrator.get_factor_breakdown(
                    raw_confidence, factors_dict
                ),  # PHASE 3
            },
            target_alignment=target_alignment,
            timestamp=datetime.now(),
        )
    
    def _determine_risk_level(
        self,
        volatility: float,
        position_size: float,
        entry_price: float,
        user_profile: Dict[str, Any]
    ) -> str:
        """
        Determine risk level for a signal.
        
        Returns:
            "low", "moderate", "high", or "very_high"
        """
        notional = position_size * entry_price
        
        # High volatility = higher risk
        if volatility > 0.3:
            base_risk = "high"
        elif volatility > 0.15:
            base_risk = "moderate"
        else:
            base_risk = "low"
        
        # Large position size = higher risk
        if notional > 10000:
            if base_risk == "low":
                base_risk = "moderate"
            elif base_risk == "moderate":
                base_risk = "high"
            else:
                base_risk = "very_high"
        
        # Adjust based on user's historical risk tendency
        user_risk_tendency = user_profile.get("risk_tendency", "moderate")
        if user_risk_tendency == "low" and base_risk in ["high", "very_high"]:
            return "high"  # Cap at high for risk-averse users
        elif user_risk_tendency == "high" and base_risk == "low":
            return "moderate"  # Boost for risk-tolerant users
        
        return base_risk
    
    def _is_universal_strategy(self, ruleset: Dict[str, Any]) -> bool:
        """
        Detect if a strategy is "universal" (e.g., SMA cross, RSI logic).
        
        Universal strategies are those that don't depend on specific asset characteristics
        and can be tested across multiple assets.
        
        Returns:
            True if strategy appears to be universal
        """
        # Check if ruleset uses common technical indicators that work across assets
        ruleset_str = str(ruleset).lower()
        
        # Universal indicators
        universal_indicators = [
            "sma", "ema", "rsi", "macd", "bollinger", "stochastic",
            "moving average", "momentum", "trend", "crossover"
        ]
        
        # Check if ruleset contains universal indicators
        has_universal = any(indicator in ruleset_str for indicator in universal_indicators)
        
        # Check if ruleset doesn't have asset-specific logic
        asset_specific = [
            "sector", "industry", "market cap", "volume profile",
            "company", "earnings", "fundamental"
        ]
        has_specific = any(term in ruleset_str for term in asset_specific)
        
        # Strategy is universal if it has universal indicators and no asset-specific logic
        return has_universal and not has_specific
    
    def backtest_with_memory(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        db: Session
    ) -> BrainBacktestResponse:
        """
        Run backtest enhanced with MCN memory.
        
        If strategy is universal, tests across DEFAULT_SYMBOLS and marks as generalized
        if it performs well on >2 assets.
        
        Combines:
        - Basic backtest (L2)
        - Multi-asset testing (if universal)
        - MCN memory-based adjustments (L3)
        """
        # Load strategy
        strategy = crud.get_user_strategy(db, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
        
        # Check if strategy is universal
        is_universal = self._is_universal_strategy(strategy.ruleset)
        
        # Run basic backtest on requested symbol (L2)
        backtest_results = self.backtest_engine.run_backtest(
            symbol=symbol,
            ruleset=strategy.ruleset,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )
        
        # If universal, test across multiple assets
        cross_asset_results = None
        if is_universal:
            try:
                cross_asset_results = self.backtest_engine.execute_backtest_across_assets(
                    strategy_ruleset=strategy.ruleset,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    symbols=DEFAULT_SYMBOLS
                )
                
                # Mark strategy as generalized if it performs well on >2 assets
                if cross_asset_results.get("generalized", False):
                    well_performing = cross_asset_results.get("well_performing_assets", [])
                    per_symbol_perf = cross_asset_results.get("per_symbol_results", {})
                    
                    # Update strategy with generalized flag and per-symbol performance
                    crud.update_user_strategy(
                        db=db,
                        strategy_id=strategy_id,
                        generalized=True,
                        per_symbol_performance={
                            symbol: {
                                "winrate": result.get("winrate", 0.0),
                                "total_return": result.get("total_return", 0.0),
                                "total_trades": result.get("total_trades", 0),
                            }
                            for symbol, result in per_symbol_perf.items()
                            if symbol in well_performing
                        }
                    )
                    
                    print(f"✅ Strategy {strategy_id} marked as generalized. Performs well on: {well_performing}")
            except Exception as e:
                print(f"⚠️  Cross-asset backtest failed for strategy {strategy_id}: {e}")
                # Continue with single-asset backtest
        
        # Get MCN memory for strategy
        memory = self.mcn_adapter.get_memory_for_strategy(strategy_id)
        
        # Calculate base score
        base_score = score_strategy(backtest_results)
        
        # Enhance with MCN memory
        # Regime fit score: how well strategy fits current market regime
        regime_fit_score = self._calculate_regime_fit(backtest_results, memory)
        
        # Memory-adjusted score: adjust based on historical patterns
        memory_adjusted_score = self._adjust_score_with_memory(base_score, memory)
        
        # Historical pattern match: similarity to successful past patterns
        pattern_match = self._calculate_pattern_match(backtest_results, memory)
        
        # Save backtest record
        backtest = crud.create_strategy_backtest(
            db=db,
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            total_return=backtest_results["total_return"],
            win_rate=backtest_results["win_rate"],
            max_drawdown=backtest_results["max_drawdown"],
            avg_pnl=backtest_results["avg_pnl"],
            total_trades=backtest_results["total_trades"],
            sharpe_ratio=backtest_results.get("sharpe_ratio"),
            results=backtest_results,
        )
        
        # Update strategy with enhanced score and cross-asset results
        update_kwargs = {
            "score": memory_adjusted_score,
            "last_backtest_at": datetime.now(),
            "last_backtest_results": backtest_results,
        }
        
        # Include cross-asset results if available
        if cross_asset_results:
            update_kwargs["last_backtest_results"] = {
                **backtest_results,
                "cross_asset": cross_asset_results,
            }
        
        crud.update_user_strategy(
            db=db,
            strategy_id=strategy_id,
            **update_kwargs
        )
        
        # Record event in MCN
        self.mcn_adapter.record_event(
            event_type="strategy_backtest",
            payload={
                "strategy_id": strategy_id,
                "symbol": symbol,
                "total_return": backtest_results["total_return"],
                "win_rate": backtest_results["win_rate"],
                "score": memory_adjusted_score,
                "timestamp": datetime.now().isoformat(),
            },
            user_id=strategy.user_id,
            strategy_id=strategy_id,
        )
        
        return BrainBacktestResponse(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            total_return=backtest_results["total_return"],
            win_rate=backtest_results["win_rate"],
            max_drawdown=backtest_results["max_drawdown"],
            avg_pnl=backtest_results["avg_pnl"],
            total_trades=backtest_results["total_trades"],
            sharpe_ratio=backtest_results.get("sharpe_ratio"),
            regime_fit_score=regime_fit_score,
            memory_adjusted_score=memory_adjusted_score,
            historical_pattern_match=pattern_match,
            results=backtest_results,
            created_at=backtest.created_at,
        )
    
    def mutate_with_memory(
        self,
        strategy_id: str,
        num_mutations: int,
        db: Session
    ) -> BrainMutationResponse:
        """
        Create mutated strategies enhanced with MCN memory.
        
        Combines:
        - Basic mutation (L2)
        - MCN-guided refinements (L3)
        """
        # Load strategy
        strategy = crud.get_user_strategy(db, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
        
        # Get MCN memory
        memory = self.mcn_adapter.get_memory_for_strategy(strategy_id)
        
        # Generate basic mutations (L2)
        mutations = self.mutation_engine.mutate_strategy(strategy, num_mutations=num_mutations)
        
        # Enhance mutations with MCN recommendations
        mutated_strategies = []
        lineage_ids = []
        mcn_recommendations = []
        
        for mutation in mutations:
            mutated_data = mutation["mutated_strategy"]
            
            # Get MCN adjustments for this mutation
            market_state = {
                "volatility": 0.2,  # Default - could fetch real market state
                "sentiment": 0.0,
            }
            adjustments = self.mcn_adapter.generate_adjustment(mutated_data, market_state)
            
            # Apply adjustments to parameters
            adjusted_parameters = dict(mutated_data["parameters"])
            for key, value in adjustments.get("parameter_tweaks", {}).items():
                if key in adjusted_parameters:
                    adjusted_parameters[key] = value
            
            # Create enhanced strategy
            new_strategy = crud.create_user_strategy(
                db=db,
                user_id=strategy.user_id,
                name=mutated_data["name"],
                description=mutated_data["description"],
                parameters=adjusted_parameters,
                ruleset=mutated_data["ruleset"],
                asset_type=mutated_data["asset_type"],
            )
            
            # Create lineage record
            lineage = crud.create_strategy_lineage(
                db=db,
                parent_strategy_id=strategy_id,
                child_strategy_id=new_strategy.id,
                mutation_type=mutation["mutation_type"],
                mutation_params=mutation["mutation_params"],
            )
            
            mutated_strategies.append({
                "id": new_strategy.id,
                "name": new_strategy.name,
                "description": new_strategy.description,
                "parameters": new_strategy.parameters,
                "ruleset": new_strategy.ruleset,
                "mcn_adjustments": adjustments,
            })
            lineage_ids.append(lineage.id)
            mcn_recommendations.append({
                "strategy_id": new_strategy.id,
                "adjustments": adjustments,
                "reasoning": f"MCN-enhanced {mutation['mutation_type']}",
            })
        
        # Record event in MCN
        self.mcn_adapter.record_event(
            event_type="strategy_mutated",
            payload={
                "parent_strategy_id": strategy_id,
                "num_mutations": len(mutated_strategies),
                "mutation_types": [m["mutation_type"] for m in mutations],
                "timestamp": datetime.now().isoformat(),
            },
            user_id=strategy.user_id,
            strategy_id=strategy_id,
        )
        
        return BrainMutationResponse(
            parent_strategy_id=strategy_id,
            mutated_strategies=mutated_strategies,
            lineage_ids=lineage_ids,
            mcn_recommendations=mcn_recommendations,
        )
    
    def context_summary(
        self,
        user_id: str,
        db: Session
    ) -> BrainContextResponse:
        """
        Get Brain context summary for a user.
        
        Returns:
            - Market regime
            - User risk profile memory
            - Relevant strategy clusters
            - Sentiment cluster summary
        """
        # Get user's strategies
        strategies = crud.list_user_strategies(db, user_id, active_only=True)
        
        # Determine market regime (simplified - could use market data)
        market_regime = MarketRegime.UNKNOWN.value
        
        # Get user risk profile from MCN memory
        # PHASE 4: User risk profile now retrieved from UserRiskProfile service
        user_risk_profile = {
            "risk_tolerance": "moderate",  # Placeholder
            "preferred_asset_types": ["STOCK"],
            "historical_performance": {},
        }
        
        # Get relevant strategy clusters
        strategy_clusters = []
        for strategy in strategies[:5]:  # Top 5 strategies
            memory = self.mcn_adapter.get_memory_for_strategy(strategy.id)
            if memory.get("clusters"):
                strategy_clusters.append({
                    "strategy_id": strategy.id,
                    "strategy_name": strategy.name,
                    "clusters": memory.get("clusters", []),
                })
        
        # Sentiment cluster summary (simplified)
        sentiment_summary = {
            "overall_sentiment": 0.0,
            "trend": "neutral",
        }
        
        return BrainContextResponse(
            user_id=user_id,
            market_regime=market_regime,
            user_risk_profile=user_risk_profile,
            relevant_strategy_clusters=strategy_clusters,
            sentiment_cluster_summary=sentiment_summary,
            recommended_actions=[
                "Review top-performing strategies",
                "Consider market regime adjustments",
            ],
            timestamp=datetime.now(),
        )
    
    def _determine_market_regime(self, market_data: Dict[str, Any]) -> str:
        """Determine current market regime from market data."""
        volatility = market_data.get("volatility", 0.0)
        sentiment = market_data.get("sentiment", 0.0)
        
        if volatility > 0.3:
            return MarketRegime.VOLATILE.value
        elif sentiment > 0.5:
            return MarketRegime.BULL.value
        elif sentiment < -0.5:
            return MarketRegime.BEAR.value
        elif volatility < 0.1:
            return MarketRegime.SIDEWAYS.value
        else:
            return MarketRegime.TRENDING.value
    
    def _calculate_regime_fit(
        self,
        backtest_results: Dict[str, Any],
        memory: Dict[str, Any]
    ) -> float:
        """Calculate how well strategy fits current market regime."""
        # Simplified: use win rate as proxy for regime fit
        win_rate = backtest_results.get("win_rate", 0.0)
        return win_rate  # Higher win rate = better regime fit
    
    def _adjust_score_with_memory(
        self,
        base_score: float,
        memory: Dict[str, Any]
    ) -> float:
        """Adjust strategy score based on MCN memory."""
        # If we have historical patterns, boost score slightly
        patterns = memory.get("historical_patterns", [])
        if patterns:
            # Boost by 5% if we have matching patterns
            return min(1.0, base_score * 1.05)
        return base_score
    
    def _calculate_pattern_match(
        self,
        backtest_results: Dict[str, Any],
        memory: Dict[str, Any]
    ) -> float:
        """Calculate similarity to historical patterns."""
        patterns = memory.get("historical_patterns", [])
        if not patterns:
            return 0.0
        
        # Simplified: compare win rate to historical patterns
        current_win_rate = backtest_results.get("win_rate", 0.0)
        if patterns:
            avg_historical_win_rate = sum(
                p.get("win_rate", 0.0) for p in patterns
            ) / len(patterns)
            # Calculate similarity (1.0 = perfect match)
            similarity = 1.0 - abs(current_win_rate - avg_historical_win_rate)
            return max(0.0, min(1.0, similarity))
        return 0.0
    
    def _calculate_position_size(
        self,
        user_id: str,
        entry_price: float,
        stop_loss: Optional[float],
        confidence: float,
        db: Session,
    ) -> float:
        """
        Calculate position size based on user risk constraints (L4).
        
        Returns:
            Position size in shares/units
        """
        # Get user trading settings
        settings = crud.get_user_trading_settings(db, user_id)
        if not settings:
            # Default position size calculation
            return 10.0  # Default 10 shares
        
        # Get account balance
        from ..broker.paper_broker import PaperBroker
        paper_broker = PaperBroker(db)
        balance_info = paper_broker.get_account_balance(user_id)
        available_balance = balance_info.get("paper_balance", 0.0)
        
        # Check stop under balance
        if settings.stop_under_balance and available_balance < settings.stop_under_balance:
            return 0.0  # Stop trading
        
        # Check capital range
        if settings.capital_range_min and available_balance < settings.capital_range_min:
            return 0.0
        if settings.capital_range_max and available_balance > settings.capital_range_max:
            available_balance = settings.capital_range_max
        
        # Calculate max risk per trade
        max_risk_amount = available_balance * (settings.max_risk_percent / 100.0)
        
        # Calculate position size based on stop loss
        if stop_loss and stop_loss > 0:
            risk_per_share = abs(entry_price - stop_loss)
            if risk_per_share > 0:
                position_size = max_risk_amount / risk_per_share
            else:
                position_size = 0.0
        else:
            # No stop loss, use max auto trade amount
            position_size = settings.max_auto_trade_amount / entry_price
        
        # Apply max auto trade amount constraint
        max_position_value = settings.max_auto_trade_amount
        max_position_size = max_position_value / entry_price
        position_size = min(position_size, max_position_size)
        
        # Apply confidence adjustment (higher confidence = larger position, up to limit)
        confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5x to 1.0x
        position_size = position_size * confidence_multiplier
        
        # Ensure minimum position size
        position_size = max(1.0, position_size)
        
        return round(position_size, 2)
    
    def _calculate_target_alignment(
        self,
        user_id: str,
        daily_profit_target: Optional[float],
        position_size: float,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        confidence: float,
        db: Session,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate target alignment for daily profit goal.
        
        Returns:
            Dictionary with target alignment info, or None if no target set
        """
        # Get user trading settings
        settings = crud.get_user_trading_settings(db, user_id)
        if not settings or not settings.daily_profit_target:
            return None
        
        target = settings.daily_profit_target
        
        # Estimate average P&L per trade
        # Use take_profit - entry as optimistic estimate, or stop_loss - entry as pessimistic
        if take_profit and entry_price > 0:
            optimistic_pnl_per_trade = (take_profit - entry_price) * position_size
        elif stop_loss and entry_price > 0:
            optimistic_pnl_per_trade = abs(entry_price - stop_loss) * position_size * 0.5  # Assume 50% win rate
        else:
            optimistic_pnl_per_trade = entry_price * position_size * 0.01  # Assume 1% return
        
        # Adjust by confidence
        estimated_pnl_per_trade = optimistic_pnl_per_trade * confidence
        
        # Calculate required trades per day
        if estimated_pnl_per_trade > 0:
            required_trades = target / estimated_pnl_per_trade
        else:
            required_trades = float('inf')
        
        # Determine risk level
        if required_trades <= 3:
            risk_level = "low"
        elif required_trades <= 5:
            risk_level = "moderate"
        elif required_trades <= 10:
            risk_level = "high"
        else:
            risk_level = "very_high"
        
        # Determine if target is realistic
        estimated_possible = required_trades <= 10 and confidence >= 0.7
        
        # Generate notes
        if not estimated_possible:
            notes = (
                f"To target ${target:.2f}/day with current capital and risk settings, "
                f"you would need approximately {required_trades:.1f} winning trades/day at "
                f"${estimated_pnl_per_trade:.2f} profit each. This is aggressive and may involve "
                f"higher drawdowns. Consider adjusting your daily target or increasing capital."
            )
        else:
            notes = (
                f"To target ${target:.2f}/day, you would need approximately {required_trades:.1f} "
                f"winning trades/day at ${estimated_pnl_per_trade:.2f} profit each. "
                f"This is {'feasible' if risk_level in ['low', 'moderate'] else 'challenging'} "
                f"with your current strategy and risk settings."
            )
        
        return {
            "daily_profit_target": target,
            "estimated_possible": estimated_possible,
            "required_avg_trades": round(required_trades, 1),
            "required_avg_pnl_per_trade": round(estimated_pnl_per_trade, 2),
            "risk_level": risk_level,
            "notes": notes,
        }

