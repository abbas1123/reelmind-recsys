"""EASE^R (Steck, 2019): closed-form shallow autoencoder for implicit feedback."""

from __future__ import annotations

import numpy as np
from scipy import sparse

from recsys.models.base import ItemSide, Recommender, binarize


class EASE(Recommender):
    """Learns an item-item weight matrix W with zero diagonal by ridge regression:

        min_W ||X - X W||^2 + lambda ||W||^2   s.t. diag(W) = 0
        P = (X^T X + lambda I)^-1,   W = -P / diag(P),   diag(W) = 0

    One matrix inversion of size n_items — seconds for MovieLens 1M.
    """

    name = "ease"

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> EASE:
        lam = float(self.params.get("lambda_", 500.0))
        B = binarize(X)
        G = (B.T @ B).toarray().astype(np.float64)
        G[np.diag_indices_from(G)] += lam
        P = np.linalg.inv(G)
        W = P / (-np.diag(P))
        np.fill_diagonal(W, 0.0)
        self.W = W.astype(np.float32)
        return self

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        return np.asarray(binarize(history) @ self.W, dtype=np.float32)
