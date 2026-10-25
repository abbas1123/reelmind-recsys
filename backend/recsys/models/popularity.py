"""Non-personalised baselines."""

from __future__ import annotations

import numpy as np
from scipy import sparse

from recsys.models.base import ItemSide, Recommender


class Popularity(Recommender):
    """Rank items by how many users interacted with them in training.

    ``half_life_events`` > 0 turns it into *trending* popularity: each interaction counts
    0.5 ** (age / half_life), where age is the number of newer interactions in the data.
    Under a temporal split this matters — what is popular *now* predicts the near future
    better than all-time counts. The half-life is chosen on validation (0 = all-time counts).

    Age is measured in interactions, not calendar days, on purpose: activity in MovieLens
    drops from ~3,000 ratings/day in 2000 to a handful per day in 2003. A half-life of "3 days"
    tuned on the dense validation period would, at serving time, mean "the last dozen
    ratings" — noise. An event-count half-life keeps the same amount of evidence in both.

    Also keeps a Bayesian-average rating (damped towards the global mean) that the
    cold-start module uses to prefer well-liked, not just frequently-rated, items.
    """

    name = "popularity"

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> Popularity:
        X = X.tocsc()
        self.counts = np.asarray(X.getnnz(axis=0), dtype=np.float32)
        sums = np.asarray(X.sum(axis=0)).ravel()
        self.global_mean = float(X.data.mean()) if X.nnz else 0.0
        self.damping = float(self.params.get("damping", 20))
        self.mean_rating = np.divide(sums, self.counts, out=np.zeros_like(sums), where=self.counts > 0)
        self.bayes_avg = (sums + self.damping * self.global_mean) / (self.counts + self.damping)

        half_life = float(self.params.get("half_life_events", 0))
        self.scores_ = self.counts.copy()
        if half_life > 0:
            if ts is None:
                raise ValueError("half_life_events > 0 needs the timestamp matrix `ts`")
            T = ts.tocsc()
            # age = number of strictly newer interactions (ties share an age)
            order = np.sort(T.data)
            age = len(order) - np.searchsorted(order, T.data, side="right")
            decayed = sparse.csc_matrix((0.5 ** (age / half_life), T.indices, T.indptr), shape=T.shape)
            self.scores_ = np.asarray(decayed.sum(axis=0), dtype=np.float32).ravel()
            self.reference_ts = float(T.data.max())
        return self

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        return np.tile(self.scores_, (history.shape[0], 1))
