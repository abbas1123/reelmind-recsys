"""Neighbourhood collaborative filtering (item-based and user-based, cosine similarity)."""

from __future__ import annotations

import numpy as np
from scipy import sparse
from sklearn.preprocessing import normalize

from recsys.models.base import ItemSide, Recommender, binarize, keep_top_k_per_column


class ItemKNN(Recommender):
    """score(u, j) = sum_i x_ui * sim(i, j) over the k most similar items i of j.

    sim(i, j) = |U_i ∩ U_j| / (||U_i|| * ||U_j|| + shrink)  — cosine with shrinkage, which
    damps similarities supported by only a few co-raters.
    """

    name = "item_knn"

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> ItemKNN:
        k = int(self.params.get("k", 100))
        shrink = float(self.params.get("shrink", 0))
        B = binarize(X).tocsc()
        co = (B.T @ B).toarray().astype(np.float32)
        norms = np.sqrt(np.diag(co))
        sim = co / (np.outer(norms, norms) + shrink + 1e-9)
        np.fill_diagonal(sim, 0.0)
        self.sim = keep_top_k_per_column(sim, k).astype(np.float32)
        return self

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        return np.asarray((binarize(history) @ self.sim).todense(), dtype=np.float32)


class UserKNN(Recommender):
    """score(u, j) = sum over the k most similar training users v of sim(u, v) * x_vj."""

    name = "user_knn"

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> UserKNN:
        self.B = binarize(X).tocsr()
        self.B_norm = normalize(self.B, norm="l2", axis=1).astype(np.float32).tocsr()
        return self

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        k = int(self.params.get("k", 100))
        h = normalize(binarize(history), norm="l2", axis=1).astype(np.float32)
        sims = np.asarray((h @ self.B_norm.T).todense(), dtype=np.float32)
        if user_idx is not None:
            sims[np.arange(len(user_idx)), user_idx] = 0.0  # never use the user as their own neighbour
        if 0 < k < sims.shape[1]:
            drop = np.argpartition(-sims, kth=k, axis=1)[:, k:]
            np.put_along_axis(sims, drop, 0.0, axis=1)
        return np.asarray((sparse.csr_matrix(sims) @ self.B).toarray(), dtype=np.float32)
