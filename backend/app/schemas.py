"""Pydantic request/response models (the public API contract)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    title: str
    year: int | None
    genres: list[str]
    tags: list[str] = Field(default_factory=list, description="Top community tags (MovieLens 32M)")
    n_ratings: int = 0
    mean_rating: float | None = None
    external_ids: dict[str, Any] = Field(default_factory=dict)


class ItemDetail(ItemOut):
    user_rating: float | None = None
    is_favorite: bool = False


class ScoredItem(BaseModel):
    item: ItemOut
    score: float
    reason: str | None = None
    source: str | None = None
    because_item_id: int | None = None


class RecSection(BaseModel):
    key: str
    title: str
    items: list[ScoredItem]


class RecommendationsResponse(BaseModel):
    user_id: int
    strategy: str
    history_size: int
    bucket: Literal["cold", "light", "warm"]
    sections: list[RecSection]


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # "   " must fail min_length, not become ""

    display_name: str = Field(min_length=1, max_length=80)


class UserOut(BaseModel):
    id: int
    display_name: str
    ml_user_id: int | None
    onboarding_done: bool
    created_at: datetime
    n_ratings: int
    n_favorites: int
    preferred_genres: list[str]


class PreferencesIn(BaseModel):
    genres: list[str] = Field(min_length=1, max_length=18)


class RatingIn(BaseModel):
    rating: int = Field(ge=1, le=5, description="Whole stars, like MovieLens 1M")


class RatingOut(BaseModel):
    item: ItemOut
    rating: float
    created_at: datetime


class FavoriteOut(BaseModel):
    item: ItemOut
    created_at: datetime


class InteractionIn(BaseModel):
    kind: Literal["view", "click", "search"]
    item_id: int | None = None
    query: str | None = Field(default=None, max_length=200)


class InteractionOut(BaseModel):
    id: int
    kind: str
    item: ItemOut | None
    query: str | None
    value: float | None
    created_at: datetime


class SearchResponse(BaseModel):
    query: str
    mode: Literal["keyword", "semantic"]
    total: int
    results: list[ScoredItem]


class GenreOut(BaseModel):
    name: str
    n_items: int


class PageOut(BaseModel):
    total: int
    items: list[ItemOut]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    engine_loaded: bool
    semantic_search: bool
    items_in_db: int
    detail: str | None = None
