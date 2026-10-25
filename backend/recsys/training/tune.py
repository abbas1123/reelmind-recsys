"""Validation-driven hyper-parameter search."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from itertools import product
from typing import Any

import numpy as np
from scipy import sparse

from recsys.evaluation.protocol import EvalTask, compute_scores, primary_value
from recsys.models.base import ItemSide, Recommender
from recsys.models.hybrid import COMPONENTS, combine, minmax_rows, weight_grid
from recsys.models.registry import create

log = logging.getLogger(__name__)


def expand_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    if not grid:
        return [{}]
    keys = list(grid)
    return [dict(zip(keys, values, strict=True)) for values in product(*(grid[k] for k in keys))]


def grid_search(name: str, grid: dict[str, list[Any]], X_train: sparse.csr_matrix, items: ItemSide,
                val_task: EvalTask, metric: str, seed: int, batch_size: int, quick: bool = False,
                ts_train: sparse.csr_matrix | None = None,
                objective: tuple[str, Callable[[Recommender], float]] | None = None,
                ) -> tuple[Recommender, dict[str, Any], list[dict[str, Any]]]:
    """Fit every configuration on train, score on validation; return the best fitted model.

    By default configurations are ranked by the ranking ``metric``. ``objective`` = (name, fn)
    overrides that with a model-specific validation loss to *minimise* (e.g. RMSE for
    explicit-rating models); the ranking metric is still recorded for comparison.
    """
    configs = expand_grid(grid)
    if quick:
        configs = configs[:1]
    results: list[dict[str, Any]] = []
    best: tuple[float, Recommender | None, dict[str, Any]] = (-np.inf, None, {})
    for params in configs:
        start = time.perf_counter()
        model = create(name, seed=seed, **params).fit(X_train, items, ts_train)
        fit_s = time.perf_counter() - start
        ranking = primary_value(compute_scores(model, val_task, batch_size), val_task, metric)
        row: dict[str, Any] = {"params": params, metric: ranking, "fit_seconds": round(fit_s, 2)}
        value = ranking
        if objective is not None:
            loss = objective[1](model)
            row[objective[0]] = loss
            value = -loss
        results.append(row)
        log.info("  %-17s %-50s %s=%.4f%s  (fit %.1fs)", name, str(params)[:50], metric, ranking,
                 f" {objective[0]}={row[objective[0]]:.4f}" if objective else "", fit_s)
        if value > best[0]:
            best = (value, model, params)
    assert best[1] is not None
    return best[1], best[2], results


def tune_hybrid_weights(component_scores: dict[str, np.ndarray], task: EvalTask, metric: str,
                        step: float) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """Exhaustive search over the weight simplex using cached component scores."""
    normed = {c: minmax_rows(component_scores[c]) for c in COMPONENTS}
    results = []
    for w in weight_grid(step):
        value = primary_value(combine(normed, w), task, metric)
        results.append({"weights": w, metric: value})
    results.sort(key=lambda r: -r[metric])
    return results[0]["weights"], results
