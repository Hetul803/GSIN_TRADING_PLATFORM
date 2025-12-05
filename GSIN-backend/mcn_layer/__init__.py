# MCN stub — replace with your private implementation later
from typing import List, Dict, Any
from time import time

# Simple in-memory store with decay & weights
_MEMORY: List[Dict[str, Any]] = []
_DECAY = 0.99  # per-maintain call
_MAX = 2000

def remember(vectors: List[List[float]], meta: List[Dict]) -> None:
    ts = time()
    for v, m in zip(vectors, meta):
        _MEMORY.append({
            "vec": [float(x) for x in v],
            "meta": dict(m),
            "w": 1.0,             # initial weight
            "ts": ts
        })
    # cap size (FIFO)
    if len(_MEMORY) > _MAX:
        del _MEMORY[:len(_MEMORY) - _MAX]

def query(vectors: List[List[float]], topk: int = 5) -> List[Dict]:
    # trivial: return latest topk by weight/time
    return sorted(_MEMORY, key=lambda r: (r["w"], r["ts"]))[-topk:]

def maintain() -> None:
    # exponential decay of weights; clip and drop near-zero
    keep: List[Dict[str, Any]] = []
    for r in _MEMORY:
        r["w"] *= _DECAY
        if r["w"] >= 1e-4:
            keep.append(r)
    _MEMORY[:] = keep

# ---- helper accessors for UI (not part of public contract) ----
def _peek(n: int = 200) -> List[Dict[str, Any]]:
    return _MEMORY[-n:]

def _stats() -> Dict[str, Any]:
    n = len(_MEMORY)
    if n == 0:
        return {"count": 0, "avg_vec": [0,0,0], "avg_w": 0.0}
    avg_vec = [sum(r["vec"][i] for r in _MEMORY)/n for i in range(3)]
    avg_w = sum(r["w"] for r in _MEMORY)/n
    return {"count": n, "avg_vec": avg_vec, "avg_w": avg_w}

