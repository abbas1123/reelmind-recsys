"""Shared fixtures.

Unit tests use tiny, hand-made tables (clearly synthetic, never written to data/).
Tests marked ``real_data`` use the processed MovieLens dataset and trained artifacts
and are skipped when those have not been produced yet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from recsys.config import get_settings


@pytest.fixture
def toy_interactions() -> pd.DataFrame:
    """6 users x 6 items with two obvious taste clusters: items {0,1,2} and {3,4,5}."""
    rows = []
    ts = 1_000_000_000
    for u in range(6):
        cluster = [0, 1, 2] if u < 3 else [3, 4, 5]
        for i in cluster:
            rows.append((u + 1, i + 1, 5.0, ts))
            ts += 10
    return pd.DataFrame(rows, columns=["user_id", "item_id", "rating", "ts"])


@pytest.fixture
def toy_matrix() -> sparse.csr_matrix:
    """Two clusters; user 0 has not seen item 2, user 3 has not seen item 5."""
    dense = np.array([
        [5, 4, 0, 0, 0, 0],
        [5, 5, 4, 0, 0, 0],
        [4, 5, 5, 0, 0, 1],
        [0, 0, 0, 5, 4, 0],
        [0, 0, 0, 4, 5, 5],
        [1, 0, 0, 5, 5, 4],
    ], dtype=np.float32)
    return sparse.csr_matrix(dense)


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def processed(settings):
    from recsys.data.dataset import ProcessedData

    if not (settings.p.processed_dir / "items.parquet").exists():
        pytest.skip("processed MovieLens data not found (run `uv run recsys preprocess`)")
    return ProcessedData.load(settings.p.processed_dir)


@pytest.fixture(scope="session")
def engine(settings):
    from recsys.inference.engine import RecommendationEngine

    if not (settings.p.models_dir / "serving" / "manifest.json").exists():
        pytest.skip("serving artifacts not found (run `uv run recsys train`)")
    return RecommendationEngine.load(settings)
