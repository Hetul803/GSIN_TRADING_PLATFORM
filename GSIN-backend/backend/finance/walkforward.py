# backend/finance/walkforward.py
from __future__ import annotations
import math
import pandas as pd
from .backtester import strat_sma_crossover, strat_rsi_meanrev
from .fees import apply_fees_equity, apply_fees_crypto

def _apply_strategy(df: pd.DataFrame, stype: str, params: dict) -> pd.DataFrame:
    st = (stype or "sma").lower()
    if st == "rsi":
        return strat_rsi_meanrev(
            df,
            rsi_len=int(params.get("rsi_len", 14)),
            oversold=int(params.get("oversold", 30)),
            overbought=int(params.get("overbought", 70)),
            name="RSI_WF",
        )
    return strat_sma_crossover(
        df,
        fast=int(params.get("fast", 5)),
        slow=int(params.get("slow", 20)),
        name="SMA_WF",
    )

def _apply_fees(df: pd.DataFrame, fee: dict) -> pd.DataFrame:
    f = (fee or {})
    typ = (f.get("type") or "equity").lower()
    if typ == "crypto":
        df["ret_after_fee"] = apply_fees_crypto(df["ret"], df["position"], taker_bps=float(f.get("taker_bps", 10.0)))
    else:
        df["ret_after_fee"] = apply_fees_equity(df["ret"], df["position"], df["Close"], bps=float(f.get("bps", 10.0)), min_fee=float(f.get("min", 1.0)))
    return df

def walk_forward_oos(
    df: pd.DataFrame,
    stype: str,
    params: dict,
    fee: dict,
    train_bars: int = 250,
    test_bars: int = 60,
    max_splits: int = 6,
) -> dict:
    """
    Rolling walk-forward:
      repeat:
        use previous `train_bars` segment only to set params (we keep params fixed here for simplicity),
        evaluate next `test_bars` as OOS,
      aggregate OOS metrics & stitch OOS equity.
    """
    n = len(df)
    if n < train_bars + test_bars + 10:
        return {"splits": 0, "oos_return": 0.0, "oos_sharpe": 0.0, "oos_dd": 0.0, "points": [], "equity": []}

    points = []
    equity_curve = []

    start = n - (train_bars + test_bars) * max_splits
    start = max(0, start)

    oos_rets = []
    for k in range(max_splits):
        i0 = start + k * test_bars
        i1 = i0 + train_bars
        i2 = i1 + test_bars
        if i2 > n:
            break
        df_train = df.iloc[i0:i1].copy()
        df_test = df.iloc[i1:i2].copy()

        # (Optional future: tune params on df_train)
        # Apply params to test
        df_tt = _apply_strategy(pd.concat([df_train.tail(50), df_test]), stype, params)  # warmup indicators
        df_tt = _apply_fees(df_tt, fee)
        df_oos = df_tt.iloc[50:].copy()  # drop warmup

        ret = df_oos["ret_after_fee"].fillna(0.0)
        retn = (1 + ret).prod() - 1
        std = ret.std()
        mean = ret.mean()
        sharpe = (mean / std * math.sqrt(252)) if std and std > 0 else 0.0
        dd = float(df_oos["Close"].max() - df_oos["Close"].min())

        oos_rets.append((retn, sharpe, dd))

        eq = (1 + ret).cumprod()
        equity_curve.extend(list(eq.values))
        # points for charting
        for ts, rv in df_oos["ret_after_fee"].items():
            points.append({"ts": pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ"), "ret": float(rv)})

    if not oos_rets:
        return {"splits": 0, "oos_return": 0.0, "oos_sharpe": 0.0, "oos_dd": 0.0, "points": [], "equity": []}

    oret = sum(r for r, _, _ in oos_rets) / len(oos_rets)
    osharpe = sum(s for _, s, _ in oos_rets) / len(oos_rets)
    odd = sum(d for _, _, d in oos_rets) / len(oos_rets)
    return {
        "splits": len(oos_rets),
        "oos_return": float(round(oret, 6)),
        "oos_sharpe": float(round(osharpe, 6)),
        "oos_dd": float(round(odd, 6)),
        "points": points,
        "equity": equity_curve,
    }

