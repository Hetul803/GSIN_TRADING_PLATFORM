# backend/market_data/volume_analyzer.py
"""
Volume confirmation analysis.
Validates entry signals based on volume trends and strength.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .market_data_provider import get_provider_with_fallback  # For live data only
from .providers.yahoo_provider import get_yahoo_historical_provider  # For historical data
from .types import CandleData


class VolumeAnalyzer:
    """Analyzes volume trends for trade confirmation."""
    
    def __init__(self):
        pass
    
    def get_volume_confirmation(
        self,
        symbol: str,
        timeframe: str = "1d"
    ) -> Dict[str, Any]:
        """
        Get volume confirmation for a symbol.
        
        Returns:
            {
                "volume_trend": "increasing" | "decreasing" | "normal",
                "volume_strength": float (0-1),
                "volume_ratio": float (recent_avg / historical_avg),
                "is_above_average": bool,
                "recommendation": "confirm" | "caution" | "block"
            }
        """
        try:
            from .market_data_provider import call_with_fallback
            
            # Get candles for volume analysis through request queue
            candles = call_with_fallback("get_candles", symbol, timeframe, limit=50)
            
            if not candles or len(candles) < 20:
                return self._default_response()
            
            volumes = [c.volume for c in candles]
            
            # Calculate volume statistics
            recent_volumes = volumes[-5:]  # Last 5 candles
            older_volumes = volumes[-20:-5]  # Previous 15 candles
            
            recent_avg = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
            older_avg = sum(older_volumes) / len(older_volumes) if older_volumes else 0
            historical_avg = sum(volumes) / len(volumes)
            
            # Determine volume trend
            if older_avg > 0:
                volume_change = ((recent_avg - older_avg) / older_avg) * 100
                
                if volume_change > 20:
                    volume_trend = "increasing"
                elif volume_change < -20:
                    volume_trend = "decreasing"
                else:
                    volume_trend = "normal"
            else:
                volume_trend = "normal"
                volume_change = 0.0
            
            # Calculate volume ratio (recent vs historical average)
            volume_ratio = recent_avg / historical_avg if historical_avg > 0 else 1.0
            is_above_average = volume_ratio > 1.0
            
            # Calculate volume strength (0-1)
            # Higher strength = more volume, increasing trend
            if volume_trend == "increasing":
                volume_strength = min(1.0, 0.5 + (volume_ratio - 1.0) * 0.5)
            elif volume_trend == "decreasing":
                volume_strength = max(0.0, 0.5 - (1.0 - volume_ratio) * 0.5)
            else:
                volume_strength = 0.5 + (volume_ratio - 1.0) * 0.2
                volume_strength = max(0.0, min(1.0, volume_strength))
            
            # Generate recommendation
            if volume_ratio < 0.5:
                # Extremely low volume
                recommendation = "block"
            elif volume_trend == "decreasing" and volume_ratio < 0.8:
                # Decreasing and below average
                recommendation = "caution"
            elif volume_trend == "increasing" and volume_ratio > 1.2:
                # Increasing and above average
                recommendation = "confirm"
            elif is_above_average:
                recommendation = "confirm"
            else:
                recommendation = "caution"
            
            return {
                "volume_trend": volume_trend,
                "volume_strength": max(0.0, min(1.0, volume_strength)),
                "volume_ratio": volume_ratio,
                "is_above_average": is_above_average,
                "recommendation": recommendation,
            }
        except Exception as e:
            print(f"Error analyzing volume for {symbol}: {e}")
            return self._default_response()
    
    def _default_response(self) -> Dict[str, Any]:
        """Return default response when analysis fails."""
        return {
            "volume_trend": "normal",
            "volume_strength": 0.5,
            "volume_ratio": 1.0,
            "is_above_average": False,
            "recommendation": "caution",
        }

