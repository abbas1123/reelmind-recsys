"""Record-level validation. Every dropped row is counted under the rule that removed it."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from recsys.config import ValidationConfig

log = logging.getLogger(__name__)


def _drop(df: pd.DataFrame, mask: pd.Series, rule: str, report: dict[str, Any]) -> pd.DataFrame:
    n = int(mask.sum())
    report["rules"][rule] = n
    if n:
        log.warning("validation: dropping %d rows (%s)", n, rule)
    return df.loc[~mask]


def validate_items(items: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    report: dict[str, Any] = {"input_rows": len(items), "rules": {}, "flags": {}}
    items = _drop(items, items["item_id"].isna(), "missing_item_id", report)
    items = _drop(items, items["item_id"].duplicated(keep="first"), "duplicate_item_id", report)
    items = _drop(items, items["title"].fillna("").str.strip().eq(""), "empty_title", report)
    # Kept but flagged: still usable through ratings and genres.
    report["flags"]["missing_year"] = int(items["year"].isna().sum())
    report["flags"]["no_genres"] = int(items["genres"].map(len).eq(0).sum())
    report["flags"]["no_tags"] = int(items["tags"].map(len).eq(0).sum())
    report["output_rows"] = len(items)
    return items.reset_index(drop=True), report


def validate_interactions(
    interactions: pd.DataFrame,
    item_ids: pd.Series,
    user_ids: pd.Series | None,
    cfg: ValidationConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Drop invalid ratings. Duplicated (user, item) pairs keep the most recent rating."""
    report: dict[str, Any] = {"input_rows": len(interactions), "rules": {}}
    df = interactions

    df = _drop(df, df[["user_id", "item_id", "rating", "ts"]].isna().any(axis=1), "missing_values", report)
    rating = df["rating"].astype("float64")
    df = _drop(df, ~np.isclose(rating, rating.round()), "non_integer_rating", report)
    rating = df["rating"].astype("float64")
    df = _drop(df, (rating < cfg.rating_min) | (rating > cfg.rating_max), "rating_out_of_range", report)

    ts_min = int(pd.Timestamp(cfg.ts_min, tz="UTC").timestamp())
    ts_max = int(pd.Timestamp(cfg.ts_max, tz="UTC").timestamp())
    df = _drop(df, (df["ts"] < ts_min) | (df["ts"] >= ts_max), "timestamp_out_of_range", report)
    df = _drop(df, ~df["item_id"].isin(item_ids), "unknown_item", report)
    if user_ids is not None:
        df = _drop(df, ~df["user_id"].isin(user_ids), "unknown_user", report)

    df = df.sort_values(["user_id", "item_id", "ts"], kind="mergesort")
    df = _drop(df, df.duplicated(["user_id", "item_id"], keep="last"), "duplicate_user_item", report)

    df = df.astype({"user_id": np.int64, "item_id": np.int64, "rating": np.float32, "ts": np.int64})
    df = df.sort_values(["ts", "user_id", "item_id"], kind="mergesort").reset_index(drop=True)
    report["output_rows"] = len(df)
    report["dropped_total"] = report["input_rows"] - report["output_rows"]
    return df, report
