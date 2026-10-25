"""Reproducible preprocessing: raw files -> validated, indexed, split, saved dataset."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from recsys.config import Settings
from recsys.data.adapters import get_adapter
from recsys.data.dataset import ProcessedData, to_csr
from recsys.data.eda import run_eda
from recsys.data.split import check_leakage, per_user_temporal_split, split_interactions
from recsys.data.validate import validate_interactions, validate_items

log = logging.getLogger(__name__)


def _file_md5(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.md5()
    with path.open("rb") as fh:
        while block := fh.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def run_preprocess(settings: Settings) -> dict[str, Any]:
    p = settings.p
    p.processed_dir.mkdir(parents=True, exist_ok=True)
    p.reports_dir.mkdir(parents=True, exist_ok=True)

    adapter = get_adapter(
        settings.dataset.name,
        enrich=settings.dataset.enrich_with_ml32m,
        min_tag_users=settings.dataset.min_tag_users,
        max_tags_per_item=settings.dataset.max_tags_per_item,
    )
    log.info("Loading raw dataset with adapter '%s'", adapter.name)
    raw = adapter.load(p.raw_dir)

    items, item_report = validate_items(raw.items)
    user_ids = raw.users["user_id"] if raw.users is not None else None
    interactions, inter_report = validate_interactions(raw.interactions, items["item_id"], user_ids,
                                                       settings.validation)

    # Indices: every catalog item gets an index (unrated items included -> content-based cold start).
    items = items.sort_values("item_id").reset_index(drop=True)
    items["item_id"] = items["item_id"].astype(np.int64)
    items["year"] = items["year"].astype("Int64")
    items["iidx"] = np.arange(len(items), dtype=np.int64)
    user_index = np.sort(interactions["user_id"].unique())
    users = pd.DataFrame({"user_id": user_index, "uidx": np.arange(len(user_index), dtype=np.int64)})
    if raw.users is not None:
        users = users.merge(raw.users.astype({"user_id": np.int64}), on="user_id", how="left")
    interactions = interactions.merge(items[["item_id", "iidx"]], on="item_id").merge(
        users[["user_id", "uidx"]], on="user_id")
    interactions = interactions.sort_values(["ts", "user_id", "item_id"], kind="mergesort").reset_index(drop=True)

    # Splits: primary (config) + per-user temporal robustness split.
    sc = settings.split
    interactions["split"] = split_interactions(interactions, sc.strategy, sc.val_fraction, sc.test_fraction)
    interactions["split_user"] = per_user_temporal_split(interactions, sc.val_fraction, sc.test_fraction)
    leakage = {
        "primary": check_leakage(interactions, "split", sc.strategy),
        "secondary": check_leakage(interactions, "split_user", "per_user_temporal"),
    }
    log.info("Primary split sizes: %s", interactions["split"].value_counts().to_dict())

    # Save tables. external_ids is a dict column -> JSON string for parquet portability.
    items_out = items.assign(external_ids=items["external_ids"].map(json.dumps))
    items_out.to_parquet(p.processed_dir / "items.parquet", index=False)
    interactions.to_parquet(p.processed_dir / "interactions.parquet", index=False)
    users.to_parquet(p.processed_dir / "users.parquet", index=False)

    mats_dir = p.processed_dir / "matrices"
    mats_dir.mkdir(exist_ok=True)
    for name, splits in {"train": ("train",), "train_val": ("train", "val"), "all": ("train", "val", "test")}.items():
        mat = to_csr(interactions[interactions["split"].isin(splits)], len(users), len(items))
        sparse.save_npz(mats_dir / f"{name}.npz", mat)

    validation = {"items": item_report, "interactions": inter_report}
    (p.processed_dir / "validation_report.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")

    manifest = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": settings.dataset.name,
        "domain": adapter.domain,
        "adapter_info": raw.info,
        "raw_md5": {
            "ml-1m.zip": _file_md5(p.raw_dir / "ml-1m.zip"),
            "ml-32m.zip": _file_md5(p.raw_dir / "ml-32m.zip") if settings.dataset.enrich_with_ml32m else None,
        },
        "config_fingerprint": settings.fingerprint("dataset", "validation", "split"),
        "seed": settings.seed,
        "split_strategy": sc.strategy,
        "n_users": len(users),
        "n_items": len(items),
        "n_interactions": len(interactions),
        "split_sizes": interactions["split"].value_counts().to_dict(),
        "leakage_checks": leakage,
    }
    (p.processed_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    data = ProcessedData.load(p.processed_dir)
    summary = run_eda(data, p.reports_dir, validation)
    manifest["eda"] = {k: summary[k] for k in ("n_items_unrated", "sparsity", "split_primary")}
    log.info("Preprocessing finished: %d users, %d items, %d interactions", len(users), len(items),
             len(interactions))
    return manifest
