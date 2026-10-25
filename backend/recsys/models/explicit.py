"""Explicit-rating models: regularised bias baseline and biased matrix factorisation (ALS)."""

from __future__ import annotations

import numpy as np
from scipy import sparse
from threadpoolctl import threadpool_limits

from recsys.models.base import ItemSide, Recommender


class BiasBaseline(Recommender):
    """r_ui ≈ mu + b_u + b_i with damped means (Koren, 2010).

    As a ranker it orders items by b_i — a "top rated, damped by support" list that is the
    same for everybody. Useful to show that rating accuracy and ranking quality differ.
    """

    name = "bias_baseline"
    predicts_ratings = True

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> BiasBaseline:
        reg_i = float(self.params.get("reg_item", 10))
        reg_u = float(self.params.get("reg_user", 10))
        X = X.tocsr().astype(np.float64)
        coo = X.tocoo()
        self.mu = float(coo.data.mean())
        n_u, n_i = X.shape
        bu, bi = np.zeros(n_u), np.zeros(n_i)
        cnt_i = np.bincount(coo.col, minlength=n_i)
        cnt_u = np.bincount(coo.row, minlength=n_u)
        for _ in range(10):
            bi = np.bincount(coo.col, weights=coo.data - self.mu - bu[coo.row], minlength=n_i) / (reg_i + cnt_i)
            bu = np.bincount(coo.row, weights=coo.data - self.mu - bi[coo.col], minlength=n_u) / (reg_u + cnt_u)
        self.bu, self.bi = bu.astype(np.float32), bi.astype(np.float32)
        return self

    def predict(self, user_idx: np.ndarray, item_idx: np.ndarray) -> np.ndarray:
        bu = np.where(user_idx < len(self.bu), self.bu[np.minimum(user_idx, len(self.bu) - 1)], 0.0)
        return np.clip(self.mu + bu + self.bi[item_idx], 1.0, 5.0)

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        return np.tile(self.mu + self.bi, (history.shape[0], 1)).astype(np.float32)


class BiasedMF(Recommender):
    """r_ui ≈ mu + b_u + b_i + p_u . q_i, fitted by alternating least squares (ALS-WR).

    Each user solve regresses (r - mu - b_i) on [q_i, 1] so the user bias is learned jointly
    with the factors; items symmetrically. Regularisation is scaled by the number of ratings.
    """

    name = "biased_mf"
    predicts_ratings = True

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> BiasedMF:
        f = int(self.params.get("factors", 32))
        reg = float(self.params.get("reg", 0.1))
        iterations = int(self.params.get("iterations", 12))
        rng = np.random.default_rng(self.seed)
        R = X.tocsr().astype(np.float64)
        Rt = R.T.tocsr()
        self.mu = float(R.data.mean())
        n_u, n_i = R.shape
        P, Q = rng.normal(0, 0.1, (n_u, f)), rng.normal(0, 0.1, (n_i, f))
        bu, bi = np.zeros(n_u), np.zeros(n_i)
        for _ in range(iterations):
            P, bu = self._solve(R, Q, bi, reg)
            Q, bi = self._solve(Rt, P, bu, reg)
        self.P, self.Q = P.astype(np.float32), Q.astype(np.float32)
        self.bu, self.bi = bu.astype(np.float32), bi.astype(np.float32)
        self._reg = reg
        return self

    def _solve(self, R: sparse.csr_matrix, other: np.ndarray, other_bias: np.ndarray,
               reg: float) -> tuple[np.ndarray, np.ndarray]:
        f = other.shape[1]
        out = np.zeros((R.shape[0], f))
        bias = np.zeros(R.shape[0])
        eye = np.eye(f + 1)
        with threadpool_limits(1, user_api="blas"):  # many tiny solves: threads only add overhead
            self._solve_rows(R, other, other_bias, reg, eye, out, bias)
        return out, bias

    def _solve_rows(self, R: sparse.csr_matrix, other: np.ndarray, other_bias: np.ndarray, reg: float,
                    eye: np.ndarray, out: np.ndarray, bias: np.ndarray) -> None:
        f = other.shape[1]
        for u in range(R.shape[0]):
            s, e = R.indptr[u], R.indptr[u + 1]
            if s == e:
                continue
            idx = R.indices[s:e]
            target = R.data[s:e] - self.mu - other_bias[idx]
            Z = np.hstack([other[idx], np.ones((e - s, 1))])
            w = np.linalg.solve(Z.T @ Z + reg * (e - s) * eye, Z.T @ target)
            out[u], bias[u] = w[:f], w[f]

    def predict(self, user_idx: np.ndarray, item_idx: np.ndarray) -> np.ndarray:
        pred = self.mu + self.bu[user_idx] + self.bi[item_idx] + np.einsum("ij,ij->i", self.P[user_idx],
                                                                            self.Q[item_idx])
        return np.clip(pred, 1.0, 5.0)

    def fold_in(self, history: sparse.csr_matrix) -> tuple[np.ndarray, np.ndarray]:
        P, bu = self._solve(history.tocsr().astype(np.float64), self.Q.astype(np.float64),
                            self.bi.astype(np.float64), self._reg)
        return P.astype(np.float32), bu.astype(np.float32)

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        if user_idx is not None:
            P, bu = self.P[user_idx], self.bu[user_idx]
        else:
            P, bu = self.fold_in(history)
        return (self.mu + bu[:, None] + self.bi[None, :] + P @ self.Q.T).astype(np.float32)
