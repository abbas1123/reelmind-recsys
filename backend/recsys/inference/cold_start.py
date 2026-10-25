"""Cold-start strategies for users with no history.

The validated part is the popularity fallback (``cold_*_n0`` in the report). Genre
affinity and MMR diversification add the user's onboarding choices on top; they are
documented heuristics, not tuned on data (there is no held-out "chosen genres" signal).
"""

from __future__ import annotations

import numpy as np
from scipy import sparse


def _minmax(v: np.ndarray) -> np.ndarray:
    lo, hi = float(np.min(v)), float(np.max(v))
    return (v - lo) / (hi - lo) if hi > lo else np.zeros_like(v, dtype=np.float64)


def genre_affinity(genre_matrix: sparse.csr_matrix, vocab: list[str], preferred: list[str]) -> np.ndarray:
    """Share of the user's preferred genres that each item carries (0..1)."""
    cols = [vocab.index(g) for g in preferred if g in vocab]
    if not cols:
        return np.zeros(genre_matrix.shape[0])
    return np.asarray(genre_matrix[:, cols].sum(axis=1)).ravel() / len(cols)


def base_cold_scores(popularity: np.ndarray, bayes_avg: np.ndarray, counts: np.ndarray,
                     min_count: int = 20) -> np.ndarray:
    """Blend of (log) popularity and damped average rating; items with too few ratings are demoted."""
    score = 0.5 * _minmax(np.log1p(popularity)) + 0.5 * _minmax(bayes_avg)
    return np.where(counts >= min_count, score, score * 0.25)


def mmr_rerank(scores: np.ndarray, candidates: np.ndarray, genre_matrix: sparse.csr_matrix, k: int,
               lam: float = 0.75) -> list[int]:
    """Maximal Marginal Relevance with genre Jaccard similarity (higher lam = less diversity)."""
    G = genre_matrix[candidates].toarray().astype(np.float64)
    sizes = G.sum(axis=1)
    rel = _minmax(scores[candidates])
    chosen: list[int] = []
    max_sim = np.zeros(len(candidates))
    available = np.ones(len(candidates), dtype=bool)
    for _ in range(min(k, len(candidates))):
        mmr = lam * rel - (1 - lam) * max_sim
        mmr[~available] = -np.inf
        j = int(np.argmax(mmr))
        chosen.append(int(candidates[j]))
        available[j] = False
        inter = G @ G[j]
        union = sizes + sizes[j] - inter
        sim = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        max_sim = np.maximum(max_sim, sim)
    return chosen


def recommend_new_user(base: np.ndarray, genre_matrix: sparse.csr_matrix, vocab: list[str],
                       preferred_genres: list[str] | None, k: int, exclude: set[int],
                       allowed: np.ndarray | None = None, pool: int = 200) -> list[tuple[int, float, str]]:
    """Return (item index, score, reason) for a user with an empty history."""
    scores = base.astype(np.float64).copy()
    affinity = np.zeros_like(scores)
    if preferred_genres:
        affinity = genre_affinity(genre_matrix, vocab, preferred_genres)
        scores = scores * (0.3 + 0.7 * affinity)
    if allowed is not None:
        scores[~allowed] = -np.inf
    for i in exclude:
        scores[i] = -np.inf
    finite = np.flatnonzero(np.isfinite(scores))
    if not len(finite):
        return []
    candidates = finite[np.argsort(-scores[finite], kind="stable")[:pool]]
    picked = mmr_rerank(scores, candidates, genre_matrix, k)
    out = []
    for i in picked:
        if preferred_genres and affinity[i] > 0:
            matched = [vocab[c] for c in genre_matrix[i].indices if vocab[c] in preferred_genres]
            reason = f"Popular in {', '.join(matched[:2])}"
        else:
            reason = "Popular and highly rated"
        out.append((i, float(scores[i]), reason))
    return out
