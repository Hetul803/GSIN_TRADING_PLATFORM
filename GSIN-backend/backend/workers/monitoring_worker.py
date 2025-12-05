# backend/workers/monitoring_worker.py
"""
Monitoring Worker - Gatekeeper for strategy lifecycle management.

This worker runs periodically to:
1. Review new user-uploaded strategies (pending_review status)
   - Check for duplicates using strategy fingerprinting
   - Run basic sanity checks (lightweight backtest)
   - Accept/reject/duplicate strategies
   
2. Compute robustness scores for existing strategies
   - Calculate robustness based on regime diversity, walk-forward stability, parameter sensitivity
   - Promote candidate → proposable based on robustness
   - Discard strategies that consistently fail robustness checks

3. Send notifications to users about strategy status changes
"""
import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from threading import Lock

from ..db.session import get_db
from ..db import crud
from ..db.models import UserStrategy
from ..strategy_engine.backtest_engine import BacktestEngine
from ..strategy_engine.scoring import score_strategy
from ..strategy_engine.status_manager import StrategyStatus, determine_strategy_status
from ..strategy_engine.strategy_fingerprint import create_strategy_fingerprint, strategies_match_fingerprint
from ..strategy_engine.strategy_status_helper import set_strategy_status
from ..strategy_engine.strategy_config import (
    MONITORING_WORKER_INTERVAL_SECONDS,
    SANITY_CHECK_MIN_TRADES,
    SANITY_CHECK_MAX_DRAWDOWN,
    SANITY_CHECK_REQUIRE_NO_NAN,
    MONITORING_ROBUSTNESS_SCORE_MIN,
    MONITORING_SHARPE_MIN,
    MONITORING_PROFIT_FACTOR_MIN,
    MONITORING_MAX_DRAWDOWN_MAX,
    MONITORING_DISCARD_ROBUSTNESS_THRESHOLD,
    MONITORING_DISCARD_MIN_TRADES,
    MONITORING_DISCARD_MIN_EVALUATION_CYCLES,
)
from ..brain.mcn_adapter import get_mcn_adapter
from ..utils.logger import log


