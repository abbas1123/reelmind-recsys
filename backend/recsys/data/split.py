"""Train / validation / test splitting without leakage.

``global_temporal`` (primary): one time cut for all users. Nothing the model sees in
training happened after anything it is evaluated on, which mirrors deployment: train on
the past, recommend for the future. Users whose first interaction is after the cut become
genuine cold-start users.

``per_user_temporal`` (robustness check): each user's latest interactions are held out.
Every user is evaluable, but other users' later interactions leak into training, so the
numbers are optimistic. It is reported separately and never used for model selection.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

TRAIN, VAL, TEST = "train", "val", "test"


def global_temporal_split(df: pd.DataFrame, val_fraction: float, test_fraction: float) -> pd.Series:
    """Label rows by two timestamp cut points. Equal timestamps always land in the same split."""
    if df.empty:
        return pd.Series([], dtype=str, index=df.index)
    ts = np.sort(df["ts"].to_numpy())
    n = len(ts)
    val_cut = ts[min(n - 1, int(np.floor(n * (1 - val_fraction - test_fraction))))]
    test_cut = ts[min(n - 1, int(np.floor(n * (1 - test_fraction))))]
    labels = np.where(df["ts"].to_numpy() < val_cut, TRAIN, np.where(df["ts"].to_numpy() < test_cut, VAL, TEST))
    return pd.Series(labels, index=df.index, name="split")


def per_user_temporal_split(df: pd.DataFrame, val_fraction: float, test_fraction: float,
                            min_interactions: int = 3) -> pd.Series:
    """Hold out each user's most recent interactions (ties broken by item id)."""
    order = df.sort_values(["user_id", "ts", "item_id"], kind="mergesort")
    pos = order.groupby("user_id").cumcount().to_numpy()
    size = order.groupby("user_id")["item_id"].transform("size").to_numpy()
    n_test = np.maximum(1, np.round(size * test_fraction)).astype(int)
    n_val = np.maximum(1, np.round(size * val_fraction)).astype(int)
    labels = np.full(len(order), TRAIN, dtype=object)
    eligible = size >= min_interactions
    labels[eligible & (pos >= size - n_test)] = TEST
    labels[eligible & (pos >= size - n_test - n_val) & (pos < size - n_test)] = VAL
    return pd.Series(labels, index=order.index, name="split").reindex(df.index)


def split_interactions(df: pd.DataFrame, strategy: str, val_fraction: float, test_fraction: float) -> pd.Series:
    if strategy == "global_temporal":
        return global_temporal_split(df, val_fraction, test_fraction)
    if strategy == "per_user_temporal":
        return per_user_temporal_split(df, val_fraction, test_fraction)
    raise ValueError(f"Unknown split strategy: {strategy}")


def check_leakage(df: pd.DataFrame, split_col: str, strategy: str) -> dict[str, Any]:
    """Assert the split is leakage-free; returns the evidence for the report."""
    parts = {name: df[df[split_col] == name] for name in (TRAIN, VAL, TEST)}
    checks: dict[str, Any] = {name: len(p) for name, p in parts.items()}

    pairs = df.groupby(["user_id", "item_id"])[split_col].nunique()
    checks["user_item_pairs_in_multiple_splits"] = int((pairs > 1).sum())

    if strategy == "global_temporal":
        checks["train_ts_max"] = int(parts[TRAIN]["ts"].max())
        checks["val_ts_min"] = int(parts[VAL]["ts"].min())
        checks["val_ts_max"] = int(parts[VAL]["ts"].max())
        checks["test_ts_min"] = int(parts[TEST]["ts"].min())
        checks["temporal_order_ok"] = bool(
            checks["train_ts_max"] < checks["val_ts_min"] and checks["val_ts_max"] < checks["test_ts_min"]
        )
    else:
        rank = {TRAIN: 0, VAL: 1, TEST: 2}
        r = df[split_col].map(rank)
        # Within each user, sorting by time must never move from a later split back to an earlier one.
        ordered = df.assign(_r=r).sort_values(["user_id", "ts", "_r"], kind="mergesort")
        backwards = ordered.groupby("user_id")["_r"].diff().fillna(0) < 0
        checks["users_with_time_inversion"] = int(ordered.loc[backwards, "user_id"].nunique())
        checks["temporal_order_ok"] = checks["users_with_time_inversion"] == 0

    if checks["user_item_pairs_in_multiple_splits"] or not checks["temporal_order_ok"]:
        raise AssertionError(f"Leakage detected in {strategy} split: {checks}")
    return checks
