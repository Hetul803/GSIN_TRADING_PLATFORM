# backend/finance/data_providers.py
from __future__ import annotations
import os, math, time
import pandas as pd
import numpy as np
import requests

# -------- Helpers --------

def _synthetic_ohlcv(n: int = 180, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.utcnow(), periods=n)
    price = 100 + np.cumsum(rng.normal(0, 1, size=n))
    high = price + rng.normal(0.3, 0.2, size=n).clip(min=0)
    low = price - rng.normal(0.3, 0.2, size=n).clip(min=0)
    open_ = price + rng.normal(0, 0.2, size=n)
    close = price
    vol = rng.integers(1e5, 3e5, size=n)
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=dates)
    return df

def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Ensure expected columns exist
    cols = {c.lower(): c for c in df.columns}
    def get(name):  # case-insensitive
        for k in cols:
            if k.startswith(name):
                return cols[k]
        return None
    mapping = {
        "Open": get("open") or "Open",
        "High": get("high") or "High",
        "Low":  get("low")  or "Low",
        "Close":get("close")or "Close",
        "Volume": get("volume") or get("vol") or "Volume",
    }
    out = pd.DataFrame({
        "Open": df[mapping["Open"]],
        "High": df[mapping["High"]],
        "Low":  df[mapping["Low"]],
        "Close":df[mapping["Close"]],
        "Volume": df[mapping["Volume"]] if mapping["Volume"] in df.columns else np.nan,
    }, index=pd.to_datetime(df.index))
    out = out.sort_index()
    return out

# -------- Alpha Vantage (equities & crypto) --------

def _alpha_func(interval: str) -> tuple[str, dict]:
    # Map interval → API function/params
    # daily/weekly/monthly also supported, keeping it simple first
    if interval.endswith("min"):
        return "TIME_SERIES_INTRADAY", {"interval": interval}
    if interval in ("1d", "1day", "daily"):
        return "TIME_SERIES_DAILY_ADJUSTED", {}
    # default to daily
    return "TIME_SERIES_DAILY_ADJUSTED", {}

def load_alpha_vantage(symbol: str, period: str, interval: str, api_key: str) -> pd.DataFrame:
    base = "https://www.alphavantage.co/query"
    func, extra = _alpha_func(interval)
    params = {"function": func, "symbol": symbol, "apikey": api_key, "datatype": "json", **extra, "outputsize": "compact"}
    r = requests.get(base, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    # Pick the right key
    if func == "TIME_SERIES_INTRADAY":
        key = next((k for k in data.keys() if "Time Series" in k), None)
    else:
        key = next((k for k in data.keys() if "Time Series" in k), None)
    if not key or key not in data:
        raise ValueError(f"AlphaVantage response missing time series keys: {list(data.keys())[:5]}")
    ts = pd.DataFrame.from_dict(data[key], orient="index").rename(columns=lambda c: c.split(". ")[-1])
    ts.index = pd.to_datetime(ts.index)
    # Numeric
    for c in ts.columns:
        ts[c] = pd.to_numeric(ts[c], errors="coerce")
    ts = ts.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close",
        "adjusted close": "Close", "volume": "Volume"
    })
    ts = ts[["Open","High","Low","Close","Volume"]].sort_index()
    # Trim roughly by period (e.g., "6mo")
    if period.endswith("mo"):
        months = int(period[:-2])
        cutoff = ts.index.max() - pd.DateOffset(months=months)
        ts = ts[ts.index >= cutoff]
    elif period.endswith("y"):
        years = int(period[:-1])
        cutoff = ts.index.max() - pd.DateOffset(years=years)
        ts = ts[ts.index >= cutoff]
    return ts

# -------- Binance (crypto) --------

def _binance_interval(interval: str) -> str:
    m = {
        "1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m",
        "1h":"1h","2h":"2h","4h":"4h","6h":"6h","8h":"8h","12h":"12h",
        "1d":"1d","3d":"3d","1w":"1w","1M":"1M"
    }
    return m.get(interval, "1h")

def load_binance(symbol: str, period: str, interval: str) -> pd.DataFrame:
    # symbol like BTCUSDT
    k = _binance_interval(interval)
    # approximate limit from period (days)
    if period.endswith("d"):
        limit = min(1000, int(period[:-1]))
    elif period.endswith("mo"):
        limit = min(1000, int(period[:-2]) * 30)
    elif period.endswith("y"):
        limit = min(1000, int(period[:-1]) * 365)
    else:
        limit = 500
    url = "https://api.binance.com/api/v3/klines"
    resp = requests.get(url, params={"symbol": symbol, "interval": k, "limit": limit}, timeout=20)
    resp.raise_for_status()
    arr = resp.json()
    if not isinstance(arr, list) or not arr:
        raise ValueError("Binance empty response")
    df = pd.DataFrame(arr, columns=[
        "open_time","Open","High","Low","Close","Volume",
        "close_time","quote_asset_volume","trades","taker_buy_base","taker_buy_quote","ignore"
    ])
    for c in ["Open","High","Low","Close","Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df.index = pd.to_datetime(df["open_time"], unit="ms")
    df = df[["Open","High","Low","Close","Volume"]].sort_index()
    return df

# -------- yfinance fallback --------

def load_yfinance(symbol: str, period: str, interval: str) -> pd.DataFrame:
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False)
        if isinstance(df, pd.DataFrame) and len(df) >= 10 and "Close" in df.columns:
            return _standardize(df)
        raise ValueError("Empty/invalid yfinance df")
    except Exception as e:
        raise RuntimeError(f"yfinance failed: {e}") from e

# -------- unified entry --------

def get_ohlcv(symbol: str, period: str, interval: str, provider: str = "alpha_vantage", api_key: str | None = None) -> pd.DataFrame:
    provider = (provider or "").lower()
    try:
        if provider == "alpha_vantage":
            if not api_key:
                raise ValueError("ALPHA_VANTAGE_KEY missing")
            return load_alpha_vantage(symbol, period, interval, api_key)
        elif provider == "binance":
            return load_binance(symbol, period, interval)
        elif provider == "yfinance":
            return load_yfinance(symbol, period, interval)
        else:
            # attempt yfinance last
            return load_yfinance(symbol, period, interval)
    except Exception:
        # final fallback
        return _synthetic_ohlcv(180)

