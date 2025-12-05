# backend/brain/cold_start_regime_detector.py
"""
Cold Start Regime Detector - Simple rule-based regime detection using SMA/VIX rules.

This detector works BEFORE MCN is fully trained, providing basic regime classification
using simple technical indicators (SMA crossovers, VIX levels, volatility).

Used as fallback when MCN is unavailable or not yet trained.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import numpy as np

from ..market_data.market_data_provider import call_with_fallback
from ..strategy_engine.indicators import IndicatorCalculator


class ColdStartRegimeDetector:
    """
    Simple rule-based regime detector for cold start scenarios.
    
    Uses:
    - SMA crossovers (50/200 day) for trend detection
    - VIX levels (if available) for volatility regime
    - Price momentum for market direction
    - Volume trends for confirmation
    """
    
    def __init__(self):
        self.indicator_calc = IndicatorCalculator()
    
    def detect_regime(self, symbol: str) -> Dict[str, Any]:
        """
        Detect market regime using simple SMA/VIX rules.
        
        Regime Classification:
        - "bull_trend": SMA50 > SMA200, positive momentum, low volatility
        - "bear_trend": SMA50 < SMA200, negative momentum, high volatility
        - "high_vol": VIX > 20 or volatility > 30%
        - "low_vol": VIX < 15 or volatility < 15%
        - "ranging": No clear trend, low momentum
        - "neutral": Default fallback
        
        Args:
            symbol: Stock symbol to analyze
        
        Returns:
            {
                "regime": str,
                "confidence": float (0-1),
                "volatility": float | None,
                "risk_level": str,
                "method": "cold_start"  # Indicates this is rule-based, not MCN
            }
        """
        try:
            # Get historical candles (need at least 200 days for SMA200)
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=250)  # Extra buffer
            
            candles = call_with_fallback(
                "get_candles",
                symbol,
                "1d",
                limit=250,
                start=start_date,
                end=end_date
            )
            
            if not candles or len(candles) < 50:
                # Not enough data
                return {
                    "regime": "neutral",
                    "confidence": 0.3,
                    "volatility": None,
                    "risk_level": "normal",
                    "method": "cold_start"
                }
            
            # Extract price data
            closes = [c.close for c in candles]
            volumes = [c.volume for c in candles]
            
            # Calculate SMAs
            sma_50 = self.indicator_calc.calculate_sma(closes, 50)
            sma_200 = self.indicator_calc.calculate_sma(closes, 200)
            
            # Calculate volatility (30-day rolling)
            if len(closes) >= 30:
                returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
                recent_returns = returns[-30:]
                volatility = np.std(recent_returns) * np.sqrt(252) * 100  # Annualized %
            else:
                volatility = None
            
            # Calculate momentum (price change over last 20 days)
            if len(closes) >= 20:
                momentum = ((closes[-1] - closes[-20]) / closes[-20]) * 100
            else:
                momentum = 0.0
            
            # Try to get VIX (volatility index) if available
            vix_level = None
            try:
                # Try to get VIX data (if symbol is VIX or we can fetch it)
                if symbol.upper() == "VIX":
                    price_data = call_with_fallback("get_price", "VIX")
                    if price_data:
                        vix_level = price_data.price
                else:
                    # Try to get VIX as market indicator
                    vix_price = call_with_fallback("get_price", "VIX")
                    if vix_price:
                        vix_level = vix_price.price
            except Exception:
                # VIX not available, use volatility instead
                pass
            
            # Classify regime using rules
            
            # Rule 1: Check volatility regime (VIX or calculated volatility)
            if vix_level is not None:
                if vix_level > 20:
                    regime = "high_vol"
                    confidence = 0.8
                    risk_level = "high"
                elif vix_level < 15:
                    regime = "low_vol"
                    confidence = 0.7
                    risk_level = "low"
                else:
                    regime = "neutral"
                    confidence = 0.5
                    risk_level = "normal"
            elif volatility is not None:
                if volatility > 30:
                    regime = "high_vol"
                    confidence = 0.75
                    risk_level = "high"
                elif volatility < 15:
                    regime = "low_vol"
                    confidence = 0.7
                    risk_level = "low"
                else:
                    regime = "neutral"
                    confidence = 0.5
                    risk_level = "normal"
            else:
                regime = "neutral"
                confidence = 0.4
                risk_level = "normal"
            
            # Rule 2: Check trend (SMA crossover)
            if len(sma_50) > 0 and len(sma_200) > 0:
                sma50_current = sma_50[-1]
                sma200_current = sma_200[-1]
                
                # Calculate SMA slopes
                if len(sma_50) >= 2:
                    sma50_slope = ((sma_50[-1] - sma_50[-2]) / sma_50[-2]) * 100
                else:
                    sma50_slope = 0.0
                
                if len(sma_200) >= 2:
                    sma200_slope = ((sma_200[-1] - sma_200[-2]) / sma_200[-2]) * 100
                else:
                    sma200_slope = 0.0
                
                # Bull trend: SMA50 > SMA200, both rising, positive momentum
                if sma50_current > sma200_current and sma50_slope > 0 and momentum > 2:
                    if regime == "high_vol":
                        # High volatility bull (risky bull)
                        regime = "bull_trend"
                        confidence = min(0.9, confidence + 0.2)
                    elif regime == "low_vol":
                        # Low volatility bull (stable bull)
                        regime = "bull_trend"
                        confidence = min(0.95, confidence + 0.3)
                    else:
                        regime = "bull_trend"
                        confidence = min(0.85, confidence + 0.15)
                
                # Bear trend: SMA50 < SMA200, both falling, negative momentum
                elif sma50_current < sma200_current and sma50_slope < 0 and momentum < -2:
                    if regime == "high_vol":
                        # High volatility bear (crash risk)
                        regime = "bear_trend"
                        confidence = min(0.9, confidence + 0.2)
                        risk_level = "high"
                    elif regime == "low_vol":
                        # Low volatility bear (slow decline)
                        regime = "bear_trend"
                        confidence = min(0.85, confidence + 0.15)
                    else:
                        regime = "bear_trend"
                        confidence = min(0.8, confidence + 0.1)
            
            # Rule 3: Check for ranging market (low momentum, SMAs close together)
            if abs(momentum) < 1.0 and len(sma_50) > 0 and len(sma_200) > 0:
                sma_diff_pct = abs(sma_50[-1] - sma_200[-1]) / sma_200[-1] * 100
                if sma_diff_pct < 2.0:  # SMAs within 2% of each other
                    regime = "ranging"
                    confidence = 0.7
                    risk_level = "normal"
            
            # Normalize regime name
            regime_map = {
                "bull_trend": "momentum",
                "bear_trend": "risk_off",
                "high_vol": "volatility",
                "low_vol": "risk_on",
                "ranging": "neutral",
            }
            normalized_regime = regime_map.get(regime, "neutral")
            
            return {
                "regime": normalized_regime,
                "confidence": min(1.0, max(0.0, confidence)),
                "volatility": volatility,
                "risk_level": risk_level,
                "method": "cold_start",
                "raw_regime": regime,  # Keep original for debugging
                "indicators": {
                    "sma50": sma_50[-1] if len(sma_50) > 0 else None,
                    "sma200": sma_200[-1] if len(sma_200) > 0 else None,
                    "momentum": momentum,
                    "vix": vix_level,
                }
            }
            
        except Exception as e:
            # Always return safe fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Cold start regime detection failed for {symbol}: {e}")
            
            return {
                "regime": "neutral",
                "confidence": 0.3,
                "volatility": None,
                "risk_level": "normal",
                "method": "cold_start"
            }

