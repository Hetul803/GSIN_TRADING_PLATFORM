# backend/brain/dynamic_context_weighting.py
"""
PHASE 6: Dynamic Context Weighting
Adjusts factor weights based on market conditions, not static multipliers.

Market conditions affect which factors are most important:
- Trending markets: Emphasize trend alignment, volume
- Ranging markets: Emphasize mean reversion, support/resistance
- High volatility: Emphasize risk management, stability
- Low volatility: Emphasize momentum, breakout patterns
"""

from typing import Dict, Any, Optional
import numpy as np


class DynamicContextWeighting:
    """
    Dynamically adjusts factor weights based on market conditions.
    """
    
    def __init__(self):
        # Base weights (used as starting point)
        self.base_weights = {
            "base_confidence": 0.30,
            "regime_match": 0.20,
            "mtn_alignment": 0.15,
            "volume_strength": 0.10,
            "mcn_similarity": 0.10,
            "user_risk_adjustment": 0.10,
            "strategy_stability": 0.05,
        }
        
        # Market condition profiles
        self.market_profiles = {
            "trending": {
                "base_confidence": 0.25,
                "regime_match": 0.15,
                "mtn_alignment": 0.25,  # Higher weight on trend alignment
                "volume_strength": 0.15,  # Higher weight on volume
                "mcn_similarity": 0.10,
                "user_risk_adjustment": 0.05,
                "strategy_stability": 0.05,
            },
            "ranging": {
                "base_confidence": 0.30,
                "regime_match": 0.25,  # Higher weight on regime match
                "mtn_alignment": 0.10,  # Lower weight (trends less important)
                "volume_strength": 0.10,
                "mcn_similarity": 0.15,  # Higher weight on pattern similarity
                "user_risk_adjustment": 0.05,
                "strategy_stability": 0.05,
            },
            "volatile": {
                "base_confidence": 0.20,
                "regime_match": 0.15,
                "mtn_alignment": 0.10,
                "volume_strength": 0.10,
                "mcn_similarity": 0.10,
                "user_risk_adjustment": 0.20,  # Higher weight on risk management
                "strategy_stability": 0.15,  # Higher weight on stability
            },
            "low_volatility": {
                "base_confidence": 0.35,
                "regime_match": 0.20,
                "mtn_alignment": 0.20,  # Higher weight on momentum
                "volume_strength": 0.15,  # Higher weight on volume confirmation
                "mcn_similarity": 0.05,
                "user_risk_adjustment": 0.03,
                "strategy_stability": 0.02,
            },
        }
    
    def get_dynamic_weights(
        self,
        market_conditions: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Get dynamic weights based on market conditions.
        
        Args:
            market_conditions: Dictionary with:
                - regime: str - "trending", "ranging", "volatile", "low_volatility"
                - volatility: float - Current volatility (0-1)
                - volume_trend: str - "increasing", "decreasing", "normal"
                - spread: float - Bid-ask spread (0-1)
        
        Returns:
            Dictionary of weights that sum to 1.0
        """
        regime = market_conditions.get("regime", "trending")
        volatility = market_conditions.get("volatility", 0.5)
        volume_trend = market_conditions.get("volume_trend", "normal")
        spread = market_conditions.get("spread", 0.0)
        
        # Start with base weights
        weights = self.base_weights.copy()
        
        # Adjust based on regime
        if regime in self.market_profiles:
            profile_weights = self.market_profiles[regime]
            # Blend base and profile weights (70% base, 30% profile)
            for key in weights:
                weights[key] = 0.7 * weights[key] + 0.3 * profile_weights.get(key, weights[key])
        
        # Adjust based on volatility
        if volatility > 0.7:  # High volatility
            # Increase risk management weights
            weights["user_risk_adjustment"] *= 1.3
            weights["strategy_stability"] *= 1.3
            # Decrease momentum weights
            weights["mtn_alignment"] *= 0.8
            weights["volume_strength"] *= 0.9
        elif volatility < 0.3:  # Low volatility
            # Increase momentum weights
            weights["mtn_alignment"] *= 1.2
            weights["volume_strength"] *= 1.2
            # Decrease risk weights
            weights["user_risk_adjustment"] *= 0.9
            weights["strategy_stability"] *= 0.9
        
        # Adjust based on volume trend
        if volume_trend == "increasing":
            weights["volume_strength"] *= 1.2
            weights["mcn_similarity"] *= 1.1
        elif volume_trend == "decreasing":
            weights["volume_strength"] *= 0.8
            weights["strategy_stability"] *= 1.1
        
        # Adjust based on spread (wider spread = less confidence)
        if spread > 0.05:  # Wide spread
            weights["base_confidence"] *= 0.9
            weights["user_risk_adjustment"] *= 1.2
        
        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights


class ConfidenceDecay:
    """
    PHASE 6: Real-time confidence decay.
    Adjusts confidence downward when:
    - Volatility increases
    - Spread widens
    - Volume decreases
    """
    
    def __init__(self):
        # Decay factors (how much to reduce confidence per unit change)
        self.volatility_decay_rate = 0.15  # 15% reduction per 0.1 increase in volatility
        self.spread_decay_rate = 0.20  # 20% reduction per 0.01 increase in spread
        self.volume_decay_rate = 0.10  # 10% reduction per 20% decrease in volume
    
    def apply_decay(
        self,
        base_confidence: float,
        market_conditions: Dict[str, Any]
    ) -> float:
        """
        Apply confidence decay based on market conditions.
        
        Args:
            base_confidence: Base confidence (0-1)
            market_conditions: Dictionary with:
                - volatility: float - Current volatility (0-1)
                - spread: float - Bid-ask spread (0-1)
                - volume_ratio: float - Current volume / average volume
        
        Returns:
            Decayed confidence (0-1)
        """
        volatility = market_conditions.get("volatility", 0.5)
        spread = market_conditions.get("spread", 0.0)
        volume_ratio = market_conditions.get("volume_ratio", 1.0)
        
        decay_factor = 1.0
        
        # Volatility decay
        if volatility > 0.5:  # Above average volatility
            volatility_excess = volatility - 0.5
            decay_factor *= (1.0 - self.volatility_decay_rate * volatility_excess * 10)
        
        # Spread decay
        if spread > 0.01:  # Wide spread
            spread_excess = spread - 0.01
            decay_factor *= (1.0 - self.spread_decay_rate * spread_excess * 100)
        
        # Volume decay
        if volume_ratio < 0.8:  # Below average volume
            volume_deficit = 0.8 - volume_ratio
            decay_factor *= (1.0 - self.volume_decay_rate * volume_deficit * 5)
        
        # Apply decay
        decayed_confidence = base_confidence * max(0.3, decay_factor)  # Minimum 30% of original
        
        return max(0.0, min(1.0, decayed_confidence))


class AnomalyDetector:
    """
    PHASE 6: Anomaly detection.
    Detects when market data deviates massively from MCN patterns.
    """
    
    def __init__(self):
        self.anomaly_threshold = 0.3  # If similarity < 0.3, consider it an anomaly
        self.volatility_anomaly_threshold = 2.0  # If volatility > 2x average, anomaly
        self.volume_anomaly_threshold = 3.0  # If volume > 3x average, anomaly
    
    def detect_anomaly(
        self,
        market_data: Dict[str, Any],
        mcn_similarity: float,
        historical_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect anomalies in market data.
        
        Args:
            market_data: Current market data
            mcn_similarity: Similarity to MCN patterns (0-1)
            historical_stats: Historical statistics:
                - avg_volatility: float
                - avg_volume: float
                - avg_price: float
        
        Returns:
            Dictionary with:
                - is_anomaly: bool
                - anomaly_type: str - "pattern", "volatility", "volume", "price"
                - severity: float - 0-1
                - recommendation: str
        """
        current_volatility = market_data.get("volatility", 0.5)
        current_volume = market_data.get("volume", 0)
        current_price = market_data.get("price", 0)
        
        avg_volatility = historical_stats.get("avg_volatility", 0.5)
        avg_volume = historical_stats.get("avg_volume", 0)
        avg_price = historical_stats.get("avg_price", 0)
        
        anomalies = []
        max_severity = 0.0
        
        # Pattern anomaly (low MCN similarity)
        if mcn_similarity < self.anomaly_threshold:
            severity = 1.0 - (mcn_similarity / self.anomaly_threshold)
            anomalies.append({
                "type": "pattern",
                "severity": severity,
                "message": f"Market pattern deviates significantly from historical patterns (similarity: {mcn_similarity:.2f})"
            })
            max_severity = max(max_severity, severity)
        
        # Volatility anomaly
        if avg_volatility > 0 and current_volatility > avg_volatility * self.volatility_anomaly_threshold:
            severity = min(1.0, (current_volatility / avg_volatility) / self.volatility_anomaly_threshold)
            anomalies.append({
                "type": "volatility",
                "severity": severity,
                "message": f"Volatility spike detected ({current_volatility:.2f} vs avg {avg_volatility:.2f})"
            })
            max_severity = max(max_severity, severity)
        
        # Volume anomaly
        if avg_volume > 0 and current_volume > avg_volume * self.volume_anomaly_threshold:
            severity = min(1.0, (current_volume / avg_volume) / self.volume_anomaly_threshold)
            anomalies.append({
                "type": "volume",
                "severity": severity,
                "message": f"Unusual volume spike detected ({current_volume:.0f} vs avg {avg_volume:.0f})"
            })
            max_severity = max(max_severity, severity)
        
        # Price anomaly (flash crash/spike)
        if avg_price > 0:
            price_change = abs(current_price - avg_price) / avg_price
            if price_change > 0.1:  # >10% deviation
                severity = min(1.0, price_change / 0.2)  # 20% = max severity
                anomalies.append({
                    "type": "price",
                    "severity": severity,
                    "message": f"Significant price deviation detected ({price_change:.1%})"
                })
                max_severity = max(max_severity, severity)
        
        is_anomaly = max_severity > 0.5  # Anomaly if severity > 50%
        
        recommendation = "proceed"
        if is_anomaly:
            if max_severity > 0.8:
                recommendation = "avoid"
            elif max_severity > 0.6:
                recommendation = "reduce_confidence"
            else:
                recommendation = "proceed_with_caution"
        
        return {
            "is_anomaly": is_anomaly,
            "anomaly_type": anomalies[0]["type"] if anomalies else None,
            "severity": max_severity,
            "anomalies": anomalies,
            "recommendation": recommendation,
            "confidence_reduction": max_severity * 0.5  # Reduce confidence by up to 50%
        }


class MetaLearner:
    """
    PHASE 6: Meta-learning.
    If Brain is repeatedly wrong in a regime, auto-adjust weighting.
    """
    
    def __init__(self):
        # Track performance by regime
        self.regime_performance: Dict[str, Dict[str, float]] = {}
        # Track performance by factor
        self.factor_performance: Dict[str, Dict[str, float]] = {}
        
        # Learning rate
        self.learning_rate = 0.1  # 10% adjustment per learning cycle
    
    def record_outcome(
        self,
        regime: str,
        factors: Dict[str, float],
        predicted_confidence: float,
        actual_outcome: bool,  # True if profitable, False if loss
        actual_return: float
    ):
        """
        Record outcome for meta-learning.
        
        Args:
            regime: Market regime
            factors: Factor values used
            predicted_confidence: Predicted confidence
            actual_outcome: Whether trade was profitable
            actual_return: Actual return (positive or negative)
        """
        # Initialize regime tracking
        if regime not in self.regime_performance:
            self.regime_performance[regime] = {
                "total_trades": 0,
                "profitable_trades": 0,
                "total_return": 0.0,
                "avg_confidence": 0.0,
            }
        
        # Update regime stats
        stats = self.regime_performance[regime]
        stats["total_trades"] += 1
        if actual_outcome:
            stats["profitable_trades"] += 1
        stats["total_return"] += actual_return
        stats["avg_confidence"] = (stats["avg_confidence"] * (stats["total_trades"] - 1) + predicted_confidence) / stats["total_trades"]
        
        # Track factor performance
        for factor_name, factor_value in factors.items():
            if factor_name not in self.factor_performance:
                self.factor_performance[factor_name] = {
                    "total_uses": 0,
                    "profitable_uses": 0,
                    "total_return": 0.0,
                }
            
            factor_stats = self.factor_performance[factor_name]
            factor_stats["total_uses"] += 1
            if actual_outcome:
                factor_stats["profitable_uses"] += 1
            factor_stats["total_return"] += actual_return
    
    def get_adjusted_weights(
        self,
        regime: str,
        base_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Get adjusted weights based on learned performance.
        
        Args:
            regime: Current market regime
            base_weights: Base weight configuration
        
        Returns:
            Adjusted weights
        """
        adjusted_weights = base_weights.copy()
        
        # Adjust based on regime performance
        if regime in self.regime_performance:
            stats = self.regime_performance[regime]
            if stats["total_trades"] >= 10:  # Need minimum data
                win_rate = stats["profitable_trades"] / stats["total_trades"]
                avg_return = stats["total_return"] / stats["total_trades"]
                
                # If performance is poor, reduce weights for this regime
                if win_rate < 0.5 or avg_return < 0:
                    # Reduce all weights slightly, but keep relative proportions
                    adjustment = 1.0 - (self.learning_rate * (0.5 - win_rate))
                    adjusted_weights = {k: v * adjustment for k, v in adjusted_weights.items()}
        
        # Adjust based on factor performance
        for factor_name in adjusted_weights:
            if factor_name in self.factor_performance:
                factor_stats = self.factor_performance[factor_name]
                if factor_stats["total_uses"] >= 5:  # Need minimum data
                    factor_win_rate = factor_stats["profitable_uses"] / factor_stats["total_uses"]
                    factor_avg_return = factor_stats["total_return"] / factor_stats["total_uses"]
                    
                    # Adjust weight based on performance
                    if factor_win_rate > 0.6 and factor_avg_return > 0:
                        # Increase weight for good-performing factors
                        adjusted_weights[factor_name] *= (1.0 + self.learning_rate)
                    elif factor_win_rate < 0.4 or factor_avg_return < 0:
                        # Decrease weight for poor-performing factors
                        adjusted_weights[factor_name] *= (1.0 - self.learning_rate)
        
        # Normalize to sum to 1.0
        total = sum(adjusted_weights.values())
        if total > 0:
            adjusted_weights = {k: v / total for k, v in adjusted_weights.items()}
        
        return adjusted_weights

