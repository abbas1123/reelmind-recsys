"""Domain-agnostic dataset contract.

Every content domain (movies, music, books, games, ...) plugs in through a
``DatasetAdapter`` that turns its raw files into the canonical tables below.
Everything downstream (validation, splitting, models, API) only sees these tables.

Canonical ``items`` columns
    item_id:int64, domain:str, title:str, raw_title:str, year:Int64 (nullable),
    genres:list[str], tags:list[str], text:str (document used for content features),
    external_ids:dict[str, Any] (e.g. imdb/tmdb ids)

Canonical ``interactions`` columns
    user_id:int64, item_id:int64, rating:float32, ts:int64 (unix seconds)

Optional ``users`` columns
    user_id:int64 plus any descriptive columns (kept for EDA only).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

ITEM_COLUMNS = ["item_id", "domain", "title", "raw_title", "year", "genres", "tags", "text", "external_ids"]
INTERACTION_COLUMNS = ["user_id", "item_id", "rating", "ts"]


@dataclass
class RawDataset:
    items: pd.DataFrame
    interactions: pd.DataFrame
    users: pd.DataFrame | None = None
    info: dict[str, Any] = field(default_factory=dict)


class DatasetAdapter(ABC):
    """Loads one dataset from ``raw_dir`` into the canonical schema."""

    name: str
    domain: str

    @abstractmethod
    def load(self, raw_dir: Path) -> RawDataset: ...

    @staticmethod
    def build_text(title: str, year: Any, genres: list[str], tags: list[str]) -> str:
        parts = [title]
        if pd.notna(year):
            parts.append(str(int(year)))
        if genres:
            parts.append("Genres: " + ", ".join(genres))
        if tags:
            parts.append("Tags: " + ", ".join(tags))
        return ". ".join(parts) + "."


_REGISTRY: dict[str, type[DatasetAdapter]] = {}


def register(cls: type[DatasetAdapter]) -> type[DatasetAdapter]:
    _REGISTRY[cls.name] = cls
    return cls


def get_adapter(name: str, **kwargs: Any) -> DatasetAdapter:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown dataset '{name}'. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**kwargs)


def registered_adapters() -> list[str]:
    return sorted(_REGISTRY)
