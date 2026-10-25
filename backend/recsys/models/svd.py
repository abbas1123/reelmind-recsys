"""PureSVD (Cremonesi et al., 2010): truncated SVD of the binary interaction matrix."""

from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import svds

from recsys.models.base import ItemSide, Recommender, binarize


class PureSVD(Recommender):
    """score(u) = x_u V V^T, where V are the top right-singular vectors of X.

    Fold-in is exact by construction: a new user's history is projected on V.
    """

    name = "pure_svd"

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> PureSVD:
        f = int(self.params.get("factors", 64))
        B = binarize(X).astype(np.float64)
        rng = np.random.default_rng(self.seed)
        v0 = rng.random(min(B.shape))
        _, s, vt = svds(B, k=f, v0=v0)
        order = np.argsort(-s)
        self.singular_values = s[order].astype(np.float32)
        self.V = vt[order].T.astype(np.float32)  # (n_items, f)
        return self

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        z = binarize(history) @ self.V
        return np.asarray(z @ self.V.T, dtype=np.float32)
