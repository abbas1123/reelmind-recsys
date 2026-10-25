"""End-to-end training pipeline.

1. Grid-search every model on the validation split (models fitted on ``train`` only).
2. Evaluate the best configuration on validation (warm + simulated cold users).
3. Refit on ``train + val`` and evaluate **once** on the test split.
4. Repeat the test evaluation under the per-user temporal split (robustness only).
5. Build the hybrid from the best CF and best content model; tune its weights on validation.
6. Select the final model by the validation primary metric.
7. Fit the serving models on all interactions and save them with metadata.
"""

from __future__ import annotations

import json
import logging
import platform
import time
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from typing import Any

import numpy as np
from scipy import sparse

from recsys.config import Settings
from recsys.data.dataset import ProcessedData
from recsys.evaluation.protocol import (
    EvalTask,
    build_cold_tasks,
    build_warm_task,
    compute_scores,
    concat_tasks,
    ranking_metrics,
    rating_metrics,
    subset_task,
)
from recsys.evaluation.report import write_reports
from recsys.logging_utils import timed
from recsys.models import embeddings as E
from recsys.models.base import ItemSide, Recommender
from recsys.models.hybrid import COMPONENTS, Hybrid
from recsys.models.registry import CF_CANDIDATES, CONTENT_CANDIDATES, FAMILY, MODELS, create
from recsys.training.tune import grid_search, tune_hybrid_weights

log = logging.getLogger(__name__)

MODEL_ORDER = ("popularity", "bias_baseline", "user_knn", "item_knn", "pure_svd", "ials", "ease", "biased_mf",
               "content_tfidf", "content_embedding")


def build_item_side(data: ProcessedData, settings: Settings, use_embeddings: bool = True) -> ItemSide:
    emb = None
    if use_embeddings:
        if E.is_available(settings):
            emb = E.item_embeddings(data.items["text"].tolist(), settings)
        else:
            log.warning("Embedding model not cached; content_embedding and semantic search are disabled. "
                        "Run `uv run recsys download-models` to enable them.")
    return ItemSide(texts=data.items["text"].tolist(), genre_matrix=data.genre_matrix, embeddings=emb)


