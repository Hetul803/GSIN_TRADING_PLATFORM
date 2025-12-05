# backend/brain/regime_detector.py
"""
Market Regime Detection using MCN clustering.
Uses embeddings of volatility, momentum, SMA/EMA slopes, volume trend, and candle patterns.
"""
from typing import Dict, Any, Optional, List
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# PHASE A: Helper function to fix all regime feature arrays to exactly 32 dimensions
def fixed32(x):
    """
    PHASE A: Standardize any array to exactly 32 dimensions.
    
    Args:
        x: Input array (any shape, any type)
    
    Returns:
        numpy array of shape (32,) dtype=np.float32
    """
    x = np.asarray(x, dtype=np.float32)
    if len(x) >= 32:
        return x[:32]
    return np.pad(x, (0, 32 - len(x)), mode='constant', constant_values=0.0)

from ..market_data.market_data_provider import get_provider_with_fallback, get_historical_provider
from ..market_data.types import CandleData
from ..strategy_engine.indicators import IndicatorCalculator
from .mcn_adapter import get_mcn_adapter
from datetime import timezone


class RegimeDetector:
    """Detects market regimes using MCN clustering with cold start fallback."""
    
    def __init__(self):
        self.mcn_adapter = get_mcn_adapter()
        self.indicator_calc = IndicatorCalculator()
        # Cold start detector for when MCN is unavailable
        from .cold_start_regime_detector import ColdStartRegimeDetector
        self.cold_start_detector = ColdStartRegimeDetector()
    
    def get_market_regime(
        self,
        symbol: str,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classify current market regime for a symbol using MCN clustering.
        
        STABILITY: Always returns a safe dict, never throws.
        
        Returns:
            {
                "regime": "unknown" | "neutral" | "risk_on" | "risk_off" | "momentum" | "volatility",
                "confidence": float (0-1),
                "volatility": float | None,
                "risk_level": "normal" | "high" | "low",
                "memory_samples": int,
                "regime_features": dict
            }
        """
        # STABILITY: Wrap entire function in try/except to ensure it never throws
        try:
            # IMPROVEMENT: Use cold start detector if MCN is unavailable or not trained
            if not self.mcn_adapter.is_available:
                # Use cold start detector (SMA/VIX rules)
                cold_start_result = self.cold_start_detector.detect_regime(symbol)
                return cold_start_result
            
            # Check if MCN has enough data (cold start scenario)
            # If MCN is available but has very few memories, use cold start
            try:
                if hasattr(self.mcn_adapter, "mcn_regime") and self.mcn_adapter.mcn_regime:
                    # Try to check MCN size
                    mcn_size = 0
                    if hasattr(self.mcn_adapter.mcn_regime, "vals") and self.mcn_adapter.mcn_regime.vals is not None:
                        mcn_size = len(self.mcn_adapter.mcn_regime.vals) if hasattr(self.mcn_adapter.mcn_regime.vals, "__len__") else 0
                    elif hasattr(self.mcn_adapter.mcn_regime, "size"):
                        mcn_size = self.mcn_adapter.mcn_regime.size
                    
                    # If MCN has less than 10 memories, it's still in cold start
                    if mcn_size < 10:
                        cold_start_result = self.cold_start_detector.detect_regime(symbol)
                        # Merge with MCN result if available (low confidence)
                        cold_start_result["confidence"] = cold_start_result.get("confidence", 0.5) * 0.7  # Reduce confidence
                        return cold_start_result
            except Exception:
                # If checking MCN size fails, use cold start
                pass
            # Get market data if not provided
            if not market_data:
                # TASK 2 FIX: For regime detection, we need both live price (for current state) and historical candles (for pattern matching)
                # Use call_with_fallback which goes through request queue
                from ..market_data.market_data_provider import call_with_fallback
                
                try:
                    price_data = call_with_fallback("get_price", symbol)
                except Exception:
                    price_data = None
                
                try:
                    volatility_data = call_with_fallback("get_volatility", symbol)
                except Exception:
                    volatility_data = None
                
                # TWELVE DATA INTEGRATION: Use historical provider through request queue for historical candles
                try:
                    end_date = datetime.now(timezone.utc)
                    start_date = end_date - timedelta(days=60)  # Get ~60 days for regime detection
                    candles = call_with_fallback(
                        "get_candles",
                        symbol,
                        "1d",
                        limit=60,
                        start=start_date,
                        end=end_date
                    )
                except Exception as e:
                    print(f"⚠️  Failed to fetch historical candles for regime detection: {e}")
                    candles = []
                
                market_data = {
                    "price": price_data.price if price_data else 0.0,
                    "volatility": volatility_data.volatility if volatility_data else 0.0,
                    "candles": candles,
                }
            
            # Extract regime features
            regime_features = self._extract_regime_features(symbol, market_data)
            
            # Create market state vector for MCN search
            market_vector = self._create_market_state_vector(symbol, regime_features, market_data)
            
            # PHASE A: Fix dimension before search (prevents broadcasting errors)
            market_vector = self.mcn_adapter._fix_dim(market_vector, self.mcn_adapter.FIXED_DIM)
            
            # PHASE A: Disable MCN regime search if vector dimension ≠ 32
            if market_vector.shape[0] != 32:
                print(f"⚠️  PHASE A: Regime vector dimension mismatch: {market_vector.shape[0]} != 32, disabling MCN search")
                return {
                    "regime": "neutral",
                    "confidence": 0.0,
                    "memory_samples": 0,
                    "regime_features": regime_features,
                }
            
            if market_vector.ndim == 1:
                market_vector = market_vector.reshape(1, -1)
            
            # PHASE A: Final dimension check before search
            if market_vector.shape[1] != 32:
                print(f"⚠️  PHASE A: Regime vector final dimension mismatch: {market_vector.shape[1]} != 32, disabling MCN search")
                return {
                    "regime": "neutral",
                    "confidence": 0.0,
                    "memory_samples": 0,
                    "regime_features": regime_features,
                }
            
            # PHASE E: Search mcn_regime for similar historical regimes
            target_mcn = self.mcn_adapter.mcn_regime
            if not target_mcn:
                return {
                    "regime": "neutral",
                    "confidence": 0.0,
                    "memory_samples": 0,
                    "regime_features": regime_features,
                }
            
            # HEAP CORRUPTION FIX: Validate vector before search
            try:
                if market_vector is None or market_vector.size == 0:
                    return {
                        "regime": "neutral",
                        "confidence": 0.0,
                        "memory_samples": 0,
                        "regime_features": regime_features,
                    }
                
                if market_vector.ndim == 1:
                    market_vector = market_vector.reshape(1, -1)
                elif market_vector.ndim != 2:
                    return {
                        "regime": "neutral",
                        "confidence": 0.0,
                        "memory_samples": 0,
                        "regime_features": regime_features,
                    }
                
                if market_vector.shape[1] != 32:
                    market_vector = self.mcn_adapter._fix_dim(market_vector.flatten(), 32).reshape(1, -1)
                
                market_vector = market_vector.astype(np.float32)
                
                # Final validation before native call
                if market_vector.shape != (1, 32):
                    return {
                        "regime": "neutral",
                        "confidence": 0.0,
                        "memory_samples": 0,
                        "regime_features": regime_features,
                    }
            except Exception:
                return {
                    "regime": "neutral",
                    "confidence": 0.0,
                    "memory_samples": 0,
                    "regime_features": regime_features,
                }
            
            # HEAP CORRUPTION FIX: Search MCN with thread lock and comprehensive error handling
            try:
                with self.mcn_adapter.thread_lock:
                    meta_list, scores = target_mcn.search(market_vector, k=50)
            except (ValueError, TypeError, AttributeError, MemoryError, RuntimeError, OSError) as e:
                # HEAP CORRUPTION FIX: Catch all native errors silently
                import logging
                logger = logging.getLogger(__name__)
                logger.debug("MCN regime search failed for %s: %s", symbol, type(e).__name__)
                return {
                    "regime": "neutral",
                    "confidence": 0.0,
                    "memory_samples": 0,
                    "regime_features": regime_features,
                }
            except Exception as e:
                # HEAP CORRUPTION FIX: Catch any other errors silently
                import logging
                logger = logging.getLogger(__name__)
                logger.debug("MCN regime search error for %s: %s", symbol, type(e).__name__)
                return {
                    "regime": "neutral",
                    "confidence": 0.0,
                    "memory_samples": 0,
                    "regime_features": regime_features,
                }
            
            # PHASE 2: Ensure meta_list and scores have matching lengths with robust checks
            if scores is not None:
                try:
                    # Convert numpy array to list if needed for len()
                    if hasattr(scores, '__len__'):
                        scores_len = len(scores)
                    else:
                        scores_len = 0
                except (TypeError, ValueError):
                    scores_len = 0
            else:
                scores_len = 0
            
            meta_list_len = len(meta_list) if meta_list else 0
            
            # PHASE 2: Truncate to minimum length to avoid shape mismatch
            min_len = min(meta_list_len, scores_len) if scores_len > 0 else meta_list_len
            if min_len < meta_list_len:
                meta_list = meta_list[:min_len]
                print(f"⚠️  MCN search returned meta_list(k={meta_list_len}) and scores(k={scores_len}), truncating to min({min_len})")
            
            if scores is not None and min_len < scores_len:
                try:
                    # Safely truncate scores array
                    if hasattr(scores, '__getitem__'):
                        scores = scores[:min_len]
                    else:
                        scores = None
                except Exception as e:
                    print(f"⚠️  Error truncating scores array: {e}")
                    scores = None
            
            # PHASE 2: Analyze regime patterns from historical samples with error handling
            try:
                regime_classifications = self._classify_regime_from_samples(
                    meta_list, scores, regime_features
                )
            except Exception as e:
                print(f"⚠️  Error classifying regime from samples: {e}")
                regime_classifications = {}
            
            # Determine dominant regime
            regime_counts = {}
            total_value = 0.0
            memory_samples = 0
            
            for regime, value_weight in regime_classifications.items():
                regime_counts[regime] = regime_counts.get(regime, 0.0) + value_weight
                total_value += value_weight
                memory_samples += 1
            
            # Get dominant regime
            if regime_counts:
                dominant_regime = max(regime_counts.items(), key=lambda x: x[1])[0]
                confidence = regime_counts[dominant_regime] / total_value if total_value > 0 else 0.0
            else:
                # PHASE: If no pattern match, return "neutral"
                dominant_regime = "neutral"
                confidence = 0.3  # Low confidence for neutral (no pattern match)
            
            # PHASE: Normalize regime to one of the allowed types
            regime_map = {
                "bull_trend": "momentum",
                "bear_trend": "risk_off",
                "high_vol": "volatility",
                "low_vol": "risk_on",
                "ranging": "neutral",
                "mixed": "neutral",
                "unknown": "neutral"
            }
            normalized_regime = regime_map.get(dominant_regime, "neutral")
            
            # Record current market state in MCN for future learning
            try:
                self._record_market_state(symbol, regime_features, normalized_regime)
            except Exception:
                # Don't fail if recording fails
                pass
            
            # STABILITY: Always return safe dict with all required fields
            volatility_value = regime_features.get("volatility") if regime_features else None
            risk_level = "high" if volatility_value and volatility_value > 0.3 else ("low" if volatility_value and volatility_value < 0.1 else "normal")
            
            return {
                "regime": normalized_regime,
                "confidence": min(1.0, max(0.0, confidence)),
                "volatility": volatility_value,
                "risk_level": risk_level,
                "memory_samples": memory_samples,
                "regime_features": regime_features,
            }
        except Exception as e:
            # STABILITY: Always-safe regime detection - catch all errors and return safe fallback
            logger.debug("MCN regime search failed for %s: %s", symbol, type(e).__name__)
            # Try to get basic market data for fallback regime detection
            try:
                from ..market_data.market_data_provider import call_with_fallback
                price_data = call_with_fallback("get_price", symbol)
                if price_data and hasattr(price_data, 'change_percent'):
                    change_pct = price_data.change_percent or 0.0
                    # Simple regime detection based on price change
                    if change_pct > 0.02:
                        regime = "momentum"
                    elif change_pct < -0.02:
                        regime = "risk_off"
                    else:
                        regime = "neutral"
                    return {
                        "regime": regime,
                        "confidence": 0.5,
                        "volatility": None,
                        "risk_level": "normal",
                        "memory_samples": 0,
                        "regime_features": {}
                    }
            except:
                pass
            return {
                "regime": "neutral",  # Changed from "unknown" to "neutral" for better UX
                "confidence": 0.3,
                "volatility": None,
                "risk_level": "normal",
                "memory_samples": 0,
                "regime_features": {}
            }
    
    def _extract_regime_features(
        self,
        symbol: str,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract features for regime classification."""
        candles = market_data.get("candles", [])
        volatility = market_data.get("volatility", 0.0)
        
        if len(candles) < 20:
            return {
                "volatility": volatility,
                "momentum": 0.0,
                "trend_strength": 0.0,
                "volume_trend": "normal",
                "sma_slope": 0.0,
                "ema_slope": 0.0,
            }
        
        # Calculate indicators
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        
        # Calculate SMA slopes (20 and 50 period)
        sma_20 = self.indicator_calc.calculate_sma(closes, 20)
        sma_50 = self.indicator_calc.calculate_sma(closes, 50)
        ema_12 = self.indicator_calc.calculate_ema(closes, 12)
        ema_26 = self.indicator_calc.calculate_ema(closes, 26)
        
        # Calculate momentum (price change over last 10 candles)
        if len(closes) >= 10:
            momentum = ((closes[-1] - closes[-10]) / closes[-10]) * 100
        else:
            momentum = 0.0
        
        # Calculate SMA slope (trend direction)
        if len(sma_20) >= 2:
            sma_slope = ((sma_20[-1] - sma_20[-2]) / sma_20[-2]) * 100
        else:
            sma_slope = 0.0
        
        # Calculate EMA slope
        if len(ema_12) >= 2:
            ema_slope = ((ema_12[-1] - ema_12[-2]) / ema_12[-2]) * 100
        else:
            ema_slope = 0.0
        
        # Calculate trend strength (how aligned are SMAs)
        if len(sma_20) > 0 and len(sma_50) > 0:
            if sma_20[-1] > sma_50[-1]:
                trend_strength = min(1.0, (sma_20[-1] - sma_50[-1]) / sma_50[-1])
            else:
                trend_strength = -min(1.0, (sma_50[-1] - sma_20[-1]) / sma_20[-1])
        else:
            trend_strength = 0.0
        
        # Calculate volume trend
        if len(volumes) >= 10:
            recent_avg_volume = sum(volumes[-5:]) / 5
            older_avg_volume = sum(volumes[-10:-5]) / 5 if len(volumes) >= 10 else recent_avg_volume
            
            if older_avg_volume > 0:
                volume_change = (recent_avg_volume - older_avg_volume) / older_avg_volume
                if volume_change > 0.2:
                    volume_trend = "increasing"
                elif volume_change < -0.2:
                    volume_trend = "decreasing"
                else:
                    volume_trend = "normal"
            else:
                volume_trend = "normal"
        else:
            volume_trend = "normal"
        
        return {
            "volatility": volatility,
            "momentum": momentum,
            "trend_strength": trend_strength,
            "volume_trend": volume_trend,
            "sma_slope": sma_slope,
            "ema_slope": ema_slope,
        }
    
    def _create_market_state_vector(
        self,
        symbol: str,
        regime_features: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> np.ndarray:
        """
        PHASE A: Create embedding vector for market state.
        All regime features are wrapped with fixed32() to ensure consistent dimensions.
        """
        # PHASE A: Extract and fix all numeric features to 32-dim arrays
        volatility = fixed32([regime_features.get('volatility', 0.0)])
        momentum = fixed32([regime_features.get('momentum', 0.0)])
        trend_strength = fixed32([regime_features.get('trend_strength', 0.0)])
        sma_slope = fixed32([regime_features.get('sma_slope', 0.0)])
        ema_slope = fixed32([regime_features.get('ema_slope', 0.0)])
        
        # PHASE A: Extract volume trend as numeric (convert string to numeric)
        volume_trend_str = regime_features.get('volume_trend', 'normal')
        volume_trend_val = 1.0 if volume_trend_str == "increasing" else (-1.0 if volume_trend_str == "decreasing" else 0.0)
        volume_trend = fixed32([volume_trend_val])
        
        # PHASE A: Create feature vector by concatenating fixed32 arrays
        feature_arrays = [volatility, momentum, trend_strength, sma_slope, ema_slope, volume_trend]
        
        # PHASE A: Add candle features (if available) - each candle feature also fixed32
        candles = market_data.get("candles", [])
        if len(candles) >= 5:
            recent_candles = candles[-5:]
            for candle in recent_candles:
                # PHASE A: Each candle feature wrapped in fixed32
                candle_features = fixed32([candle.open, candle.high, candle.low, candle.close, candle.volume])
                feature_arrays.append(candle_features)
        
        # PHASE A: Concatenate all fixed32 arrays (each is 32-dim, so total will be 32 * N)
        # Then take first 32 elements to ensure exact 32-dim output
        if feature_arrays:
            combined = np.concatenate(feature_arrays)
            # PHASE A: Ensure output is exactly 32 dimensions
            combined = fixed32(combined)
        else:
            combined = fixed32([0.0] * 32)
        
        # PHASE A: Final check - must be exactly 32
        if len(combined) != 32:
            print(f"⚠️  PHASE A: Combined feature vector dimension mismatch: {len(combined)} != 32, forcing to 32")
            combined = fixed32(combined)
        
        return combined.astype(np.float32)
    
    def _classify_regime_from_samples(
        self,
        meta_list: List[Dict[str, Any]],
        scores: Optional[List[float]],
        regime_features: Dict[str, Any]
    ) -> Dict[str, float]:
        """Classify regime from historical MCN samples.
        
        PHASE 2: Robust error handling to prevent shape mismatch errors.
        """
        regime_classifications = {}
        
        # PHASE 2: Safely get scores length without evaluating numpy array as boolean
        scores_len = 0
        if scores is not None:
            try:
                # Handle numpy arrays and lists
                if hasattr(scores, '__len__'):
                    scores_len = len(scores)
                elif hasattr(scores, 'shape'):
                    scores_len = scores.shape[0] if len(scores.shape) > 0 else 0
            except (TypeError, ValueError, AttributeError):
                scores_len = 0
        
        # PHASE 2: Ensure we don't iterate beyond available scores
        max_iter = min(len(meta_list), scores_len if scores_len > 0 else len(meta_list), 50)
        
        for i in range(max_iter):
            try:
                meta = meta_list[i]
                payload = meta.get("payload", {})
                
                # PHASE 2: Safely access scores[i] without boolean evaluation
                value_weight = 0.0
                if scores is not None and i < scores_len:
                    try:
                        # Handle numpy arrays and lists
                        if hasattr(scores, '__getitem__'):
                            score_val = scores[i]
                            # Convert numpy scalar to float if needed
                            if hasattr(score_val, 'item'):
                                value_weight = float(score_val.item())
                            else:
                                value_weight = float(score_val)
                        else:
                            value_weight = 0.0
                    except (TypeError, IndexError, ValueError, AttributeError) as e:
                        # PHASE 2: Log warning but continue processing
                        if i == 0:  # Only log once to avoid spam
                            print(f"⚠️  MCN regime search shape mismatch at index {i}, using default weight: {e}")
                        value_weight = 0.0
            except (IndexError, KeyError, AttributeError) as e:
                # PHASE 2: Skip invalid meta entries
                continue
            
            # Extract regime from historical events
            historical_regime = payload.get("market_regime", None)
            if not historical_regime:
                # Try to infer from payload data
                historical_regime = self._infer_regime_from_payload(payload, regime_features)
            
            if historical_regime:
                regime_classifications[historical_regime] = (
                    regime_classifications.get(historical_regime, 0.0) + value_weight
                )
        
        return regime_classifications
    
    def _infer_regime_from_payload(
        self,
        payload: Dict[str, Any],
        current_features: Dict[str, Any]
    ) -> Optional[str]:
        """Infer regime from payload data."""
        volatility = payload.get("volatility", 0.0)
        momentum = payload.get("momentum", 0.0)
        trend_strength = payload.get("trend_strength", 0.0)
        
        # Classify based on features
        if volatility > 0.3:
            return "high_vol"
        elif volatility < 0.1:
            return "low_vol"
        elif trend_strength > 0.1 and momentum > 2.0:
            return "bull_trend"
        elif trend_strength < -0.1 and momentum < -2.0:
            return "bear_trend"
        elif abs(trend_strength) < 0.05:
            return "ranging"
        else:
            return "mixed"
    
    def _classify_from_features(self, regime_features: Dict[str, Any]) -> str:
        """Classify regime directly from features (fallback)."""
        volatility = regime_features.get("volatility", 0.0)
        momentum = regime_features.get("momentum", 0.0)
        trend_strength = regime_features.get("trend_strength", 0.0)
        
        if volatility > 0.3:
            return "high_vol"
        elif volatility < 0.1:
            return "low_vol"
        elif trend_strength > 0.1 and momentum > 2.0:
            return "bull_trend"
        elif trend_strength < -0.1 and momentum < -2.0:
            return "bear_trend"
        elif abs(trend_strength) < 0.05:
            return "ranging"
        else:
            return "mixed"
    
    def _record_market_state(
        self,
        symbol: str,
        regime_features: Dict[str, Any],
        regime: str
    ):
        """Record current market state in MCN for future learning."""
        payload = {
            "symbol": symbol,
            "regime": regime,
            "volatility": regime_features.get("volatility", 0.0),
            "momentum": regime_features.get("momentum", 0.0),
            "trend_strength": regime_features.get("trend_strength", 0.0),
            "volume_trend": regime_features.get("volume_trend", "normal"),
            "timestamp": datetime.now().isoformat(),
        }
        
        self.mcn_adapter.record_event(
            event_type="market_snapshot",
            payload=payload,
        )

