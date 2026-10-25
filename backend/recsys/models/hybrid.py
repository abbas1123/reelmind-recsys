"""Weighted + switching hybrid of collaborative, content and popularity scores.

    s(u, i) = w_cf * norm(s_cf) + w_cb * norm(s_cb) + w_pop * norm(s_pop)

``norm`` is per-user min-max scaling, so components on different scales are comparable.
The weight set is *switched* by the length of the user's history:

    0 interactions          -> "cold"  weights (popularity / onboarding)
    1 .. warm_min - 1       -> "light" weights (tuned on simulated cold users)
    >= warm_min             -> "warm"  weights (tuned on warm validation users)

All weights are chosen on the validation split (see ``recsys.training.tune``).
"""

from __future__ import annotations

from itertools import product

import numpy as np
from scipy import sparse

from recsys.models.base import ItemSide, Recommender

COMPONENTS = ("cf", "cb", "pop")


def minmax_rows(scores: np.ndarray) -> np.ndarray:
    lo = scores.min(axis=1, keepdims=True)
    hi = scores.max(axis=1, keepdims=True)
    span = hi - lo
    return np.divide(scores - lo, span, out=np.zeros_like(scores), where=span > 0)


def weight_grid(step: float) -> list[dict[str, float]]:
    """All (w_cf, w_cb, w_pop) on the simplex with the given step."""
    n = int(round(1 / step))
    out = []
    for a, b in product(range(n + 1), repeat=2):
        if a + b <= n:
            out.append({"cf": round(a * step, 4), "cb": round(b * step, 4), "pop": round((n - a - b) * step, 4)})
    return out


def combine(normed: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    out = np.zeros_like(normed["pop"])
    for c in COMPONENTS:
        if weights.get(c, 0.0):
            out += weights[c] * normed[c]
    return out


class Hybrid(Recommender):
    name = "hybrid"

    def __init__(self, cf: Recommender, cb: Recommender, pop: Recommender,
                 weights: dict[str, dict[str, float]] | None = None, warm_min_history: int = 5, **params) -> None:
        super().__init__(**params)
        self.components = {"cf": cf, "cb": cb, "pop": pop}
        self.weights = weights or {
            "cold": {"cf": 0.0, "cb": 0.0, "pop": 1.0},
            "light": {"cf": 0.4, "cb": 0.4, "pop": 0.2},
            "warm": {"cf": 0.8, "cb": 0.1, "pop": 0.1},
        }
        self.warm_min_history = warm_min_history

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> Hybrid:
        for comp in self.components.values():
            comp.fit(X, items, ts)
        return self

    def component_scores(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> dict[str, np.ndarray]:
        return {name: m.score(history, user_idx) for name, m in self.components.items()}

    def bucket(self, history_len: np.ndarray) -> np.ndarray:
        return np.where(history_len == 0, "cold", np.where(history_len < self.warm_min_history, "light", "warm"))

    def combine_scores(self, raw: dict[str, np.ndarray], history_len: np.ndarray) -> np.ndarray:
        normed = {c: minmax_rows(raw[c]) for c in COMPONENTS}
        buckets = self.bucket(history_len)
        out = np.zeros_like(normed["pop"])
        for b in ("cold", "light", "warm"):
            rows = buckets == b
            if rows.any():
                out[rows] = combine({c: normed[c][rows] for c in COMPONENTS}, self.weights[b])
        return out

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        return self.combine_scores(self.component_scores(history, user_idx), np.diff(history.tocsr().indptr))

    def describe(self) -> dict:
        return {
            "name": self.name,
            "components": {k: v.describe() for k, v in self.components.items()},
            "weights": self.weights,
            "warm_min_history": self.warm_min_history,
        }
