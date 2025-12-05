# backend/strategy_engine/seed_loader.py
"""
Seed Strategy Loader - Loads 100 predefined strategies at startup.
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..db import crud
from ..db.models import AssetType, UserStrategy
from .backtest_engine import BacktestEngine
from .scoring import score_strategy
from .mutation_engine import MutationEngine
from ..brain.mcn_adapter import get_mcn_adapter
from .strategy_fingerprint import create_strategy_fingerprint
from .status_manager import StrategyStatus


def load_seed_strategies(db: Session, seed_dir: Path = None) -> int:
    """
    Load seed strategies from JSON files.
    
    Args:
        db: Database session
        seed_dir: Directory containing seed strategy JSON files (default: seed_strategies/)
    
    Returns:
        Number of strategies loaded
    """
    if seed_dir is None:
        # Default to seed_strategies/ directory in project root
        seed_dir = Path(__file__).resolve().parents[2] / "seed_strategies"
    
    if not seed_dir.exists():
        print(f"⚠️  Seed strategies directory not found: {seed_dir}")
        print("   Creating sample strategies...")
        _create_sample_strategies(seed_dir)
    
    # Load all JSON files
    strategy_files = list(seed_dir.glob("*.json"))
    if not strategy_files:
        print(f"⚠️  No strategy files found in {seed_dir}")
        return 0
    
    loaded_count = 0
    backtest_engine = BacktestEngine()
    mutation_engine = MutationEngine()
    mcn_adapter = get_mcn_adapter()
    
    # Get or create system user for seed strategies
    from ..db.models import User, UserRole
    system_user_id = os.getenv("SEED_STRATEGIES_USER_ID")
    
    if system_user_id:
        # Check if user exists
        system_user = db.query(User).filter(User.id == system_user_id).first()
        if not system_user:
            print(f"⚠️  User ID '{system_user_id}' not found, will use admin user instead...")
            system_user_id = None
    
    if not system_user_id:
        # Try to find existing admin user
        admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if admin_user:
            system_user_id = admin_user.id
            print(f"  ✅ Using existing admin user: {admin_user.email}")
        else:
            # Create system user (only if no admin exists)
            import uuid
            try:
                system_user = User(
                    id=str(uuid.uuid4()),
                    email="system@gsin.fin",
                    name="System",
                    role=UserRole.ADMIN,
                )
                db.add(system_user)
                db.commit()
                db.refresh(system_user)
                system_user_id = system_user.id
                print(f"  ✅ Created system user: {system_user.email}")
            except Exception as e:
                # If creation fails (e.g., duplicate email), try to get existing system user
                existing_system = db.query(User).filter(User.email == "system@gsin.fin").first()
                if existing_system:
                    system_user_id = existing_system.id
                    print(f"  ✅ Using existing system user: {existing_system.email}")
                else:
                    # Last resort: use first user in database
                    first_user = db.query(User).first()
                    if first_user:
                        system_user_id = first_user.id
                        print(f"  ⚠️  Using first available user: {first_user.email}")
                    else:
                        print(f"  ❌ Failed to create or find system user: {e}")
                        raise ValueError("Cannot load seed strategies: No system user available")
    
    # PHASE 2: Collect all strategies first, then deduplicate using fingerprints
    all_strategy_data = []
    
    for strategy_file in strategy_files:
        try:
            with open(strategy_file, 'r') as f:
                data = json.load(f)
                # Handle both single dict and list of dicts
                if isinstance(data, list):
                    all_strategy_data.extend(data)
                else:
                    all_strategy_data.append(data)
        except Exception as e:
            print(f"  ⚠️  Failed to read {strategy_file.name}: {e}")
            continue
    
    # Also load from proven_strategies.json if it exists (check both seed_dir and backend/seed_strategies)
    proven_files = [
        seed_dir / "proven_strategies.json",
        Path(__file__).resolve().parents[1] / "seed_strategies" / "proven_strategies.json"
    ]
    
    for proven_file in proven_files:
        if proven_file.exists():
            try:
                with open(proven_file, 'r') as f:
                    proven_data = json.load(f)
                    if isinstance(proven_data, list):
                        all_strategy_data.extend(proven_data)
                        print(f"  📚 Loaded {len(proven_data)} strategies from {proven_file.name}")
                    else:
                        all_strategy_data.append(proven_data)
                        print(f"  📚 Loaded 1 strategy from {proven_file.name}")
                break  # Only load from first found file
            except Exception as e:
                print(f"  ⚠️  Failed to read {proven_file}: {e}")
                continue
    
    # Get existing strategy fingerprints to avoid duplicates
    existing_strategies = db.query(UserStrategy).filter(
        UserStrategy.status != StrategyStatus.DISCARDED,
        UserStrategy.status != StrategyStatus.REJECTED,
        UserStrategy.status != StrategyStatus.DUPLICATE
    ).all()
    
    existing_fingerprints = set()
    for existing in existing_strategies:
        try:
            fp = create_strategy_fingerprint(existing.ruleset)
            existing_fingerprints.add(fp)
        except Exception:
            pass  # Skip if fingerprinting fails
    
    # Process and deduplicate strategies
    seen_fingerprints = set()
    unique_strategies = []
    
    for strategy_data in all_strategy_data:
        try:
            # Normalize ruleset for fingerprinting
            from .strategy_normalizer import normalize_strategy_ruleset
            raw_ruleset = strategy_data.get("ruleset", {})
            normalized_ruleset = normalize_strategy_ruleset(raw_ruleset)
            
            # Create fingerprint
            fp = create_strategy_fingerprint(normalized_ruleset)
            
            # Skip if duplicate
            if fp in existing_fingerprints or fp in seen_fingerprints:
                print(f"  ⏭️  Strategy '{strategy_data.get('name')}' is duplicate (fingerprint match), skipping...")
                continue
            
            seen_fingerprints.add(fp)
            unique_strategies.append((strategy_data, normalized_ruleset))
        except Exception as e:
            print(f"  ⚠️  Failed to process strategy '{strategy_data.get('name', 'unknown')}': {e}")
            continue
    
    if len(unique_strategies) == 0:
        print(f"  ✅ All {len(all_strategy_data)} strategies already exist in database (skipping duplicates)")
    else:
        duplicates = len(all_strategy_data) - len(unique_strategies)
        print(f"  📊 Found {len(all_strategy_data)} total strategies: {len(unique_strategies)} new, {duplicates} duplicates")
    
    # Now load unique strategies
    for strategy_data, normalized_ruleset in unique_strategies:
        try:
            
            # Map asset_type string to enum
            asset_type_str = strategy_data.get("asset_type", "STOCK")
            try:
                asset_type = AssetType[asset_type_str]
            except KeyError:
                asset_type = AssetType.STOCK  # Default to STOCK
            
            # Seed strategies go through same flow as user uploads: pending_review → Monitoring Worker → experiment
            # Extract symbol for backtest
            backtest_symbol = strategy_data.get("backtest_symbol") or strategy_data.get("symbol_universe")
            if isinstance(backtest_symbol, list):
                backtest_symbol = backtest_symbol[0] if backtest_symbol else None
            
            strategy = crud.create_user_strategy(
                db=db,
                user_id=system_user_id,
                name=strategy_data.get("name", "Unknown Strategy"),
                description=strategy_data.get("description", ""),
                parameters=strategy_data.get("parameters", {}),
                ruleset=normalized_ruleset,  # Use normalized ruleset
                asset_type=asset_type,
                initial_status=StrategyStatus.PENDING_REVIEW,  # Seed strategies start as pending_review, go through Monitoring Worker
            )
            
            # Ensure strategy is active (Monitoring Worker will process it)
            # StrategyStatus is already imported at the top of the file
            crud.update_user_strategy(
                db=db,
                strategy_id=strategy.id,
                is_active=True,  # Mark as active so Monitoring Worker picks it up
                status=StrategyStatus.PENDING_REVIEW,  # Start as pending_review, Monitoring Worker will check and promote to experiment
            )
            
            print(f"  ✅ Created strategy: {strategy.name} (active, status=pending_review)")
            
            # Run initial backtest if symbol provided
            # Note: Seed strategies are created with pending_review status and will be processed by:
            # 1. Monitoring Worker (checks duplicates, sanity, then promotes to experiment)
            # 2. Evolution Worker (runs backtests, mutates, promotes)
            if backtest_symbol:
                try:
                    symbol = backtest_symbol
                    timeframe = strategy_data.get("timeframe", "1d")
                    # Normalize timeframe
                    if timeframe.upper() == "1D":
                        timeframe = "1d"
                    start_date = datetime.now(timezone.utc).replace(year=2023, month=1, day=1)
                    end_date = datetime.now(timezone.utc)
                    
                    backtest_results = backtest_engine.run_backtest(
                        symbol=symbol,
                        ruleset=strategy.ruleset,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    
                    # Score strategy
                    score = score_strategy(backtest_results)
                    
                    # Save backtest (sharpe_ratio should be in results dict, not as direct argument)
                    crud.create_strategy_backtest(
                        db=db,
                        strategy_id=strategy.id,
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        total_return=backtest_results.get("total_return", 0.0),
                        win_rate=backtest_results.get("win_rate", 0.0),
                        max_drawdown=backtest_results.get("max_drawdown", 0.0),
                        avg_pnl=backtest_results.get("avg_pnl", 0.0),
                        total_trades=backtest_results.get("total_trades", 0),
                        results=backtest_results,  # sharpe_ratio is included in results dict
                    )
                    
                    # IMPROVEMENT 1: Determine status based on backtest results
                    from .status_manager import determine_strategy_status
                    total_trades = backtest_results.get("total_trades", 0)
                    win_rate = backtest_results.get("win_rate", 0.0)
                    max_drawdown = abs(backtest_results.get("max_drawdown", 0.0))
                    
                    # Determine if strategy should be candidate or proposable
                    new_status, is_proposable = determine_strategy_status(
                        total_trades=total_trades,
                        win_rate=win_rate,
                        max_drawdown=max_drawdown,
                        score=score,
                        current_status=StrategyStatus.EXPERIMENT
                    )
                    
                    # Update strategy with score, status, and backtest results
                    crud.update_user_strategy(
                        db=db,
                        strategy_id=strategy.id,
                        score=score,
                        status=new_status,
                        is_proposable=is_proposable,
                        last_backtest_at=datetime.now(timezone.utc),
                        last_backtest_results=backtest_results,
                    )
                    
                    status_msg = f"status={new_status}" + (", proposable" if is_proposable else "")
                    print(f"    📊 Backtested on {symbol}: {backtest_results.get('total_return', 0):.2f}% return, score: {score:.3f}, {status_msg}")
                    
                    # Record in MCN
                    mcn_adapter.record_event(
                        event_type="strategy_backtest",
                        payload={
                            "strategy_id": strategy.id,
                            "symbol": symbol,
                            "total_return": backtest_results.get("total_return", 0.0),
                            "win_rate": backtest_results.get("win_rate", 0.0),
                            "score": score,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        user_id=system_user_id,
                        strategy_id=strategy.id,
                    )
                except Exception as e:
                    print(f"    ⚠️  Backtest failed for {strategy.name}: {e}")
            
            loaded_count += 1
            
        except Exception as e:
            print(f"  ❌ Failed to load {strategy_file.name}: {e}")
            db.rollback()  # Rollback failed transaction
            continue
    
    # Mutate top performers
    if loaded_count > 0:
        print("\n  🔄 Mutating top performers...")
        _mutate_top_strategies(db, mutation_engine, mcn_adapter, system_user_id)
    
    return loaded_count


def _create_sample_strategies(seed_dir: Path):
    """Create sample strategy JSON files if directory doesn't exist."""
    seed_dir.mkdir(parents=True, exist_ok=True)
    
    sample_strategies = [
        {
            "name": "Simple Moving Average Crossover",
            "description": "Buy when fast SMA crosses above slow SMA, sell when it crosses below",
            "parameters": {"sma_fast": 12, "sma_slow": 26},
            "ruleset": {
                "indicators": [{"type": "sma", "period": 12}, {"type": "sma", "period": 26}],
                "conditions": [
                    {"type": "crossover", "fast": "sma_12", "slow": "sma_26", "direction": "above"}
                ],
                "timeframe": "1d"
            },
            "asset_type": "STOCK",
            "backtest_symbol": "AAPL",
            "timeframe": "1d"
        },
        {
            "name": "RSI Oversold/Overbought",
            "description": "Buy when RSI < 30, sell when RSI > 70",
            "parameters": {"rsi_period": 14, "oversold": 30, "overbought": 70},
            "ruleset": {
                "indicators": [{"type": "rsi", "period": 14}],
                "conditions": [
                    {"type": "rsi", "operator": "<", "threshold": 30, "action": "BUY"},
                    {"type": "rsi", "operator": ">", "threshold": 70, "action": "SELL"}
                ],
                "timeframe": "1d"
            },
            "asset_type": "STOCK",
            "backtest_symbol": "AAPL",
            "timeframe": "1d"
        },
    ]
    
    for i, strategy in enumerate(sample_strategies):
        file_path = seed_dir / f"strategy_{i+1:03d}.json"
        with open(file_path, 'w') as f:
            json.dump(strategy, f, indent=2)
    
    print(f"  ✅ Created {len(sample_strategies)} sample strategy files in {seed_dir}")


