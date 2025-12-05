#!/usr/bin/env python3
"""
PHASE 6: Load Proven Strategies into MCN
Generates embeddings, stores in MCN memory, populates strategy lineage,
improves regime associations, and improves similarity search.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import numpy as np

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.brain.mcn_adapter import get_mcn_adapter
from backend.utils.logger import log


def load_proven_strategies(file_path: Path) -> List[Dict[str, Any]]:
    """Load proven strategies from JSON file."""
    if not file_path.exists():
        log(f"❌ Strategies file not found: {file_path}")
        return []
    
    with open(file_path, 'r') as f:
        strategies = json.load(f)
    
    log(f"✅ Loaded {len(strategies)} strategies from {file_path}")
    return strategies


def create_strategy_embedding(mcn_adapter, strategy: Dict[str, Any]) -> np.ndarray:
    """Create embedding vector for a strategy."""
    # Create rich text representation
    text_parts = [
        f"strategy_name: {strategy.get('name', 'unknown')}",
        f"description: {strategy.get('description', '')}",
        f"market: {strategy.get('market', 'unknown')}",
        f"timeframe: {strategy.get('timeframe', 'unknown')}",
    ]
    
    # Add entry rules
    if "entry_rules" in strategy:
        entry_text = "entry: " + " ".join([
            f"{rule.get('indicator', '')}_{rule.get('condition', '')}"
            for rule in strategy["entry_rules"]
        ])
        text_parts.append(entry_text)
    
    # Add exit rules
    if "exit_rules" in strategy:
        exit_text = "exit: " + " ".join([
            f"{rule.get('indicator', '')}_{rule.get('condition', '')}"
            for rule in strategy["exit_rules"]
        ])
        text_parts.append(exit_text)
    
    # Add risk parameters
    if "risk" in strategy:
        risk = strategy["risk"]
        text_parts.append(f"risk_stop_loss: {risk.get('stop_loss_pct', 0)}")
        text_parts.append(f"risk_take_profit: {risk.get('take_profit_pct', 0)}")
    
    # Add performance metrics
    text_parts.append(f"confidence: {strategy.get('confidence', 0)}")
    text_parts.append(f"historical_winrate: {strategy.get('historical_winrate', 0)}")
    text_parts.append(f"expected_rr: {strategy.get('expected_rr', 0)}")
    
    # Create embedding
    text = " ".join(text_parts)
    return mcn_adapter._embed_text(text)


def store_strategy_in_mcn(mcn_adapter, strategy: Dict[str, Any], embedding: np.ndarray):
    """Store strategy in MCN with metadata."""
    if not mcn_adapter.is_available or not mcn_adapter.mcn:
        log("⚠️  MCN not available, skipping strategy storage")
        return False
    
    try:
        # Prepare metadata
        meta = {
            "event_type": "proven_strategy",
            "strategy_name": strategy.get("name", "unknown"),
            "description": strategy.get("description", ""),
            "market": strategy.get("market", "unknown"),
            "timeframe": strategy.get("timeframe", "unknown"),
            "confidence": strategy.get("confidence", 0),
            "historical_winrate": strategy.get("historical_winrate", 0),
            "expected_rr": strategy.get("expected_rr", 0),
            "entry_rules": strategy.get("entry_rules", []),
            "exit_rules": strategy.get("exit_rules", []),
            "risk": strategy.get("risk", {}),
            "examples": strategy.get("examples", []),
        }
        
        # Ensure embedding is 2D
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        
        # Store in MCN
        mcn_adapter.mcn.add(embedding.astype(np.float32), meta_batch=[meta])
        
        log(f"✅ Stored strategy '{strategy.get('name')}' in MCN")
        return True
    except Exception as e:
        log(f"❌ Failed to store strategy '{strategy.get('name')}': {e}")
        import traceback
        traceback.print_exc()
        return False


def populate_strategy_lineage(mcn_adapter, strategies: List[Dict[str, Any]]):
    """Create lineage relationships between similar strategies."""
    if not mcn_adapter.is_available or not mcn_adapter.mcn:
        log("⚠️  MCN not available, skipping lineage population")
        return
    
    log("🔗 Creating strategy lineage relationships...")
    
    # Group strategies by similarity (same market, timeframe, similar rules)
    strategy_groups = {}
    for i, strategy in enumerate(strategies):
        key = f"{strategy.get('market')}_{strategy.get('timeframe')}"
        if key not in strategy_groups:
            strategy_groups[key] = []
        strategy_groups[key].append((i, strategy))
    
    # Record lineage events
    for group_key, group_strategies in strategy_groups.items():
        if len(group_strategies) > 1:
            # Create lineage event
            lineage_meta = {
                "event_type": "strategy_lineage",
                "group_key": group_key,
                "strategy_count": len(group_strategies),
                "strategies": [s[1].get("name") for s in group_strategies],
            }
            
            # Create embedding for lineage
            lineage_text = f"lineage_group: {group_key} strategies: {' '.join([s[1].get('name', '') for s in group_strategies])}"
            lineage_embedding = mcn_adapter._embed_text(lineage_text)
            
            if lineage_embedding.ndim == 1:
                lineage_embedding = lineage_embedding.reshape(1, -1)
            
            try:
                mcn_adapter.mcn.add(lineage_embedding.astype(np.float32), meta_batch=[lineage_meta])
                log(f"✅ Created lineage group for {group_key} with {len(group_strategies)} strategies")
            except Exception as e:
                log(f"⚠️  Failed to create lineage: {e}")


def improve_regime_associations(mcn_adapter, strategies: List[Dict[str, Any]]):
    """Associate strategies with market regimes based on their characteristics."""
    if not mcn_adapter.is_available or not mcn_adapter.mcn:
        log("⚠️  MCN not available, skipping regime associations")
        return
    
    log("📊 Creating regime associations...")
    
    # Map strategies to regimes based on their characteristics
    regime_mapping = {
        "trending": ["Momentum Breakout Strategy", "Trend Following EMA Crossover", "Multi-Timeframe Trend Alignment"],
        "ranging": ["Mean Reversion RSI Strategy", "Support/Resistance Bounce Strategy", "VWAP Bounce Strategy"],
        "volatile": ["Bollinger Band Squeeze Strategy", "Low Volatility Breakout Strategy", "Earnings Play Strategy"],
    }
    
    for regime, strategy_names in regime_mapping.items():
        matching_strategies = [s for s in strategies if s.get("name") in strategy_names]
        
        for strategy in matching_strategies:
            regime_meta = {
                "event_type": "regime_association",
                "regime": regime,
                "strategy_name": strategy.get("name"),
                "confidence": strategy.get("confidence", 0),
            }
            
            regime_text = f"regime: {regime} strategy: {strategy.get('name', '')}"
            regime_embedding = mcn_adapter._embed_text(regime_text)
            
            if regime_embedding.ndim == 1:
                regime_embedding = regime_embedding.reshape(1, -1)
            
            try:
                mcn_adapter.mcn.add(regime_embedding.astype(np.float32), meta_batch=[regime_meta])
                log(f"✅ Associated '{strategy.get('name')}' with regime '{regime}'")
            except Exception as e:
                log(f"⚠️  Failed to create regime association: {e}")


def main():
    """Main entry point."""
    log("🚀 Starting proven strategies MCN loading...")
    
    # Get MCN adapter
    mcn_adapter = get_mcn_adapter()
    if not mcn_adapter.is_available:
        log("❌ MCN not available. Please ensure MemoryClusterNetworks is installed.")
        return 1
    
    # Load strategies
    strategies_file = Path(__file__).parent / "proven_strategies.json"
    strategies = load_proven_strategies(strategies_file)
    
    if not strategies:
        log("❌ No strategies to load")
        return 1
    
    log(f"📚 Processing {len(strategies)} strategies...")
    
    # Process each strategy
    stored_count = 0
    for i, strategy in enumerate(strategies, 1):
        log(f"  [{i}/{len(strategies)}] Processing: {strategy.get('name', 'Unknown')}")
        
        # Create embedding
        embedding = create_strategy_embedding(mcn_adapter, strategy)
        
        # Store in MCN
        if store_strategy_in_mcn(mcn_adapter, strategy, embedding):
            stored_count += 1
    
    log(f"✅ Stored {stored_count}/{len(strategies)} strategies in MCN")
    
    # Populate lineage
    populate_strategy_lineage(mcn_adapter, strategies)
    
    # Improve regime associations
    improve_regime_associations(mcn_adapter, strategies)
    
    # Save MCN state
    if mcn_adapter.save_state():
        log("✅ MCN state saved successfully")
    else:
        log("⚠️  Failed to save MCN state")
    
    log("🎉 Proven strategies loaded into MCN successfully!")
    return 0


def load_seed_strategies_into_mcn(db: Session, seed_file: Path) -> int:
    """
    Load seed strategies from JSON file into database and MCN.
    
    This is a wrapper function that combines:
    - Loading strategies into database (via seed_loader)
    - Loading strategies into MCN memory
    
    Args:
        db: Database session
        seed_file: Path to proven_strategies.json file
    
    Returns:
        Number of strategies loaded
    """
    from ..strategy_engine.seed_loader import load_seed_strategies
    
    # First, load strategies into database
    seed_dir = seed_file.parent
    db_count = load_seed_strategies(db, seed_dir)
    
    # Then, load into MCN using existing MCN loading logic
    mcn_adapter = get_mcn_adapter()
    if not mcn_adapter.is_available:
        log("⚠️  MCN not available, skipping MCN loading")
        return db_count
    
    # Load strategies from JSON
    strategies = load_proven_strategies(seed_file)
    if not strategies:
        return db_count
    
    log(f"📚 Processing {len(strategies)} strategies for MCN...")
    
    # Process each strategy for MCN
    stored_count = 0
    for i, strategy in enumerate(strategies, 1):
        log(f"  [{i}/{len(strategies)}] Processing: {strategy.get('name', 'Unknown')}")
        
        # Create embedding
        embedding = create_strategy_embedding(mcn_adapter, strategy)
        
        # Store in MCN
        if store_strategy_in_mcn(mcn_adapter, strategy, embedding):
            stored_count += 1
    
    log(f"✅ Stored {stored_count}/{len(strategies)} strategies in MCN")
    
    # Populate lineage
    populate_strategy_lineage(mcn_adapter, strategies)
    
    # Improve regime associations
    improve_regime_associations(mcn_adapter, strategies)
    
    # Save MCN state
    if mcn_adapter.save_state():
        log("✅ MCN state saved successfully")
    
    return db_count


if __name__ == "__main__":
    sys.exit(main())

