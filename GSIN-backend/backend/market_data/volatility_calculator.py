# backend/market_data/volatility_calculator.py
"""
Real volatility calculation using proper methods:
- Standard deviation (historical volatility)
- ATR (Average True Range)
- GARCH (Generalized Autoregressive Conditional Heteroskedasticity)
"""
import numpy as np
from typing import List, Optional
from datetime import datetime, timedelta

from ..types import VolatilityData, CandleData


class VolatilityCalculator:
    """Calculate real volatility metrics."""
    
    @staticmethod
    def calculate_volatility(
        candles: List[CandleData],
        method: str = "stddev"
    ) -> VolatilityData:
        """
        Calculate volatility using specified method.
        
        Args:
            candles: List of candle data
            method: "stddev", "atr", or "garch"
        
        Returns:
            VolatilityData
        """
        if not candles or len(candles) < 2:
            return VolatilityData(
                symbol=candles[0].symbol if candles else "UNKNOWN",
                volatility=0.0,
                method=method,
                timestamp=datetime.now()
            )
        
        symbol = candles[0].symbol
        
        if method == "stddev":
            return VolatilityCalculator._calculate_stddev_volatility(candles, symbol)
        elif method == "atr":
            return VolatilityCalculator._calculate_atr_volatility(candles, symbol)
        elif method == "garch":
            return VolatilityCalculator._calculate_garch_volatility(candles, symbol)
        else:
            return VolatilityCalculator._calculate_stddev_volatility(candles, symbol)
    
    @staticmethod
    def _calculate_stddev_volatility(
        candles: List[CandleData],
        symbol: str
    ) -> VolatilityData:
        """Calculate historical volatility using standard deviation of returns."""
        if len(candles) < 2:
            return VolatilityData(
                symbol=symbol,
                volatility=0.0,
                method="stddev",
                timestamp=datetime.now()
            )
        
        # Calculate returns
        returns = []
        for i in range(1, len(candles)):
            prev_close = candles[i-1].close
            curr_close = candles[i].close
            if prev_close > 0:
                ret = (curr_close - prev_close) / prev_close
                returns.append(ret)
        
        if not returns:
            return VolatilityData(
                symbol=symbol,
                volatility=0.0,
                method="stddev",
                timestamp=datetime.now()
            )
        
        # Annualized volatility (assuming daily candles)
        daily_vol = np.std(returns)
        annualized_vol = daily_vol * np.sqrt(252)  # 252 trading days per year
        
        return VolatilityData(
            symbol=symbol,
            volatility=annualized_vol,
            method="stddev",
            timestamp=datetime.now()
        )
    
    @staticmethod
    def _calculate_atr_volatility(
        candles: List[CandleData],
        symbol: str,
        period: int = 14
    ) -> VolatilityData:
        """Calculate Average True Range (ATR) volatility."""
        if len(candles) < period + 1:
            return VolatilityData(
                symbol=symbol,
                volatility=0.0,
                method="atr",
                timestamp=datetime.now()
            )
        
        # Calculate True Range
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        if not true_ranges:
            return VolatilityData(
                symbol=symbol,
                volatility=0.0,
                method="atr",
                timestamp=datetime.now()
            )
        
        # Calculate ATR (simple moving average of TR)
        atr_values = []
        for i in range(period - 1, len(true_ranges)):
            window = true_ranges[i - period + 1:i + 1]
            atr = np.mean(window)
            atr_values.append(atr)
        
        if not atr_values:
            return VolatilityData(
                symbol=symbol,
                volatility=0.0,
                method="atr",
                timestamp=datetime.now()
            )
        
        # Normalize ATR by current price
        current_price = candles[-1].close
        normalized_atr = (atr_values[-1] / current_price) if current_price > 0 else 0.0
        
        # Annualize (rough approximation)
        annualized_vol = normalized_atr * np.sqrt(252)
        
        return VolatilityData(
            symbol=symbol,
            volatility=annualized_vol,
            method="atr",
            timestamp=datetime.now()
        )
    
    @staticmethod
    def _calculate_garch_volatility(
        candles: List[CandleData],
        symbol: str
    ) -> VolatilityData:
        """
        Calculate GARCH volatility (simplified version).
        
        Note: Full GARCH requires arch library. This is a simplified approximation.
        """
        if len(candles) < 30:
            # Fallback to stddev if insufficient data
            return VolatilityCalculator._calculate_stddev_volatility(candles, symbol)
        
        # Calculate returns
        returns = []
        for i in range(1, len(candles)):
            prev_close = candles[i-1].close
            curr_close = candles[i].close
            if prev_close > 0:
                ret = (curr_close - prev_close) / prev_close
                returns.append(ret)
        
        if len(returns) < 30:
            return VolatilityCalculator._calculate_stddev_volatility(candles, symbol)
        
        # Simplified GARCH(1,1) approximation
        # Full implementation would use arch library
        # This is a basic EWMA (Exponentially Weighted Moving Average) approximation
        
        alpha = 0.1  # Weight for recent volatility
        beta = 0.85  # Weight for previous volatility
        gamma = 0.05  # Weight for long-term average
        
        # Initialize
        long_term_var = np.var(returns)
        var_t = long_term_var
        
        # Iterate through returns
        for ret in returns[-30:]:  # Use last 30 returns
            var_t = gamma * long_term_var + alpha * (ret ** 2) + beta * var_t
        
        # Annualize
        volatility = np.sqrt(var_t) * np.sqrt(252)
        
        return VolatilityData(
            symbol=symbol,
            volatility=volatility,
            method="garch",
            timestamp=datetime.now()
        )

