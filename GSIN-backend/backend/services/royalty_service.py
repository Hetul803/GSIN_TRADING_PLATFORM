# backend/services/royalty_service.py
"""
PHASE 5: Royalty service for calculating and recording royalties on profitable trades.
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from ..db.models import Trade, UserStrategy, User, RoyaltyLedger, SubscriptionTier, SubscriptionPlan
from ..db import crud


class RoyaltyService:
    """Service for calculating and recording royalties."""
    
    # Royalty rate: 5% for ALL tiers (strategy creators get 5% when others use their strategies)
    ROYALTY_RATE = 0.05  # 5% royalty to strategy creator
    
    # Default platform fee (used as fallback if plan not found)
    DEFAULT_PLATFORM_FEE_RATE = 0.05  # 5% default platform fee
    
    def calculate_royalty(
        self,
        trade: Trade,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate royalty for a profitable trade.
        
        Royalty Logic:
        - Strategy creators receive mutation-based royalty (5%, 3%, 1.5%, or 0%) based on similarity and mutation count
        - 5%: Similarity > 70% AND mutations < 3
        - 3%: Similarity 50-70% AND mutations < 3
        - 1.5%: Similarity 40-50% OR mutations = 3
        - 0%: Similarity < 40% OR mutations > 3
        - Platform fee is based on strategy creator's subscription plan (3-7% based on tier)
        - Platform fee is deducted from the royalty amount
        
        Returns:
            Dictionary with royalty details if trade is profitable and has strategy_id, None otherwise
        """
        # Only calculate royalties for profitable trades
        if not trade.realized_pnl or trade.realized_pnl <= 0:
            return None
        
        # Only calculate if trade was executed using a strategy
        if not trade.strategy_id:
            return None
        
        # Get strategy
        strategy = crud.get_user_strategy(db, trade.strategy_id)
        if not strategy:
            return None
        
        # Get strategy owner
        strategy_owner = crud.get_user_by_id(db, strategy.user_id)
        if not strategy_owner:
            return None
        
        # Calculate mutation-based royalty rate
        # Find original strategy and calculate mutation distance
        from ..strategy_engine.mutation_royalty import mutation_royalty_calculator
        
        # Find original strategy by traversing lineage backwards
        original_strategy_id = self._find_original_strategy(strategy.id, db)
        original_strategy = crud.get_user_strategy(db, original_strategy_id) if original_strategy_id else strategy
        
        # Count mutations from original
        mutation_count = self._count_mutations_from_original(original_strategy_id, strategy.id, db)
        
        # Calculate royalty eligibility based on mutation distance
        original_dict = {
            "ruleset": original_strategy.ruleset,
            "parameters": original_strategy.parameters
        }
        current_dict = {
            "ruleset": strategy.ruleset,
            "parameters": strategy.parameters
        }
        
        royalty_eligibility = mutation_royalty_calculator.determine_royalty_eligibility(
            original_dict,
            current_dict,
            mutation_count
        )
        
        # Use mutation-based royalty rate (5%, 3%, 1.5%, or 0%)
        royalty_rate = royalty_eligibility.royalty_percent
        
        # Get platform fee from strategy owner's subscription plan (3-7% based on tier)
        platform_fee_rate = self.DEFAULT_PLATFORM_FEE_RATE  # Default fallback (5%)
        if strategy_owner.current_plan_id:
            plan = crud.get_subscription_plan(db, strategy_owner.current_plan_id)
            if plan and plan.platform_fee_percent is not None:
                platform_fee_rate = plan.platform_fee_percent / 100.0  # Convert percent to decimal
        # Platform fee varies 3-7% based on subscription tier (handled in plan.platform_fee_percent)
        
        # Calculate royalty and platform fees
        trade_profit = trade.realized_pnl
        
        # Royalty to creator = profit * royalty_rate (mutation-based: 5%, 3%, 1.5%, or 0%)
        creator_royalty = trade_profit * royalty_rate
        
        # Platform fee = royalty_amount * platform_fee_rate (based on creator's plan)
        platform_fee = creator_royalty * platform_fee_rate
        
        # Net amount to creator (royalty minus platform fee)
        net_amount = creator_royalty - platform_fee
        
        return {
            "strategy_owner_id": strategy.user_id,
            "strategy_id": strategy.id,
            "trade_id": trade.id,
            "profit": trade_profit,
            "creator_royalty": creator_royalty,
            "royalty_rate": royalty_rate,
            "platform_fee": platform_fee,
            "platform_fee_rate": platform_fee_rate,  # Use calculated rate from plan
            "net_amount": net_amount
        }
    
    def record_royalty(
        self,
        trade: Trade,
        db: Session
    ) -> Optional[RoyaltyLedger]:
        """
        Calculate and record royalty for a profitable trade.
        
        Returns:
            RoyaltyLedger entry if royalty was recorded, None otherwise
        """
        royalty_data = self.calculate_royalty(trade, db)
        if not royalty_data:
            return None
        
        # FINAL ALIGNMENT: Create royalty ledger entry with all fields
        royalty_entry = RoyaltyLedger(
            id=str(uuid.uuid4()),
            user_id=royalty_data["strategy_owner_id"],
            strategy_id=royalty_data["strategy_id"],
            trade_id=royalty_data["trade_id"],
            royalty_amount=royalty_data["creator_royalty"],  # Store creator royalty
            royalty_rate=royalty_data["royalty_rate"],
            platform_fee=royalty_data["platform_fee"],
            platform_fee_rate=royalty_data["platform_fee_rate"],
            net_amount=royalty_data["net_amount"],
            trade_profit=royalty_data["profit"],
        )
        
        db.add(royalty_entry)
        db.commit()
        db.refresh(royalty_entry)
        
        return royalty_entry
    
    def _find_original_strategy(self, strategy_id: str, db: Session) -> str:
        """Find original strategy by traversing lineage backwards."""
        from ..db.models import StrategyLineage
        parent_lineages = db.query(StrategyLineage).filter(
            StrategyLineage.child_strategy_id == strategy_id
        ).all()
        
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
        
        from ..db.models import StrategyLineage
        parent_lineages = db.query(StrategyLineage).filter(
            StrategyLineage.child_strategy_id == current_strategy_id
        ).all()
        
        if not parent_lineages:
            return 0
        
        parent_id = parent_lineages[0].parent_strategy_id
        return 1 + self._count_mutations_from_original(original_strategy_id, parent_id, db)


# Singleton instance
royalty_service = RoyaltyService()

