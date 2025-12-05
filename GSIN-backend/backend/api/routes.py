# backend/api/routes.py
from __future__ import annotations
from fastapi import APIRouter, UploadFile, Form, Body, Depends, Query, Header
from typing import Optional, Any, Dict
import json, random

from ..api.metrics_store import get_series
# PHASE 4: Legacy imports removed - these modules are deprecated
# from ..finance.backtester import run_backtest, recent_signals, pnl_series
# from ..finance.walkforward import walk_forward_oos
# from ..core.feedback_loop import feedback_after_backtest
# from ..core.registry import REGISTRY
from ..db.session import get_db
from ..db import crud
from ..utils.jwt_deps import get_current_user_id_optional

router = APIRouter()

@router.get("/metrics")
def metrics():
    return {"series": get_series()}

@router.get("/strategies")
def strategies(db = Depends(get_db)):
    return {"items": crud.list_strategies(db)}

# NOTE: Legacy endpoints removed - use /api/strategies and /api/backtest instead
# These endpoints used old finance module which is deprecated
# All functionality moved to strategy_engine module

@router.get("/royalties")
def royalties(db = Depends(get_db)):
    return {"rows": crud.list_royalties(db, limit=50)}

@router.get("/leaderboard")
def leaderboard(db = Depends(get_db), limit: int = 20):
    # naive: last N runs by Sharpe, after-fee
    from ..db.models import Run
    rows = db.query(Run).order_by(Run.sharpe.desc()).limit(limit).all()
    out = []
    for r in rows:
        out.append({
            "strategy": r.strategy_name,
            "symbol": r.symbol,
            "stype": r.stype,
            "ret": r.ret,
            "sharpe": r.sharpe,
            "dd": r.dd,
            "trades": r.trades,
            "turnover": r.turnover,
            "regime": r.regime
        })
    return {"rows": out}

