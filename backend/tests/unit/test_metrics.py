"""Metric correctness against hand-computed values and the plain-Python reference versions."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse

from recsys.evaluation import metrics as M


def test_hand_computed_example():
    # ranked list [a, b, c, d, e] with relevant {b, d, z}  (z never recommended)
    recs, rel, k = [1, 2, 3, 4, 5], {2, 4, 99}, 5
    assert M.precision_single(recs, rel, k) == pytest.approx(2 / 5)
    assert M.recall_single(recs, rel, k) == pytest.approx(2 / 3)
    dcg = 1 / np.log2(3) + 1 / np.log2(5)
    idcg = 1 / np.log2(2) + 1 / np.log2(3) + 1 / np.log2(4)
    assert M.ndcg_single(recs, rel, k) == pytest.approx(dcg / idcg)
    assert M.ap_single(recs, rel, k) == pytest.approx((1 / 2 + 2 / 4) / 3)


def test_vectorised_matches_reference():
    rng = np.random.default_rng(0)
    n_users, n_items, k = 50, 40, 10
    scores = rng.random((n_users, n_items))
    rel_dense = rng.random((n_users, n_items)) < 0.15
    rel_dense[0] = False
    rel_dense[0, 3] = True  # at least one relevant item per user
    relevant = sparse.csr_matrix(rel_dense.astype(np.float32))
    recs = M.top_k(scores, k)
    hits = M.hits_matrix(recs, relevant)
    n_rel = rel_dense.sum(axis=1)
    for u in range(n_users):
        r, s = recs[u].tolist(), set(np.flatnonzero(rel_dense[u]).tolist())
        assert M.precision_at_k(hits, k)[u] == pytest.approx(M.precision_single(r, s, k))
        assert M.recall_at_k(hits, n_rel, k)[u] == pytest.approx(M.recall_single(r, s, k))
        assert M.ndcg_at_k(hits, n_rel, k)[u] == pytest.approx(M.ndcg_single(r, s, k))
        assert M.average_precision_at_k(hits, n_rel, k)[u] == pytest.approx(M.ap_single(r, s, k))


def test_top_k_order_and_ties():
    scores = np.array([[0.1, 0.9, 0.5, 0.9]])
    assert M.top_k(scores, 3).tolist() == [[1, 3, 2]]  # tie broken by lower index


def test_perfect_and_empty_rankings():
    hits = np.array([[True, True, False], [False, False, False]])
    n_rel = np.array([2, 1])
    assert M.ndcg_at_k(hits, n_rel, 3).tolist() == pytest.approx([1.0, 0.0])
    assert M.mrr_at_k(np.array([[False, True, True]]), 3).tolist() == [0.5]
    assert M.hit_rate_at_k(hits, 3).tolist() == [1.0, 0.0]


def test_rating_errors():
    assert M.rmse(np.array([1, 3]), np.array([2, 5])) == pytest.approx(np.sqrt((1 + 4) / 2))
    assert M.mae(np.array([1, 3]), np.array([2, 5])) == pytest.approx(1.5)


def test_beyond_accuracy():
    recs = np.array([[0, 1], [0, 2]])
    assert M.catalog_coverage(recs, 4) == pytest.approx(3 / 4)
    genres = sparse.csr_matrix(np.array([[1, 0], [1, 0], [0, 1], [1, 1]], dtype=np.float32))
    # list 1: identical genres -> distance 0; list 2: disjoint -> 1
    assert M.intra_list_diversity(recs, genres) == pytest.approx(0.5)
    assert M.gini_index(np.array([[0, 0], [0, 0]]), 2) == pytest.approx(0.5)
    assert M.gini_index(np.array([[0, 1]]), 2) == pytest.approx(0.0)
    pop = np.array([99, 0, 0, 0])
    assert M.novelty(np.array([[1]]), pop, 99) > M.novelty(np.array([[0]]), pop, 99)


def test_bootstrap_ci_contains_mean():
    vals = np.random.default_rng(1).random(500)
    lo, hi = M.bootstrap_ci(vals, 300, seed=0)
    assert lo < vals.mean() < hi
