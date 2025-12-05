import numpy as np
from sklearn.cluster import KMeans

class Compressor:
    def __init__(self, eps_ratio=0.5, value_weighted=True):
        self.eps_ratio = eps_ratio
        self.value_weighted = value_weighted

    def compress(self, vectors: np.ndarray, values: np.ndarray):
        n, d = vectors.shape
        if n < 100:
            return vectors, np.arange(n)
        k = max(int(n * self.eps_ratio), 1)
        km = KMeans(n_clusters=k, n_init="auto")
        labels = km.fit_predict(vectors)
        centroids = []
        for c in range(k):
            idx = np.where(labels == c)[0]
            if len(idx) == 0: 
                continue
            if self.value_weighted:
                w = values[idx][:, None]
                centroids.append((vectors[idx] * w).sum(axis=0) / (w.sum() + 1e-9))
            else:
                centroids.append(vectors[idx].mean(axis=0))
        return np.array(centroids, dtype="float32"), labels
