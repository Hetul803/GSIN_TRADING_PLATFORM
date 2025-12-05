import numpy as np

try:
    import faiss  # optional; we still compute cosine separately
    _FAISS = True
except Exception:
    _FAISS = False

class MemoryStore:
    def __init__(self, dim: int):
        self.dim = dim
        self.vectors = np.empty((0, dim), dtype="float32")
        self.meta = []  # arbitrary dicts per item
        self.index = None
        if _FAISS:
            self.index = faiss.IndexFlatL2(dim)

    def add(self, vecs: np.ndarray, meta_batch=None):
        vecs = vecs.astype("float32")
        n = vecs.shape[0]
        self.vectors = np.vstack([self.vectors, vecs])
        # ensure meta length matches vectors length
        if meta_batch is None:
            meta_batch = [{} for _ in range(n)]
        if len(meta_batch) != n:
            # trim or pad to match n exactly
            if len(meta_batch) > n:
                meta_batch = meta_batch[:n]
            else:
                meta_batch = list(meta_batch) + [{} for _ in range(n - len(meta_batch))]
        self.meta.extend(meta_batch)

        if _FAISS:
            if self.index is None or self.index.d != self.dim:
                self.index = faiss.IndexFlatL2(self.dim)
            self.index.add(vecs)

    def size(self):
        return self.vectors.shape[0]
