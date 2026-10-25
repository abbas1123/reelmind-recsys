"""Common interface for every recommender.

All models share one contract so the evaluation protocol, the hybrid and the inference
engine can treat them interchangeably:

* ``fit(X, items, ts)`` — X is the user x item **rating** matrix (CSR, float32). Each model
  decides how to turn ratings into its own signal (binary, confidence, centred, ...).
  ``ts`` (optional) has the same sparsity and holds unix timestamps (used by time-aware models).
* ``score(history, user_idx)`` — dense scores (n_rows x n_items) for the users whose
  interaction rows are given in ``history``. ``user_idx`` maps rows to training users when
  they are known (warm); ``None`` means fold-in from the history alone (new users).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import joblib
import numpy as np
from scipy import sparse


@dataclass
class ItemSide:
    """Item-side information available to content-aware models."""

    texts: list[str]
    genre_matrix: sparse.csr_matrix
    embeddings: np.ndarray | None = None  # (n_items, dim), L2-normalised
    extra: dict[str, Any] = field(default_factory=dict)


class Recommender(ABC):
    name: ClassVar[str]
    #: True when the model can produce ranking scores (all models here can).
    ranks: ClassVar[bool] = True
    #: True when the model predicts explicit ratings (enables RMSE / MAE).
    predicts_ratings: ClassVar[bool] = False

    def __init__(self, **params: Any) -> None:
        self.params = params
        self.seed: int = int(params.pop("seed", 42))

    # ---------------------------------------------------------------- contract
    @abstractmethod
    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> Recommender: ...

    @abstractmethod
    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray: ...

    def predict(self, user_idx: np.ndarray, item_idx: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError(f"{self.name} does not predict explicit ratings")

    # ------------------------------------------------------------- persistence
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)

    @staticmethod
    def load(path: Path) -> Recommender:
        model = joblib.load(path)
        if not isinstance(model, Recommender):
            raise TypeError(f"{path} does not contain a Recommender")
        return model

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "params": dict(self.params), "seed": self.seed}

    def __repr__(self) -> str:
        args = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"{type(self).__name__}({args})"


# ----------------------------------------------------------------- shared helpers
def binarize(X: sparse.csr_matrix) -> sparse.csr_matrix:
    B = X.copy().astype(np.float32)
    B.data[:] = 1.0
    return B


def l2_normalize_rows(M: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    return M / np.maximum(norms, 1e-12)


def keep_top_k_per_column(S: np.ndarray, k: int) -> sparse.csr_matrix:
    """Sparsify a dense item-item matrix: keep the k largest entries in each column."""
    n = S.shape[0]
    if k <= 0 or k >= n:
        return sparse.csr_matrix(S)
    idx = np.argpartition(-S, kth=k - 1, axis=0)[:k]
    cols = np.broadcast_to(np.arange(n), idx.shape)
    vals = S[idx, cols]
    return sparse.csr_matrix((vals.ravel(), (idx.ravel(), cols.ravel())), shape=S.shape)
