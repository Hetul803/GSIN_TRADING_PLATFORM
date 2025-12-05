from collections import deque
from threading import Lock

_metrics = deque(maxlen=500)
_counter = 0
_lock = Lock()

def push_metric(ret: float, sharpe: float):
    global _counter
    with _lock:
        _metrics.append({"i": _counter, "ret": round(ret, 6), "sharpe": round(sharpe, 6)})
        _counter += 1

def get_series():
    return list(_metrics)
