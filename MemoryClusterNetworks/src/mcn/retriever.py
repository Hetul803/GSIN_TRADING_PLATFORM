# src/mcn/retriever.py
import numpy as np

def score_with_values(sims: np.ndarray, values: np.ndarray, topk: int = 5):
    """
    sims: shape (1, N) cosine similarities for a single query vs all memory vectors
    values: shape (N,) current value scores for each memory vector
    returns: (indices, scores) of topk items by (similarity * value)
    """
    # flatten to (N,)
    s = sims.reshape(-1).astype("float32")
    v = values.reshape(-1).astype("float32")
    # guard against zeros/NaNs
    v = np.where(np.isfinite(v), v, 0.0)
    s = np.where(np.isfinite(s), s, 0.0)
    scores = s * v
    # top-k
    k = min(int(topk), scores.shape[0]) if scores.shape[0] else 0
    if k <= 0:
        return np.array([], dtype=int), np.array([], dtype="float32")
    idx = np.argpartition(-scores, kth=k-1)[:k]
    # sort those k by score
    order = np.argsort(-scores[idx])
    idx = idx[order]
    return idx, scores[idx]
