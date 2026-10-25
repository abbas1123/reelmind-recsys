"""Checks on the real MovieLens data and the artifacts produced by the pipeline."""

from __future__ import annotations

import json

import numpy as np
import pytest

from recsys.evaluation.protocol import build_warm_task, compute_scores, primary_value
from recsys.models.registry import create

pytestmark = pytest.mark.real_data


def test_processed_counts_match_movielens_1m(processed):
    assert processed.n_users == 6040
    assert processed.n_items == 3883
    assert len(processed.interactions) == 1_000_209
    assert processed.interactions["rating"].between(1, 5).all()
    assert not processed.interactions.duplicated(["user_id", "item_id"]).any()


def test_primary_split_is_temporal_and_disjoint(processed):
    df = processed.interactions
    tr, va, te = (df[df.split == s] for s in ("train", "val", "test"))
    assert tr.ts.max() < va.ts.min() and va.ts.max() < te.ts.min()
    assert abs(len(tr) / len(df) - 0.8) < 0.01
    assert processed.manifest["leakage_checks"]["primary"]["temporal_order_ok"]
    assert processed.manifest["leakage_checks"]["secondary"]["temporal_order_ok"]


def test_unrated_catalog_items_exist_for_cold_item_handling(processed):
    rated = set(processed.interactions["item_id"])
    unrated = set(processed.items["item_id"]) - rated
    assert len(unrated) == 177


def test_report_contains_real_metrics(settings):
    report = json.loads((settings.p.reports_dir / "model_comparison.json").read_text(encoding="utf-8"))
    assert not report["quick_mode"], "report was produced by a quick (smoke-test) run"
    metric = report["protocol"]["primary_metric"]
    assert report["selection"]["selected"] in report["models"]
    for name, entry in report["models"].items():
        if "skipped" in entry:
            continue
        for part in ("val", "test", "secondary_test"):
            value = entry[part]["metrics"][metric]
            assert 0.0 <= value <= 1.0, (name, part, value)
        assert entry["test"]["n_users"] == report["protocol"]["tasks"]["test_warm"]


def test_reported_test_metric_is_reproducible(processed, settings):
    """Refit two deterministic models with their reported best params and recompute the test metric."""
    report = json.loads((settings.p.reports_dir / "model_comparison.json").read_text(encoding="utf-8"))
    metric = report["protocol"]["primary_metric"]
    thr = report["protocol"]["relevance_threshold"]
    task = build_warm_task(processed, ("train", "val"), "test", thr)
    X = processed.matrix(("train", "val"))
    T = processed.matrix(("train", "val"), value="ts")
    for name in ("popularity", "ease"):
        params = report["models"][name]["best_params"]
        model = create(name, seed=report["seed"], **params).fit(X, None, T)
        value = primary_value(compute_scores(model, task), task, metric)
        assert value == pytest.approx(report["models"][name]["test"]["metrics"][metric], abs=1e-6), name


def test_engine_self_check(engine):
    result = engine.self_check(n_users=30)
    assert result["ok"], result["problems"]


def test_recommendations_for_real_users_are_valid(engine):
    rng = np.random.default_rng(0)
    for uid in rng.choice(engine.movielens_user_ids(), 25, replace=False):
        hist = engine.movielens_history(int(uid))
        recs = engine.recommend(hist, k=20, ml_user_id=int(uid))
        ids = [r.item_id for r in recs]
        assert len(ids) == 20 and len(set(ids)) == 20
        assert not set(ids) & {i for i, _ in hist}
        assert all(np.isfinite(r.score) for r in recs)


def test_fold_in_user_matches_taste(engine):
    """A brand-new user who loves classic sci-fi should get mostly sci-fi/action back (no retraining)."""
    hist = [(260, 5.0), (1196, 5.0), (1210, 5.0), (2571, 5.0), (1240, 5.0)]  # Star Wars IV-VI, Matrix, Terminator
    recs = engine.recommend(hist, k=10)
    genres = [set(engine.items.at[engine.item_index[r.item_id], "genres"]) for r in recs]
    assert sum(bool(g & {"Sci-Fi", "Action", "Adventure"}) for g in genres) >= 8
    assert any(r.reason.startswith("Because you liked") for r in recs)


def test_genre_filter_and_cold_items(engine, processed):
    recs = engine.recommend([(1, 5.0)], k=10, genre="Horror")
    assert all("Horror" in engine.items.at[engine.item_index[r.item_id], "genres"] for r in recs)
    unrated = sorted(set(processed.items["item_id"]) - set(processed.interactions["item_id"]))
    sims = engine.similar_items(unrated[0], k=5, mode="content")
    assert len(sims) == 5  # an item nobody rated still has content neighbours
    # ...but no collaborative ones: the list must be empty, not the first catalog ids padded in at score 0.
    assert engine.similar_items(unrated[0], k=5, mode="collaborative") == []
