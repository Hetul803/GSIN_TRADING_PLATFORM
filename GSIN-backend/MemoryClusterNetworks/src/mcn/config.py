# mcn/config.py
"""
Central config for MCN defaults.
Safe, conservative values results on AG News.
You can import these anywhere without changing your working core.
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class MCNDefaults:
    # Compression radius for clustering (cosine space).
    # Smaller eps => less merging (safer), larger => more aggressive compression.
    eps: float = 0.12

    # Decay rate (per second). 1e-6 ≈ very gentle decay over days/weeks.
    decay_lambda: float = 1e-6

    # Value weights (frequency, recency, similarity, age_penalty)
    alpha: float = 0.50
    beta: float  = 0.25
    gamma: float = 0.25
    delta: float = 0.10

    # Memory budget (active vectors) for production targets
    max_active_items: int = 1500

    # Visualization sample size
    viz_sample: int = 5000

    # Grid search ranges (Week 3 tuning)
    grid_eps: tuple = (0.08, 0.10, 0.12, 0.15)
    grid_lambda: tuple = (5e-7, 1e-6, 2e-6, 5e-6)

DEFAULTS = MCNDefaults()
