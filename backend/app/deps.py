"""Dependency providers and shared helpers for routers."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Item, User
from app.schemas import ItemOut, ScoredItem, UserOut
from recsys.config import Settings
from recsys.inference.engine import RecommendationEngine


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_engine(request: Request) -> RecommendationEngine:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=request.app.state.engine_error or "Recommendation engine not loaded. Run `uv run recsys pipeline`.",
        )
    return engine


def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


def get_item(item_id: int, db: Session) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return item


# ----------------------------------------------------------------- serializers
def item_out(item: Item, engine: RecommendationEngine | None, max_tags: int = 8) -> ItemOut:
    stats = engine.item_stats(item.id) if engine is not None and engine.has_item(item.id) else {}
    return ItemOut(
        id=item.id,
        domain=item.domain,
        title=item.title,
        year=item.year,
        genres=list(item.genres or []),
        tags=list(item.tags or [])[:max_tags],
        n_ratings=stats.get("n_ratings", 0),
        mean_rating=round(stats["mean_rating"], 3) if stats.get("mean_rating") is not None else None,
        external_ids=item.external_ids or {},
    )


def items_by_ids(db: Session, ids: list[int]) -> dict[int, Item]:
    if not ids:
        return {}
    rows = db.scalars(select(Item).where(Item.id.in_(ids))).all()
    return {r.id: r for r in rows}


def scored(db: Session, engine: RecommendationEngine, rows: list[tuple[int, float, str | None, str | None, int | None]]
           ) -> list[ScoredItem]:
    lookup = items_by_ids(db, [r[0] for r in rows])
    return [ScoredItem(item=item_out(lookup[i], engine), score=round(s, 5), reason=reason, source=src,
                       because_item_id=because)
            for i, s, reason, src, because in rows if i in lookup]


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        display_name=user.display_name,
        ml_user_id=user.ml_user_id,
        onboarding_done=user.onboarding_done,
        created_at=user.created_at,
        n_ratings=len(user.ratings),
        n_favorites=len(user.favorites),
        preferred_genres=sorted(p.genre for p in user.preferences),
    )


def user_history(user: User, engine: RecommendationEngine) -> list[tuple[int, float]]:
    """MovieLens history (for linked profiles) + app ratings (override) + favorites as 5 stars if unrated."""
    hist: dict[int, float] = {}
    if user.ml_user_id is not None:
        hist.update(dict(engine.movielens_history(user.ml_user_id)))
    hist.update({r.item_id: float(r.rating) for r in user.ratings})
    for f in user.favorites:
        hist.setdefault(f.item_id, 5.0)
    return list(hist.items())


def has_app_activity(user: User) -> bool:
    return bool(user.ratings) or bool(user.favorites)

