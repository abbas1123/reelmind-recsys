"""Typed configuration loaded from ``configs/default.yaml`` with environment overrides.

Environment variables use the ``RECSYS_`` prefix and ``__`` for nesting, e.g.
``RECSYS_SEED=7`` or ``RECSYS_EVALUATION__BOOTSTRAP_SAMPLES=200``.
``RECSYS_CONFIG`` points to an alternative YAML file.
"""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("RECSYS_PROJECT_ROOT", BACKEND_DIR.parent)).resolve()
DEFAULT_CONFIG = BACKEND_DIR / "configs" / "default.yaml"


class PathsConfig(BaseModel):
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    artifacts_dir: Path = Path("artifacts")
    models_dir: Path = Path("artifacts/models")
    reports_dir: Path = Path("artifacts/reports")
    embeddings_dir: Path = Path("artifacts/embeddings")
    hf_cache_dir: Path = Path("artifacts/hf_cache")
    posters_dir: Path = Path("artifacts/posters")
    db_path: Path = Path("data/app.db")

    def resolved(self, root: Path = PROJECT_ROOT) -> PathsConfig:
        """Return a copy where every relative path is anchored at the project root."""
        values = {name: (p if p.is_absolute() else (root / p)) for name, p in self.model_dump().items()}
        return PathsConfig(**values)


class DatasetConfig(BaseModel):
    name: str = "movielens-1m"
    enrich_with_ml32m: bool = True
    min_tag_users: int = 2
    max_tags_per_item: int = 25


class ValidationConfig(BaseModel):
    rating_min: int = 1
    rating_max: int = 5
    ts_min: str = "1995-01-01"
    ts_max: str = "2004-01-01"


class SplitConfig(BaseModel):
    strategy: Literal["global_temporal", "per_user_temporal"] = "global_temporal"
    val_fraction: float = Field(0.10, gt=0, lt=0.5)
    test_fraction: float = Field(0.10, gt=0, lt=0.5)


class EvaluationConfig(BaseModel):
    relevance_threshold: float = 4
    k_values: list[int] = [10, 20]
    primary_metric: str = "ndcg@10"
    bootstrap_samples: int = 1000
    light_user_max_train: int = 20
    cold_start_reveal: list[int] = [1, 3, 5]
    eval_batch_size: int = 1024


class HybridConfig(BaseModel):
    weight_step: float = 0.1
    warm_min_history: int = 5
    genre_pref_boost: float = 0.15


class EmbeddingsConfig(BaseModel):
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    batch_size: int = 128


class ApiConfig(BaseModel):
    cors_origins: list[str] = ["http://localhost:5173"]
    default_k: int = 20


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RECSYS_", env_nested_delimiter="__", extra="ignore")

    seed: int = 42
    paths: PathsConfig = PathsConfig()
    dataset: DatasetConfig = DatasetConfig()
    validation: ValidationConfig = ValidationConfig()
    split: SplitConfig = SplitConfig()
    evaluation: EvaluationConfig = EvaluationConfig()
    models: dict[str, dict[str, list[Any]]] = {}
    hybrid: HybridConfig = HybridConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    api: ApiConfig = ApiConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_file = Path(os.environ.get("RECSYS_CONFIG", DEFAULT_CONFIG))
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file))

    @property
    def p(self) -> PathsConfig:
        """Absolute paths."""
        return self.paths.resolved()

    def fingerprint(self, *sections: str) -> str:
        """Short stable hash of selected config sections (used in artifact metadata)."""
        dump = self.model_dump(mode="json")
        chosen = {s: dump[s] for s in sections} if sections else dump
        return hashlib.sha256(json.dumps(chosen, sort_keys=True).encode()).hexdigest()[:12]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
