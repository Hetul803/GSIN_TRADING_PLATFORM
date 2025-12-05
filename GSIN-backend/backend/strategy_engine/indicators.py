# backend/strategy_engine/indicators.py
"""
Technical indicators library for strategy execution.
Supports: RSI, MACD, EMA, VWAP, Bollinger Bands, ATR, SMA
"""
from typing import List, Dict, Any, Optional
import numpy as np
from ..market_data.types import CandleData


class IndicatorCalculator:
    """Calculator for technical indicators."""
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return []
        sma = []
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            sma.append(sum(window) / period)
        return sma
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return []
        ema = []
        multiplier = 2.0 / (period + 1)
        # First EMA value is SMA
        sma = sum(prices[:period]) / period
        ema.append(sma)
        
        for i in range(period, len(prices)):
            ema_val = (prices[i] - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_val)
        return ema
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
        """Calculate Relative Strength Index (RSI)."""
        if len(prices) < period + 1:
            return []
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]
        
        rsi = []
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100.0 - (100.0 / (1.0 + rs)))
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100.0 - (100.0 / (1.0 + rs)))
        
        return rsi
    
    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, List[float]]:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        if len(prices) < slow_period:
            return {"macd": [], "signal": [], "histogram": []}
        
        ema_fast = IndicatorCalculator.calculate_ema(prices, fast_period)
        ema_slow = IndicatorCalculator.calculate_ema(prices, slow_period)
        
        # Align lengths
        min_len = min(len(ema_fast), len(ema_slow))
        macd_line = [ema_fast[i] - ema_slow[i] for i in range(min_len)]
        
        # Calculate signal line (EMA of MACD)
        signal_line = IndicatorCalculator.calculate_ema(macd_line, signal_period)
        
        # Calculate histogram
        histogram = []
        for i in range(len(signal_line)):
            if i < len(macd_line):
                histogram.append(macd_line[i] - signal_line[i])
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, List[float]]:
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            return {"upper": [], "middle": [], "lower": []}
        
        sma = IndicatorCalculator.calculate_sma(prices, period)
        bands = {"upper": [], "middle": sma, "lower": []}
        
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            std = np.std(window)
            middle = sma[i - (period - 1)]
            bands["upper"].append(middle + (num_std * std))
            bands["lower"].append(middle - (num_std * std))
        
        return bands
    
    @staticmethod
    def calculate_atr(candles: List[CandleData], period: int = 14) -> List[float]:
        """Calculate Average True Range (ATR)."""
        if len(candles) < period + 1:
            return []
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            true_ranges.append(max(tr1, tr2, tr3))
        
        # Initial ATR is SMA of first period
        atr = [sum(true_ranges[:period]) / period]
        
        # Subsequent ATR using Wilder's smoothing
        for i in range(period, len(true_ranges)):
            atr_val = (atr[-1] * (period - 1) + true_ranges[i]) / period
            atr.append(atr_val)
        
        return atr
    
    @staticmethod
    def calculate_vwap(candles: List[CandleData]) -> List[float]:
        """Calculate Volume-Weighted Average Price (VWAP)."""
        if not candles:
            return []
        
        vwap = []
        cumulative_volume = 0.0
        cumulative_price_volume = 0.0
        
        for candle in candles:
            typical_price = (candle.high + candle.low + candle.close) / 3.0
            volume = candle.volume if hasattr(candle, 'volume') and candle.volume else 1.0
            
            cumulative_volume += volume
            cumulative_price_volume += typical_price * volume
            
            if cumulative_volume > 0:
                vwap.append(cumulative_price_volume / cumulative_volume)
            else:
                vwap.append(typical_price)
        
        return vwap
    
    @staticmethod
    def calculate_all_indicators(candles: List[CandleData]) -> Dict[str, Any]:
        """Calculate all common indicators from candles."""
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        
        indicators = {
            "sma_20": IndicatorCalculator.calculate_sma(closes, 20),
            "sma_50": IndicatorCalculator.calculate_sma(closes, 50),
            "sma_200": IndicatorCalculator.calculate_sma(closes, 200),
            "ema_12": IndicatorCalculator.calculate_ema(closes, 12),
            "ema_26": IndicatorCalculator.calculate_ema(closes, 26),
            "ema_50": IndicatorCalculator.calculate_ema(closes, 50),
            "rsi": IndicatorCalculator.calculate_rsi(closes, 14),
            "macd": IndicatorCalculator.calculate_macd(closes, 12, 26, 9),
            "bollinger": IndicatorCalculator.calculate_bollinger_bands(closes, 20, 2.0),
            "atr": IndicatorCalculator.calculate_atr(candles, 14),
            "vwap": IndicatorCalculator.calculate_vwap(candles),
        }
        
        return indicators

