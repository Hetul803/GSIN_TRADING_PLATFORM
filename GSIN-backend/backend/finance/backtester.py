# backend/finance/backtester.py
from __future__ import annotations
import os
import numpy as np
import pandas as pd
from .data_providers import get_ohlcv
from .fees import apply_fees_equity, apply_fees_crypto

# ---------- Data Loading ----------

def load_symbol(symbol: str = "AAPL", period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    provider = os.environ.get("PROVIDER") or "alpha_vantage"
    api_key = os.environ.get("ALPHA_VANTAGE_KEY")
    return get_ohlcv(symbol=symbol, period=period, interval=interval, provider=provider, api_key=api_key)

# ---------- Helpers ----------

def regime_features(close: pd.Series) -> dict:
    ret = close.pct_change()
    vol20 = float(ret.rolling(20).std().iloc[-1] or 0.0)
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    slope = float((close.iloc[-1] - ma20.iloc[-1]) / (std20.iloc[-1] + 1e-9))
    trend = 1 if slope > 0.5 else (-1 if slope < -0.5 else 0)
    vol_bucket = 2 if vol20 > 0.03 else (1 if vol20 > 0.015 else 0)
    return {"regime_trend": trend, "regime_vol": vol_bucket, "vol20": vol20, "slope20": slope}

def _perf_metrics(df: pd.DataFrame, name: str) -> dict:
    ret = df["ret_after_fee"].fillna(0.0)
    total_return = (1.0 + ret).prod() - 1.0
    std = ret.std()
    mean = ret.mean()
    sharpe = (mean / std * np.sqrt(252)) if (std and std > 0) else 0.0
    dd = float(df["Close"].max() - df["Close"].min())
    trades = int(df["position"].diff().abs().fillna(0).sum())
    turnover = float(df["position"].abs().sum() / max(len(df), 1))
    rf = regime_features(df["Close"])
    return {
        "name": name,
        "return": round(float(total_return), 6),
        "sharpe": round(float(sharpe), 6),
        "dd": round(dd, 6),
        "n": int(len(df)),
        "trades": trades,
        "turnover": round(turnover, 6),
        "regime": rf,
    }

# ---------- Strategies ----------

def strat_sma_crossover(df: pd.DataFrame, fast: int = 5, slow: int = 20, name: str = "SMA_X") -> pd.DataFrame:
    df = df.copy()
    fast = max(2, int(fast))
    slow = max(fast + 1, int(slow))
    df["fast"] = df["Close"].rolling(fast).mean()
    df["slow"] = df["Close"].rolling(slow).mean()
    df["signal"] = np.where(df["fast"] > df["slow"], 1.0, -1.0)
    df["position"] = df["signal"].shift(1).fillna(0.0)
    df["ret"] = df["Close"].pct_change() * df["position"]
    return df

def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(gain, index=series.index).rolling(length).mean()
    roll_down = pd.Series(loss, index=series.index).rolling(length).mean()
    rs = roll_up / (roll_down + 1e-12)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def strat_rsi_meanrev(df: pd.DataFrame, rsi_len: int = 14, oversold: int = 30, overbought: int = 70, name: str = "RSI_MR") -> pd.DataFrame:
    df = df.copy()
    rsi_len = max(2, int(rsi_len))
    oversold = max(1, min(oversold, 49))
    overbought = max(51, min(overbought, 99))
    df["RSI"] = _rsi(df["Close"], rsi_len)
    sig = np.where(df["RSI"] < oversold, 1.0, np.where(df["RSI"] > overbought, -1.0, 0.0))
    df["signal"] = sig
    df["position"] = df["signal"].shift(1).fillna(0.0)
    df["ret"] = df["Close"].pct_change() * df["position"]
    return df

# ---------- Orchestrator ----------

def run_backtest(
    symbol: str = "AAPL",
    period: str = "3mo",
    interval: str = "1d",
    strategy: dict | None = None,
    fees: dict | None = None,
) -> dict:
    df = load_symbol(symbol=symbol, period=period, interval=interval)
    stype = (strategy or {}).get("type", "sma").lower()
    params = (strategy or {}).get("params", {}) or {}

    if stype == "sma":
        fast = int(params.get("fast", 5))
        slow = int(params.get("slow", 20))
        df = strat_sma_crossover(df, fast=fast, slow=slow, name=f"SMA_{symbol}")
        name = f"SMA_{symbol}(5,20)" if (fast, slow) == (5, 20) else f"SMA_{symbol}({fast},{slow})"
    elif stype == "rsi":
        rsi_len = int(params.get("rsi_len", 14))
        oversold = int(params.get("oversold", 30))
        overbought = int(params.get("overbought", 70))
        df = strat_rsi_meanrev(df, rsi_len=rsi_len, oversold=oversold, overbought=overbought, name=f"RSI_{symbol}")
        name = f"RSI_{symbol}(len={rsi_len},os={oversold},ob={overbought})"
    else:
        df = strat_sma_crossover(df, fast=5, slow=20, name=f"SMA_{symbol}")
        name = f"SMA_{symbol}(5,20)"

    f = fees or {}
    typ = (f.get("type") or "equity").lower()
    if typ == "crypto":
        df["ret_after_fee"] = apply_fees_crypto(df["ret"], df["position"], taker_bps=float(f.get("taker_bps", 10.0)))
    else:
        df["ret_after_fee"] = apply_fees_equity(df["ret"], df["position"], df["Close"], bps=float(f.get("bps", 10.0)), min_fee=float(f.get("min", 1.0)))

    m = _perf_metrics(df, name)
    return m

# ---------- PnL helper for charting ----------

def pnl_series(
    symbol: str = "AAPL",
    period: str = "6mo",
    interval: str = "1d",
    strategy: dict | None = None,
    fees: dict | None = None,
) -> list[dict]:
    df = load_symbol(symbol=symbol, period=period, interval=interval)
    stype = (strategy or {}).get("type", "sma").lower()
    params = (strategy or {}).get("params", {}) or {}

    if stype == "rsi":
        df = strat_rsi_meanrev(df, rsi_len=int(params.get("rsi_len", 14)), oversold=int(params.get("oversold", 30)), overbought=int(params.get("overbought", 70)))
    else:
        df = strat_sma_crossover(df, fast=int(params.get("fast", 5)), slow=int(params.get("slow", 20)))

    f = fees or {}
    typ = (f.get("type") or "equity").lower()
    if typ == "crypto":
        df["ret_after_fee"] = apply_fees_crypto(df["ret"], df["position"], taker_bps=float(f.get("taker_bps", 10.0)))
    else:
        df["ret_after_fee"] = apply_fees_equity(df["ret"], df["position"], df["Close"], bps=float(f.get("bps", 10.0)), min_fee=float(f.get("min", 1.0)))

    eq = (1 + df["ret_after_fee"].fillna(0.0)).cumprod()
    out = []
    for ts, e in eq.items():
        out.append({
            "ts": pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "equity": float(e)
        })
    return out

# ---------- Signals (UI helper) ----------

def recent_signals(symbol: str = "AAPL", period: str = "3mo", interval: str = "1d", lookback: int = 20) -> list[dict]:
    df = load_symbol(symbol=symbol, period=period, interval=interval).tail(lookback).copy()
    df["SMA5"] = df["Close"].rolling(5).mean()
    df["action"] = np.where(df["Close"] > df["SMA5"], "BUY", "SELL")
    out = []
    for ts, row in df.iterrows():
        conf = float(min(1.0, max(0.0, abs((row["Close"] - row["SMA5"]) / (row["Close"] + 1e-9)))))
        out.append({"ts": pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ"), "symbol": symbol, "action": str(row["action"]), "confidence": round(conf, 3)})
    return out

