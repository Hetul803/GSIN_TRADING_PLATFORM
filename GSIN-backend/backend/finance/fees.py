# backend/finance/fees.py
from __future__ import annotations
import numpy as np
import pandas as pd

def apply_fees_equity(ret: pd.Series, position: pd.Series, price: pd.Series, bps: float = 10.0, min_fee: float = 1.0) -> pd.Series:
    """
    Simple fee model:
      - Charge bps (round-trip ~2*bps if flipping) when position changes magnitude.
      - Apply a minimum fee translated to return space using price proxy (very rough).
    """
    ret = ret.copy().fillna(0.0)
    position = position.copy().fillna(0.0)
    price = price.copy()

    # Trade occurs when position changes
    trade = position.diff().fillna(0.0).abs()
    # Fee per trade in return terms ~ bps/1e4 * |delta position|
    fee_rt = (bps / 1e4) * trade
    # Add a rough min fee in return space (scaled)
    min_rt = (min_fee / price.clip(lower=1.0)).fillna(0.0) * (trade > 0)

    return ret - fee_rt - min_rt

def apply_fees_crypto(ret: pd.Series, position: pd.Series, taker_bps: float = 10.0) -> pd.Series:
    """
    Crypto taker fee ~0.1% per side (taker_bps=10).
    Charge when position changes (enter/exit/flip).
    """
    ret = ret.copy().fillna(0.0)
    position = position.copy().fillna(0.0)
    trade = position.diff().fillna(0.0).abs()
    fee_rt = (taker_bps / 1e4) * trade
    return ret - fee_rt

