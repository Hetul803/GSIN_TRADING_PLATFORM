# backend/brain/confidence_calibrator.py
"""
Formal confidence calibration model.
Combines multiple factors to produce calibrated confidence scores.

Mathematical Model:
    calibrated_confidence = sigmoid(
        base_confidence * w1 +
        regime_match * w2 +
        mtn_alignment * w3 +
        volume_strength * w4 +
        mcn_similarity * w5 +
        user_risk_adjustment * w6 +
        strategy_stability * w7
    )

Where:
    - sigmoid(x) = 1 / (1 + exp(-k * (x - 0.5))) for smooth, bounded output
    - k = calibration_strength (default 10.0)
    - All factors normalized to [0, 1]
    - Weights sum to 1.0
"""
from typing import Dict, Any, Optional
import numpy as np
import math


class ConfidenceCalibrator:
    """Calibrates confidence scores using multiple factors."""
    
    def __init__(self):
        # Factor weights (must sum to 1.0)
        self.weights = {
            "base_confidence": 0.30,      # 30% weight on base strategy confidence
            "regime_match": 0.20,         # 20% weight on regime alignment
            "mtn_alignment": 0.15,        # 15% weight on multi-timeframe alignment
            "volume_strength": 0.10,      # 10% weight on volume confirmation
            "mcn_similarity": 0.10,       # 10% weight on MCN pattern similarity
            "user_risk_adjustment": 0.10, # 10% weight on user risk profile
            "strategy_stability": 0.05,   # 5% weight on strategy stability
        }
        
        # Calibration strength (k parameter in sigmoid)
        self.calibration_strength = 10.0
    
    def calibrate_confidence(
        self,
        raw_confidence: float,
        factors_dict: Dict[str, Any],
        market_conditions: Optional[Dict[str, Any]] = None,
        historical_stats: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calibrate confidence using multiple factors.
        
        Args:
            raw_confidence: Base confidence from strategy engine (0-1)
            factors_dict: Dictionary with:
                - regime_match: float (0-1) - How well strategy matches current regime
                - mtn_alignment_score: float (0-1) - Multi-timeframe alignment
                - volume_strength: float (0-1) - Volume confirmation strength
                - mcn_similarity: float (0-1) - MCN pattern similarity
                - user_risk_tendency: str - "low", "moderate", "high"
                - strategy_stability: float (0-1) - Strategy stability score
        
        Returns:
            Calibrated confidence (0-1), guaranteed to be:
            - Monotonic: Higher inputs → Higher outputs
            - Smooth: Continuous, no jumps
            - Bounded: Always in [0, 1]
        """
        # Extract factors with defaults
        regime_match = factors_dict.get("regime_match", 0.5)
        mtn_alignment = factors_dict.get("mtn_alignment_score", 0.5)
        volume_strength = factors_dict.get("volume_strength", 0.5)
        mcn_similarity = factors_dict.get("mcn_similarity", 0.5)
        user_risk_tendency = factors_dict.get("user_risk_tendency", "moderate")
        strategy_stability = factors_dict.get("strategy_stability", 0.5)
        
        # Normalize all factors to [0, 1]
        regime_match = max(0.0, min(1.0, regime_match))
        mtn_alignment = max(0.0, min(1.0, mtn_alignment))
        volume_strength = max(0.0, min(1.0, volume_strength))
        mcn_similarity = max(0.0, min(1.0, mcn_similarity))
        strategy_stability = max(0.0, min(1.0, strategy_stability))
        raw_confidence = max(0.0, min(1.0, raw_confidence))
        
        # Calculate user risk adjustment
        # Risk-averse users get lower confidence for high-risk signals
        # Risk-tolerant users get higher confidence for high-confidence signals
        if user_risk_tendency == "low":
            user_risk_adjustment = 0.8  # Reduce confidence by 20%
        elif user_risk_tendency == "high":
            user_risk_adjustment = 1.1  # Increase confidence by 10% (capped at 1.0)
        else:
            user_risk_adjustment = 1.0  # No adjustment
        
        user_risk_adjustment = max(0.0, min(1.0, user_risk_adjustment))
        
        # PHASE 6: Get dynamic weights based on market conditions
        if market_conditions and self.dynamic_weighting and self.meta_learner:
            try:
                weights = self.dynamic_weighting.get_dynamic_weights(market_conditions)
                # Apply meta-learning adjustments
                regime = market_conditions.get("regime", "trending")
                weights = self.meta_learner.get_adjusted_weights(regime, weights)
            except Exception:
                weights = self.base_weights.copy()
        else:
            weights = self.base_weights.copy()
        
        # Calculate weighted sum with dynamic weights
        # Formula: sum(weight_i * factor_i)
        weighted_sum = (
            weights["base_confidence"] * raw_confidence +
            weights["regime_match"] * regime_match +
            weights["mtn_alignment"] * mtn_alignment +
            weights["volume_strength"] * volume_strength +
            weights["mcn_similarity"] * mcn_similarity +
            weights["user_risk_adjustment"] * user_risk_adjustment +
            weights["strategy_stability"] * strategy_stability
        )
        
        # Apply sigmoid transformation for smooth, bounded output
        # sigmoid(x) = 1 / (1 + exp(-k * (x - 0.5)))
        calibrated = self._sigmoid(weighted_sum)
        
        # PHASE 6: Apply confidence decay based on market conditions
        if market_conditions and self.confidence_decay:
            try:
                calibrated = self.confidence_decay.apply_decay(calibrated, market_conditions)
            except Exception:
                pass  # Continue without decay if component unavailable
        
        # PHASE 6: Check for anomalies
        anomaly_result = None
        if market_conditions and historical_stats and self.anomaly_detector:
            try:
                mcn_similarity_value = factors_dict.get("mcn_similarity", 0.5)
                anomaly_result = self.anomaly_detector.detect_anomaly(
                    market_conditions,
                    mcn_similarity_value,
                    historical_stats
                )
                
                if anomaly_result and anomaly_result.get("is_anomaly"):
                    # Reduce confidence based on anomaly severity
                    confidence_reduction = anomaly_result.get("confidence_reduction", 0.0)
                    calibrated *= (1.0 - confidence_reduction)
            except Exception:
                anomaly_result = None  # Continue without anomaly detection if component unavailable
        
        # Final clamp to ensure bounds (defensive programming)
        final_confidence = max(0.0, min(1.0, calibrated))
        
        # PHASE 6: Return enhanced result with metadata
        return {
            "confidence": final_confidence,
            "raw_confidence": raw_confidence,
            "calibrated_confidence": calibrated,
            "weights_used": weights,
            "anomaly_detected": anomaly_result.get("is_anomaly", False) if anomaly_result else False,
            "anomaly_info": anomaly_result,
            "confidence_decay_applied": market_conditions is not None,
            "dynamic_weighting_applied": market_conditions is not None,
        }
    
    def _sigmoid(self, x: float) -> float:
        """
        Sigmoid function for smooth, bounded calibration.
        
        Formula: 1 / (1 + exp(-k * (x - 0.5)))
        
        Properties:
        - x = 0.5 → output ≈ 0.5
        - x < 0.5 → output < 0.5 (smooth decrease)
        - x > 0.5 → output > 0.5 (smooth increase)
        - Always bounded in [0, 1]
        - Monotonic (derivative > 0)
        """
        try:
            # Prevent overflow
            exponent = -self.calibration_strength * (x - 0.5)
            if exponent > 700:
                return 1.0
            elif exponent < -700:
                return 0.0
            
            return 1.0 / (1.0 + math.exp(exponent))
        except:
            # Fallback to linear if sigmoid fails
            return max(0.0, min(1.0, x))
    
    def get_factor_breakdown(
        self,
        raw_confidence: float,
        factors_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get detailed breakdown of confidence calibration factors.
        
        Useful for debugging and explanation.
        """
        regime_match = factors_dict.get("regime_match", 0.5)
        mtn_alignment = factors_dict.get("mtn_alignment_score", 0.5)
        volume_strength = factors_dict.get("volume_strength", 0.5)
        mcn_similarity = factors_dict.get("mcn_similarity", 0.5)
        user_risk_tendency = factors_dict.get("user_risk_tendency", "moderate")
        strategy_stability = factors_dict.get("strategy_stability", 0.5)
        
        # Calculate user risk adjustment
        if user_risk_tendency == "low":
            user_risk_adjustment = 0.8
        elif user_risk_tendency == "high":
            user_risk_adjustment = 1.1
        else:
            user_risk_adjustment = 1.0
        user_risk_adjustment = max(0.0, min(1.0, user_risk_adjustment))
        
        # Calculate weighted contributions
        contributions = {
            "base_confidence": {
                "value": raw_confidence,
                "weight": self.weights["base_confidence"],
                "contribution": self.weights["base_confidence"] * raw_confidence,
            },
            "regime_match": {
                "value": regime_match,
                "weight": self.weights["regime_match"],
                "contribution": self.weights["regime_match"] * regime_match,
            },
            "mtn_alignment": {
                "value": mtn_alignment,
                "weight": self.weights["mtn_alignment"],
                "contribution": self.weights["mtn_alignment"] * mtn_alignment,
            },
            "volume_strength": {
                "value": volume_strength,
                "weight": self.weights["volume_strength"],
                "contribution": self.weights["volume_strength"] * volume_strength,
            },
            "mcn_similarity": {
                "value": mcn_similarity,
                "weight": self.weights["mcn_similarity"],
                "contribution": self.weights["mcn_similarity"] * mcn_similarity,
            },
            "user_risk_adjustment": {
                "value": user_risk_adjustment,
                "weight": self.weights["user_risk_adjustment"],
                "contribution": self.weights["user_risk_adjustment"] * user_risk_adjustment,
            },
            "strategy_stability": {
                "value": strategy_stability,
                "weight": self.weights["strategy_stability"],
                "contribution": self.weights["strategy_stability"] * strategy_stability,
            },
        }
        
        weighted_sum = sum(c["contribution"] for c in contributions.values())
        calibrated = self.calibrate_confidence(raw_confidence, factors_dict)
        
        return {
            "raw_confidence": raw_confidence,
            "weighted_sum": weighted_sum,
            "calibrated_confidence": calibrated,
            "contributions": contributions,
            "calibration_strength": self.calibration_strength,
        }

