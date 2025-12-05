# backend/strategy_engine/mutation_royalty.py
"""
Mutation Royalty Structure - Determines royalty eligibility for mutated strategies.

Royalty Rules:
1. Original uploader gets 5% royalty if strategy similarity > 70% AND mutation_count < 3
2. After 3 mutations OR similarity < 50%, strategy becomes "brain-generated" (no royalties to original)
3. Mutation distance calculated based on:
   - Parameter changes (indicator values, thresholds)
   - Timeframe changes
   - Entry/exit rule changes
   - Symbol changes
   - Indicator additions/removals
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
import hashlib


@dataclass
class MutationDistance:
    """Represents the distance between original and mutated strategy."""
    similarity_score: float  # 0-1, higher = more similar
    mutation_count: int  # Number of mutations from original
    parameter_changes: int  # Number of parameter changes
    rule_changes: int  # Number of rule changes
    timeframe_changed: bool
    symbols_changed: bool
    indicators_changed: bool
    total_changes: int  # Total number of changes


@dataclass
class RoyaltyEligibility:
    """Determines if original uploader is eligible for royalties."""
    is_eligible: bool
    royalty_percent: float  # 0.0 to 0.05 (5%)
    reason: str  # Why eligible or not
    mutation_distance: MutationDistance
    is_brain_generated: bool  # True if too mutated to be considered user-generated


class MutationRoyaltyCalculator:
    """
    Calculates royalty eligibility based on mutation distance.
    """
    
    # Royalty thresholds
    MIN_SIMILARITY_FOR_FULL_ROYALTY = 0.70  # 70% similarity for 5%
    MIN_SIMILARITY_FOR_MEDIUM_ROYALTY = 0.50  # 50% similarity for 3%
    MIN_SIMILARITY_FOR_LOW_ROYALTY = 0.40  # 40% similarity for 1.5%
    MAX_MUTATIONS_FOR_FULL_ROYALTY = 2  # < 3 mutations for 5%
    MAX_MUTATIONS_FOR_MEDIUM_ROYALTY = 2  # < 3 mutations for 3%
    MAX_MUTATIONS_FOR_LOW_ROYALTY = 3  # = 3 mutations for 1.5%
    
    # Royalty rates (based on mutation distance)
    FULL_ROYALTY_RATE = 0.05  # 5% for highly similar strategies (>70% AND <3 mutations)
    MEDIUM_ROYALTY_RATE = 0.03  # 3% for moderately similar strategies (50-70% AND <3 mutations)
    LOW_ROYALTY_RATE = 0.015  # 1.5% for low similarity strategies (40-50% OR =3 mutations)
    NO_ROYALTY_RATE = 0.0  # 0% for brain-generated strategies (<40% OR >3 mutations)
    
    def calculate_mutation_distance(
        self,
        original_strategy: Dict[str, Any],
        mutated_strategy: Dict[str, Any],
        mutation_count: int = 1
    ) -> MutationDistance:
        """
        Calculate mutation distance between original and mutated strategy.
        
        Args:
            original_strategy: Original strategy definition
            mutated_strategy: Mutated strategy definition
            mutation_count: Number of mutations from original (1 = first mutation)
        
        Returns:
            MutationDistance with detailed change analysis
        """
        original_ruleset = original_strategy.get("ruleset", {})
        mutated_ruleset = mutated_strategy.get("ruleset", {})
        
        # Count parameter changes
        original_params = original_strategy.get("parameters", {})
        mutated_params = mutated_strategy.get("parameters", {})
        parameter_changes = self._count_parameter_changes(original_params, mutated_params)
        
        # Count rule changes
        rule_changes = self._count_rule_changes(original_ruleset, mutated_ruleset)
        
        # Check timeframe change
        timeframe_changed = (
            original_ruleset.get("timeframe") != mutated_ruleset.get("timeframe")
        )
        
        # Check symbol changes
        original_symbols = set(original_ruleset.get("symbols", []))
        mutated_symbols = set(mutated_ruleset.get("symbols", []))
        symbols_changed = original_symbols != mutated_symbols
        
        # Check indicator changes
        indicators_changed = self._check_indicator_changes(original_ruleset, mutated_ruleset)
        
        # Calculate total changes
        total_changes = (
            parameter_changes +
            rule_changes +
            (1 if timeframe_changed else 0) +
            (1 if symbols_changed else 0) +
            (1 if indicators_changed else 0)
        )
        
        # Calculate similarity score (0-1)
        similarity_score = self._calculate_similarity_score(
            original_strategy,
            mutated_strategy,
            parameter_changes,
            rule_changes,
            timeframe_changed,
            symbols_changed,
            indicators_changed
        )
        
        return MutationDistance(
            similarity_score=similarity_score,
            mutation_count=mutation_count,
            parameter_changes=parameter_changes,
            rule_changes=rule_changes,
            timeframe_changed=timeframe_changed,
            symbols_changed=symbols_changed,
            indicators_changed=indicators_changed,
            total_changes=total_changes
        )
    
    def _count_parameter_changes(
        self,
        original_params: Dict[str, Any],
        mutated_params: Dict[str, Any]
    ) -> int:
        """Count number of parameter changes."""
        changes = 0
        
        # Compare all parameters
        all_params = set(list(original_params.keys()) + list(mutated_params.keys()))
        
        for param in all_params:
            original_val = original_params.get(param)
            mutated_val = mutated_params.get(param)
            
            if original_val != mutated_val:
                # Check if change is significant (>10% difference for numbers)
                if isinstance(original_val, (int, float)) and isinstance(mutated_val, (int, float)):
                    if original_val != 0:
                        change_percent = abs((mutated_val - original_val) / original_val)
                        if change_percent > 0.10:  # More than 10% change
                            changes += 1
                    else:
                        changes += 1
                else:
                    changes += 1
        
        return changes
    
    def _count_rule_changes(
        self,
        original_ruleset: Dict[str, Any],
        mutated_ruleset: Dict[str, Any]
    ) -> int:
        """Count number of rule changes."""
        changes = 0
        
        # Compare entry rules
        original_entry = original_ruleset.get("entry_rules", [])
        mutated_entry = mutated_ruleset.get("entry_rules", [])
        if original_entry != mutated_entry:
            changes += 1
        
        # Compare exit rules
        original_exit = original_ruleset.get("exit_rules", {})
        mutated_exit = mutated_ruleset.get("exit_rules", {})
        if original_exit != mutated_exit:
            changes += 1
        
        return changes
    
    def _check_indicator_changes(
        self,
        original_ruleset: Dict[str, Any],
        mutated_ruleset: Dict[str, Any]
    ) -> bool:
        """Check if indicators changed."""
        # Extract indicator names from rules
        original_indicators = self._extract_indicators(original_ruleset)
        mutated_indicators = self._extract_indicators(mutated_ruleset)
        
        return original_indicators != mutated_indicators
    
    def _extract_indicators(self, ruleset: Dict[str, Any]) -> set:
        """Extract indicator names from ruleset."""
        indicators = set()
        
        entry_rules = ruleset.get("entry_rules", [])
        for rule in entry_rules:
            if isinstance(rule, dict):
                indicator = rule.get("indicator") or rule.get("type")
                if indicator:
                    indicators.add(indicator)
        
        return indicators
    
    def _calculate_similarity_score(
        self,
        original_strategy: Dict[str, Any],
        mutated_strategy: Dict[str, Any],
        parameter_changes: int,
        rule_changes: int,
        timeframe_changed: bool,
        symbols_changed: bool,
        indicators_changed: bool
    ) -> float:
        """
        Calculate similarity score (0-1).
        Higher = more similar to original.
        """
        # Start with 1.0 (100% similar)
        similarity = 1.0
        
        # Penalize for changes
        # Parameter changes: -0.05 per change (max -0.30)
        similarity -= min(0.30, parameter_changes * 0.05)
        
        # Rule changes: -0.10 per change (max -0.20)
        similarity -= min(0.20, rule_changes * 0.10)
        
        # Timeframe change: -0.15
        if timeframe_changed:
            similarity -= 0.15
        
        # Symbol change: -0.20
        if symbols_changed:
            similarity -= 0.20
        
        # Indicator change: -0.25
        if indicators_changed:
            similarity -= 0.25
        
        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, similarity))
    
    def determine_royalty_eligibility(
        self,
        original_strategy: Dict[str, Any],
        mutated_strategy: Dict[str, Any],
        mutation_count: int,
        lineage_chain: Optional[List[Dict[str, Any]]] = None
    ) -> RoyaltyEligibility:
        """
        Determine if original uploader is eligible for royalties.
        
        Args:
            original_strategy: Original strategy uploaded by user
            mutated_strategy: Current (possibly mutated) strategy
            mutation_count: Number of mutations from original
            lineage_chain: Chain of mutations from original to current
        
        Returns:
            RoyaltyEligibility with eligibility status and royalty rate
        """
        # Calculate mutation distance
        mutation_distance = self.calculate_mutation_distance(
            original_strategy,
            mutated_strategy,
            mutation_count
        )
        
        # Check eligibility criteria
        similarity = mutation_distance.similarity_score
        mutations = mutation_distance.mutation_count
        
        # Rule 1: 5% Royalty - Similarity > 70% AND mutations < 3
        if similarity > self.MIN_SIMILARITY_FOR_FULL_ROYALTY and mutations < self.MAX_MUTATIONS_FOR_FULL_ROYALTY + 1:
            return RoyaltyEligibility(
                is_eligible=True,
                royalty_percent=self.FULL_ROYALTY_RATE,
                reason=f"Strategy is highly similar ({similarity:.1%}) and has {mutations} mutations. Original uploader receives 5% royalty.",
                mutation_distance=mutation_distance,
                is_brain_generated=False
            )
        
        # Rule 2: 3% Royalty - Similarity 50-70% AND mutations < 3
        if similarity >= self.MIN_SIMILARITY_FOR_MEDIUM_ROYALTY and similarity <= self.MIN_SIMILARITY_FOR_FULL_ROYALTY and mutations < self.MAX_MUTATIONS_FOR_MEDIUM_ROYALTY + 1:
            return RoyaltyEligibility(
                is_eligible=True,
                royalty_percent=self.MEDIUM_ROYALTY_RATE,
                reason=f"Strategy is moderately similar ({similarity:.1%}) with {mutations} mutations. Original uploader receives 3% royalty.",
                mutation_distance=mutation_distance,
                is_brain_generated=False
            )
        
        # Rule 3: 1.5% Royalty - Similarity 40-50% OR mutations = 3
        if (similarity >= self.MIN_SIMILARITY_FOR_LOW_ROYALTY and similarity < self.MIN_SIMILARITY_FOR_MEDIUM_ROYALTY) or mutations == self.MAX_MUTATIONS_FOR_LOW_ROYALTY:
            return RoyaltyEligibility(
                is_eligible=True,
                royalty_percent=self.LOW_ROYALTY_RATE,
                reason=f"Strategy has low similarity ({similarity:.1%}) or {mutations} mutations. Original uploader receives 1.5% royalty.",
                mutation_distance=mutation_distance,
                is_brain_generated=False
            )
        
        # Rule 4: 0% Royalty (Brain-Generated) - Similarity < 40% OR mutations > 3
        return RoyaltyEligibility(
            is_eligible=False,
            royalty_percent=self.NO_ROYALTY_RATE,
            reason=f"Strategy similarity ({similarity:.1%}) is below 40% or has {mutations} mutations (>3). This is now considered brain-generated.",
            mutation_distance=mutation_distance,
            is_brain_generated=True
        )


# Singleton instance
mutation_royalty_calculator = MutationRoyaltyCalculator()

