"""Every model must recover the obvious pattern in a two-cluster toy matrix and survive save/load."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse

from recsys.data.dataset import history_vector
from recsys.evaluation.metrics import top_k
from recsys.evaluation.protocol import mask_seen
from recsys.models.base import ItemSide, Recommender
from recsys.models.hybrid import Hybrid, minmax_rows, weight_grid
from recsys.models.registry import MODELS, create

TOY_PARAMS = {
    "user_knn": {"k": 2},
    "item_knn": {"k": 3, "shrink": 0},
    "pure_svd": {"factors": 2},
    "ials": {"factors": 2, "reg": 0.1, "alpha": 10, "iterations": 10},
    "ease": {"lambda_": 1.0},
    "content_tfidf": {"k": 0, "weighting": "binary"},
    "content_embedding": {"k": 0, "weighting": "binary"},
}
# Explicit MF predicts *ratings*, not what a user will pick next, so it is checked separately
# (test_biased_mf_fits_ratings_better_than_biases) instead of with the top-1 ranking tests.
PERSONALISED = list(TOY_PARAMS)


@pytest.fixture
def toy_items() -> ItemSide:
    texts = ["space robots laser battle", "space robots galaxy war", "space galaxy laser alien",
             "romance love paris wedding", "romance love wedding letters", "love paris letters romance"]
    genres = sparse.csr_matrix(np.array([[1, 0]] * 3 + [[0, 1]] * 3, dtype=np.float32))
    emb = np.array([[1, 0, 0.1]] * 3 + [[0, 1, 0.1]] * 3, dtype=np.float32)
    emb += np.random.default_rng(0).normal(0, 0.01, emb.shape).astype(np.float32)
    return ItemSide(texts=texts, genre_matrix=genres, embeddings=emb)


@pytest.mark.parametrize("name", PERSONALISED)
def test_model_recommends_within_cluster(name, toy_matrix, toy_items):
    model = create(name, seed=0, **TOY_PARAMS[name]).fit(toy_matrix, toy_items)
    users = np.array([0, 3])
    scores = model.score(toy_matrix[users], users)
    best = top_k(mask_seen(scores, toy_matrix[users]), 1)[:, 0]
    assert best.tolist() == [2, 5], f"{name} picked {best}"


@pytest.mark.parametrize("name", PERSONALISED)
def test_fold_in_for_unknown_user(name, toy_matrix, toy_items):
    model = create(name, seed=0, **TOY_PARAMS[name]).fit(toy_matrix, toy_items)
    hist = history_vector({3: 5.0, 4: 5.0}, 6)  # brand-new user who likes the romance cluster
    scores = mask_seen(model.score(hist, None), hist)
    assert int(np.argmax(scores[0])) == 5


@pytest.mark.parametrize("name", sorted(MODELS))
def test_save_load_roundtrip(name, toy_matrix, toy_items, tmp_path):
    model = create(name, seed=0, **TOY_PARAMS.get(name, {})).fit(toy_matrix, toy_items)
    path = tmp_path / f"{name}.joblib"
    model.save(path)
    loaded = Recommender.load(path)
    users = np.arange(6)
    np.testing.assert_allclose(model.score(toy_matrix, users), loaded.score(toy_matrix, users), rtol=1e-6)


def test_training_is_deterministic(toy_matrix):
    a = create("ials", seed=7, factors=2, iterations=5).fit(toy_matrix)
    b = create("ials", seed=7, factors=2, iterations=5).fit(toy_matrix)
    np.testing.assert_array_equal(a.U, b.U)


def test_explicit_models_predict_valid_ratings(toy_matrix):
    for name in ("bias_baseline", "biased_mf"):
        model = create(name, seed=0).fit(toy_matrix)
        pred = model.predict(np.array([0, 1, 4]), np.array([0, 2, 4]))
        assert np.all((pred >= 1) & (pred <= 5))
        # observed high ratings should be predicted above the global mean
        assert pred[0] > model.mu - 0.5


def test_biased_mf_fits_ratings_better_than_biases(toy_matrix):
    coo = toy_matrix.tocoo()
    y = coo.data
    base = create("bias_baseline", reg_item=1, reg_user=1).fit(toy_matrix)
    mf = create("biased_mf", seed=0, factors=2, reg=0.01, iterations=20).fit(toy_matrix)
    err_base = np.sqrt(np.mean((base.predict(coo.row, coo.col) - y) ** 2))
    err_mf = np.sqrt(np.mean((mf.predict(coo.row, coo.col) - y) ** 2))
    assert err_mf < err_base


def test_content_model_scores_unrated_items(toy_items):
    X = sparse.csr_matrix(np.array([[5, 0, 0, 0, 0, 0]], dtype=np.float32))  # items 1..5 never rated
    model = create("content_tfidf", k=0, weighting="binary").fit(X, toy_items)
    scores = model.score(X)
    assert scores[0, 1] > 0 and scores[0, 2] > 0  # cold items in the same cluster get signal
    assert scores[0, 1] > scores[0, 4]


def test_centered_weighting_pushes_down_disliked(toy_items):
    X = sparse.csr_matrix(np.array([[1, 0, 0, 5, 0, 0]], dtype=np.float32))
    model = create("content_tfidf", k=0, weighting="centered").fit(X, toy_items)
    s = model.score(X)[0]
    assert s[4] > 0 > s[1]


def test_hybrid_switches_weights_by_history(toy_matrix, toy_items):
    cf = create("ease", lambda_=1.0)
    cb = create("content_tfidf", k=0)
    pop = create("popularity")
    weights = {"cold": {"cf": 0, "cb": 0, "pop": 1}, "light": {"cf": 0, "cb": 1, "pop": 0},
               "warm": {"cf": 1, "cb": 0, "pop": 0}}
    hyb = Hybrid(cf, cb, pop, weights=weights, warm_min_history=3).fit(toy_matrix, toy_items)
    np.testing.assert_array_equal(hyb.bucket(np.array([0, 1, 2, 3])), ["cold", "light", "light", "warm"])
    empty = history_vector({}, 6)
    np.testing.assert_allclose(hyb.score(empty)[0], minmax_rows(pop.score(empty))[0])
    warm = toy_matrix[[1]]
    np.testing.assert_allclose(hyb.score(warm, np.array([1]))[0], minmax_rows(cf.score(warm))[0], rtol=1e-6)


def test_weight_grid_is_simplex():
    grid = weight_grid(0.25)
    assert len(grid) == 15
    assert all(abs(sum(w.values()) - 1) < 1e-9 for w in grid)


def test_trending_popularity_prefers_recent_items():
    X = sparse.csr_matrix(np.array([[5, 5], [5, 0], [0, 5]], dtype=np.float32))
    # item 0: rated twice long ago; item 1: rated twice, once by the most recent interaction
    ts = sparse.csr_matrix(np.array([[1, 400], [2, 0], [0, 300]], dtype=np.float64))
    all_time = create("popularity").fit(X, ts=ts).score(X[:1])[0]
    trending = create("popularity", half_life_events=1).fit(X, ts=ts).score(X[:1])[0]
    assert all_time[0] == all_time[1]
    assert trending[1] > trending[0]
    with pytest.raises(ValueError):
        create("popularity", half_life_events=1).fit(X)


def test_trending_decay_ignores_calendar_gaps():
    """Only the order of interactions matters, not how far apart in time they are."""
    X = sparse.csr_matrix(np.array([[5, 5], [5, 5]], dtype=np.float32))
    dense = sparse.csr_matrix(np.array([[1, 2], [3, 4]], dtype=np.float64))
    sparse_tail = sparse.csr_matrix(np.array([[1, 2], [3, 4e6]], dtype=np.float64))
    a = create("popularity", half_life_events=2).fit(X, ts=dense).scores_
    b = create("popularity", half_life_events=2).fit(X, ts=sparse_tail).scores_
    np.testing.assert_allclose(a, b)


@pytest.mark.parametrize("only", [["ease"], ["content_tfidf"], ["popularity"]])
def test_train_only_without_cf_and_content_fails_before_fitting(monkeypatch, only):
    """`recsys train --only ease` used to train for minutes and then crash in the hybrid step (max() of nothing)."""
    from recsys.config import Settings
    from recsys.training import train

    def no_data(*_a, **_k):
        raise AssertionError("must fail before loading data")

    monkeypatch.setattr(train.ProcessedData, "load", no_data)
    with pytest.raises(ValueError, match="--only must include"):
        train.run_training(Settings(), only=only)