def library_versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for pkg in ("numpy", "scipy", "pandas", "scikit-learn", "sentence-transformers", "torch"):
        try:
            out[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            out[pkg] = "not installed"
    return out


class _Evaluator:
    """Bundles tasks, popularity statistics and settings so every model is scored identically."""

    def __init__(self, data: ProcessedData, settings: Settings, matrices: dict[str, sparse.csr_matrix]):
        self.data, self.settings = data, settings
        self.ev = settings.evaluation
        self.metric = self.ev.primary_metric
        self.pop = {k: np.asarray(m.getnnz(axis=0), dtype=np.float64) for k, m in matrices.items()}
        self.n_users = {k: int((m.getnnz(axis=1) > 0).sum()) for k, m in matrices.items()}

    def full(self, scores: np.ndarray, task: EvalTask, pop_key: str, bootstrap: bool = True) -> dict[str, Any]:
        return ranking_metrics(scores, task, self.ev.k_values, self.pop[pop_key], self.n_users[pop_key],
                               self.data.genre_matrix, bootstrap=self.ev.bootstrap_samples if bootstrap else 0,
                               seed=self.settings.seed, light_max=self.ev.light_user_max_train,
                               primary=self.metric)

    def model(self, model: Recommender, task: EvalTask, pop_key: str, bootstrap: bool = True) -> dict[str, Any]:
        return self.full(compute_scores(model, task, self.ev.eval_batch_size), task, pop_key, bootstrap)


def run_training(settings: Settings, quick: bool = False, only: list[str] | None = None) -> dict[str, Any]:
    if only is not None and not (set(only) & set(CF_CANDIDATES) and set(only) & set(CONTENT_CANDIDATES)):
        # Fail before any fitting: the hybrid step needs one CF and one content model.
        raise ValueError(f"--only must include at least one CF model {CF_CANDIDATES} and one content model "
                         f"{CONTENT_CANDIDATES}; the hybrid is built from both.")
    t_start = time.perf_counter()
    p, ev, seed = settings.p, settings.evaluation, settings.seed
    metric = ev.primary_metric
    data = ProcessedData.load(p.processed_dir)
    items = build_item_side(data, settings)

    X = {
        "train": data.matrix(("train",)),
        "train_val": data.matrix(("train", "val")),
        "all": data.matrix(("train", "val", "test")),
        "sec_train_val": data.matrix(("train", "val"), split_col="split_user"),
    }
    T = {  # timestamps with the same sparsity (time-aware models)
        "train": data.matrix(("train",), value="ts"),
        "train_val": data.matrix(("train", "val"), value="ts"),
        "all": data.matrix(("train", "val", "test"), value="ts"),
        "sec_train_val": data.matrix(("train", "val"), split_col="split_user", value="ts"),
    }
    thr = ev.relevance_threshold
    tasks = {
        "val": build_warm_task(data, ("train",), "val", thr, name="val_warm"),
        "test": build_warm_task(data, ("train", "val"), "test", thr, name="test_warm"),
        "sec_test": build_warm_task(data, ("train", "val"), "test", thr, split_col="split_user",
                                    name="secondary_test_warm"),
    }
    cold_val = build_cold_tasks(data, ("train",), "val", thr, ev.cold_start_reveal)
    cold_test = build_cold_tasks(data, ("train", "val"), "test", thr, ev.cold_start_reveal)
    evaluator = _Evaluator(data, settings, X)
    bs = ev.eval_batch_size

    names = [n for n in MODEL_ORDER if (only is None or n in only or n == "popularity")]
    report_models: dict[str, Any] = {}
    val_cache: dict[str, dict[str, Any]] = {}
    best_params: dict[str, dict[str, Any]] = {}

    for name in names:
        if name == "content_embedding" and items.embeddings is None:
            report_models[name] = {"family": FAMILY[name], "skipped": "embedding model not cached"}
            continue
        grid = settings.models.get(name, {})
        # Explicit-rating models are tuned on their own objective (validation RMSE).
        objective = None
        if MODELS[name].predicts_ratings:
            objective = ("val_rmse", lambda m: rating_metrics(m, data, ("train",), "val")["rmse"])
        with timed(log, f"[{name}] grid search ({len(grid) and np.prod([len(v) for v in grid.values()])} configs)"):
            model, params, grid_results = grid_search(name, grid, X["train"], items, tasks["val"], metric, seed,
                                                      bs, quick=quick, ts_train=T["train"], objective=objective)
        best_params[name] = params
        entry: dict[str, Any] = {"family": FAMILY[name], "best_params": params, "grid": grid_results,
                                 "tuned_on": objective[0] if objective else f"val {metric}"}

        val_scores = compute_scores(model, tasks["val"], bs)
        cold_scores = [compute_scores(model, t, bs) for t in cold_val]
        entry["val"] = evaluator.full(val_scores, tasks["val"], "train")
        entry["val_cold"] = {t.name: evaluator.full(s, t, "train", bootstrap=False)
                             for t, s in zip(cold_val, cold_scores, strict=True)}
        if model.predicts_ratings:
            entry["rating"] = {"val": rating_metrics(model, data, ("train",), "val")}
        if name in (*CF_CANDIDATES, *CONTENT_CANDIDATES, "popularity"):
            val_cache[name] = {"val": val_scores, "cold": cold_scores}

        with timed(log, f"[{name}] refit on train+val and evaluate on test") as tinfo:
            model_tv = create(name, seed=seed, **params).fit(X["train_val"], items, T["train_val"])
            entry["test"] = evaluator.model(model_tv, tasks["test"], "train_val")
            entry["test_cold"] = {t.name: evaluator.model(model_tv, t, "train_val", bootstrap=False)
                                  for t in cold_test}
            if model_tv.predicts_ratings:
                entry["rating"]["test"] = rating_metrics(model_tv, data, ("train", "val"), "test")
        entry["fit_seconds_train_val"] = round(tinfo["seconds"], 1)

        model_sec = create(name, seed=seed, **params).fit(X["sec_train_val"], items, T["sec_train_val"])
        entry["secondary_test"] = evaluator.model(model_sec, tasks["sec_test"], "sec_train_val", bootstrap=False)
        report_models[name] = entry
        log.info("[%s] val %s=%.4f | test %s=%.4f", name, metric, entry["val"]["metrics"][metric], metric,
                 entry["test"]["metrics"][metric])

    # ------------------------------------------------------------------ hybrid
    cf_name = max((n for n in CF_CANDIDATES if n in val_cache),
                  key=lambda n: report_models[n]["val"]["metrics"][metric])
    cb_name = max((n for n in CONTENT_CANDIDATES if n in val_cache),
                  key=lambda n: report_models[n]["val"]["metrics"][metric])
    log.info("Hybrid components: cf=%s, cb=%s", cf_name, cb_name)
    hybrid_entry, weights = _tune_hybrid(settings, evaluator, tasks, cold_val, val_cache, cf_name, cb_name)

    def make_hybrid(w: dict[str, dict[str, float]]) -> Hybrid:
        return Hybrid(create(cf_name, seed=seed, **best_params[cf_name]),
                      create(cb_name, seed=seed, **best_params[cb_name]),
                      create("popularity", seed=seed, **best_params["popularity"]), weights=w,
                      warm_min_history=settings.hybrid.warm_min_history)

    with timed(log, "[hybrid] refit on train+val and evaluate on test") as tinfo:
        hyb_tv = make_hybrid(weights).fit(X["train_val"], items, T["train_val"])
        hybrid_entry["test"] = evaluator.model(hyb_tv, tasks["test"], "train_val")
        hybrid_entry["test_cold"] = {t.name: evaluator.model(hyb_tv, t, "train_val", bootstrap=False)
                                     for t in cold_test}
    hybrid_entry["fit_seconds_train_val"] = round(tinfo["seconds"], 1)
    hyb_sec = make_hybrid(weights).fit(X["sec_train_val"], items, T["sec_train_val"])
    hybrid_entry["secondary_test"] = evaluator.model(hyb_sec, tasks["sec_test"], "sec_train_val", bootstrap=False)
    report_models["hybrid"] = hybrid_entry

    # --------------------------------------------------------------- selection
    ranked = sorted(
        ((n, e["val"]["metrics"][metric], e["val"]["beyond"].get(f"coverage@{min(ev.k_values)}", 0))
         for n, e in report_models.items() if "val" in e),
        key=lambda r: (-r[1], -r[2]),
    )
    selected = ranked[0][0]
    log.info("Selected model by validation %s: %s (%.4f)", metric, selected, ranked[0][1])

    # ----------------------------------------------------------------- serving
    serving_weights = json.loads(json.dumps(weights))
    serving_cf = cf_name
    if selected != "hybrid":
        # The winner serves warm users; light/cold users keep the validated fallback weights.
        if selected in CONTENT_CANDIDATES:
            serving_weights["warm"] = {"cf": 0.0, "cb": 1.0, "pop": 0.0}
        else:
            serving_cf = selected
            serving_weights["warm"] = {"cf": 1.0, "cb": 0.0, "pop": 0.0}
    serving = _fit_serving(settings, data, items, X["all"], T["all"], serving_cf, cb_name, best_params,
                           serving_weights, selected)

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "quick_mode": quick,
        "dataset": {k: data.manifest.get(k) for k in ("dataset", "n_users", "n_items", "n_interactions",
                                                       "split_strategy", "split_sizes", "config_fingerprint",
                                                       "raw_md5")},
        "protocol": {
            "primary_metric": metric,
            "relevance_threshold": thr,
            "k_values": ev.k_values,
            "bootstrap_samples": ev.bootstrap_samples,
            "tasks": {t.name: t.n_users for t in [*tasks.values(), *cold_val, *cold_test]},
            "light_user_max_train": ev.light_user_max_train,
            "cold_start_reveal": ev.cold_start_reveal,
        },
        "models": report_models,
        "selection": {
            "selected": selected,
            "rule": f"highest validation {metric} on warm users (tie-break: catalog coverage)",
            "ranking": [{"model": n, metric: v, "coverage": c} for n, v, c in ranked],
        },
        "serving": serving,
        "library_versions": library_versions(),
        "seed": seed,
        "total_seconds": round(time.perf_counter() - t_start, 1),
    }
    write_reports(report, p.reports_dir)
    log.info("Training pipeline finished in %.1f min", report["total_seconds"] / 60)
    return report


