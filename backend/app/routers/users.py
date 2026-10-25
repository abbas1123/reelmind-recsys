"""Profiles and onboarding."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import Item, User, UserGenrePreference
from app.deps import get_db, get_engine, get_user, item_out, items_by_ids, user_out
from app.schemas import GenreOut, ItemOut, PreferencesIn, UserCreate, UserOut
from recsys.inference.engine import RecommendationEngine

router = APIRouter(tags=["users & onboarding"])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    return [user_out(u) for u in db.scalars(select(User).order_by(User.created_at.desc())).all()]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    user = User(display_name=body.display_name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/users/from-movielens/{ml_user_id}", response_model=UserOut)
def profile_from_movielens(ml_user_id: int, db: Session = Depends(get_db),
                           engine: RecommendationEngine = Depends(get_engine)) -> UserOut:
    """Browse as a real MovieLens user: the profile reuses that user's rating history."""
    if not engine.movielens_history(ml_user_id):
        raise HTTPException(status_code=404, detail=f"MovieLens user {ml_user_id} not found (valid: 1..6040)")
    user = db.scalar(select(User).where(User.ml_user_id == ml_user_id))
    if user is None:
        user = User(display_name=f"MovieLens user #{ml_user_id}", ml_user_id=ml_user_id, onboarding_done=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user_out(user)


@router.get("/users/{user_id}", response_model=UserOut)
def read_user(user: User = Depends(get_user)) -> UserOut:
    return user_out(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user: User = Depends(get_user), db: Session = Depends(get_db)) -> None:
    db.delete(db.merge(user))
    db.commit()


@router.get("/genres", response_model=list[GenreOut])
def list_genres(db: Session = Depends(get_db)) -> list[GenreOut]:
    counts: dict[str, int] = {}
    for genres in db.scalars(select(Item.genres)).all():
        for g in genres or []:
            counts[g] = counts.get(g, 0) + 1
    return [GenreOut(name=g, n_items=n) for g, n in sorted(counts.items())]


@router.get("/onboarding/candidates", response_model=list[ItemOut])
def onboarding_candidates(genres: list[str] = Query(default=[]), k: int = Query(24, ge=1, le=60),
                          db: Session = Depends(get_db),
                          engine: RecommendationEngine = Depends(get_engine)) -> list[ItemOut]:
    """Well-known, well-rated movies from the chosen genres for the user to rate first."""
    ids = engine.onboarding_candidates(genres, k)
    lookup = items_by_ids(db, ids)
    return [item_out(lookup[i], engine) for i in ids if i in lookup]


@router.put("/users/{user_id}/preferences", response_model=UserOut)
def set_preferences(body: PreferencesIn, user: User = Depends(get_user), db: Session = Depends(get_db),
                    engine: RecommendationEngine = Depends(get_engine)) -> UserOut:
    unknown = sorted(set(body.genres) - set(engine.genre_vocab))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown genres: {unknown}. Valid: {engine.genre_vocab}")
    user = db.merge(user)
    user.preferences.clear()
    db.flush()
    for g in sorted(set(body.genres)):
        user.preferences.append(UserGenrePreference(user_id=user.id, genre=g))
    user.onboarding_done = True
    db.commit()
    db.refresh(user)
    return user_out(user)


def count_items(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Item)) or 0)
