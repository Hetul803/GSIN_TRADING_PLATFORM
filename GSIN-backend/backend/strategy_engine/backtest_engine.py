# backend/strategy_engine/backtest_engine.py
"""
Backtesting engine for strategies.
Uses market data to simulate strategy execution and calculate metrics.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import statistics

from ..market_data.types import CandleData
from ..market_data.market_data_provider import get_historical_provider
# TWELVE DATA INTEGRATION: Backtest engine uses historical provider (Twelve Data PRIMARY)
from .monte_carlo import MonteCarloSimulator
from .indicators import IndicatorCalculator
from .ruleset_parser import RulesetParser
from .constants import DEFAULT_SYMBOLS, MIN_ASSETS_FOR_GENERALIZATION, GENERALIZATION_WINRATE_THRESHOLD
from .backtest_constants import get_required_candles


class BacktestEngine:
    """Engine for running strategy backtests."""
    
    def __init__(self, market_provider=None):
        # TWELVE DATA INTEGRATION: Use historical provider (Twelve Data PRIMARY) for backtesting
        if market_provider is None:
            self.market_provider = get_historical_provider()
        else:
            self.market_provider = market_provider
        self.indicator_calc = IndicatorCalculator()
        self.ruleset_parser = RulesetParser()
        self.monte_carlo = MonteCarloSimulator(n_simulations=1000)
    
    def run_backtest(
        self,
        symbol: str,
        ruleset: Dict[str, Any],
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        train_test_split: float = 0.7,
        use_rolling_walkforward: bool = False,  # Default False for backward compatibility, set True for rolling WFA
        user_risk_profile: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        strategy_risk_score: Optional[float] = None,
        unlimited_capital_mode: bool = True  # Default to unlimited for Brain research
    ) -> Dict[str, Any]:
        """
        Run a backtest for a strategy with rolling walk-forward analysis for true stability validation.
        
        IMPROVEMENT: Upgraded from simple 50/50 split to rolling walk-forward analysis
        (Train 2021/Test 2022, Train 2022/Test 2023) to prove true stability.
        
        Args:
            symbol: Symbol to test (e.g., "AAPL")
            ruleset: Strategy ruleset with conditions and indicators
            timeframe: Timeframe (e.g., "1d", "1h")
            start_date: Backtest start date
            end_date: Backtest end date
            train_test_split: Fraction of data for training (default 0.7 = 70% train, 30% test)
            use_rolling_walkforward: If True, use rolling walk-forward instead of simple split
        
        Returns:
            Dictionary with backtest results including:
            - Combined metrics (full period)
            - train_metrics (in-sample performance)
            - test_metrics (out-of-sample performance)
            - wfa_results (walk-forward analysis results if enabled)
            - overfitting_detected (boolean flag)
        """
        # NORMALIZE: Normalize ruleset before validation
        from .strategy_normalizer import normalize_strategy_ruleset
        try:
            normalized_ruleset = normalize_strategy_ruleset(ruleset)
        except Exception as e:
            # If normalization fails, try to add minimal exit rules and continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Strategy normalization failed, adding default exit rules: {e}")
            normalized_ruleset = dict(ruleset)
            if "exit_rules" not in normalized_ruleset or not normalized_ruleset.get("exit_rules"):
                normalized_ruleset["exit_rules"] = {
                    "stop_loss": 0.02,
                    "take_profit": 0.05
                }
        
        # PHASE 6: Validate strategy ruleset (now using normalized format)
        validation_result = self._validate_strategy_ruleset(normalized_ruleset)
        if not validation_result["valid"]:
            # If validation fails, try to fix by adding default exit rules
            if "exit rule" in validation_result.get("error", "").lower():
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Strategy missing exit rules, adding defaults: {validation_result['error']}")
                # Add default exit rules and re-validate
                if "exit_rules" not in normalized_ruleset:
                    normalized_ruleset["exit_rules"] = {}
                if not normalized_ruleset["exit_rules"].get("stop_loss") and not normalized_ruleset["exit_rules"].get("take_profit") and not normalized_ruleset["exit_rules"].get("exit_conditions"):
                    normalized_ruleset["exit_rules"]["stop_loss"] = 0.02
                    normalized_ruleset["exit_rules"]["take_profit"] = 0.05
                    # Re-validate after adding defaults
                    validation_result = self._validate_strategy_ruleset(normalized_ruleset)
            
            if not validation_result["valid"]:
                # Only log for truly malformed strategies (not normalized ones)
                # This should rarely happen after normalization
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Strategy validation failed: {validation_result['error']}")
                # Return empty result instead of raising error (prevents breaking evolution)
                return {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_trades": 0,
                "trades": [],
                "win_rate": 0.0,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "avg_pnl": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "equity_curve": [],
                "train_metrics": {},
                "test_metrics": {},
                "overfitting_detected": False,
                "error": validation_result["error"],
                "validation_failed": True
            }
        
        # Use normalized ruleset for backtest
        ruleset = normalized_ruleset
        
        # TWELVE DATA INTEGRATION: Request maximum history (up to 5000 candles)
        # Calculate number of candles needed (accounting for weekends/holidays)
        days_diff = (end_date - start_date).days
        # Estimate trading days (roughly 70% of calendar days are trading days)
        estimated_trading_days = int(days_diff * 0.7)
        
        # Request maximum realistic history from Twelve Data
        if timeframe == "1d":
            # For daily, request up to 5000 candles (~20 years of trading days)
            limit = min(estimated_trading_days + 100, 5000)
        elif timeframe == "1h":
            limit = min(estimated_trading_days * 6.5 + 100, 5000)  # ~6.5 hours per trading day
        elif timeframe in ["15m", "30m"]:
            limit = min(estimated_trading_days * 26 + 200, 5000)  # ~26 15-min periods per trading day
        else:
            limit = min(days_diff * 2 + 100, 5000)
        
        # Ensure we request at least 100 candles for meaningful backtest
        limit = max(limit, 100)
        
        # Fetch candles
        candles = self._fetch_candles(symbol, timeframe, limit, start_date, end_date)
        
        # Defensive check: ensure candles is never None
        if candles is None:
            candles = []
        
        # Ensure candles is a list
        if not isinstance(candles, (list, tuple)):
            print(f"⚠️  _fetch_candles returned non-list type {type(candles)}, treating as empty")
            candles = []
        
        # DYNAMIC CANDLE REQUIREMENTS: Only abort if data is extremely short (< 10 candles)
        # Adapt to available data instead of hard-coding minimums
        if len(candles) < 10:
            # Very short data - might not be useful
            error_msg = (
                f"Insufficient data for backtest: only {len(candles)} candles "
                f"for {symbol} ({timeframe}) in range {start_date.date()} to {end_date.date()}. "
                f"Need at least 10 candles to run backtest."
            )
            print(f"⚠️  {error_msg}")
            # Return empty result instead of raising error (prevents breaking evolution)
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_trades": 0,
                "trades": [],
                "win_rate": 0.0,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "avg_pnl": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "equity_curve": [],
                "train_metrics": {},
                "test_metrics": {},
                "overfitting_detected": False,
                "error": error_msg,
                "insufficient_data": True
            }
        
        # Log warning if data is shorter than recommended but still proceed
        min_candles_recommended = get_required_candles(timeframe)
        if len(candles) < min_candles_recommended:
            print(f"⚠️  Backtest using {len(candles)} candles (recommended: {min_candles_recommended} for {timeframe}) - adapting indicators to available data")
        
        # Also check absolute minimum
        if len(candles) < 2:
            error_msg = (
                f"Insufficient data for backtest: only {len(candles)} candles "
                f"for {symbol} ({timeframe}) in range {start_date.date()} to {end_date.date()}."
            )
            print(f"⚠️  {error_msg}")
            # PHASE 6: Return empty result instead of raising error
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_trades": 0,
                "trades": [],
                "win_rate": 0.0,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "avg_pnl": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "equity_curve": [],
                "train_metrics": {},
                "test_metrics": {},
                "overfitting_detected": False,
                "error": error_msg,
                "insufficient_data": True
            }
        
        # IMPROVEMENT: Use rolling walk-forward analysis if enabled
        # FIX: Make walk-forward more flexible - adapt to available data
        if use_rolling_walkforward and len(candles) >= 50:  # Reduced from 100 to 50
            from .walk_forward import WalkForwardOptimizer
            
            # Calculate available months from data
            data_span_days = (end_date - start_date).days
            data_span_months = data_span_days / 30.0
            
            # Adapt parameters based on available data
            if data_span_months >= 18:  # 18+ months: use full walk-forward
                in_sample = 12
                out_sample = 3
                step = 3
            elif data_span_months >= 12:  # 12-18 months: reduce training period
                in_sample = 6
                out_sample = 3
                step = 3
            elif data_span_months >= 9:  # 9-12 months: smaller periods
                in_sample = 4
                out_sample = 2
                step = 2
            else:  # Less than 9 months: use minimal walk-forward
                in_sample = 3
                out_sample = 1
                step = 1
            
            wfa_optimizer = WalkForwardOptimizer(
                in_sample_months=in_sample,
                out_of_sample_months=out_sample,
                step_months=step,
                min_periods=1  # Allow even 1 period for minimal validation
            )
            
            try:
                wfa_result = wfa_optimizer.run_walk_forward(
                    strategy=ruleset,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Use walk-forward results
                all_trades = []
                for period_result in wfa_result.out_of_sample_results:
                    all_trades.extend(period_result.get("trades", []))
                
                # Aggregate metrics from walk-forward
                all_metrics = wfa_result.aggregated_metrics
                train_metrics = {}  # WFA doesn't provide separate train metrics
                test_metrics = wfa_result.aggregated_metrics  # Use aggregated out-of-sample
                
                # Calculate consistency from WFA
                consistency_score = wfa_result.consistency_score
                overfitting_risk = wfa_result.overfitting_risk
                overfitting_detected = overfitting_risk in ["Medium", "High"]
                
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "total_trades": len(all_trades),
                    "trades": all_trades,
                    **all_metrics,
                    "equity_curve": self._calculate_equity_curve(all_trades, candles) if all_trades else [],
                    "train_metrics": train_metrics,
                    "test_metrics": test_metrics,
                    "overfitting_detected": overfitting_detected,
                    "wfa_results": {
                        "consistency_score": consistency_score,
                        "overfitting_risk": overfitting_risk,
                        "periods_tested": len(wfa_result.periods),
                        "periods": [
                            {
                                "period_number": p.period_number,
                                "in_sample_start": p.in_sample_start.isoformat(),
                                "in_sample_end": p.in_sample_end.isoformat(),
                                "out_of_sample_start": p.out_of_sample_start.isoformat(),
                                "out_of_sample_end": p.out_of_sample_end.isoformat(),
                            }
                            for p in wfa_result.periods
                        ]
                    }
                }
            except Exception as e:
                # If WFA fails, fall back to simple split
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Rolling walk-forward analysis failed, using simple split: {e}")
                use_rolling_walkforward = False
        
        # Fallback to simple train/test split
        split_idx = int(len(candles) * train_test_split)
        train_candles = candles[:split_idx]
        test_candles = candles[split_idx:]
        
        if len(train_candles) < 2 or len(test_candles) < 2:
            # If split is too small, use full dataset without split
            train_candles = candles
            test_candles = []
        
        # Execute strategy on full dataset
        all_trades = self._execute_strategy(candles, ruleset, symbol=symbol)
        
        # Execute on train set
        train_trades = self._execute_strategy(train_candles, ruleset, symbol=symbol) if train_candles else []
        
        # Execute on test set
        test_trades = self._execute_strategy(test_candles, ruleset, symbol=symbol) if test_candles else []
        
        # Calculate metrics for each set
        all_metrics = self._calculate_metrics(all_trades, candles)
        train_metrics = self._calculate_metrics(train_trades, train_candles) if train_trades else {}
        test_metrics = self._calculate_metrics(test_trades, test_candles) if test_trades else {}
        
        # Add date info to metrics
        train_metrics["start_date"] = start_date.isoformat()
        train_metrics["end_date"] = (start_date + (end_date - start_date) * train_test_split).isoformat() if train_candles else None
        test_metrics["start_date"] = (start_date + (end_date - start_date) * train_test_split).isoformat() if test_candles else None
        test_metrics["end_date"] = end_date.isoformat() if test_candles else None
        
        # Detect overfitting
        overfitting_detected = self._detect_overfitting(train_metrics, test_metrics)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_trades": len(all_trades),
            "trades": all_trades,
            **all_metrics,
            "equity_curve": self._calculate_equity_curve(all_trades, candles),
            "train_metrics": train_metrics,
            "test_metrics": test_metrics,
            "overfitting_detected": overfitting_detected,
        }
    
    def _detect_overfitting(
        self,
        train_metrics: Dict[str, Any],
        test_metrics: Dict[str, Any]
    ) -> bool:
        """
        Detect if strategy is overfit based on train vs test performance.
        
        Overfitting indicators:
        - High train win_rate (>= 0.9) but low test win_rate (< 0.6)
        - Large gap between train and test returns
        - Train Sharpe much higher than test Sharpe
        
        Returns:
            True if overfitting is detected, False otherwise
        """
        if not train_metrics or not test_metrics:
            return False
        
        train_win_rate = train_metrics.get("win_rate", 0.0)
        test_win_rate = test_metrics.get("win_rate", 0.0)
        train_return = train_metrics.get("total_return", 0.0)
        test_return = test_metrics.get("total_return", 0.0)
        train_sharpe = train_metrics.get("sharpe_ratio", 0.0)
        test_sharpe = test_metrics.get("sharpe_ratio", 0.0)
        
        # Check 1: Win rate degradation
        # If train win_rate is excellent (>= 0.9) but test is poor (< 0.6), likely overfit
        if train_win_rate >= 0.9 and test_win_rate < 0.6:
            return True
        
        # Check 2: Return degradation
        # If train return is positive but test return is negative, likely overfit
        if train_return > 10.0 and test_return < -5.0:
            return True
        
        # Check 3: Sharpe ratio degradation
        # If train Sharpe is high but test Sharpe is negative, likely overfit
        if train_sharpe > 1.5 and test_sharpe < 0.0:
            return True
        
        # Check 4: Large performance gap
        # If train performance is much better than test (gap > 30%), likely overfit
        win_rate_gap = train_win_rate - test_win_rate
        if win_rate_gap > 0.3:
            return True
        
        return False
    
    def _fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[CandleData]:
        """
        TWELVE DATA INTEGRATION: Fetch candles using Twelve Data for historical data.
        
        This method is used for:
        - Backtests
        - Strategy evolution
        - MCN distance calculations
        - Strategy validations
        
        Returns:
            List of candles within the date range, sorted by timestamp (never None, empty list on error)
        """
        # Ensure timezone-aware dates
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        # PHASE 1: Log request - for daily backtests, we request "last N candles" not a date range
        provider_name = "Twelve Data"
        if timeframe == "1d":
            print(f"📊 [{provider_name}] Fetching last N candles for {symbol} ({timeframe})")
        else:
            print(f"📊 [{provider_name}] Fetching candles for {symbol} ({timeframe}): start={start_date.date()}, end={end_date.date()}")
        
        # TWELVE DATA INTEGRATION: Use historical provider through request queue
        try:
            from ..market_data.market_data_provider import call_with_fallback
            
            # Calculate limit based on date range - request maximum history
            days_diff = (end_date - start_date).days
            estimated_trading_days = int(days_diff * 0.7)
            
            # Request maximum realistic history (up to 5000 for Twelve Data)
            # For 1d timeframe, ensure we request at least 350 candles (recommended minimum)
            if timeframe == "1d":
                limit = max(min(estimated_trading_days + 100, 5000), 350)  # At least 350 for 1d
            elif timeframe == "1h":
                limit = min(estimated_trading_days * 6.5 + 100, 5000)
            elif timeframe in ["15m", "30m"]:
                limit = min(estimated_trading_days * 26 + 200, 5000)
            else:
                limit = min(days_diff * 2 + 100, 5000)
            
            limit = max(limit, 100)  # Minimum 100 candles for other timeframes
            
            # Use call_with_fallback which goes through request queue
            all_candles = call_with_fallback(
                "get_candles",
                symbol,
                timeframe,
                limit=limit,
                start=start_date,
                end=end_date
            )
            
            # Defensive check: ensure all_candles is never None
            if all_candles is None:
                provider_name = historical_provider.__class__.__name__
                print(f"⚠️  {provider_name} returned None for {symbol} ({timeframe}), treating as empty list")
                return []
            
            # Ensure all_candles is a list/iterable
            if not isinstance(all_candles, (list, tuple)):
                provider_name = historical_provider.__class__.__name__
                print(f"⚠️  {provider_name} returned non-list type {type(all_candles)} for {symbol} ({timeframe}), treating as empty")
                return []
                
        except Exception as e:
            # If historical provider fetch fails, log and return empty list (never None)
            provider_name = historical_provider.__class__.__name__ if historical_provider else "Unknown"
            print(f"⚠️  Failed to fetch candles from {provider_name} for {symbol} ({timeframe}): {e}")
            import traceback
            traceback.print_exc()
            return []
        
        # Log how many candles we got from provider
        print(f"📈 Provider returned {len(all_candles)} total candles for {symbol} ({timeframe})")
        
        # PHASE 1: Fix candle date slicing - detect and correct if system clock is ahead
        # Always convert provider candles to ascending order
        # Always compute candle range from actual timestamps in data
        # Remove forward-date slicing bug
        
        # Ensure all timestamps are timezone-aware
        now_utc = datetime.now(timezone.utc)
        for candle in all_candles:
            if candle.timestamp.tzinfo is None:
                candle.timestamp = candle.timestamp.replace(tzinfo=timezone.utc)
        
        # Sort by timestamp (ascending) to get chronological order
        all_candles.sort(key=lambda x: x.timestamp)
        
        # PHASE 1: Remove forward-dated candles (system clock ahead bug fix)
        # Filter out any candles with timestamps in the future
        filtered_candles = [c for c in all_candles if c.timestamp <= now_utc]
        
        if len(filtered_candles) < len(all_candles):
            removed = len(all_candles) - len(filtered_candles)
            print(f"⚠️  Removed {removed} forward-dated candles (system clock ahead) for {symbol} ({timeframe})")
        
        # PHASE 1: Use last N candles (up to MAX_BARS_PER_BACKTEST or all available)
        MAX_BARS_PER_BACKTEST = 5000
        if len(filtered_candles) > MAX_BARS_PER_BACKTEST:
            # Use most recent N candles
            filtered = filtered_candles[-MAX_BARS_PER_BACKTEST:]
            print(f"📊 Using last {len(filtered)} candles (out of {len(filtered_candles)} total) for {symbol} ({timeframe})")
        else:
            filtered = filtered_candles
            print(f"✅ Using all {len(filtered)} candles for {symbol} ({timeframe})")
        
        # PHASE 1: Log actual candle range from timestamps (for info only, not blocking)
        if len(filtered) > 0:
            first_ts = filtered[0].timestamp
            last_ts = filtered[-1].timestamp
            # Ensure timezone-aware
            if first_ts.tzinfo is None:
                first_ts = first_ts.replace(tzinfo=timezone.utc)
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            print(f"   Candle range: {first_ts.date()} to {last_ts.date()} (computed from timestamps)")
        
        return filtered
    
    def _apply_slippage_and_spread(
        self,
        price: float,
        side: str,
        symbol: str,
        is_entry: bool
    ) -> float:
        """
        PHASE 2: Apply slippage and spread simulation to trade prices.
        
        Args:
            price: Base price (close price from candle)
            side: "BUY" or "SELL"
            symbol: Symbol being traded
            is_entry: True for entry, False for exit
        
        Returns:
            Adjusted price with slippage and spread applied
        """
        # Slippage: 0.1% per trade (realistic for market orders)
        slippage_pct = 0.001  # 0.1%
        
        # Spread: varies by asset type
        # Stocks: 0.01-0.05% (tight spread)
        # Crypto: 0.1-0.5% (wider spread)
        # Forex: 0.01-0.03% (very tight)
        if symbol.endswith("USD") or symbol.endswith("USDT") or symbol.endswith("-USD"):
            # Crypto
            spread_pct = 0.003  # 0.3% average for crypto
        elif any(forex_pair in symbol.upper() for forex_pair in ["EUR", "GBP", "JPY", "AUD", "CAD"]):
            # Forex
            spread_pct = 0.0002  # 0.02% for forex
        else:
            # Stocks/ETFs
            spread_pct = 0.0003  # 0.03% for stocks
        
        # Apply slippage (always negative impact)
        price_with_slippage = price * (1 - slippage_pct) if side == "BUY" else price * (1 + slippage_pct)
        
        # Apply spread
        # BUY: pay ask (higher), SELL: receive bid (lower)
        if side == "BUY":
            # Buying: pay ask price (higher)
            adjusted_price = price_with_slippage * (1 + spread_pct / 2)
        else:
            # Selling: receive bid price (lower)
            adjusted_price = price_with_slippage * (1 - spread_pct / 2)
        
        return adjusted_price
    
    def _execute_strategy(
        self,
        candles: List[CandleData],
        ruleset: Dict[str, Any],
        symbol: str = "UNKNOWN"  # PHASE 2: Add symbol for slippage/spread calculation
    ) -> List[Dict[str, Any]]:
        """
        Execute strategy logic on candles using parsed ruleset.
        
        Supports multi-indicator conditions with AND/OR logic.
        """
        trades = []
        position = None  # Current position: {"side": "BUY", "entry_price": 100.0, "entry_time": datetime, "stop_loss": float, "take_profit": float}
        
        # Parse ruleset
        parsed = self.ruleset_parser.parse_ruleset(ruleset)
        conditions = parsed.get("conditions", [])
        exit_rules = parsed.get("exit", {})
        
        # Calculate all indicators
        indicators = self.indicator_calc.calculate_all_indicators(candles)
        
        # Get ATR for dynamic stop loss/take profit
        atr_values = indicators.get("atr", [])
        
        # Execute strategy
        for i in range(len(candles)):
            candle = candles[i]
            
            # Check entry conditions
            if position is None:
                # PHASE 2: Volatility filter - skip trades in extreme volatility (>3x normal)
                volatility_values = indicators.get("volatility", [])
                if i < len(volatility_values) and volatility_values[i] is not None:
                    # Calculate average volatility
                    avg_volatility = statistics.mean([v for v in volatility_values[:i+1] if v is not None]) if volatility_values[:i+1] else 1.0
                    current_volatility = volatility_values[i]
                    if current_volatility > avg_volatility * 3.0:
                        # Skip trade in extreme volatility
                        continue
                
                # PHASE 2: Volume confirmation - require minimum volume (e.g., 10x average)
                volume_values = indicators.get("volume", [])
                if i < len(volume_values) and volume_values[i] is not None:
                    # Calculate average volume
                    avg_volume = statistics.mean([v for v in volume_values[:i+1] if v is not None and v > 0]) if volume_values[:i+1] else 1.0
                    current_volume = volume_values[i]
                    if current_volume < avg_volume * 0.1:  # Less than 10% of average = too low
                        # Skip trade due to low liquidity
                        continue
                
                # Evaluate conditions for entry signal
                if self.ruleset_parser.evaluate_conditions(conditions, indicators, i):
                    # Determine side from ruleset or default to BUY
                    side = ruleset.get("side", "BUY")
                    
                    # Get entry price
                    base_entry_price = candle.close
                    if parsed.get("entry") == "open":
                        base_entry_price = candle.open
                    elif parsed.get("entry") == "high":
                        base_entry_price = candle.high
                    elif parsed.get("entry") == "low":
                        base_entry_price = candle.low
                    
                    # PHASE 2: Apply slippage and spread to entry price
                    entry_price = self._apply_slippage_and_spread(
                        base_entry_price, side, symbol, is_entry=True
                    )
                    
                    # Calculate exit prices (stop loss, take profit) using adjusted entry price
                    atr = atr_values[i] if i < len(atr_values) and atr_values else None
                    exit_prices = self.ruleset_parser.calculate_exit_prices(
                        entry_price, side, exit_rules, atr
                    )
                    
                    position = {
                        "side": side,
                        "entry_price": entry_price,  # Already adjusted for slippage/spread
                        "entry_time": candle.timestamp,
                        "entry_index": i,
                        "stop_loss": exit_prices.get("stop_loss"),
                        "take_profit": exit_prices.get("take_profit"),
                    }
            
            # Check exit conditions (stop loss, take profit, or signal reversal)
            if position:
                current_price = candle.close
                exit_reason = None
                exit_price = current_price
                
                # Check stop loss
                if position["stop_loss"]:
                    if position["side"] == "BUY" and current_price <= position["stop_loss"]:
                        exit_price = position["stop_loss"]
                        exit_reason = "stop_loss"
                    elif position["side"] == "SELL" and current_price >= position["stop_loss"]:
                        exit_price = position["stop_loss"]
                        exit_reason = "stop_loss"
                
                # Check take profit
                if not exit_reason and position["take_profit"]:
                    if position["side"] == "BUY" and current_price >= position["take_profit"]:
                        exit_price = position["take_profit"]
                        exit_reason = "take_profit"
                    elif position["side"] == "SELL" and current_price <= position["take_profit"]:
                        exit_price = position["take_profit"]
                        exit_reason = "take_profit"
                
                # Check signal reversal (opposite conditions met)
                if not exit_reason:
                    # Evaluate exit conditions (could be separate or opposite of entry)
                    exit_conditions = ruleset.get("exit_conditions", [])
                    if exit_conditions:
                        if self.ruleset_parser.evaluate_conditions(exit_conditions, indicators, i):
                            exit_reason = "signal_reversal"
                
                # Exit position if any condition met
                if exit_reason:
                    # PHASE 2: Apply slippage and spread to exit price
                    exit_price_with_costs = self._apply_slippage_and_spread(
                        exit_price, position["side"], symbol, is_entry=False
                    )
                    
                    pnl = ((exit_price_with_costs - position["entry_price"]) / position["entry_price"]) * 100
                    if position["side"] == "SELL":
                        pnl = -pnl  # Invert for SELL
                    
                    trades.append({
                        "side": position["side"],
                        "entry_price": position["entry_price"],  # Already adjusted
                        "exit_price": exit_price_with_costs,  # Adjusted for slippage/spread
                        "entry_time": position["entry_time"].isoformat(),
                        "exit_time": candle.timestamp.isoformat(),
                        "pnl": pnl,
                        "quantity": 1.0,
                        "exit_reason": exit_reason,
                        "slippage_applied": True,  # Flag for tracking
                    })
                    position = None
        
        # Close any open position at end
        if position and len(candles) > 0:
            last_candle = candles[-1]
            exit_price = last_candle.close
            
            # PHASE 2: Apply slippage and spread to exit price (entry already adjusted when position created)
            exit_price_with_costs = self._apply_slippage_and_spread(
                exit_price, position["side"], symbol, is_entry=False
            )
            
            pnl = ((exit_price_with_costs - position["entry_price"]) / position["entry_price"]) * 100
            if position["side"] == "SELL":
                pnl = -pnl
            
            trades.append({
                "side": position["side"],
                "entry_price": position["entry_price"],  # Already adjusted
                "exit_price": exit_price_with_costs,  # Adjusted for slippage/spread
                "entry_time": position["entry_time"].isoformat(),
                "exit_time": last_candle.timestamp.isoformat(),
                "pnl": pnl,
                "quantity": 1.0,
                "exit_reason": "end_of_data",
                "slippage_applied": True,  # Flag for tracking
            })
        
        return trades
    
    # _calculate_sma removed - now using IndicatorCalculator
    
    def _calculate_metrics(
        self,
        trades: List[Dict[str, Any]],
        candles: List[CandleData]
    ) -> Dict[str, Any]:
        """
        PHASE 6: Calculate comprehensive backtest metrics from trades.
        
        Calculates:
        - winrate
        - sharpe
        - drawdown
        - expectancy
        - profit factor
        """
        if len(trades) == 0:
            return {
                "total_return": 0.0,
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "avg_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_win": 0.0,
                "avg_loss": 0.0
            }
        
        # Calculate returns
        pnls = [t["pnl"] for t in trades]
        total_return = sum(pnls)
        avg_pnl = statistics.mean(pnls) if pnls else 0.0
        
        # Win rate
        winning_trades_list = [p for p in pnls if p > 0]
        losing_trades_list = [p for p in pnls if p < 0]
        win_rate = len(winning_trades_list) / len(pnls) if pnls else 0.0
        
        # Average win and loss
        avg_win = statistics.mean(winning_trades_list) if winning_trades_list else 0.0
        avg_loss = abs(statistics.mean(losing_trades_list)) if losing_trades_list else 0.0
        
        # Profit factor: total wins / total losses
        total_wins = sum(winning_trades_list) if winning_trades_list else 0.0
        total_losses = abs(sum(losing_trades_list)) if losing_trades_list else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else (total_wins if total_wins > 0 else 0.0)
        
        # Expectancy: (win_rate * avg_win) - (loss_rate * avg_loss)
        loss_rate = 1.0 - win_rate
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
        
        # Max drawdown
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown
        
        # Sharpe ratio (annualized if possible)
        if len(pnls) > 1:
            std_dev = statistics.stdev(pnls) if len(pnls) > 1 else 0.0
            sharpe_ratio = (avg_pnl / std_dev) if std_dev > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        return {
            "total_return": total_return,
            "win_rate": win_rate,
            "max_drawdown": -max_dd,  # Negative value
            "avg_pnl": avg_pnl,
            "sharpe_ratio": sharpe_ratio,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "winning_trades": len(winning_trades_list),
            "losing_trades": len(losing_trades_list),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total_trades": len(trades)
        }
    
    def _calculate_equity_curve(
        self,
        trades: List[Dict[str, Any]],
        candles: List[CandleData]
    ) -> List[Dict[str, Any]]:
        """
        Calculate equity curve over time.
        Uses nominal starting capital (100,000) for backtesting - no user capital constraints.
        This is the "Brain lab" environment with effectively unlimited capital.
        """
        if not trades:
            return []
        
        # Use nominal starting capital for backtesting (not constrained by user balance)
        NOMINAL_STARTING_CAPITAL = 100000.0
        equity = NOMINAL_STARTING_CAPITAL
        curve = [{"timestamp": trades[0]["entry_time"], "equity": equity}]
        
        for trade in trades:
            # Calculate P&L in dollars (not percentage) based on nominal capital
            # trade["pnl"] is percentage, convert to dollar amount
            pnl_dollars = (trade["pnl"] / 100.0) * NOMINAL_STARTING_CAPITAL * (trade.get("quantity", 1.0) / 100.0)
            equity += pnl_dollars
            curve.append({
                "timestamp": trade["exit_time"],
                "equity": equity
            })
        
        return curve
    
    def _validate_strategy_ruleset(self, ruleset: Dict[str, Any]) -> Dict[str, Any]:
        """
        ISSUE 1 FIX: Validate strategy ruleset before backtesting.
        
        Ensures:
        - Required fields exist (entry_conditions/conditions, exit_rules)
        - Entry and exit rules are non-empty lists
        - Conditions have required keys (type, operator, value)
        - Optionally logs warnings for unusual values but DO NOT raise unless fatal
        
        Returns:
            {"valid": bool, "error": str | None}
        
        Raises:
            Never raises - returns validation result instead
        """
        if not isinstance(ruleset, dict):
            return {"valid": False, "error": "Ruleset must be a dictionary"}
        
        # VALIDATION: Check for entry conditions (normalized format should have entry_conditions)
        entry_conditions = (
            ruleset.get("entry_conditions") or 
            ruleset.get("conditions") or 
            ruleset.get("entry_rules") or
            ruleset.get("entry")  # Also check legacy "entry" field
        )
        
        # Normalize entry_conditions to a list if needed
        if entry_conditions is None:
            # Try to normalize using strategy_normalizer
            try:
                from .strategy_normalizer import normalize_strategy_ruleset
                normalized = normalize_strategy_ruleset(ruleset)
                entry_conditions = normalized.get("entry_conditions", [])
            except Exception:
                entry_conditions = []
        
        # Convert to list if it's a dict or single item
        if isinstance(entry_conditions, dict):
            entry_conditions = [entry_conditions]
        elif not isinstance(entry_conditions, list):
            entry_conditions = [entry_conditions] if entry_conditions else []
        
        # Only reject if truly malformed (after normalization, this should be rare)
        if entry_conditions is None or (isinstance(entry_conditions, list) and len(entry_conditions) == 0):
            # Empty list is OK - might have default entry logic or be filled dynamically
            # Don't fail validation, just log a warning
            pass
        
        # FIX 2: Validate individual conditions only if list is non-empty
        if isinstance(entry_conditions, list) and len(entry_conditions) > 0:
            for i, condition in enumerate(entry_conditions):
                if not isinstance(condition, dict):
                    return {"valid": False, "error": f"Entry condition {i} must be a dictionary"}
                # Only require 'indicator' OR 'type' OR 'operator' - be lenient
                # (Removed warning - normalized strategies should have proper structure)
                if "indicator" not in condition and "type" not in condition and "operator" not in condition:
                    # Might be a special condition type - allow it
                    pass
        
        # Check for exit rules (normalized format should have exit_rules with exit_conditions, stop_loss, or take_profit)
        exit_rules = ruleset.get("exit_rules", {})
        if not isinstance(exit_rules, dict):
            exit_rules = {}
        
        exit_list = ruleset.get("exit")  # Also check legacy "exit" field
        
        # Check for stop_loss in multiple possible locations
        has_stop_loss = (
            exit_rules.get("stop_loss") is not None 
            or exit_rules.get("stop_loss_percent") is not None
            or ruleset.get("stop_loss") is not None
            or ruleset.get("stop_loss_percent") is not None
        )
        
        # Check for take_profit in multiple possible locations
        has_take_profit = (
            exit_rules.get("take_profit") is not None 
            or exit_rules.get("take_profit_percent") is not None
            or ruleset.get("take_profit") is not None
            or ruleset.get("take_profit_percent") is not None
        )
        
        # Check for exit_conditions
        exit_conditions = exit_rules.get("exit_conditions") or ruleset.get("exit_conditions") or []
        # Also check if exit is a list (legacy format)
        if isinstance(exit_list, list) and len(exit_list) > 0:
            exit_conditions = exit_list
        elif isinstance(exit_list, dict):
            # If exit is a dict, it might contain exit rules
            if exit_list.get("stop_loss") or exit_list.get("take_profit") or exit_list.get("exit_conditions"):
                exit_rules = exit_list
                has_stop_loss = has_stop_loss or exit_list.get("stop_loss") is not None
                has_take_profit = has_take_profit or exit_list.get("take_profit") is not None
                if exit_list.get("exit_conditions"):
                    exit_conditions = exit_list.get("exit_conditions")
        
        has_exit_conditions = isinstance(exit_conditions, list) and len(exit_conditions) > 0
        
        # If no exit rules found, this is a critical error (should have been caught by normalization)
        if not (has_stop_loss or has_take_profit or has_exit_conditions):
            return {
                "valid": False, 
                "error": "Strategy must have at least one exit rule (stop_loss, take_profit, exit_conditions, or exit)"
            }
        
        # Validate exit conditions if present
        if has_exit_conditions:
            for i, condition in enumerate(exit_conditions):
                if not isinstance(condition, dict):
                    return {"valid": False, "error": f"Exit condition {i} must be a dictionary"}
        
        # Validation passed - no warnings needed (normalized strategies should have all fields)
        # Removed verbose warnings to keep logs clean
        
        return {"valid": True, "error": None}
    
    def execute_backtest_across_assets(
        self,
        strategy_ruleset: Dict[str, Any],
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute backtest across multiple assets to test strategy generalization.
        
        Args:
            strategy_ruleset: Strategy ruleset with conditions and indicators
            timeframe: Timeframe (e.g., "1d", "1h")
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to test (defaults to DEFAULT_SYMBOLS)
        
        Returns:
            Dictionary with:
            - per_symbol_results: Dict mapping symbol to backtest results
            - best_performing_symbol: Symbol with highest winrate
            - worst_performing_symbol: Symbol with lowest winrate
            - average_winrate: Average winrate across all symbols
            - volatility_adjusted_return: Average return adjusted for volatility
            - regime_breakdown: Performance by regime (if available)
            - total_trade_count: Total trades across all symbols
            - generalized: Boolean indicating if strategy performs well on >2 assets
        """
        if symbols is None:
            symbols = DEFAULT_SYMBOLS
        
        per_symbol_results = {}
        all_trades = []
        regime_performance = {}
        
        for symbol in symbols:
            try:
                result = self.run_backtest(
                    symbol=symbol,
                    ruleset=strategy_ruleset,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    train_test_split=0.7
                )
                
                per_symbol_results[symbol] = {
                    "winrate": result.get("win_rate", 0.0),
                    "total_return": result.get("total_return", 0.0),
                    "max_drawdown": result.get("max_drawdown", 0.0),
                    "avg_pnl": result.get("avg_pnl", 0.0),
                    "sharpe_ratio": result.get("sharpe_ratio", 0.0),
                    "total_trades": result.get("total_trades", 0),
                    "trades": result.get("trades", []),
                    "equity_curve": result.get("equity_curve", []),
                    "overfitting_detected": result.get("overfitting_detected", False),
                }
                
                # Collect trades for aggregate analysis
                all_trades.extend(result.get("trades", []))
                
                # Extract regime breakdown if available
                if "regime_breakdown" in result:
                    for regime, perf in result["regime_breakdown"].items():
                        if regime not in regime_performance:
                            regime_performance[regime] = {"winrate": [], "return": []}
                        regime_performance[regime]["winrate"].append(perf.get("winrate", 0.0))
                        regime_performance[regime]["return"].append(perf.get("return", 0.0))
                
            except Exception as e:
                # Log error but continue with other symbols
                print(f"⚠️  Backtest failed for {symbol}: {e}")
                per_symbol_results[symbol] = {
                    "error": str(e),
                    "winrate": 0.0,
                    "total_return": 0.0,
                    "total_trades": 0,
                }
        
        # Calculate aggregate metrics
        successful_results = {
            k: v for k, v in per_symbol_results.items()
            if "error" not in v and v.get("total_trades", 0) > 0
        }
        
        if not successful_results:
            return {
                "per_symbol_results": per_symbol_results,
                "best_performing_symbol": None,
                "worst_performing_symbol": None,
                "average_winrate": 0.0,
                "volatility_adjusted_return": 0.0,
                "regime_breakdown": {},
                "total_trade_count": 0,
                "generalized": False,
            }
        
        # Find best and worst performing symbols
        best_symbol = max(successful_results.items(), key=lambda x: x[1].get("winrate", 0.0))
        worst_symbol = min(successful_results.items(), key=lambda x: x[1].get("winrate", 1.0))
        
        # Calculate average winrate
        winrates = [v.get("winrate", 0.0) for v in successful_results.values()]
        average_winrate = sum(winrates) / len(winrates) if winrates else 0.0
        
        # Calculate volatility-adjusted return (average return / average drawdown)
        returns = [v.get("total_return", 0.0) for v in successful_results.values()]
        drawdowns = [abs(v.get("max_drawdown", 0.0)) for v in successful_results.values()]
        avg_return = sum(returns) / len(returns) if returns else 0.0
        avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else 1.0
        volatility_adjusted_return = avg_return / avg_drawdown if avg_drawdown > 0 else avg_return
        
        # Aggregate regime breakdown
        aggregated_regime_breakdown = {}
        for regime, data in regime_performance.items():
            if data["winrate"]:
                aggregated_regime_breakdown[regime] = {
                    "avg_winrate": sum(data["winrate"]) / len(data["winrate"]),
                    "avg_return": sum(data["return"]) / len(data["return"]) if data["return"] else 0.0,
                    "symbol_count": len(data["winrate"]),
                }
        
        # Determine if strategy is generalized (>2 assets with winrate > threshold)
        well_performing_assets = [
            symbol for symbol, result in successful_results.items()
            if result.get("winrate", 0.0) >= GENERALIZATION_WINRATE_THRESHOLD
        ]
        is_generalized = len(well_performing_assets) >= MIN_ASSETS_FOR_GENERALIZATION
        
        return {
            "per_symbol_results": per_symbol_results,
            "best_performing_symbol": best_symbol[0] if best_symbol else None,
            "worst_performing_symbol": worst_symbol[0] if worst_symbol else None,
            "average_winrate": average_winrate,
            "volatility_adjusted_return": volatility_adjusted_return,
            "regime_breakdown": aggregated_regime_breakdown,
            "total_trade_count": len(all_trades),
            "generalized": is_generalized,
            "well_performing_assets": well_performing_assets,
            "asset_count": len(successful_results),
        }