def _mutate_top_strategies(db: Session, mutation_engine, mcn_adapter, system_user_id: str, top_n: int = 10):
    """Mutate top N strategies by score."""
    from ..db.models import UserStrategy
    
    top_strategies = db.query(UserStrategy).filter(
        UserStrategy.user_id == system_user_id,
        UserStrategy.score.isnot(None)
    ).order_by(UserStrategy.score.desc()).limit(top_n).all()
    
    for strategy in top_strategies:
        try:
            mutations = mutation_engine.mutate_strategy(strategy, num_mutations=1)
            if mutations:
                # Create one mutation
                mutation = mutations[0]
                mutated_data = mutation.get("mutated_strategy", {})
                new_strategy = crud.create_user_strategy(
                    db=db,
                    user_id=system_user_id,
                    name=mutated_data.get("name", f"{strategy.name} - Mutated"),
                    description=mutated_data.get("description", f"Mutated from {strategy.name}"),
                    parameters=mutated_data.get("parameters", strategy.parameters),
                    ruleset=mutated_data.get("ruleset", strategy.ruleset),
                    asset_type=mutated_data.get("asset_type", strategy.asset_type),
                )
                
                # Create lineage
                crud.create_strategy_lineage(
                    db=db,
                    parent_strategy_id=strategy.id,
                    child_strategy_id=new_strategy.id,
                    mutation_type=mutation.get("mutation_type", "unknown"),
                    mutation_params=mutation.get("mutation_params"),
                    creator_user_id=system_user_id,
                )
                
                print(f"    🧬 Mutated {strategy.name} -> {new_strategy.name}")
        except Exception as e:
            print(f"    ⚠️  Mutation failed for {strategy.name}: {e}")

