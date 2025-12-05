import numpy as np
from time import time

class ValueEstimator:
    def __init__(self, n_items=0, alpha=0.5, beta=0.3, gamma=0.15, delta=0.05, lambda_decay=1e-6):
        self.alpha, self.beta, self.gamma, self.delta = alpha, beta, gamma, delta
        self.lambda_decay = lambda_decay
        self.freq = np.zeros(n_items)        # usage count
        self.last_access = np.zeros(n_items) + time()
        self.sim_recent = np.zeros(n_items)  # similarity to recent queries
        self.birth = np.zeros(n_items) + time()
        self.values = np.ones(n_items)

    def grow(self, n_new):
        t = time()
        self.freq = np.hstack([self.freq, np.zeros(n_new)])
        self.last_access = np.hstack([self.last_access, np.zeros(n_new) + t])
        self.sim_recent = np.hstack([self.sim_recent, np.zeros(n_new)])
        self.birth = np.hstack([self.birth, np.zeros(n_new) + t])
        self.values = np.hstack([self.values, np.ones(n_new)])

    def touch(self, idxs, sim_batch):
        t = time()
        self.freq[idxs] += 1
        self.last_access[idxs] = t
        self.sim_recent[idxs] = np.clip(sim_batch, 0, 1)

    def compute_values(self):
        t = time()
        age = np.clip(t - self.birth, 1.0, None)
        recency = 1.0 / np.clip(t - self.last_access, 1.0, None)
        V = (self.alpha*self._norm(self.freq) +
             self.beta*self._norm(recency) +
             self.gamma*self._norm(self.sim_recent) -
             self.delta*self._norm(age))
        self.values = np.clip(V, 0.0, None)
        return self.values

    def decay(self, dt=None):
        if dt is None: dt = 86400.0  # default daily decay if called once/day
        self.values *= np.exp(-self.lambda_decay * dt)

    @staticmethod
    def _norm(x):
        if x.size == 0: return x
        lo, hi = np.percentile(x, 1), np.percentile(x, 99)
        if hi <= lo: return np.zeros_like(x)
        return np.clip((x - lo) / (hi - lo), 0, 1)
