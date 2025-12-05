# backend/workers/evolution_worker.py
"""
Evolution Worker - Self-evolving strategy system.

This worker runs periodically to:
1. Backtest all active strategies with updated data
2. Update metrics and status (experiment → candidate → proposable)
3. Mutate poor/borderline strategies
4. Discard strategies that fail repeatedly
5. Record all events to MCN for learning

Configuration:
- EVOLUTION_INTERVAL_SECONDS: How often to run (default: 480 seconds / 8 minutes)
- MIN_TRADES_FOR_EVAL: Minimum trades to evaluate (default: 50)
- MAX_EVOLUTION_ATTEMPTS: Max attempts before discard (default: 10)
- MAX_STRATEGIES_TO_MAINTAIN: Max active strategies (default: 100)
- Note: Win rate thresholds are now in strategy_config.py (flexible: 80% high-win or 60% high-sharpe)
"""
import os
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from ..db.session import get_db
from ..db import crud
from ..strategy_engine.backtest_engine import BacktestEngine
from ..strategy_engine.scoring import score_strategy
from ..strategy_engine.status_manager import (
    determine_strategy_status,
    should_discard_strategy,
    StrategyStatus
)
from ..strategy_engine.strategy_status_helper import set_strategy_status
from ..strategy_engine.mutation_engine import MutationEngine
from ..strategy_engine.mutation_engine_enhanced import EnhancedMutationEngine
from ..strategy_engine.constants import DEFAULT_SYMBOLS
from ..strategy_engine.strategy_thresholds import (
    get_evolution_phase,
    get_thresholds_for_phase,
    check_strategy_meets_thresholds,
    EvolutionPhase
)
from ..brain.mcn_adapter import get_mcn_adapter
from ..brain.mcn_backup import get_backup_manager  # PHASE 4


# Configuration constants - Use centralized config with env var overrides
from ..strategy_engine.strategy_config import (
    EVOLUTION_INTERVAL_SECONDS as DEFAULT_EVOLUTION_INTERVAL,
    MAX_EVOLUTION_ATTEMPTS as DEFAULT_MAX_ATTEMPTS,
    MAX_STRATEGIES_TO_MAINTAIN as DEFAULT_MAX_STRATEGIES,
    MIN_TRADES_FOR_CANDIDATE
)

