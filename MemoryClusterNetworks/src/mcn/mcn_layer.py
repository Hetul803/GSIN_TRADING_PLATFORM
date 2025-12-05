# src/mcn/mcn_layer.py
import numpy as np, time
from collections import deque
from .memory_store import MemoryStore
from .value_estimator import ValueEstimator
from .compressor import Compressor
from .retriever import score_with_values
from .persistence import save_state, load_state

class MCNLayer:
    """
    MCN layer with adaptive maintenance + persistence + simple event logging.
    `auto_maintain` controls whether add/search/decay can auto-trigger maintenance.
    """

    def __init__(
        self,
        dim: int,
        # Core policy
        budget: int | None = None,            # target #items to keep after maintenance
        hysteresis_pct: float = 0.10,         # wait until size ≥ budget*(1+hyst) before compressing
        keep_top_quantile: float = 0.25,      # protect top-q by value
        warmup_hours: float = 48.0,           # recent items protected from merge
        # Latency SLO trigger (optional)
        latency_slo_ms: float | None = None,  # p95 target; None disables SLO trigger
        slo_window: int = 200,
        slo_breach_count: int = 3,
        # Toggle auto maintenance (NEW)
        auto_maintain: bool = True,
        # Legacy / misc
        max_items: int | None = 50000,        # used if budget=None
        lambda_decay: float = 1e-6,
        min_clusters: int = 1
    ):
        self.store = MemoryStore(dim)
        self.vals = ValueEstimator(0, lambda_decay=lambda_decay)

        # Policy
        self.budget = budget if budget is not None else max_items
        self.hysteresis_pct = float(max(0.0, hysteresis_pct))
        self.keep_top_quantile = float(np.clip(keep_top_quantile, 0.0, 1.0))
        self.warmup_secs = float(max(0.0, warmup_hours)) * 3600.0
        self.min_clusters = int(max(1, min_clusters))
        self.compressor = Compressor(eps_ratio=0.5, value_weighted=True)

        # Latency SLO tracking
        self.latency_slo_ms = latency_slo_ms
        self._lat_buf: deque[float] = deque(maxlen=slo_window)
        self._slo_breaches = 0
        self._slo_breach_count = slo_breach_count

        # Toggle
        self.auto_maintain = bool(auto_maintain)

        # Logging
        self.events: list[dict] = []  # append dicts: {"t": ts, "event": str, ...}

    # ---------- helpers ----------
    @staticmethod
    def _l2norm(x):
        return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)

    def _size(self):
        return self.store.vectors.shape[0]

    def _over_budget(self):
        if self.budget is None:
            return False
        n = self._size()
        return n >= int(self.budget * (1.0 + self.hysteresis_pct))

    def _log(self, event: str, **kw):
        rec = {"t": time.time(), "event": event, "size": self._size()}
        rec.update(kw)
        self.events.append(rec)

    def _maybe_auto_maintain(self, reason: str):
        if self.auto_maintain:
            self.maintain(reason=reason)

    def _slo_trigger(self):
        if self.latency_slo_ms is None or len(self._lat_buf) < self._lat_buf.maxlen:
            return False
        p95 = np.percentile(np.array(self._lat_buf), 95)
        if p95 * 1000.0 > self.latency_slo_ms:
            self._slo_breaches += 1
        else:
            self._slo_breaches = 0
        return self._slo_breaches >= self._slo_breach_count

    # ---------- public API ----------
    def add(self, vecs: np.ndarray, meta_batch=None):
        before = self._size()
        self.store.add(vecs, meta_batch)
        n_new = self._size() - before
        self.vals.grow(n_new)
        self._log("add", added=n_new)

        if self._over_budget():
            self._maybe_auto_maintain(reason="over_budget")

    def search(self, qvec: np.ndarray, k: int = 5):
        if self._size() == 0:
            return [], []
        t0 = time.time()

        q = qvec.reshape(1, -1).astype("float32")
        q = self._l2norm(q)
        Vn = self._l2norm(self.store.vectors)
        sims = (q @ Vn.T)

        vals = self.vals.compute_values()
        if not np.any(vals > 0):
            vals = np.ones_like(vals)

        idx, scores = score_with_values(sims, vals, topk=k)
        self.vals.touch(idx, sims.flatten()[idx])

        # latency track
        self._lat_buf.append(time.time() - t0)
        if self._slo_trigger():
            self._maybe_auto_maintain(reason="latency_slo")

        return [self.store.meta[i] for i in idx], scores

    def decay(self, dt=None):
        self.vals.decay(dt=dt)
        self._log("decay", dt=float(dt if dt is not None else 0.0))
        if self._over_budget():
            self._maybe_auto_maintain(reason="over_budget_after_decay")

    # ---------- maintenance / compression ----------
    def maintain(self, budget: int | None = None, keep_top_quantile: float | None = None, reason: str = "manual"):
        V = self.store.vectors
        M = self.store.meta
        n = V.shape[0]
        if n == 0:
            self._log("maintain_skip_empty")
            return

        B = int(budget if budget is not None else (self.budget or n))
        q = float(self.keep_top_quantile if keep_top_quantile is None else keep_top_quantile)
        q = float(np.clip(q, 0.0, 1.0))

        if n <= B:
            self._log("maintain_skip_within_budget", budget=B)
            return

        vals = self.vals.compute_values()
        order = np.argsort(-vals)
        now = time.time()
        ages = now - self.vals.birth
        warm_mask = ages < self.warmup_secs

        # Protect warm-up + top-q by value
        keep_mask = warm_mask.copy()
        keep_target = min(int(np.ceil(q * n)), B)
        keep_idx_by_value = order[:keep_target]
        keep_mask[keep_idx_by_value] = True

        keep_idx = np.where(keep_mask)[0]
        tail_idx = np.where(~keep_mask)[0]

        if keep_idx.size >= B:
            top_idx = order[:B]
            self._rebuild_from_indices(top_idx)
            self._log("maintain_trim_topB", budget=B, kept=len(top_idx), reason=reason)
            self._lat_buf.clear()
            self._slo_breaches = 0
            return

        remaining = max(B - keep_idx.size, self.min_clusters)
        if tail_idx.size == 0:
            self._log("maintain_skip_no_tail", budget=B, kept=keep_idx.size, reason=reason)
            return

        # Cluster tail to approx 'remaining' centroids
        tail_V = V[tail_idx]
        tail_vals = vals[tail_idx]
        eps_ratio = max(remaining / max(1, tail_V.shape[0]), 1.0 / max(1, tail_V.shape[0]))
        old_ratio = self.compressor.eps_ratio
        self.compressor.eps_ratio = eps_ratio
        centroids, labels = self.compressor.compress(tail_V, tail_vals)
        self.compressor.eps_ratio = old_ratio

        # Metadata for centroids (rep = highest-value member)
        new_meta_centroids = []
        for c in range(centroids.shape[0]):
            member_local = np.where(labels == c)[0]
            if member_local.size == 0:
                new_meta_centroids.append({"centroid_of": []})
                continue
            member_global = tail_idx[member_local]
            rep = member_global[np.argmax(vals[member_global])]
            rep_meta = M[rep] if rep < len(M) else {}
            rep_copy = dict(rep_meta)
            rep_copy["centroid_of"] = list(map(int, member_global.tolist()))
            new_meta_centroids.append(rep_copy)

        kept_V = V[keep_idx]
        kept_meta = [M[i] for i in keep_idx]
        new_V = np.vstack([kept_V, centroids]).astype("float32")
        new_meta = kept_meta + new_meta_centroids

        before = self._size()
        self.store = MemoryStore(V.shape[1])
        self.store.add(new_V, meta_batch=new_meta)
        self.vals = ValueEstimator(len(new_meta), lambda_decay=self.vals.lambda_decay)
        after = self._size()

        self._log("maintain_done", reason=reason, before=int(before), after=int(after), kept=len(kept_meta), centroids=int(centroids.shape[0]))
        self._lat_buf.clear()
        self._slo_breaches = 0

    def _rebuild_from_indices(self, idx: np.ndarray):
        V = self.store.vectors
        M = self.store.meta
        new_V = V[idx]
        new_meta = [M[i] for i in idx]
        self.store = MemoryStore(V.shape[1])
        self.store.add(new_V, meta_batch=new_meta)
        self.vals = ValueEstimator(len(new_meta), lambda_decay=self.vals.lambda_decay)

    # Legacy helper
    def compress(self):
        if self.budget is None: return
        if self._size() <= self.budget: return
        self.maintain(budget=self.budget, reason="legacy_compress")

    def size(self):
        return self._size()

    # ---------- persistence ----------
    def save(self, path: str, extra: dict | None = None):
        policy = dict(
            budget=self.budget,
            hysteresis_pct=self.hysteresis_pct,
            keep_top_quantile=self.keep_top_quantile,
            warmup_secs=self.warmup_secs,
            min_clusters=self.min_clusters,
            latency_slo_ms=self.latency_slo_ms,
            auto_maintain=self.auto_maintain,
        )
        save_state(
            path,
            vectors=self.store.vectors,
            meta=self.store.meta,
            values=self.vals.values,
            birth=self.vals.birth,
            lambda_decay=self.vals.lambda_decay,
            dim=self.store.vectors.shape[1] if self._size() > 0 else 0,
            policy=policy,
            extra=extra or {"events": self.events}
        )
        self._log("save", path=path)

    @classmethod
    def load(cls, path: str):
        state = load_state(path)
        dim = state["dim"]
        pol = state.get("policy", {})
        self = cls(dim=dim,
                   budget=pol.get("budget"),
                   hysteresis_pct=pol.get("hysteresis_pct", 0.10),
                   keep_top_quantile=pol.get("keep_top_quantile", 0.25),
                   warmup_hours=pol.get("warmup_secs", 48*3600)/3600.0,
                   latency_slo_ms=pol.get("latency_slo_ms"),
                   auto_maintain=pol.get("auto_maintain", True))
        # rebuild store
        self.store.add(state["vectors"].astype("float32"), meta_batch=state["meta"])
        # rebuild estimator
        self.vals = ValueEstimator(self.size(), lambda_decay=state["lambda_decay"])
        self.vals.values = state["values"].astype("float32")
        self.vals.birth = state["birth"].astype("float64")
        # events
        extra = state.get("extra") or {}
        self.events = extra.get("events", [])
        self._log("load", path=path)
        return self