def _tune_hybrid(settings: Settings, evaluator: _Evaluator, tasks: dict[str, EvalTask], cold_val: list[EvalTask],
                 cache: dict[str, dict[str, Any]], cf_name: str, cb_name: str
                 ) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    metric, step = settings.evaluation.primary_metric, settings.hybrid.weight_step
    warm_min = settings.hybrid.warm_min_history
    src = {"cf": cf_name, "cb": cb_name, "pop": "popularity"}

    val_task = tasks["val"]
    comp_val = {c: cache[src[c]]["val"] for c in COMPONENTS}
    warm_rows = np.flatnonzero(val_task.history_len >= warm_min)
    w_warm, search_warm = tune_hybrid_weights({c: s[warm_rows] for c, s in comp_val.items()},
                                              subset_task(val_task, warm_rows), metric, step)

    # Light users (1..warm_min-1 interactions): simulated cold users + short warm histories.
    parts_task, parts_scores = [], {c: [] for c in COMPONENTS}
    sources = [(t, {c: cache[src[c]]["cold"][i] for c in COMPONENTS}) for i, t in enumerate(cold_val)]
    sources.append((val_task, comp_val))
    for task, comp in sources:
        rows = np.flatnonzero((task.history_len >= 1) & (task.history_len < warm_min))
        if len(rows):
            parts_task.append(subset_task(task, rows))
            for c in COMPONENTS:
                parts_scores[c].append(comp[c][rows])
    light_task = concat_tasks(parts_task, "val_light_pooled")
    w_light, search_light = tune_hybrid_weights({c: np.vstack(v) for c, v in parts_scores.items()}, light_task,
                                                metric, step)
    weights = {"cold": {"cf": 0.0, "cb": 0.0, "pop": 1.0}, "light": w_light, "warm": w_warm}
    log.info("Hybrid weights: %s", weights)

    scorer = Hybrid(None, None, None, weights=weights, warm_min_history=warm_min)  # type: ignore[arg-type]
    entry: dict[str, Any] = {
        "family": FAMILY["hybrid"],
        "best_params": {"cf": cf_name, "cb": cb_name, "weights": weights, "warm_min_history": warm_min},
        "weight_search": {
            "warm": {"n_users": len(warm_rows), "top": search_warm[:10]},
            "light": {"n_users": light_task.n_users, "top": search_light[:10]},
            "cold": "fixed: popularity only (CF and content scores are constant for an empty history)",
        },
        "val": evaluator.full(scorer.combine_scores(comp_val, val_task.history_len), val_task, "train"),
        "val_cold": {},
        "note": "Weights and components are chosen on validation, so the validation number is optimistic; "
                "the test split is the unbiased check.",
    }
    for i, t in enumerate(cold_val):
        comp = {c: cache[src[c]]["cold"][i] for c in COMPONENTS}
        entry["val_cold"][t.name] = evaluator.full(scorer.combine_scores(comp, t.history_len), t, "train",
                                                   bootstrap=False)
    return entry, weights


