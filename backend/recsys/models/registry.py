"""Name -> model class registry plus model families used by training and reporting."""

from __future__ import annotations

from typing import Any

from recsys.models.base import Recommender
from recsys.models.content import ContentEmbedding, ContentTFIDF
from recsys.models.ease import EASE
from recsys.models.explicit import BiasBaseline, BiasedMF
from recsys.models.ials import IALS
from recsys.models.knn import ItemKNN, UserKNN
from recsys.models.popularity import Popularity
from recsys.models.svd import PureSVD

MODELS: dict[str, type[Recommender]] = {
    cls.name: cls
    for cls in (Popularity, UserKNN, ItemKNN, PureSVD, IALS, EASE, BiasBaseline, BiasedMF, ContentTFIDF,
                ContentEmbedding)
}

FAMILY: dict[str, str] = {
    "popularity": "baseline",
    "bias_baseline": "baseline (explicit)",
    "user_knn": "collaborative",
    "item_knn": "collaborative",
    "pure_svd": "collaborative",
    "ials": "collaborative",
    "ease": "collaborative",
    "biased_mf": "collaborative (explicit)",
    "content_tfidf": "content",
    "content_embedding": "content",
    "hybrid": "hybrid",
}

CF_CANDIDATES = ("user_knn", "item_knn", "pure_svd", "ials", "ease")
CONTENT_CANDIDATES = ("content_tfidf", "content_embedding")


def create(name: str, **params: Any) -> Recommender:
    if name not in MODELS:
        raise KeyError(f"Unknown model '{name}'. Available: {sorted(MODELS)}")
    return MODELS[name](**params)