# Allow env var overrides (for deployment flexibility)
EVOLUTION_INTERVAL_SECONDS = int(os.environ.get("EVOLUTION_INTERVAL_SECONDS", str(DEFAULT_EVOLUTION_INTERVAL)))  # Default: 8 minutes (480s)
MIN_TRADES_FOR_EVAL = int(os.environ.get("MIN_TRADES_FOR_EVAL", str(MIN_TRADES_FOR_CANDIDATE)))  # Default: 50
MAX_EVOLUTION_ATTEMPTS = int(os.environ.get("MAX_EVOLUTION_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS)))  # Default: 10
MAX_STRATEGIES_TO_MAINTAIN = int(os.environ.get("MAX_STRATEGIES_TO_MAINTAIN", str(DEFAULT_MAX_STRATEGIES)))  # Default: 100
PARALLEL_WORKERS = int(os.environ.get("EVOLUTION_PARALLEL_WORKERS", "3"))  # Process 3 strategies in parallel

# Twelve Data rate limiting (377 credits/min for Grow plan)
TWELVEDATA_CREDITS_PER_MIN = 377
TWELVEDATA_CREDITS_PER_REQUEST = 1  # Each historical OHLCV request costs 1 credit
# Evolution batch size - configurable via EVOLUTION_BATCH_SIZE env var (default: 50)
EVOLUTION_BATCH_SIZE = int(os.environ.get("EVOLUTION_BATCH_SIZE", "50"))  # Number of strategies to process per cycle
MAX_REQUESTS_PER_CYCLE = min(EVOLUTION_BATCH_SIZE, int(TWELVEDATA_CREDITS_PER_MIN * 0.8))  # Cap at rate limit or batch size


class EvolutionWorker:
    """Worker that evolves strategies through backtesting, mutation, and selection."""
    
    def __init__(self):
        self.backtest_engine = BacktestEngine()
        # Use enhanced mutation engine with genetic algorithm
        self.mutation_engine = EnhancedMutationEngine()
        # Keep old engine as fallback
        self.legacy_mutation_engine = MutationEngine()
        self.mcn_adapter = get_mcn_adapter()
    
    def run_evolution_cycle(self, db: Session) -> Dict[str, Any]:
        """
        Run a single evolution cycle.
        
        Returns:
            Summary of evolution cycle results
        """
        print("🧬 Starting evolution cycle...")
        
        # PHASE 2: Auto-detect evolution phase and log transition
        phase, phase_info = get_evolution_phase(db)
        thresholds = get_thresholds_for_phase(phase)
        print(f"📊 Evolution Phase: {phase_info['name']} - {phase_info['description']}")
        print(f"   Thresholds: winrate≥{thresholds['winrate_min']:.2%}, sharpe≥{thresholds['sharpe_min']:.2f}, trades≥{thresholds['trades_min']}")
        if thresholds.get("max_drawdown_max"):
            print(f"   Max drawdown: ≤{thresholds['max_drawdown_max']:.1f}%")
        if thresholds.get("symbol_robustness_required"):
            print(f"   Symbol robustness: required across {thresholds['min_symbols']} symbols")
        
        # Get all active strategies (query directly from DB)
        from ..db.models import UserStrategy
        from datetime import datetime, timezone, timedelta
        
        # Query for active strategies that are not discarded
        try:
            all_strategies = db.query(UserStrategy).filter(
                UserStrategy.is_active == True,
                UserStrategy.status != StrategyStatus.DISCARDED
            ).all()
            print(f"📊 Found {len(all_strategies)} active strategies in database")
        except Exception as e:
            print(f"❌ Error querying strategies: {e}")
            import traceback
            traceback.print_exc()
            all_strategies = []
        
        # Prioritize strategies that:
        # 1. Have never been backtested (last_backtest_at == None)
        # 2. Have old backtests (older than 7 days)
        # 3. Are in EXPERIMENT status (newly created)
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        
        def get_priority(strategy):
            """Calculate priority for strategy (lower number = higher priority)."""
            # Highest priority: never backtested
            if strategy.last_backtest_at is None:
                return 0
            # Second priority: old backtest (>7 days)
            if strategy.last_backtest_at < seven_days_ago:
                return 1
            # Third priority: experiment status (newly created)
            if strategy.status == StrategyStatus.EXPERIMENT:
                return 2
            # Lower priority: already evaluated
            return 3
        
        # Sort by priority
        active_strategies = sorted(all_strategies, key=get_priority)
        
        # Evolution batch size - configurable via EVOLUTION_BATCH_SIZE env var
        # Limit to MAX_REQUESTS_PER_CYCLE (which respects both batch size and rate limits)
        strategies_to_process = active_strategies[:MAX_REQUESTS_PER_CYCLE]
        if len(active_strategies) > MAX_REQUESTS_PER_CYCLE:
            print(f"⚠️  Limiting to {MAX_REQUESTS_PER_CYCLE} strategies per cycle (batch size: {EVOLUTION_BATCH_SIZE}, rate limit: {int(TWELVEDATA_CREDITS_PER_MIN * 0.8)}) ({len(active_strategies)} total available)")
        
        # Log priority breakdown
        never_backtested = sum(1 for s in strategies_to_process if s.last_backtest_at is None)
        old_backtests = sum(1 for s in strategies_to_process if s.last_backtest_at and s.last_backtest_at < seven_days_ago)
        experiment_status = sum(1 for s in strategies_to_process if s.status == StrategyStatus.EXPERIMENT)
        
        print(f"📊 Found {len(strategies_to_process)} active strategies to evaluate (out of {len(active_strategies)} total)")
        if never_backtested > 0:
            print(f"   - {never_backtested} never backtested (highest priority)")
        if old_backtests > 0:
            print(f"   - {old_backtests} with old backtests (>7 days)")
        if experiment_status > 0:
            print(f"   - {experiment_status} in experiment status")
        
        # Use limited list for processing
        active_strategies = strategies_to_process
        
        stats = {
            "total_strategies": len(active_strategies),
            "promoted_to_candidate": 0,
            "promoted_to_proposable": 0,
            "demoted": 0,
            "mutated": 0,
            "discarded": 0,
            "backtests_run": 0,
            "errors": 0,
        }
        
        # PHASE 4: Create MCN backup before mutation rounds
        backup_manager = get_backup_manager()
        backup_path = backup_manager.create_backup("before_evolution_cycle")
        if backup_path:
            print(f"✅ MCN backup created: {backup_path}")
        
        # PHASE 4: Process strategies in parallel
        # Use ThreadPoolExecutor to process 4-8 strategies concurrently
        # Each strategy gets its own database session to avoid conflicts
        db_lock = Lock()  # Lock for MCN event recording
        
        def process_strategy_with_session(strategy):
            """Process a single strategy with its own DB session."""
            try:
                # Create new DB session for this thread
                from ..db.session import SessionLocal
                thread_db = SessionLocal()
                try:
                    result = self._process_strategy(thread_db, strategy)
                    return result
                finally:
                    thread_db.close()
            except Exception as e:
                print(f"❌ Error processing strategy {strategy.id}: {e}")
                import traceback
                traceback.print_exc()
                return {"action": "error", "error": str(e)}
        
        # Process strategies in parallel
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            # Submit all strategies
            future_to_strategy = {
                executor.submit(process_strategy_with_session, strategy): strategy
                for strategy in active_strategies
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_strategy):
                strategy = future_to_strategy[future]
                try:
                    result = future.result()
                    stats["backtests_run"] += 1
                    
                    if result["action"] == "promoted_to_candidate":
                        stats["promoted_to_candidate"] += 1
                    elif result["action"] == "promoted_to_proposable":
                        stats["promoted_to_proposable"] += 1
                    elif result["action"] == "demoted":
                        stats["demoted"] += 1
                    elif result["action"] == "mutated":
                        stats["mutated"] += 1
                    elif result["action"] == "discarded":
                        stats["discarded"] += 1
                    elif result["action"] == "error":
                        stats["errors"] += 1
                    elif result["action"] == "improved":
                        # Log improvements for monitoring
                        pass
                    elif result["action"] == "worse":
                        # Log degradations for monitoring
                        pass
                except Exception as e:
                    print(f"❌ Error getting result for strategy {strategy.id}: {e}")
                    stats["errors"] += 1
        
        # Enforce max strategies limit (keep best performers)
        self._enforce_strategy_limit(db, MAX_STRATEGIES_TO_MAINTAIN)
        
        # STABILITY: Log evolution summary - one line per cycle
        print(f"[GSIN] Evolution summary: total={stats['total_strategies']}, tested={stats['backtests_run']}, mutated={stats['mutated']}, promoted={stats['promoted_to_proposable']}, discarded={stats['discarded']}")
        return stats
    
    def _process_strategy(
        self,
        db: Session,
        strategy
    ) -> Dict[str, Any]:
        """
        Process a single strategy: backtest, update status, mutate if needed.
        
        Returns:
            Dictionary with action taken and details
        """
        strategy_id = strategy.id
        current_status = strategy.status or StrategyStatus.EXPERIMENT
        
        # Skip if already discarded
        if current_status == StrategyStatus.DISCARDED:
            return {"action": "skipped", "reason": "already_discarded"}
        
        # Run backtest with updated data
        # Use a default symbol and timeframe if not specified
        symbol = strategy.ruleset.get("ticker") or strategy.ruleset.get("symbol") or strategy.ruleset.get("default_symbol", "AAPL")
        # Handle if ticker is a list - use first symbol
        if isinstance(symbol, list):
            symbol = symbol[0] if symbol else "AAPL"
        timeframe = strategy.ruleset.get("timeframe", "1d")
        
        # Calculate date range (last 6 months, but ensure we have enough historical data)
        # Use a date range that's more likely to have data (avoid weekends/holidays)
        end_date = datetime.now(timezone.utc)
        # Start from 200 days ago to ensure we get enough trading days (accounting for weekends/holidays)
        start_date = end_date - timedelta(days=200)
        
        # If strategy is generalized, test across all DEFAULT_SYMBOLS
        symbols_to_test = DEFAULT_SYMBOLS if strategy.generalized else [symbol]
        
        try:
            # For generalized strategies, run cross-asset backtest
            if strategy.generalized and len(symbols_to_test) > 1:
                cross_asset_results = self.backtest_engine.execute_backtest_across_assets(
                    strategy_ruleset=strategy.ruleset,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    symbols=symbols_to_test
                )
                
                # Use average metrics from cross-asset results
                per_symbol = cross_asset_results.get("per_symbol_results", {})
                successful = {k: v for k, v in per_symbol.items() if "error" not in v and v.get("total_trades", 0) > 0}
                
                if successful:
                    avg_winrate = sum(v.get("winrate", 0.0) for v in successful.values()) / len(successful)
                    avg_return = sum(v.get("total_return", 0.0) for v in successful.values()) / len(successful)
                    avg_drawdown = sum(abs(v.get("max_drawdown", 0.0)) for v in successful.values()) / len(successful)
                    total_trades = sum(v.get("total_trades", 0) for v in successful.values())
                    
                    backtest_results = {
                        "total_return": avg_return,
                        "win_rate": avg_winrate,
                        "max_drawdown": -avg_drawdown,
                        "avg_pnl": avg_return / total_trades if total_trades > 0 else 0.0,
                        "total_trades": total_trades,
                        "sharpe_ratio": cross_asset_results.get("volatility_adjusted_return", 0.0),
                        "cross_asset": cross_asset_results,
                    }
                else:
                    # Fallback to single symbol if cross-asset fails
                    # FIX: Normalize ruleset before backtest
                    from ..strategy_engine.strategy_normalizer import normalize_strategy_ruleset
                    normalized_ruleset = normalize_strategy_ruleset(strategy.ruleset)
                    backtest_results = self.backtest_engine.run_backtest(
                        symbol=symbol,
                        ruleset=normalized_ruleset,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        train_test_split=0.7,
                        use_rolling_walkforward=True  # IMPROVEMENT: Use rolling walk-forward for true stability validation
                    )
            else:
                # Single symbol backtest
                # FIX: Normalize ruleset before backtest
                from ..strategy_engine.strategy_normalizer import normalize_strategy_ruleset
                normalized_ruleset = normalize_strategy_ruleset(strategy.ruleset)
                backtest_results = self.backtest_engine.run_backtest(
                    symbol=symbol,
                    ruleset=normalized_ruleset,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    train_test_split=0.7,
                    use_rolling_walkforward=True  # IMPROVEMENT: Use rolling walk-forward for true stability validation
                )
        except ValueError as e:
            # PHASE 8: Insufficient data error - skip ticker, don't break evolution cycle
            error_msg = str(e)
            if "Insufficient data" in error_msg or "insufficient_data" in error_msg.lower():
                print(f"⚠️  Backtest failed for strategy {strategy_id} ({symbol}, {timeframe}): {error_msg}")
                print(f"   Date range: {start_date.date()} to {end_date.date()}")
                print(f"   ⏭️  Skipping {symbol} - insufficient data (evolution cycle continues)")
                # PHASE 8: Don't increment evolution attempts for insufficient data - it's not a strategy failure
                return {"action": "skipped_insufficient_data", "symbol": symbol, "error": str(e)}
            else:
                print(f"⚠️  Backtest failed for strategy {strategy_id}: {e}")
                # Increment evolution attempts on failure
                crud.update_user_strategy(
                    db=db,
                    strategy_id=strategy_id,
                    evolution_attempts=(strategy.evolution_attempts or 0) + 1
                )
                return {"action": "backtest_failed", "error": str(e)}
        except Exception as e:
            # PHASE 8: Handle all exceptions gracefully - don't break evolution cycle
            print(f"⚠️  Backtest failed for strategy {strategy_id}: {e}")
            # Check if it's a data issue
            error_str = str(e).lower()
            if "insufficient" in error_str or "no data" in error_str or "empty" in error_str:
                print(f"   ⏭️  Skipping due to data issue (evolution cycle continues)")
                return {"action": "skipped_data_issue", "error": str(e)}
            # Increment evolution attempts on failure
            crud.update_user_strategy(
                db=db,
                strategy_id=strategy_id,
                evolution_attempts=(strategy.evolution_attempts or 0) + 1
            )
            return {"action": "backtest_failed", "error": str(e)}
        
        # Calculate unified score
        score = score_strategy(backtest_results, use_test_metrics=True)
        
        # Prepare strategy dict for status determination
        strategy_dict = {
            "id": strategy_id,
            "evolution_attempts": strategy.evolution_attempts or 0,
            "status": current_status,
        }
        
        # Check if should discard
        if should_discard_strategy(strategy_dict, backtest_results):
            # Mark as discarded using centralized helper
            set_strategy_status(
                db=db,
                strategy=strategy,
                new_status=StrategyStatus.DISCARDED,
                reason="Strategy failed discard criteria based on backtest results",
                triggered_by="evolution_worker",
                score=score,
                last_backtest_at=datetime.now(timezone.utc),
                last_backtest_results=backtest_results,
                train_metrics=backtest_results.get("train_metrics"),
                test_metrics=backtest_results.get("test_metrics"),
            )
            
            # Record discard event in MCN (non-blocking)
            try:
                if self.mcn_adapter and self.mcn_adapter.is_available:
                    self.mcn_adapter.record_event(
                        event_type="strategy_discarded",
                        payload={
                            "strategy_id": strategy_id,
                            "reason": "max_attempts_reached",
                            "final_score": score,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        strategy_id=strategy_id,
                    )
            except Exception as e:
                # MCN errors should not block evolution
                print(f"⚠️  MCN event recording failed (non-fatal): {e}")
            
            return {"action": "discarded", "reason": "max_attempts"}
        
        # IMPROVEMENT 1: Determine new status based on backtest results
        # Add score to backtest_results for status determination
        backtest_results["score"] = score
        
        new_status, is_proposable = determine_strategy_status(
            strategy=strategy_dict,
            backtest_results=backtest_results,
            current_status=current_status,
            db=db  # Pass DB for MCN checks
        )
        
        # PHASE C: Increment evolution_attempts every cycle
        current_attempts = (strategy.evolution_attempts or 0) + 1
        
        # Use centralized helper for status changes that should trigger notifications
        # (promotions to candidate or proposable)
        if new_status in [StrategyStatus.CANDIDATE, StrategyStatus.PROPOSABLE] and new_status != current_status:
            set_strategy_status(
                db=db,
                strategy=strategy,
                new_status=new_status,
                reason=f"Strategy promoted based on backtest results (score: {score:.3f})",
                triggered_by="evolution_worker",
                score=score,
                last_backtest_at=datetime.now(timezone.utc),
                last_backtest_results=backtest_results,
                train_metrics=backtest_results.get("train_metrics"),
                test_metrics=backtest_results.get("test_metrics"),
                evolution_attempts=current_attempts,
            )
        else:
            # For other status changes or no change, update directly (no notification needed)
            crud.update_user_strategy(
                db=db,
                strategy_id=strategy_id,
                score=score,
                status=new_status,
                is_proposable=is_proposable,
                last_backtest_at=datetime.now(timezone.utc),
                last_backtest_results=backtest_results,
                train_metrics=backtest_results.get("train_metrics"),
                test_metrics=backtest_results.get("test_metrics"),
                evolution_attempts=current_attempts,
            )
        
        # Record backtest event in MCN (non-blocking)
        try:
            if self.mcn_adapter and self.mcn_adapter.is_available:
                self.mcn_adapter.record_event(
                    event_type="strategy_backtest",
                    payload={
                        "strategy_id": strategy_id,
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "total_return": backtest_results.get("total_return", 0.0),
                        "win_rate": backtest_results.get("win_rate", 0.0),
                        "max_drawdown": backtest_results.get("max_drawdown", 0.0),
                        "score": score,
                        "status": new_status,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    strategy_id=strategy_id,
                )
        except Exception as e:
            # MCN errors should not block backtesting
            print(f"⚠️  MCN event recording failed (non-fatal): {e}")
        
        # PHASE C: Determine action taken with specific logging
        action = "no_change"
        win_rate = backtest_results.get("win_rate", 0.0)
        previous_score = strategy.score or 0.0
        
        if new_status == StrategyStatus.CANDIDATE and current_status == StrategyStatus.EXPERIMENT:
            action = "promoted_to_candidate"
            print(f"✅ PHASE C: promoted {strategy_id} (experiment → candidate) - winrate={win_rate:.2f}, sharpe={sharpe_ratio:.2f}, score={score:.2f}")
        elif new_status == StrategyStatus.PROPOSABLE and current_status != StrategyStatus.PROPOSABLE:
            action = "promoted_to_proposable"
            print(f"✅ PHASE C: promoted {strategy_id} (candidate → proposable) - winrate={win_rate:.2f}, sharpe={sharpe_ratio:.2f}, score={score:.2f}")
        elif new_status != current_status and new_status in [StrategyStatus.EXPERIMENT, StrategyStatus.CANDIDATE]:
            action = "worse"
            print(f"⚠️  PHASE C: worse {strategy_id} (demoted)")
        elif score > previous_score:
            action = "improved"
            print(f"📈 PHASE C: improved {strategy_id} (score: {previous_score:.2f} → {score:.2f})")
        elif score < previous_score:
            action = "worse"
            print(f"📉 PHASE C: worse {strategy_id} (score: {previous_score:.2f} → {score:.2f})")
        
        # PHASE C: Fix mutation logic - force mutation when attempts >= 3, or when winrate < threshold
        should_mutate = False
        mutation_reason = ""
        
        if current_attempts >= 3:
            should_mutate = True
            mutation_reason = "attempts >= 3"
        elif win_rate < 0.60 and new_status in [StrategyStatus.EXPERIMENT, StrategyStatus.CANDIDATE]:
            should_mutate = True
            mutation_reason = f"winrate {win_rate:.2f} < 0.60"
        
        # PHASE C: Check if strategy should be discarded
        if current_attempts >= MAX_EVOLUTION_ATTEMPTS:
            action = "discarded"
            print(f"🗑️  PHASE C: discarded {strategy_id} (attempts: {current_attempts} >= {MAX_EVOLUTION_ATTEMPTS})")
            crud.update_user_strategy(
                db=db,
                strategy_id=strategy_id,
                status=StrategyStatus.DISCARDED,
                is_active=False,
            )
            # PHASE C: Return early if discarded
            return {"action": action, "strategy_id": strategy_id}
        
        # CRITICAL FIX: Mutation logic was unreachable due to early return above
        # Now mutations will execute when should_mutate is True
        if should_mutate and current_attempts < MAX_EVOLUTION_ATTEMPTS:
            print(f"🧬 PHASE C: Mutation triggered for {strategy_id} (reason: {mutation_reason}, attempts: {current_attempts})")
            # PHASE C: Mutate strategy - prioritize indicator mutation when winrate < threshold
            if win_rate < 0.60:
                # PHASE C: When winrate < threshold, mutate indicators
                print(f"🧬 PHASE C: Mutating indicators for {strategy_id} (reason: {mutation_reason})")
                try:
                    # PHASE C: Force indicator substitution mutation
                    indicator_mutation = self.mutation_engine._mutate_indicator_substitution(strategy)
                    mutations = [indicator_mutation]
                except Exception as e:
                    # Fallback to normal mutation if indicator substitution fails
                    print(f"⚠️  PHASE C: Indicator substitution failed, using normal mutation: {e}")
                    mutations = self.mutation_engine.mutate_strategy(strategy, num_mutations=1)
            else:
                # PHASE C: Normal mutation
                mutations = self.mutation_engine.mutate_strategy(strategy, num_mutations=2)
            
            action = "mutated"
            for mutation in mutations:
                print(f"🧬 PHASE C: mutated {strategy_id} → new child (type: {mutation.get('mutation_type', 'unknown')})")
                # Create new strategy from mutation
                mutated_data = mutation.get("mutated_strategy", mutation)  # Handle both formats
                
                # Extract parent IDs for lineage if crossover
                parent_ids = [strategy_id]
                if mutation.get("mutation_type") == "crossover":
                    mutation_params = mutation.get("mutation_params", {})
                    parent1_id = mutation_params.get("parent1_id")
                    parent2_id = mutation_params.get("parent2_id")
                    if parent1_id and parent2_id:
                        parent_ids = [parent1_id, parent2_id]
                
                # Calculate royalty eligibility before creating strategy
                from ..strategy_engine.mutation_royalty import mutation_royalty_calculator
                
                # Find original strategy
                original_strategy_id = self._find_original_strategy(strategy_id, db)
                original_strategy = crud.get_user_strategy(db, original_strategy_id) if original_strategy_id else strategy
                
                # Count mutations from original
                mutation_count = self._count_mutations_from_original(original_strategy_id, strategy_id, db) + 1
                
                # Calculate royalty eligibility
                original_dict = {
                    "ruleset": original_strategy.ruleset,
                    "parameters": original_strategy.parameters
                }
                mutated_dict = {
                    "ruleset": mutated_data.get("ruleset", strategy.ruleset),
                    "parameters": mutated_data.get("parameters", strategy.parameters)
                }
                
                royalty_eligibility = mutation_royalty_calculator.determine_royalty_eligibility(
                    original_dict,
                    mutated_dict,
                    mutation_count
                )
                
                new_strategy = crud.create_user_strategy(
                    db=db,
                    user_id=strategy.user_id,
                    name=mutated_data.get("name", f"{strategy.name} (Mutated)"),
                    description=mutated_data.get("description", ""),
                    parameters=mutated_data.get("parameters", strategy.parameters),
                    ruleset=mutated_data.get("ruleset", strategy.ruleset),
                    asset_type=mutated_data.get("asset_type", strategy.asset_type),
                )
                
                # Create lineage record(s) for all parents
                for parent_id in parent_ids:
                    crud.create_strategy_lineage(
                        db=db,
                        parent_strategy_id=parent_id,
                        child_strategy_id=new_strategy.id,
                        mutation_type=mutation.get("mutation_type", "mutation"),
                        creator_user_id=strategy.user_id,
                    )
                
                # Record mutation event in MCN (non-blocking)
                try:
                    if self.mcn_adapter and self.mcn_adapter.is_available:
                        self.mcn_adapter.record_event(
                            event_type="strategy_mutated",
                            payload={
                                "parent_strategy_id": strategy_id,
                                "child_strategy_id": new_strategy.id,
                                "mutation_type": mutation["mutation_type"],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                            strategy_id=strategy_id,
                        )
                except Exception as e:
                    # MCN errors should not block evolution
                    print(f"⚠️  MCN event recording failed (non-fatal): {e}")
            
            # Increment evolution attempts
            crud.update_user_strategy(
                db=db,
                strategy_id=strategy_id,
                evolution_attempts=(strategy.evolution_attempts or 0) + 1
            )
            
            action = "mutated"
        
        return {
            "action": action,
            "old_status": current_status,
            "new_status": new_status,
            "score": score,
        }
    
    def _find_original_strategy(self, strategy_id: str, db: Session) -> str:
        """Find original strategy by traversing lineage backwards."""
        from ..db import crud
        parent_lineages = crud.get_strategy_lineages_by_child(db, strategy_id)
        
        if not parent_lineages:
            # This is the original
            return strategy_id
        
        # Recursively find original
        parent_id = parent_lineages[0].parent_strategy_id
        return self._find_original_strategy(parent_id, db)
    
    def _count_mutations_from_original(self, original_strategy_id: str, current_strategy_id: str, db: Session) -> int:
        """Count number of mutations from original strategy."""
        if original_strategy_id == current_strategy_id:
            return 0
        
        from ..db import crud
        parent_lineages = crud.get_strategy_lineages_by_child(db, current_strategy_id)
        
        if not parent_lineages:
            return 0
        
        parent_id = parent_lineages[0].parent_strategy_id
        return 1 + self._count_mutations_from_original(original_strategy_id, parent_id, db)
    
    def _enforce_strategy_limit(self, db: Session, max_strategies: int):
        """
        Enforce maximum number of active strategies.
        Keep only the best performers (by score).
        """
        from ..db.models import UserStrategy
        all_strategies = db.query(UserStrategy).filter(
            UserStrategy.is_active == True
        ).all()
        active_strategies = [s for s in all_strategies if s.status != StrategyStatus.DISCARDED]
        
        if len(active_strategies) <= max_strategies:
            return
        
        # Sort by score (descending), keep top N
        sorted_strategies = sorted(
            active_strategies,
            key=lambda s: s.score if s.score is not None else 0.0,
            reverse=True
        )
        
        # Mark excess strategies as inactive
        for strategy in sorted_strategies[max_strategies:]:
            crud.update_user_strategy(
                db=db,
                strategy_id=strategy.id,
                is_active=False
            )
            print(f"🔇 Deactivated strategy {strategy.id} (limit reached)")


def run_evolution_worker_once():
    """Run evolution worker once (for testing or manual trigger)."""
    from ..db.session import get_db
    db = next(get_db())
    try:
        worker = EvolutionWorker()
        stats = worker.run_evolution_cycle(db)
        return stats
    finally:
        db.close()


def run_evolution_worker_loop():
    """Run evolution worker in a continuous loop (for production)."""
    from ..db.session import get_db
    from ..utils.logger import log
    import os
    
    # Use EVOLUTION_INTERVAL_SECONDS from config (default: 480s / 8 minutes)
    interval_seconds = EVOLUTION_INTERVAL_SECONDS
    
    log(f"🚀 Evolution worker started (interval: {interval_seconds} seconds)")
    
    while True:
        try:
            db = next(get_db())
            try:
                worker = EvolutionWorker()
                stats = worker.run_evolution_cycle(db)
                log(f"✅ Evolution cycle complete: {stats}")
            finally:
                db.close()
        except Exception as e:
            log(f"❌ Evolution worker error: {e}")
            import traceback
            traceback.print_exc()
        
        # PHASE C: Sleep for configured interval
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # Run once for testing
    run_evolution_worker_once()

