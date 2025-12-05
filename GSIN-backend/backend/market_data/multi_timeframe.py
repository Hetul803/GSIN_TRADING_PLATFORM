# backend/market_data/multi_timeframe.py
"""
Multi-timeframe trend analysis.
Computes trend indicators across multiple timeframes for confirmation.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from .market_data_provider import get_provider_with_fallback
from .types import CandleData
from ..strategy_engine.indicators import IndicatorCalculator


class MultiTimeframeAnalyzer:
    """Analyzes trends across multiple timeframes."""
    
    def __init__(self):
        self.indicator_calc = IndicatorCalculator()
        self.timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
    
    def get_multi_timeframe_trend(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Get trend analysis across multiple timeframes.
        
        Returns:
            {
                "trend_short": "up" | "down" | "flat",
                "trend_medium": "up" | "down" | "flat",
                "trend_long": "up" | "down" | "flat",
                "alignment_score": float (0-1),
                "timeframe_details": {
                    "1m": {"trend": "up", "rsi": float, "macd_hist": float},
                    ...
                }
            }
        """
        try:
            provider = get_provider_with_fallback()
            if not provider:
                return self._default_response()
            
            timeframe_details = {}
            
            # Analyze each timeframe
            for tf in self.timeframes:
                try:
                    candles = provider.get_candles(symbol, tf, limit=50)
                    if candles and len(candles) >= 20:
                        trend_info = self._analyze_timeframe(candles, tf)
                        timeframe_details[tf] = trend_info
                except Exception as e:
                    print(f"Error analyzing timeframe {tf} for {symbol}: {e}")
                    continue
            
            # Classify trends into short/medium/long
            trend_short = self._classify_trend_group(
                [timeframe_details.get("1m", {}), timeframe_details.get("5m", {})]
            )
            trend_medium = self._classify_trend_group(
                [timeframe_details.get("15m", {}), timeframe_details.get("1h", {})]
            )
            trend_long = self._classify_trend_group(
                [timeframe_details.get("4h", {}), timeframe_details.get("1d", {})]
            )
            
            # Calculate alignment score
            alignment_score = self._calculate_alignment_score(
                trend_short, trend_medium, trend_long
            )
            
            return {
                "trend_short": trend_short,
                "trend_medium": trend_medium,
                "trend_long": trend_long,
                "alignment_score": alignment_score,
                "timeframe_details": timeframe_details,
            }
        except Exception as e:
            print(f"Error getting multi-timeframe trend for {symbol}: {e}")
            return self._default_response()
    
    def _analyze_timeframe(
        self,
        candles: List[CandleData],
        timeframe: str
    ) -> Dict[str, Any]:
        """Analyze a single timeframe."""
        closes = [c.close for c in candles]
        
        # Calculate EMA slope (trend direction)
        ema_12 = self.indicator_calc.calculate_ema(closes, 12)
        ema_26 = self.indicator_calc.calculate_ema(closes, 26)
        
        # Determine trend from EMA
        if len(ema_12) >= 2 and len(ema_26) >= 2:
            ema_12_slope = ((ema_12[-1] - ema_12[-2]) / ema_12[-2]) * 100
            ema_26_slope = ((ema_26[-1] - ema_26[-2]) / ema_26[-2]) * 100
            
            if ema_12[-1] > ema_26[-1] and ema_12_slope > 0:
                trend = "up"
            elif ema_12[-1] < ema_26[-1] and ema_12_slope < 0:
                trend = "down"
            else:
                trend = "flat"
        else:
            trend = "flat"
            ema_12_slope = 0.0
            ema_26_slope = 0.0
        
        # Calculate RSI
        rsi = self.indicator_calc.calculate_rsi(closes, 14)
        rsi_value = rsi[-1] if rsi else 50.0
        
        # Calculate MACD histogram
        macd = self.indicator_calc.calculate_macd(closes, 12, 26, 9)
        macd_hist = macd["histogram"][-1] if macd["histogram"] else 0.0
        
        # Calculate volume delta (recent vs older average)
        volumes = [c.volume for c in candles]
        if len(volumes) >= 10:
            recent_avg = sum(volumes[-5:]) / 5
            older_avg = sum(volumes[-10:-5]) / 5
            volume_delta = ((recent_avg - older_avg) / older_avg) * 100 if older_avg > 0 else 0.0
        else:
            volume_delta = 0.0
        
        return {
            "trend": trend,
            "rsi": rsi_value,
            "macd_hist": macd_hist,
            "volume_delta": volume_delta,
            "ema_slope": ema_12_slope,
        }
    
    def _classify_trend_group(self, timeframe_infos: List[Dict[str, Any]]) -> str:
        """Classify trend for a group of timeframes (short/medium/long)."""
        if not timeframe_infos:
            return "flat"
        
        trends = [info.get("trend", "flat") for info in timeframe_infos if info]
        
        if not trends:
            return "flat"
        
        up_count = trends.count("up")
        down_count = trends.count("down")
        
        if up_count > down_count:
            return "up"
        elif down_count > up_count:
            return "down"
        else:
            return "flat"
    
    def _calculate_alignment_score(
        self,
        trend_short: str,
        trend_medium: str,
        trend_long: str
    ) -> float:
        """
        Calculate alignment score (0-1) based on trend agreement.
        
        Formula:
        - All aligned (all up or all down): 1.0
        - Two aligned: 0.67
        - All different: 0.33
        - Any flat reduces score
        """
        trends = [trend_short, trend_medium, trend_long]
        
        # Count non-flat trends
        non_flat = [t for t in trends if t != "flat"]
        
        if len(non_flat) == 0:
            return 0.5  # Neutral if all flat
        
        # Check alignment
        if len(set(non_flat)) == 1:
            # All non-flat trends are the same
            alignment = 1.0
        elif len(set(non_flat)) == 2:
            # Two different trends
            alignment = 0.67
        else:
            # All different
            alignment = 0.33
        
        # Penalize for flat trends
        flat_count = trends.count("flat")
        flat_penalty = flat_count * 0.1
        
        return max(0.0, min(1.0, alignment - flat_penalty))
    
    def _default_response(self) -> Dict[str, Any]:
        """Return default response when analysis fails."""
        return {
            "trend_short": "flat",
            "trend_medium": "flat",
            "trend_long": "flat",
            "alignment_score": 0.5,
            "timeframe_details": {},
        }