def _fit_serving(settings: Settings, data: ProcessedData, items: ItemSide, X_all: sparse.csr_matrix,
                 T_all: sparse.csr_matrix, cf_name: str, cb_name: str, best_params: dict[str, dict[str, Any]],
                 weights: dict[str, dict[str, float]], selected: str) -> dict[str, Any]:
    out_dir = settings.p.models_dir / "serving"
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = settings.seed
    with timed(log, "Fitting serving models on all interactions"):
        hybrid = Hybrid(create(cf_name, seed=seed, **best_params[cf_name]),
                        create(cb_name, seed=seed, **best_params[cb_name]),
                        create("popularity", seed=seed, **best_params["popularity"]), weights=weights,
                        warm_min_history=settings.hybrid.warm_min_history).fit(X_all, items, T_all)
        hybrid.save(out_dir / "hybrid.joblib")
        # Item-item collaborative similarity for "similar movies" and explanations.
        item_item_name = cf_name if cf_name in ("ease", "item_knn") else "item_knn"
        if item_item_name == cf_name:
            item_item = hybrid.components["cf"]
        else:
            item_item = create("item_knn", seed=seed, **best_params.get("item_knn", {"k": 100, "shrink": 10}))
            item_item.fit(X_all, items)
        item_item.save(out_dir / "item_item.joblib")
        content_sim = hybrid.components["cb"]
        if cb_name != "content_tfidf":
            # TF-IDF vectoriser is used for keyword relevance in search even when embeddings win.
            tfidf = create("content_tfidf", seed=seed, **best_params.get("content_tfidf", {"k": 200}))
            tfidf.fit(X_all, items).save(out_dir / "content_tfidf.joblib")
        else:
            content_sim.save(out_dir / "content_tfidf.joblib")

    emb_file = None
    if items.embeddings is not None:
        emb_file = out_dir / "item_embeddings.npy"
        np.save(emb_file, items.embeddings)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "selected_model": selected,
        "trained_on": "all interactions (train + val + test)",
        "n_interactions": int(X_all.nnz),
        "hybrid": hybrid.describe(),
        "cf_model": cf_name,
        "content_model": cb_name,
        "item_item_model": item_item_name,
        "embedding_model": settings.embeddings.model_name if emb_file else None,
        "embeddings_file": emb_file.name if emb_file else None,
        "data_fingerprint": data.manifest.get("config_fingerprint"),
        "raw_md5": data.manifest.get("raw_md5"),
        "library_versions": library_versions(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    log.info("Serving artifacts written to %s", out_dir)
    return manifest
