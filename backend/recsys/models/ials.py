"""Implicit ALS (Hu, Koren & Volinsky, 2008), implemented with NumPy/SciPy.

Every observed interaction is a positive preference p_ui = 1 with confidence
c_ui = 1 + alpha * rating / 5; unobserved cells are p = 0 with confidence 1.

    min  sum_ui c_ui (p_ui - x_u . y_i)^2 + reg (||x_u||^2 + ||y_i||^2)

Alternating closed-form updates. The trick that keeps it cheap: Y^T C_u Y = Y^T Y + Y_u^T (C_u - I) Y_u,
so each user solve only touches the items that user interacted with.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy import sparse
from threadpoolctl import threadpool_limits

from recsys.models.base import ItemSide, Recommender

log = logging.getLogger(__name__)


def _confidence(X: sparse.csr_matrix, alpha: float) -> sparse.csr_matrix:
    C = X.copy().astype(np.float64).tocsr()
    C.data = 1.0 + alpha * (C.data / 5.0)
    return C


def _solve_side(C: sparse.csr_matrix, Y: np.ndarray, reg: float) -> np.ndarray:
    """For every row of C solve (Y^T C_u Y + reg I) x_u = Y^T C_u p_u."""
    f = Y.shape[1]
    YtY = Y.T @ Y
    reg_eye = reg * np.eye(f)
    out = np.zeros((C.shape[0], f))
    indptr, indices, data = C.indptr, C.indices, C.data
    with threadpool_limits(1, user_api="blas"):  # many tiny solves: threads only add overhead
        _solve_rows(indptr, indices, data, Y, YtY, reg_eye, out)
    return out


def _solve_rows(indptr: np.ndarray, indices: np.ndarray, data: np.ndarray, Y: np.ndarray, YtY: np.ndarray,
                reg_eye: np.ndarray, out: np.ndarray) -> None:
    for u in range(len(indptr) - 1):
        start, end = indptr[u], indptr[u + 1]
        if start == end:
            continue
        idx, c = indices[start:end], data[start:end]
        Yu = Y[idx]
        A = YtY + (Yu.T * (c - 1.0)) @ Yu + reg_eye
        b = Yu.T @ c
        out[u] = np.linalg.solve(A, b)


class IALS(Recommender):
    name = "ials"

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> IALS:
        f = int(self.params.get("factors", 64))
        reg = float(self.params.get("reg", 1.0))
        alpha = float(self.params.get("alpha", 10.0))
        iterations = int(self.params.get("iterations", 15))
        rng = np.random.default_rng(self.seed)

        Cui = _confidence(X, alpha)
        Ciu = Cui.T.tocsr()
        U = rng.normal(0, 0.01, (X.shape[0], f))
        V = rng.normal(0, 0.01, (X.shape[1], f))
        for it in range(iterations):
            U = _solve_side(Cui, V, reg)
            V = _solve_side(Ciu, U, reg)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("iALS iteration %d/%d", it + 1, iterations)
        self.U, self.V = U.astype(np.float32), V.astype(np.float32)
        self._alpha, self._reg = alpha, reg
        return self

    def user_factors(self, history: sparse.csr_matrix) -> np.ndarray:
        """Fold-in: the exact ALS user update with item factors fixed."""
        return _solve_side(_confidence(history, self._alpha), self.V.astype(np.float64), self._reg).astype(np.float32)

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        Uq = self.U[user_idx] if user_idx is not None else self.user_factors(history)
        return Uq @ self.V.T
