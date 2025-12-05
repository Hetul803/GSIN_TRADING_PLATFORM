# backend/api/health.py
from __future__ import annotations
from fastapi import APIRouter
from typing import Dict, Any
from datetime import datetime, timezone

from ..api.metrics_store import get_series
from ..db.session import SessionLocal, engine
from ..db import crud
from ..db.models import UserStrategy, Trade
from ..workers.evolution_worker import EvolutionWorker
from ..workers.monitoring_worker import MonitoringWorker
from ..brain.mcn_adapter import get_mcn_adapter

health_router = APIRouter()

@health_router.get("/health")
def health() -> Dict[str, Any]:
    """Basic health check endpoint."""
    status = {
        "db": False,
        "metrics": False,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    ok = True

    # DB check
    try:
        with SessionLocal() as db:
            # Simple query to test connection
            db.execute("SELECT 1")
            status["db"] = True
    except Exception as e:
        ok = False
        status["db_error"] = str(e)

    # Metrics in-memory store check
    try:
        _ = get_series()
        status["metrics"] = True
    except Exception:
        ok = False

    return {
        "ok": ok,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@health_router.get("/ready")
def readiness() -> Dict[str, Any]:
    """Readiness check - more comprehensive than health check."""
    checks = {
        "database": {"status": False, "message": ""},
        "mcn": {"status": False, "message": ""},
        "workers": {"status": False, "message": ""},
    }
    all_ready = True

    # Database check
    try:
        with SessionLocal() as db:
            # Test read
            db.query(UserStrategy).limit(1).all()
            # Test write (transaction rollback)
            db.rollback()
            checks["database"]["status"] = True
            checks["database"]["message"] = "Database connection healthy"
    except Exception as e:
        all_ready = False
        checks["database"]["message"] = f"Database error: {str(e)}"

    # MCN check
    try:
        mcn_adapter = get_mcn_adapter()
        if mcn_adapter and mcn_adapter.is_available:
            checks["mcn"]["status"] = True
            checks["mcn"]["message"] = "MCN available"
        else:
            checks["mcn"]["message"] = "MCN not available (fallback mode)"
            # MCN is optional, so don't fail readiness
    except Exception as e:
        checks["mcn"]["message"] = f"MCN check failed: {str(e)}"
        # MCN is optional, so don't fail readiness

    # Workers check (verify they can be instantiated)
    try:
        # Just check if workers can be imported and instantiated
        evolution_worker = EvolutionWorker()
        monitoring_worker = MonitoringWorker()
        checks["workers"]["status"] = True
        checks["workers"]["message"] = "Workers initialized"
    except Exception as e:
        all_ready = False
        checks["workers"]["message"] = f"Worker initialization error: {str(e)}"

    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