class MonitoringWorker:
    """Worker that monitors and gates strategy lifecycle."""
    
    def __init__(self):
        self.backtest_engine = BacktestEngine()
        self.mcn_adapter = get_mcn_adapter()
    
    def run_monitoring_cycle(self, db: Session) -> Dict[str, Any]:
        """
        Run a single monitoring cycle.
        
        Returns:
            Summary of monitoring cycle results
        """
        log("🔍 Starting monitoring cycle...")
        
        stats = {
            "pending_review_processed": 0,
            "duplicates_found": 0,
            "rejected": 0,
            "accepted": 0,
            "robustness_checks": 0,
            "promoted_to_proposable": 0,
            "discarded": 0,
            "notifications_sent": 0,
        }
        
        try:
            # 1. Process pending_review strategies (new user uploads)
            pending_strategies = db.query(UserStrategy).filter(
                UserStrategy.status == StrategyStatus.PENDING_REVIEW
            ).all()
            
            log(f"📋 Found {len(pending_strategies)} strategies with PENDING_REVIEW status")
            
            for strategy in pending_strategies:
                result = self._process_pending_strategy(db, strategy)
                stats["pending_review_processed"] += 1
                
                if result["action"] == "duplicate":
                    stats["duplicates_found"] += 1
                elif result["action"] == "rejected":
                    stats["rejected"] += 1
                elif result["action"] == "accepted":
                    stats["accepted"] += 1
                
                if result.get("notification_sent"):
                    stats["notifications_sent"] += 1
            
            # 2. Compute robustness for experiment/candidate strategies
            active_strategies = db.query(UserStrategy).filter(
                UserStrategy.is_active == True,
                UserStrategy.status.in_([StrategyStatus.EXPERIMENT, StrategyStatus.CANDIDATE]),
                UserStrategy.status != StrategyStatus.DISCARDED
            ).all()
            
            for strategy in active_strategies:
                # Only check strategies with enough data
                if strategy.last_backtest_results and strategy.last_backtest_results.get("total_trades", 0) >= MONITORING_DISCARD_MIN_TRADES:
                    result = self._check_robustness_and_promote(db, strategy)
                    stats["robustness_checks"] += 1
                    
                    if result["action"] == "promoted_to_proposable":
                        stats["promoted_to_proposable"] += 1
                    elif result["action"] == "discarded":
                        stats["discarded"] += 1
                    
                    if result.get("notification_sent"):
                        stats["notifications_sent"] += 1
        
        except Exception as e:
            log(f"❌ Monitoring cycle error: {e}")
            import traceback
            traceback.print_exc()
        
        log(f"✅ Monitoring cycle complete: {stats}")
        return stats
    
    def _process_pending_strategy(
        self,
        db: Session,
        strategy: UserStrategy
    ) -> Dict[str, Any]:
        """
        Process a pending_review strategy:
        1. Check for duplicates
        2. Run sanity check
        3. Accept or reject
        """
        strategy_id = strategy.id
        
        # Step 1: Check for duplicates
        duplicate = self._check_duplicate(db, strategy)
        if duplicate:
            # Mark as duplicate using centralized helper
            set_strategy_status(
                db=db,
                strategy=strategy,
                new_status=StrategyStatus.DUPLICATE,
                reason="This strategy matches an existing strategy in our system.",
                triggered_by="monitoring_worker"
            )
            
            return {
                "action": "duplicate",
                "duplicate_of": duplicate.id,
                "notification_sent": True
            }
        
        # Step 2: Run sanity check (lightweight backtest)
        sanity_result = self._run_sanity_check(strategy)
        
        if not sanity_result["passed"]:
            # Mark as rejected using centralized helper
            set_strategy_status(
                db=db,
                strategy=strategy,
                new_status=StrategyStatus.REJECTED,
                reason=sanity_result.get("reason", "Strategy failed initial validation checks."),
                triggered_by="monitoring_worker"
            )
            
            return {
                "action": "rejected",
                "reason": sanity_result.get("reason"),
                "notification_sent": True
            }
        
        # Step 3: Accept - mark as experiment and eligible for Evolution Worker
        set_strategy_status(
            db=db,
            strategy=strategy,
            new_status=StrategyStatus.EXPERIMENT,
            reason="Your strategy passed initial checks and is now being backtested by the Brain.",
            triggered_by="monitoring_worker",
            last_backtest_at=datetime.now(timezone.utc),
            last_backtest_results=sanity_result.get("backtest_results")
        )
        
        return {
            "action": "accepted",
            "notification_sent": True
        }
    
    def _check_duplicate(
        self,
        db: Session,
        strategy: UserStrategy
    ) -> Optional[UserStrategy]:
        """Check if strategy matches an existing strategy's fingerprint."""
        strategy_fp = create_strategy_fingerprint(strategy.ruleset)
        
        # Get all active strategies (excluding this one)
        existing_strategies = db.query(UserStrategy).filter(
            UserStrategy.id != strategy.id,
            UserStrategy.status != StrategyStatus.DISCARDED,
            UserStrategy.status != StrategyStatus.REJECTED,
            UserStrategy.status != StrategyStatus.DUPLICATE
        ).all()
        
        for existing in existing_strategies:
            existing_fp = create_strategy_fingerprint(existing.ruleset)
            if strategy_fp == existing_fp:
                return existing
        
        return None
    
    def _run_sanity_check(
        self,
        strategy: UserStrategy
    ) -> Dict[str, Any]:
        """
        Run a lightweight sanity check on a new strategy.
        
        Uses a small historical window to quickly validate basic functionality.
        """
        try:
            # Extract symbol and timeframe
            symbol = strategy.ruleset.get("ticker") or strategy.ruleset.get("symbol") or strategy.ruleset.get("default_symbol", "AAPL")
            if isinstance(symbol, list):
                symbol = symbol[0] if symbol else "AAPL"
            timeframe = strategy.ruleset.get("timeframe", "1d")
            
            # Use a smaller date range for sanity check (6-12 months for daily, smaller for intraday)
            end_date = datetime.now(timezone.utc)
            if timeframe in ["1d", "4h"]:
                start_date = end_date - timedelta(days=180)  # 6 months
            elif timeframe in ["1h", "15m"]:
                start_date = end_date - timedelta(days=30)  # 1 month
            else:
                start_date = end_date - timedelta(days=7)  # 1 week for very short timeframes
            
            # Run lightweight backtest
            backtest_results = self.backtest_engine.run_backtest(
                symbol=symbol,
                ruleset=strategy.ruleset,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                train_test_split=0.7
            )
            
            # Extract metrics
            total_trades = backtest_results.get("total_trades", 0)
            win_rate = backtest_results.get("win_rate", 0.0)
            max_drawdown = abs(backtest_results.get("max_drawdown", 0.0))
            sharpe_ratio = backtest_results.get("sharpe_ratio", 0.0)
            
            # Check for NaNs
            has_nan = (
                total_trades != total_trades or
                win_rate != win_rate or
                max_drawdown != max_drawdown or
                sharpe_ratio != sharpe_ratio
            )
            
            # Apply sanity thresholds
            if total_trades < SANITY_CHECK_MIN_TRADES:
                return {
                    "passed": False,
                    "reason": f"Strategy generated only {total_trades} trades (minimum: {SANITY_CHECK_MIN_TRADES})."
                }
            
            if max_drawdown > SANITY_CHECK_MAX_DRAWDOWN:
                return {
                    "passed": False,
                    "reason": f"Strategy has excessive drawdown: {max_drawdown:.1f}% (maximum allowed: {SANITY_CHECK_MAX_DRAWDOWN:.0%})."
                }
            
            if SANITY_CHECK_REQUIRE_NO_NAN and has_nan:
                return {
                    "passed": False,
                    "reason": "Strategy produced invalid metrics (NaN values detected)."
                }
            
            # Passed sanity check
            return {
                "passed": True,
                "backtest_results": backtest_results
            }
        
        except Exception as e:
            return {
                "passed": False,
                "reason": f"Strategy validation failed: {str(e)}"
            }
    
    def _check_robustness_and_promote(
        self,
        db: Session,
        strategy: UserStrategy
    ) -> Dict[str, Any]:
        """
        Compute robustness score and promote/discard based on thresholds.
        """
        if not strategy.last_backtest_results:
            return {"action": "skipped", "reason": "no_backtest_data"}
        
        # Calculate robustness score
        robustness_score = self._calculate_robustness_score(strategy)
        
        current_status = strategy.status or StrategyStatus.EXPERIMENT
        
        # Check if should promote candidate → proposable
        # FIXED: Monitoring Worker is the ONLY component that promotes candidate → proposable
        # FIXED: Added MCN checks and flexible thresholds to match status_manager
        if current_status == StrategyStatus.CANDIDATE:
            metrics = strategy.last_backtest_results
            win_rate = metrics.get("win_rate", 0.0) or 0.0
            sharpe = metrics.get("sharpe_ratio", 0.0) or 0.0
            profit_factor = metrics.get("profit_factor", 0.0) or 0.0
            max_drawdown = abs(metrics.get("max_drawdown", 0.0))
            total_trades = metrics.get("total_trades", 0) or 0
            score = strategy.score or 0.0
            test_metrics = metrics.get("test_metrics", {})
            test_win_rate = test_metrics.get("win_rate", win_rate) if test_metrics else win_rate
            
            # Get MCN robustness data
            mcn_regime_stability_score = 0.0
            mcn_overfitting_risk = "Unknown"
            
            try:
                from ..brain.mcn_adapter import get_mcn_adapter
                mcn_adapter = get_mcn_adapter()
                lineage_memory = mcn_adapter.get_strategy_lineage_memory(strategy.id, db)
                if lineage_memory:
                    ancestor_stability = lineage_memory.get("ancestor_stability", 0.5)
                    has_overfit = lineage_memory.get("has_overfit_ancestors", False)
                    
                    # Calculate regime stability from per_symbol_performance if available
                    if strategy.per_symbol_performance:
                        profitable_symbols = sum(1 for perf in strategy.per_symbol_performance.values() 
                                               if isinstance(perf, dict) and perf.get("win_rate", 0.0) >= 0.5)
                        total_symbols = len(strategy.per_symbol_performance)
                        if total_symbols > 0:
                            mcn_regime_stability_score = profitable_symbols / total_symbols
                        else:
                            mcn_regime_stability_score = ancestor_stability
                    else:
                        mcn_regime_stability_score = ancestor_stability
                    
                    mcn_overfitting_risk = "High" if has_overfit else "Low"
                else:
                    # Default to passing if MCN unavailable
                    mcn_regime_stability_score = 0.75
                    mcn_overfitting_risk = "Low"
            except Exception as e:
                # Default to passing if MCN check fails
                mcn_regime_stability_score = 0.75
                mcn_overfitting_risk = "Low"
            
            # Flexible thresholds: Path 1 (High Win) OR Path 2 (High Sharpe)
            from ..strategy_engine.strategy_config import (
                WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_WIN,
                WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_SHARPE,
                MIN_SHARPE_FOR_PROPOSABLE_HIGH_WIN,
                MIN_SHARPE_FOR_PROPOSABLE_HIGH_SHARPE,
                MIN_PROFIT_FACTOR_FOR_PROPOSABLE,
                MAX_DRAWDOWN_FOR_PROPOSABLE,
                MIN_SCORE_FOR_PROPOSABLE,
                MIN_TEST_WIN_RATE,
                MCN_REGIME_STABILITY_SCORE_MIN,
                MCN_OVERFITTING_RISK_REQUIRED,
                MIN_TRADES_FOR_PROPOSABLE,
            )
            
            path1_met = (
                total_trades >= MIN_TRADES_FOR_PROPOSABLE and
                win_rate >= WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_WIN and  # 80%
                sharpe >= MIN_SHARPE_FOR_PROPOSABLE_HIGH_WIN and  # 1.0
                profit_factor >= MIN_PROFIT_FACTOR_FOR_PROPOSABLE and  # 1.2
                max_drawdown <= MAX_DRAWDOWN_FOR_PROPOSABLE and  # 20%
                score >= MIN_SCORE_FOR_PROPOSABLE and  # 0.70
                test_win_rate >= MIN_TEST_WIN_RATE  # 0.70
            )
            
            path2_met = (
                total_trades >= MIN_TRADES_FOR_PROPOSABLE and
                win_rate >= WIN_RATE_THRESHOLD_PROPOSABLE_HIGH_SHARPE and  # 60%
                sharpe >= MIN_SHARPE_FOR_PROPOSABLE_HIGH_SHARPE and  # 1.5
                profit_factor >= MIN_PROFIT_FACTOR_FOR_PROPOSABLE and  # 1.2
                max_drawdown <= MAX_DRAWDOWN_FOR_PROPOSABLE and  # 20%
                score >= MIN_SCORE_FOR_PROPOSABLE and  # 0.70
                test_win_rate >= MIN_TEST_WIN_RATE  # 0.70
            )
            
            # MCN requirements
            mcn_requirements_met = (
                mcn_regime_stability_score >= MCN_REGIME_STABILITY_SCORE_MIN and
                mcn_overfitting_risk == MCN_OVERFITTING_RISK_REQUIRED
            )
            
            # Base requirements: Either path must be met + robustness score + MCN checks
            if (
                (path1_met or path2_met) and
                robustness_score >= MONITORING_ROBUSTNESS_SCORE_MIN and
                mcn_requirements_met
            ):
                # Promote to proposable using centralized helper
                set_strategy_status(
                    db=db,
                    strategy=strategy,
                    new_status=StrategyStatus.PROPOSABLE,
                    reason="Your strategy has passed robustness checks and is now available for other users to run. You are now eligible for royalties according to your plan.",
                    triggered_by="monitoring_worker"
                )
                
                return {
                    "action": "promoted_to_proposable",
                    "robustness_score": robustness_score,
                    "notification_sent": True
                }
        
        # Check if should discard experiment strategies
        if current_status == StrategyStatus.EXPERIMENT:
            # Check if strategy has been evaluated enough times
            evaluation_cycles = (strategy.evolution_attempts or 0) + (1 if strategy.last_backtest_at else 0)
            
            if (
                robustness_score < MONITORING_DISCARD_ROBUSTNESS_THRESHOLD and
                strategy.last_backtest_results.get("total_trades", 0) >= MONITORING_DISCARD_MIN_TRADES and
                evaluation_cycles >= MONITORING_DISCARD_MIN_EVALUATION_CYCLES
            ):
                # Discard using centralized helper
                set_strategy_status(
                    db=db,
                    strategy=strategy,
                    new_status=StrategyStatus.DISCARDED,
                    reason="Your strategy has been deprecated based on new performance data.",
                    triggered_by="monitoring_worker"
                )
                
                return {
                    "action": "discarded",
                    "robustness_score": robustness_score,
                    "notification_sent": True
                }
        
        return {
            "action": "no_change",
            "robustness_score": robustness_score
        }
    
    def _calculate_robustness_score(
        self,
        strategy: UserStrategy
    ) -> float:
        """
        Calculate robustness score (0-100) based on:
        - Regime diversity
        - Walk-forward stability
        - Parameter sensitivity
        - Classic metrics
        """
        if not strategy.last_backtest_results:
            return 0.0
        
        metrics = strategy.last_backtest_results
        score_components = []
        
        # Component 1: Classic metrics (40% weight)
        sharpe = metrics.get("sharpe_ratio", 0.0) or 0.0
        profit_factor = metrics.get("profit_factor", 0.0) or 0.0
        max_drawdown = abs(metrics.get("max_drawdown", 0.0))
        
        classic_score = 0.0
        if sharpe > 0:
            classic_score += min(1.0, sharpe / 2.0) * 0.15  # Sharpe component (15%)
        if profit_factor > 0:
            classic_score += min(1.0, profit_factor / 2.0) * 0.15  # Profit factor component (15%)
        if max_drawdown < 0.30:
            classic_score += (1.0 - max_drawdown / 0.30) * 0.10  # Drawdown component (10%)
        
        score_components.append(classic_score * 0.40)
        
        # Component 2: Regime diversity (30% weight)
        # Check per_symbol_performance as proxy for regime diversity
        regime_score = 0.5  # Default
        if strategy.per_symbol_performance:
            profitable_symbols = sum(
                1 for perf in strategy.per_symbol_performance.values()
                if isinstance(perf, dict) and perf.get("win_rate", 0.0) >= 0.5
            )
            total_symbols = len(strategy.per_symbol_performance)
            if total_symbols > 0:
                regime_score = profitable_symbols / total_symbols
        
        score_components.append(regime_score * 0.30)
        
        # Component 3: Walk-forward stability (20% weight)
        train_metrics = strategy.train_metrics or {}
        test_metrics = strategy.test_metrics or metrics
        
        train_winrate = train_metrics.get("win_rate", 0.0)
        test_winrate = test_metrics.get("win_rate", 0.0)
        
        if train_winrate > 0:
            stability_ratio = test_winrate / train_winrate if train_winrate > 0 else 0.0
            # Penalize if test performance is much worse than train (overfitting)
            stability_score = min(1.0, stability_ratio / 0.8)  # 80% of train = full score
        else:
            stability_score = 0.5  # Default if no train/test split
        
        score_components.append(stability_score * 0.20)
        
        # Component 4: Parameter sensitivity (10% weight)
        # Simplified: if strategy has been mutated and still performs well, it's robust
        # For now, use evolution_attempts as proxy (more attempts = more tested = more robust)
        sensitivity_score = min(1.0, (strategy.evolution_attempts or 0) / 5.0)
        score_components.append(sensitivity_score * 0.10)
        
        # Combine components
        total_score = sum(score_components) * 100  # Scale to 0-100
        
        return max(0.0, min(100.0, total_score))
    


def run_monitoring_worker_once():
    """Run monitoring worker once (for testing)."""
    db = next(get_db())
    try:
        worker = MonitoringWorker()
        stats = worker.run_monitoring_cycle(db)
        return stats
    finally:
        db.close()


def run_monitoring_worker_loop():
    """Run monitoring worker in a continuous loop."""
    from ..db.session import get_db
    from ..utils.logger import log
    
    interval_seconds = MONITORING_WORKER_INTERVAL_SECONDS
    log(f"🔍 Monitoring worker started (interval: {interval_seconds} seconds)")
    
    while True:
        try:
            db = next(get_db())
            try:
                worker = MonitoringWorker()
                stats = worker.run_monitoring_cycle(db)
                log(f"✅ Monitoring cycle complete: {stats}")
            finally:
                db.close()
        except Exception as e:
            log(f"❌ Monitoring worker error: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # Run once for testing
    run_monitoring_worker_once()

