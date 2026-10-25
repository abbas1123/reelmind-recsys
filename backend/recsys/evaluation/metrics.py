"""Ranking, rating and beyond-accuracy metrics.

Vectorised versions work on a ``hits`` matrix: ``hits[u, r]`` is True when the item at
rank ``r`` (0-based) of user ``u``'s list is relevant. Plain-Python reference versions
(suffix ``_single``) exist for testing and teaching.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse


# ----------------------------------------------------------------- top-k helpers
def top_k(scores: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k highest scores per row, best first. Ties are broken by lower index."""
    n_items = scores.shape[1]
    k = min(k, n_items)
    part = np.argpartition(-scores, kth=k - 1, axis=1)[:, :k]
    part_scores = np.take_along_axis(scores, part, axis=1)
    # lexsort: primary key = -score, secondary = index (stable, deterministic)
    order = np.lexsort((part, -part_scores), axis=1)
    return np.take_along_axis(part, order, axis=1)


def hits_matrix(recs: np.ndarray, relevant: sparse.csr_matrix) -> np.ndarray:
    """Boolean (n_users, k): is recs[u, r] in relevant row u?"""
    rel = relevant.tocsr()
    out = np.zeros(recs.shape, dtype=bool)
    for u in range(recs.shape[0]):
        row = rel.indices[rel.indptr[u]:rel.indptr[u + 1]]
        if len(row):
            out[u] = np.isin(recs[u], row, assume_unique=False)
    return out


# ------------------------------------------------------------ ranking (vectorised)
def precision_at_k(hits: np.ndarray, k: int) -> np.ndarray:
    return hits[:, :k].sum(axis=1) / k


def recall_at_k(hits: np.ndarray, n_relevant: np.ndarray, k: int) -> np.ndarray:
    return hits[:, :k].sum(axis=1) / np.maximum(n_relevant, 1)


def ndcg_at_k(hits: np.ndarray, n_relevant: np.ndarray, k: int) -> np.ndarray:
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    dcg = (hits[:, :k] * discounts[: hits[:, :k].shape[1]]).sum(axis=1)
    ideal_len = np.minimum(n_relevant, k)
    cum = np.concatenate([[0.0], np.cumsum(discounts)])
    idcg = cum[ideal_len]
    return np.divide(dcg, idcg, out=np.zeros_like(dcg), where=idcg > 0)


def average_precision_at_k(hits: np.ndarray, n_relevant: np.ndarray, k: int) -> np.ndarray:
    h = hits[:, :k].astype(np.float64)
    prec_at_i = np.cumsum(h, axis=1) / np.arange(1, h.shape[1] + 1)
    denom = np.minimum(n_relevant, k)
    return np.divide((prec_at_i * h).sum(axis=1), denom, out=np.zeros(len(h)), where=denom > 0)


def hit_rate_at_k(hits: np.ndarray, k: int) -> np.ndarray:
    return hits[:, :k].any(axis=1).astype(np.float64)


def mrr_at_k(hits: np.ndarray, k: int) -> np.ndarray:
    h = hits[:, :k]
    first = h.argmax(axis=1)
    return np.where(h.any(axis=1), 1.0 / (first + 1), 0.0)


# ------------------------------------------------------- ranking (reference, 1 user)
def precision_single(recs: list[int], relevant: set[int], k: int) -> float:
    return sum(1 for i in recs[:k] if i in relevant) / k


def recall_single(recs: list[int], relevant: set[int], k: int) -> float:
    return sum(1 for i in recs[:k] if i in relevant) / len(relevant) if relevant else 0.0


def ndcg_single(recs: list[int], relevant: set[int], k: int) -> float:
    dcg = sum(1 / np.log2(r + 2) for r, i in enumerate(recs[:k]) if i in relevant)
    idcg = sum(1 / np.log2(r + 2) for r in range(min(len(relevant), k)))
    return dcg / idcg if idcg else 0.0


def ap_single(recs: list[int], relevant: set[int], k: int) -> float:
    score, hits = 0.0, 0
    for r, i in enumerate(recs[:k]):
        if i in relevant:
            hits += 1
            score += hits / (r + 1)
    return score / min(len(relevant), k) if relevant else 0.0


# ------------------------------------------------------------------- rating error
def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


# ---------------------------------------------------------------- beyond accuracy
def catalog_coverage(recs: np.ndarray, n_items: int) -> float:
    """Share of the catalog that appears in at least one recommendation list."""
    return len(np.unique(recs)) / n_items


def intra_list_diversity(recs: np.ndarray, genre_matrix: sparse.csr_matrix) -> float:
    """Mean pairwise genre Jaccard distance inside each list (0 = identical genres, 1 = disjoint)."""
    g = genre_matrix.tocsr().astype(np.float64)
    k = recs.shape[1]
    if k < 2:
        return 0.0
    vals = []
    for row in recs:
        sub = g[row].toarray()
        inter = sub @ sub.T
        sizes = sub.sum(axis=1)
        union = sizes[:, None] + sizes[None, :] - inter
        sim = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        off = ~np.eye(k, dtype=bool)
        vals.append(float((1 - sim)[off].mean()))
    return float(np.mean(vals))


def novelty(recs: np.ndarray, item_popularity: np.ndarray, n_users: int) -> float:
    """Mean self-information -log2(p(i)) of recommended items, p(i) = share of users who interacted."""
    p = (item_popularity[recs] + 1) / (n_users + 1)
    return float(np.mean(-np.log2(p)))


def gini_index(recs: np.ndarray, n_items: int) -> float:
    """Concentration of recommendation exposure over the catalog (0 = equal, 1 = one item)."""
    counts = np.bincount(recs.ravel(), minlength=n_items).astype(np.float64)
    if counts.sum() == 0:
        return 0.0
    v = np.sort(counts)
    cum = np.cumsum(v)
    return float((n_items + 1 - 2 * (cum / cum[-1]).sum()) / n_items)


def bootstrap_ci(values: np.ndarray, n_samples: int, seed: int, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean over users."""
    values = np.asarray(values, dtype=np.float64)
    if len(values) == 0 or n_samples <= 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(n_samples, len(values)))
    means = values[idx].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))
