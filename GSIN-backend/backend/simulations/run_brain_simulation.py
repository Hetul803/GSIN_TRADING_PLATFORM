# backend/simulations/run_brain_simulation.py
"""
Brain Simulation Script - Test Brain & MCN behavior offline.

This script runs a series of backtests, evolution cycles, and signal generation
without hitting real APIs or executing real trades. Useful for:
- Validating Brain logic
- Testing strategy evolution
- Verifying MCN learning
- Sanity-checking before production

Usage:
    python -m backend.simulations.run_brain_simulation
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db import crud
from backend.strategy_engine.backtest_engine import BacktestEngine
from backend.strategy_engine.scoring import score_strategy
from backend.strategy_engine.status_manager import determine_strategy_status, StrategyStatus
from backend.brain.brain_service import BrainService
from backend.brain.mcn_adapter import get_mcn_adapter


def run_simulation():
    """Run a complete Brain simulation."""
    print("🧠 Starting Brain Simulation...")
    print("=" * 60)
    
    db = next(get_db())
    try:
        # Step 1: Load or create test strategies
        print("\n📋 Step 1: Loading test strategies...")
        strategies = crud.list_user_strategies(db, user_id=None, active_only=True)
        if not strategies:
            print("⚠️  No strategies found. Please create strategies first.")
            return
        
        print(f"   Found {len(strategies)} strategies")
        
        # Step 2: Run backtests
        print("\n📊 Step 2: Running backtests...")
        backtest_engine = BacktestEngine()
        test_symbols = ["AAPL", "MSFT", "GOOGL"]
        results_summary = []
        
        for strategy in strategies[:5]:  # Test first 5 strategies
            symbol = test_symbols[0]  # Use first symbol
            timeframe = strategy.ruleset.get("timeframe", "1d")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            
            try:
                print(f"   Backtesting {strategy.name} ({strategy.id[:8]}...)")
                results = backtest_engine.run_backtest(
                    symbol=symbol,
                    ruleset=strategy.ruleset,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    train_test_split=0.7
                )
                
                score = score_strategy(results, use_test_metrics=True)
                new_status, is_proposable = determine_strategy_status(
                    strategy={"id": strategy.id, "evolution_attempts": strategy.evolution_attempts or 0, "status": strategy.status or "experiment"},
                    backtest_results=results,
                    current_status=strategy.status or "experiment"
                )
                
                results_summary.append({
                    "strategy_id": strategy.id,
                    "name": strategy.name,
                    "score": score,
                    "status": new_status,
                    "is_proposable": is_proposable,
                    "win_rate": results.get("win_rate", 0.0),
                    "total_trades": results.get("total_trades", 0),
                    "overfitting_detected": results.get("overfitting_detected", False),
                })
                
                print(f"      Score: {score:.3f}, Status: {new_status}, Proposable: {is_proposable}")
            except Exception as e:
                print(f"      ❌ Error: {e}")
                continue
        
        # Step 3: Check MCN stats
        print("\n🧠 Step 3: Checking MCN stats...")
        mcn_adapter = get_mcn_adapter()
        if mcn_adapter.is_available:
            print(f"   MCN Available: ✅")
            print(f"   Storage Path: {mcn_adapter.storage_path}")
        else:
            print(f"   MCN Available: ❌")
        
        # Step 4: Test Brain signal generation
        print("\n🎯 Step 4: Testing Brain signal generation...")
        brain_service = BrainService()
        proposable_strategies = [s for s in results_summary if s["is_proposable"]]
        
        if proposable_strategies:
            test_strategy = proposable_strategies[0]
            test_user_id = "test_user"  # Would need real user ID
            
            try:
                # Get a real user ID from DB
                from backend.db.models import User
                users = db.query(User).limit(1).all()
                if users:
                    test_user_id = users[0].id
                
                signal = brain_service.generate_signal(
                    strategy_id=test_strategy["strategy_id"],
                    user_id=test_user_id,
                    symbol="AAPL",
                    db=db
                )
                
                print(f"   ✅ Signal generated for {test_strategy['name']}:")
                print(f"      Side: {signal.side}, Entry: ${signal.entry:.2f}")
                print(f"      Confidence: {signal.confidence:.2%}, Risk: {signal.risk_level}")
                print(f"      Explanation: {signal.explanation[:100]}...")
            except Exception as e:
                print(f"   ❌ Signal generation failed: {e}")
        else:
            print("   ⚠️  No proposable strategies to test signal generation")
        
        # Step 5: Summary
        print("\n📈 Step 5: Simulation Summary")
        print("=" * 60)
        print(f"Total strategies tested: {len(results_summary)}")
        print(f"Proposable strategies: {len([r for r in results_summary if r['is_proposable']])}")
        print(f"Average score: {sum(r['score'] for r in results_summary) / len(results_summary) if results_summary else 0:.3f}")
        print(f"Overfitting detected: {len([r for r in results_summary if r.get('overfitting_detected')])}")
        
        print("\n✅ Simulation complete!")
        
    finally:
        db.close()


if __name__ == "__main__":
    run_simulation()

