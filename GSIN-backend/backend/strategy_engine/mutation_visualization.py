# backend/strategy_engine/mutation_visualization.py
"""
Mutation Visualization - Shows users how their strategies were mutated.

Provides:
- Mutation tree/graph visualization
- Detailed change log
- Before/after comparisons
- Similarity scores
- Royalty eligibility status
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session

from ..db import crud
from ..db.models import StrategyLineage, UserStrategy
from .mutation_royalty import mutation_royalty_calculator, MutationDistance


@dataclass
class MutationNode:
    """Represents a node in the mutation tree."""
    strategy_id: str
    strategy_name: str
    created_at: datetime
    similarity_to_original: float
    mutation_type: str
    mutation_params: Dict[str, Any]
    changes_summary: str
    royalty_eligible: bool
    royalty_percent: float
    is_brain_generated: bool


@dataclass
class MutationTree:
    """Complete mutation tree from original to current."""
    original_strategy_id: str
    original_strategy_name: str
    original_uploader_id: str
    nodes: List[MutationNode]
    total_mutations: int
    current_similarity: float
    current_royalty_eligible: bool
    current_royalty_percent: float


@dataclass
class MutationChange:
    """Represents a single change in a mutation."""
    change_type: str  # "parameter", "rule", "timeframe", "symbol", "indicator"
    field_name: str
    old_value: Any
    new_value: Any
    impact: str  # "low", "medium", "high"


class MutationVisualizationEngine:
    """
    Generates mutation visualization data for users.
    """
    
    def get_mutation_tree(
        self,
        strategy_id: str,
        db: Session
    ) -> Optional[MutationTree]:
        """
        Get complete mutation tree for a strategy.
        
        Args:
            strategy_id: Current strategy ID
            db: Database session
        
        Returns:
            MutationTree with all mutations from original
        """
        # Get current strategy
        current_strategy = crud.get_user_strategy(db, strategy_id)
        if not current_strategy:
            return None
        
        # Find original strategy (traverse lineage backwards)
        original_strategy_id = self._find_original_strategy(strategy_id, db)
        if not original_strategy_id:
            # This is the original strategy
            original_strategy_id = strategy_id
        
        original_strategy = crud.get_user_strategy(db, original_strategy_id)
        if not original_strategy:
            return None
        
        # Build mutation chain
        mutation_chain = self._build_mutation_chain(original_strategy_id, strategy_id, db)
        
        # Build nodes
        nodes = []
        for i, mutation in enumerate(mutation_chain):
            node = self._create_mutation_node(mutation, original_strategy, db, i + 1)
            nodes.append(node)
        
        # Get current strategy's royalty eligibility
        current_royalty = self._calculate_current_royalty(
            original_strategy,
            current_strategy,
            len(mutation_chain),
            db
        )
        
        return MutationTree(
            original_strategy_id=original_strategy_id,
            original_strategy_name=original_strategy.name,
            original_uploader_id=original_strategy.user_id,
            nodes=nodes,
            total_mutations=len(mutation_chain),
            current_similarity=current_royalty.mutation_distance.similarity_score,
            current_royalty_eligible=current_royalty.is_eligible,
            current_royalty_percent=current_royalty.royalty_percent
        )
    
    def get_mutation_changes(
        self,
        parent_strategy_id: str,
        child_strategy_id: str,
        db: Session
    ) -> List[MutationChange]:
        """
        Get detailed list of changes between parent and child strategy.
        
        Args:
            parent_strategy_id: Parent strategy ID
            child_strategy_id: Child strategy ID
            db: Database session
        
        Returns:
            List of MutationChange objects
        """
        parent = crud.get_user_strategy(db, parent_strategy_id)
        child = crud.get_user_strategy(db, child_strategy_id)
        
        if not parent or not child:
            return []
        
        changes = []
        
        # Compare parameters
        parent_params = parent.parameters or {}
        child_params = child.parameters or {}
        
        all_params = set(list(parent_params.keys()) + list(child_params.keys()))
        for param in all_params:
            parent_val = parent_params.get(param)
            child_val = child_params.get(param)
            
            if parent_val != child_val:
                impact = "high" if isinstance(parent_val, (int, float)) and isinstance(child_val, (int, float)) and parent_val != 0 and abs((child_val - parent_val) / parent_val) > 0.20 else "medium"
                changes.append(MutationChange(
                    change_type="parameter",
                    field_name=param,
                    old_value=parent_val,
                    new_value=child_val,
                    impact=impact
                ))
        
        # Compare ruleset
        parent_ruleset = parent.ruleset or {}
        child_ruleset = child.ruleset or {}
        
        # Timeframe
        if parent_ruleset.get("timeframe") != child_ruleset.get("timeframe"):
            changes.append(MutationChange(
                change_type="timeframe",
                field_name="timeframe",
                old_value=parent_ruleset.get("timeframe"),
                new_value=child_ruleset.get("timeframe"),
                impact="high"
            ))
        
        # Symbols
        parent_symbols = set(parent_ruleset.get("symbols", []))
        child_symbols = set(child_ruleset.get("symbols", []))
        if parent_symbols != child_symbols:
            changes.append(MutationChange(
                change_type="symbol",
                field_name="symbols",
                old_value=list(parent_symbols),
                new_value=list(child_symbols),
                impact="high"
            ))
        
        # Entry rules
        parent_entry = parent_ruleset.get("entry_rules", [])
        child_entry = child_ruleset.get("entry_rules", [])
        if parent_entry != child_entry:
            changes.append(MutationChange(
                change_type="rule",
                field_name="entry_rules",
                old_value=parent_entry,
                new_value=child_entry,
                impact="high"
            ))
        
        # Exit rules
        parent_exit = parent_ruleset.get("exit_rules", {})
        child_exit = child_ruleset.get("exit_rules", {})
        if parent_exit != child_exit:
            changes.append(MutationChange(
                change_type="rule",
                field_name="exit_rules",
                old_value=parent_exit,
                new_value=child_exit,
                impact="high"
            ))
        
        return changes
    
    def _find_original_strategy(
        self,
        strategy_id: str,
        db: Session
    ) -> Optional[str]:
        """Find original strategy by traversing lineage backwards."""
        # Get all parent lineages
        parent_lineages = crud.get_strategy_lineages_by_child(db, strategy_id)
        
        if not parent_lineages:
            # This is the original
            return strategy_id
        
        # Recursively find original
        parent_id = parent_lineages[0].parent_strategy_id
        return self._find_original_strategy(parent_id, db)
    
    def _build_mutation_chain(
        self,
        original_strategy_id: str,
        current_strategy_id: str,
        db: Session
    ) -> List[StrategyLineage]:
        """Build chain of mutations from original to current."""
        chain = []
        current_id = current_strategy_id
        
        while current_id != original_strategy_id:
            parent_lineages = crud.get_strategy_lineages_by_child(db, current_id)
            if not parent_lineages:
                break
            
            lineage = parent_lineages[0]
            chain.insert(0, lineage)  # Insert at beginning
            current_id = lineage.parent_strategy_id
        
        return chain
    
    def _create_mutation_node(
        self,
        lineage: StrategyLineage,
        original_strategy: UserStrategy,
        db: Session,
        mutation_number: int
    ) -> MutationNode:
        """Create a mutation node from lineage."""
        child_strategy = crud.get_user_strategy(db, lineage.child_strategy_id)
        if not child_strategy:
            return None
        
        # Calculate similarity
        original_dict = {
            "ruleset": original_strategy.ruleset,
            "parameters": original_strategy.parameters
        }
        child_dict = {
            "ruleset": child_strategy.ruleset,
            "parameters": child_strategy.parameters
        }
        
        mutation_distance = mutation_royalty_calculator.calculate_mutation_distance(
            original_dict,
            child_dict,
            mutation_number
        )
        
        # Determine royalty eligibility
        royalty_eligibility = mutation_royalty_calculator.determine_royalty_eligibility(
            original_dict,
            child_dict,
            mutation_number
        )
        
        # Generate changes summary
        changes_summary = self._generate_changes_summary(mutation_distance)
        
        return MutationNode(
            strategy_id=lineage.child_strategy_id,
            strategy_name=child_strategy.name,
            created_at=lineage.created_at,
            similarity_to_original=mutation_distance.similarity_score,
            mutation_type=lineage.mutation_type,
            mutation_params=lineage.mutation_params or {},
            changes_summary=changes_summary,
            royalty_eligible=royalty_eligibility.is_eligible,
            royalty_percent=royalty_eligibility.royalty_percent,
            is_brain_generated=royalty_eligibility.is_brain_generated
        )
    
    def _generate_changes_summary(self, mutation_distance: MutationDistance) -> str:
        """Generate human-readable changes summary."""
        parts = []
        
        if mutation_distance.parameter_changes > 0:
            parts.append(f"{mutation_distance.parameter_changes} parameter(s) changed")
        
        if mutation_distance.rule_changes > 0:
            parts.append(f"{mutation_distance.rule_changes} rule(s) changed")
        
        if mutation_distance.timeframe_changed:
            parts.append("timeframe changed")
        
        if mutation_distance.symbols_changed:
            parts.append("symbol(s) changed")
        
        if mutation_distance.indicators_changed:
            parts.append("indicator(s) changed")
        
        if not parts:
            return "Minor adjustments"
        
        return ", ".join(parts)
    
    def _calculate_current_royalty(
        self,
        original_strategy: UserStrategy,
        current_strategy: UserStrategy,
        mutation_count: int,
        db: Session
    ) -> Any:
        """Calculate current royalty eligibility."""
        original_dict = {
            "ruleset": original_strategy.ruleset,
            "parameters": original_strategy.parameters
        }
        current_dict = {
            "ruleset": current_strategy.ruleset,
            "parameters": current_strategy.parameters
        }
        
        return mutation_royalty_calculator.determine_royalty_eligibility(
            original_dict,
            current_dict,
            mutation_count
        )


# Singleton instance
mutation_visualization_engine = MutationVisualizationEngine()

