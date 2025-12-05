# GSIN backend.api
from fastapi import APIRouter, Query
from typing import Any, Dict
from mcn_layer import _peek, _stats

mcn_router = APIRouter(prefix="/mcn", tags=["mcn"])

@mcn_router.get("/memory")
def memory(n: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
    return {"items": _peek(n)}

@mcn_router.get("/stats")
def stats() -> Dict[str, Any]:
    return _stats()
