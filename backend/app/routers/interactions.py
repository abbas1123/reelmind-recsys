"""Ratings, favorites and interaction history."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db import Favorite, Interaction, Rating, User
from app.deps import get_db, get_engine, get_item, get_user, item_out, items_by_ids
from app.schemas import FavoriteOut, InteractionIn, InteractionOut, RatingIn, RatingOut
from recsys.inference.engine import RecommendationEngine

router = APIRouter(tags=["ratings, favorites & history"])


def _log(db: Session, user_id: int, kind: str, item_id: int | None = None, query: str | None = None,
         value: float | None = None) -> Interaction:
    row = Interaction(user_id=user_id, item_id=item_id, kind=kind, query=query, value=value)
    db.add(row)
    return row


@router.put("/users/{user_id}/ratings/{item_id}", response_model=RatingOut)
def rate(item_id: int, body: RatingIn, user: User = Depends(get_user), db: Session = Depends(get_db),
         engine: RecommendationEngine = Depends(get_engine)) -> RatingOut:
    item = get_item(item_id, db)
    value, now = float(body.rating), datetime.now(UTC)
    # One atomic upsert: a get-then-insert lets two quick clicks race into a UNIQUE error (500).
    db.execute(sqlite_insert(Rating).values(user_id=user.id, item_id=item_id, rating=value, created_at=now)
               .on_conflict_do_update(index_elements=["user_id", "item_id"], set_={"rating": value, "created_at": now}))
    _log(db, user.id, "rate", item_id, value=value)
    db.commit()
    row = db.get(Rating, (user.id, item_id), populate_existing=True)
    return RatingOut(item=item_out(item, engine), rating=row.rating, created_at=row.created_at)


@router.delete("/users/{user_id}/ratings/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def unrate(item_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)) -> Response:
    row = db.get(Rating, (user.id, item_id))
    if row is not None:
        db.delete(row)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/ratings", response_model=list[RatingOut])
def list_ratings(user: User = Depends(get_user), db: Session = Depends(get_db),
                 engine: RecommendationEngine = Depends(get_engine)) -> list[RatingOut]:
    rows = db.scalars(select(Rating).where(Rating.user_id == user.id).order_by(Rating.created_at.desc())).all()
    lookup = items_by_ids(db, [r.item_id for r in rows])
    return [RatingOut(item=item_out(lookup[r.item_id], engine), rating=r.rating, created_at=r.created_at)
            for r in rows if r.item_id in lookup]


@router.put("/users/{user_id}/favorites/{item_id}", response_model=FavoriteOut)
def add_favorite(item_id: int, user: User = Depends(get_user), db: Session = Depends(get_db),
                 engine: RecommendationEngine = Depends(get_engine)) -> FavoriteOut:
    item = get_item(item_id, db)
    # Insert-or-ignore (race-safe, see rate()); only a real insert is logged as "added".
    added = db.execute(sqlite_insert(Favorite).values(user_id=user.id, item_id=item_id).on_conflict_do_nothing())
    if added.rowcount:
        _log(db, user.id, "favorite", item_id, value=1.0)
    db.commit()
    row = db.get(Favorite, (user.id, item_id), populate_existing=True)
    return FavoriteOut(item=item_out(item, engine), created_at=row.created_at)


@router.delete("/users/{user_id}/favorites/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(item_id: int, user: User = Depends(get_user), db: Session = Depends(get_db)) -> Response:
    row = db.get(Favorite, (user.id, item_id))
    if row is not None:
        db.delete(row)
        _log(db, user.id, "favorite", item_id, value=0.0)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/{user_id}/favorites", response_model=list[FavoriteOut])
def list_favorites(user: User = Depends(get_user), db: Session = Depends(get_db),
                   engine: RecommendationEngine = Depends(get_engine)) -> list[FavoriteOut]:
    rows = db.scalars(select(Favorite).where(Favorite.user_id == user.id)
                      .order_by(Favorite.created_at.desc())).all()
    lookup = items_by_ids(db, [r.item_id for r in rows])
    return [FavoriteOut(item=item_out(lookup[r.item_id], engine), created_at=r.created_at)
            for r in rows if r.item_id in lookup]


@router.post("/users/{user_id}/interactions", response_model=InteractionOut, status_code=status.HTTP_201_CREATED)
def log_interaction(body: InteractionIn, user: User = Depends(get_user), db: Session = Depends(get_db),
                    engine: RecommendationEngine = Depends(get_engine)) -> InteractionOut:
    item = get_item(body.item_id, db) if body.item_id is not None else None
    row = _log(db, user.id, body.kind, body.item_id, body.query)
    db.commit()
    db.refresh(row)
    return InteractionOut(id=row.id, kind=row.kind, item=item_out(item, engine) if item else None, query=row.query,
                          value=row.value, created_at=row.created_at)


@router.get("/users/{user_id}/history", response_model=list[InteractionOut])
def history(limit: int = Query(50, ge=1, le=500), user: User = Depends(get_user), db: Session = Depends(get_db),
            engine: RecommendationEngine = Depends(get_engine)) -> list[InteractionOut]:
    rows = db.scalars(select(Interaction).where(Interaction.user_id == user.id)
                      .order_by(Interaction.created_at.desc(), Interaction.id.desc()).limit(limit)).all()
    lookup = items_by_ids(db, [r.item_id for r in rows if r.item_id is not None])
    return [InteractionOut(id=r.id, kind=r.kind, item=item_out(lookup[r.item_id], engine)
                           if r.item_id in lookup else None, query=r.query, value=r.value, created_at=r.created_at)
            for r in rows]
