"""Loader for the processed dataset produced by ``recsys preprocess``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from recsys.data.features import genre_matrix, genre_vocabulary


@dataclass
class ProcessedData:
    items: pd.DataFrame          # one row per catalog item, ordered by iidx
    interactions: pd.DataFrame   # user_id, item_id, rating, ts, uidx, iidx, split, split_user
    users: pd.DataFrame          # user_id, uidx (+ descriptive columns, unused by models)
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def n_users(self) -> int:
        return len(self.users)

    @property
    def n_items(self) -> int:
        return len(self.items)

    @cached_property
    def genre_vocab(self) -> list[str]:
        return genre_vocabulary(self.items["genres"])

    @cached_property
    def genre_matrix(self) -> sparse.csr_matrix:
        return genre_matrix(self.items["genres"], self.genre_vocab)

    @cached_property
    def item_id_to_idx(self) -> dict[int, int]:
        return dict(zip(self.items["item_id"].astype(int), self.items["iidx"].astype(int), strict=True))

    @cached_property
    def user_id_to_idx(self) -> dict[int, int]:
        return dict(zip(self.users["user_id"].astype(int), self.users["uidx"].astype(int), strict=True))

    def rows(self, splits: tuple[str, ...], split_col: str = "split") -> pd.DataFrame:
        return self.interactions[self.interactions[split_col].isin(splits)]

    def matrix(self, splits: tuple[str, ...] = ("train",), split_col: str = "split",
               value: str = "rating") -> sparse.csr_matrix:
        """User x item matrix built from the requested splits: ratings (float32) or timestamps (float64)."""
        dtype = np.float64 if value == "ts" else np.float32
        return to_csr(self.rows(splits, split_col), self.n_users, self.n_items, value=value, dtype=dtype)

    @classmethod
    def load(cls, processed_dir: Path) -> ProcessedData:
        if not (processed_dir / "items.parquet").exists():
            raise FileNotFoundError(f"No processed data in {processed_dir}. Run `uv run recsys preprocess`.")
        items = pd.read_parquet(processed_dir / "items.parquet")
        items["genres"] = items["genres"].map(list)
        items["tags"] = items["tags"].map(list)
        interactions = pd.read_parquet(processed_dir / "interactions.parquet")
        users = pd.read_parquet(processed_dir / "users.parquet")
        manifest = json.loads((processed_dir / "manifest.json").read_text(encoding="utf-8"))
        return cls(items=items, interactions=interactions, users=users, manifest=manifest)


def to_csr(rows: pd.DataFrame, n_users: int, n_items: int, value: str = "rating",
           dtype: type = np.float32) -> sparse.csr_matrix:
    data = rows[value].to_numpy(dtype=dtype)
    mat = sparse.csr_matrix((data, (rows["uidx"].to_numpy(), rows["iidx"].to_numpy())), shape=(n_users, n_items))
    mat.sum_duplicates()
    return mat


def history_vector(item_ratings: dict[int, float], n_items: int) -> sparse.csr_matrix:
    """1 x n_items sparse row from {iidx: rating}; used for fold-in of unseen users."""
    if not item_ratings:
        return sparse.csr_matrix((1, n_items), dtype=np.float32)
    cols = np.fromiter(item_ratings.keys(), dtype=np.int64)
    vals = np.fromiter(item_ratings.values(), dtype=np.float32)
    return sparse.csr_matrix((vals, (np.zeros_like(cols), cols)), shape=(1, n_items))
