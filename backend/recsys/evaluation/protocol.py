"""Evaluation protocol shared by every model.

A ``EvalTask`` fixes *who* is evaluated, *what the model may see* (history) and *what
counts as a hit* (relevant held-out items). All models are scored on identical tasks.

Warm task  — users with history in the training splits and >= 1 relevant held-out item.
Cold tasks — users with *no* training history. Their first ``n`` held-out interactions
             (in time order) are revealed as history; the rest is the target. ``n = 0`` is
             the pure cold start that only popularity / onboarding can serve.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from recsys.data.dataset import ProcessedData, to_csr
from recsys.evaluation import metrics as M
from recsys.models.base import Recommender

log = logging.getLogger(__name__)


@dataclass
class EvalTask:
    name: str
    history: sparse.csr_matrix          # (n_eval, n_items) ratings the model may use
    user_idx: np.ndarray | None         # rows -> training user index (None = fold-in only)
    relevant: sparse.csr_matrix         # (n_eval, n_items) 1 where relevant
    history_len: np.ndarray             # interactions in history per row
    new_item_mask: np.ndarray           # (n_items,) True if item has no training interactions

    @property
    def n_users(self) -> int:
        return self.history.shape[0]


def _relevant_matrix(rows: pd.DataFrame, row_of_user: dict[int, int], n_rows: int, n_items: int,
                     threshold: float) -> sparse.csr_matrix:
    rel = rows[rows["rating"] >= threshold]
    r = rel["uidx"].map(row_of_user).to_numpy()
    return sparse.csr_matrix((np.ones(len(rel), dtype=np.float32), (r, rel["iidx"].to_numpy())),
                             shape=(n_rows, n_items))


def build_warm_task(data: ProcessedData, train_splits: tuple[str, ...], target_split: str,
                    threshold: float, split_col: str = "split", name: str | None = None) -> EvalTask:
    train = data.rows(train_splits, split_col)
    target = data.rows((target_split,), split_col)
    train_users = set(train["uidx"].unique())
    rel_users = set(target.loc[target["rating"] >= threshold, "uidx"].unique())
    users = np.array(sorted(train_users & rel_users), dtype=np.int64)
    row_of = {int(u): i for i, u in enumerate(users)}

    X_train = to_csr(train, data.n_users, data.n_items)
    history = X_train[users]
    relevant = _relevant_matrix(target[target["uidx"].isin(row_of)], row_of, len(users), data.n_items, threshold)
    new_items = np.asarray(X_train.getnnz(axis=0) == 0)
    task = EvalTask(name or f"warm_{target_split}", history, users, relevant,
                    np.diff(history.indptr), new_items)
    log.info("Task %s: %d users, %d relevant items", task.name, task.n_users, relevant.nnz)
    return task


def build_cold_tasks(data: ProcessedData, train_splits: tuple[str, ...], target_split: str, threshold: float,
                     reveal: list[int], split_col: str = "split") -> list[EvalTask]:
    train = data.rows(train_splits, split_col)
    target = data.rows((target_split,), split_col)
    cold = target[~target["uidx"].isin(set(train["uidx"].unique()))]
    cold = cold.sort_values(["uidx", "ts", "iidx"], kind="mergesort")
    cold = cold.assign(pos=cold.groupby("uidx").cumcount())
    new_items = np.asarray(to_csr(train, data.n_users, data.n_items).getnnz(axis=0) == 0)

    tasks = []
    for n in [0, *reveal]:
        hist_rows = cold[cold["pos"] < n]
        tgt_rows = cold[cold["pos"] >= n]
        users = np.array(sorted(set(tgt_rows.loc[tgt_rows["rating"] >= threshold, "uidx"])), dtype=np.int64)
        row_of = {int(u): i for i, u in enumerate(users)}
        hist_rows = hist_rows[hist_rows["uidx"].isin(row_of)]
        history = sparse.csr_matrix(
            (hist_rows["rating"].to_numpy(np.float32), (hist_rows["uidx"].map(row_of).to_numpy(),
                                                       hist_rows["iidx"].to_numpy())),
            shape=(len(users), data.n_items))
        relevant = _relevant_matrix(tgt_rows[tgt_rows["uidx"].isin(row_of)], row_of, len(users), data.n_items,
                                    threshold)
        task = EvalTask(f"cold_{target_split}_n{n}", history, None, relevant, np.diff(history.indptr), new_items)
        log.info("Task %s: %d users", task.name, task.n_users)
        tasks.append(task)
    return tasks


# --------------------------------------------------------------------- scoring
def compute_scores(model: Recommender, task: EvalTask, batch_size: int = 1024) -> np.ndarray:
    out = np.empty((task.n_users, task.history.shape[1]), dtype=np.float32)
    for start in range(0, task.n_users, batch_size):
        end = min(start + batch_size, task.n_users)
        uidx = task.user_idx[start:end] if task.user_idx is not None else None
        out[start:end] = model.score(task.history[start:end], uidx)
    return out


def mask_seen(scores: np.ndarray, history: sparse.csr_matrix) -> np.ndarray:
    s = scores.copy()
    rows, cols = history.nonzero()
    s[rows, cols] = -np.inf
    return s


def ranking_metrics(scores: np.ndarray, task: EvalTask, ks: list[int], item_popularity: np.ndarray,
                    n_train_users: int, genre_matrix: sparse.csr_matrix, bootstrap: int = 0, seed: int = 42,
                    light_max: int = 20, primary: str = "ndcg@10") -> dict[str, Any]:
    """Compute every ranking metric for already-computed scores (seen items are masked here)."""
    if task.n_users == 0:
        return {"n_users": 0, "metrics": {}, "beyond": {}, "segments": {}}
    kmax = max(ks)
    recs = M.top_k(mask_seen(scores, task.history), kmax)
    hits = M.hits_matrix(recs, task.relevant)
    n_rel = np.diff(task.relevant.indptr)

    per_user: dict[str, np.ndarray] = {}
    for k in ks:
        per_user[f"precision@{k}"] = M.precision_at_k(hits, k)
        per_user[f"recall@{k}"] = M.recall_at_k(hits, n_rel, k)
        per_user[f"ndcg@{k}"] = M.ndcg_at_k(hits, n_rel, k)
        per_user[f"map@{k}"] = M.average_precision_at_k(hits, n_rel, k)
        per_user[f"hit_rate@{k}"] = M.hit_rate_at_k(hits, k)
        per_user[f"mrr@{k}"] = M.mrr_at_k(hits, k)

    out: dict[str, Any] = {
        "n_users": task.n_users,
        "metrics": {name: float(v.mean()) for name, v in per_user.items()},
    }
    if bootstrap and primary in per_user:
        out["ci95"] = {primary: list(M.bootstrap_ci(per_user[primary], bootstrap, seed))}

    k0 = min(ks)
    top = recs[:, :k0]
    out["beyond"] = {
        f"coverage@{k0}": M.catalog_coverage(top, scores.shape[1]),
        f"ild@{k0}": M.intra_list_diversity(top, genre_matrix),
        f"novelty@{k0}": M.novelty(top, item_popularity, n_train_users),
        f"gini@{k0}": M.gini_index(top, scores.shape[1]),
    }

    # New items (no training interactions): micro recall@kmax over relevant new items.
    new_rel = task.relevant.multiply(task.new_item_mask[None, :].astype(np.float32)).tocsr()
    new_rel.eliminate_zeros()  # multiply() keeps explicit zeros, which nnz would count
    if new_rel.nnz:
        new_hits = M.hits_matrix(recs, new_rel).sum()
        out[f"new_item_recall@{kmax}"] = float(new_hits / new_rel.nnz)
        out["new_item_relevant"] = int(new_rel.nnz)

    if task.user_idx is not None:
        light = task.history_len < light_max
        segs = {}
        for seg_name, mask in (("light", light), ("heavy", ~light)):
            if mask.any():
                segs[seg_name] = {"n_users": int(mask.sum()),
                                  "ndcg@10": float(per_user.get("ndcg@10", per_user[f"ndcg@{k0}"])[mask].mean()),
                                  "recall@20": float(per_user.get("recall@20", per_user[f"recall@{kmax}"])[mask]
                                                     .mean())}
        out["segments"] = segs
    return out


def rating_metrics(model: Recommender, data: ProcessedData, train_splits: tuple[str, ...], target_split: str,
                   split_col: str = "split") -> dict[str, Any]:
    """RMSE / MAE on every held-out rating; ``warm`` restricts to known users and items."""
    train = data.rows(train_splits, split_col)
    target = data.rows((target_split,), split_col)
    pred = model.predict(target["uidx"].to_numpy(), target["iidx"].to_numpy())
    y = target["rating"].to_numpy(np.float64)
    warm = target["uidx"].isin(set(train["uidx"])).to_numpy() & target["iidx"].isin(set(train["iidx"])).to_numpy()
    return {
        "n_ratings": int(len(y)),
        "rmse": M.rmse(y, pred),
        "mae": M.mae(y, pred),
        "n_warm_ratings": int(warm.sum()),
        "rmse_warm": M.rmse(y[warm], pred[warm]) if warm.any() else None,
        "mae_warm": M.mae(y[warm], pred[warm]) if warm.any() else None,
    }


# ------------------------------------------------------------- task utilities
def subset_task(task: EvalTask, rows: np.ndarray, name: str | None = None) -> EvalTask:
    rows = np.asarray(rows)
    return EvalTask(
        name or task.name,
        task.history[rows],
        task.user_idx[rows] if task.user_idx is not None else None,
        task.relevant[rows],
        task.history_len[rows],
        task.new_item_mask,
    )


def concat_tasks(tasks: list[EvalTask], name: str) -> EvalTask:
    """Stack several tasks (fold-in only: user_idx is dropped)."""
    return EvalTask(
        name,
        sparse.vstack([t.history for t in tasks]).tocsr(),
        None,
        sparse.vstack([t.relevant for t in tasks]).tocsr(),
        np.concatenate([t.history_len for t in tasks]),
        tasks[0].new_item_mask,
    )


def primary_value(scores: np.ndarray, task: EvalTask, metric: str = "ndcg@10") -> float:
    """Fast path used inside hyper-parameter searches: one metric, no extras."""
    name, k = metric.split("@")
    k = int(k)
    recs = M.top_k(mask_seen(scores, task.history), k)
    hits = M.hits_matrix(recs, task.relevant)
    n_rel = np.diff(task.relevant.indptr)
    fn = {
        "ndcg": lambda: M.ndcg_at_k(hits, n_rel, k),
        "recall": lambda: M.recall_at_k(hits, n_rel, k),
        "precision": lambda: M.precision_at_k(hits, k),
        "map": lambda: M.average_precision_at_k(hits, n_rel, k),
        "hit_rate": lambda: M.hit_rate_at_k(hits, k),
    }[name]
    return float(fn().mean()) if task.n_users else float("nan")
