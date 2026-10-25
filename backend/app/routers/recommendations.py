"""Personalised recommendations."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import User
from app.deps import get_db, get_engine, get_user, has_app_activity, scored, user_history
from app.schemas import RecommendationsResponse, RecSection
from recsys.inference.engine import RecommendationEngine

router = APIRouter(tags=["recommendations"])


@router.get("/users/{user_id}/recommendations", response_model=RecommendationsResponse)
def recommendations(
    k: int = Query(20, ge=1, le=100),
    genre: str | None = Query(None, description="Only recommend items of this genre"),
    strategy: Literal["hybrid", "cf", "content", "popularity"] = "hybrid",
    user: User = Depends(get_user),
    db: Session = Depends(get_db),
    engine: RecommendationEngine = Depends(get_engine),
) -> RecommendationsResponse:
    history = user_history(user, engine)
    preferred = sorted(p.genre for p in user.preferences)
    seen = {i for i, _ in history}
    # Stored training factors are only valid when the profile has no extra app activity.
    ml_id = user.ml_user_id if (user.ml_user_id is not None and not has_app_activity(user)) else None

    top = engine.recommend(history, k=k, preferred_genres=preferred, genre=genre, strategy=strategy,
                           ml_user_id=ml_id)
    sections = [RecSection(key="top_picks", title="Top picks for you" if history else "Popular picks to start with",
                           items=scored(db, engine, [(r.item_id, r.score, r.reason, r.source, r.because_item_id)
                                                     for r in top]))]

    anchor = _anchor_item(user, history)
    if anchor is not None:
        shown = seen | {r.item_id for r in top}
        sims = [s for s in engine.similar_items(anchor, k=k + len(shown)) if s[0] not in shown][:12]
        sections.append(RecSection(
            key="because_you_liked",
            title=f"Because you liked {engine.title(anchor)}",
            items=scored(db, engine, [(i, s, f"Similar to {engine.title(anchor)} ({src})", src, anchor)
                                      for i, s, src in sims]),
        ))

    trend_genre = genre or (preferred[0] if preferred else _top_genre(history, engine))
    trending = engine.trending(k=12, genre=trend_genre, exclude=seen)
    sections.append(RecSection(
        key="trending",
        title=f"Trending in {trend_genre}" if trend_genre else "Trending now",
        items=scored(db, engine, [(i, 0.0, "Trending (time-decayed popularity)", "popularity", None)
                                  for i in trending]),
    ))

    n = len(history)
    bucket = "cold" if n == 0 else ("light" if n < engine.hybrid.warm_min_history else "warm")
    return RecommendationsResponse(user_id=user.id, strategy=strategy, history_size=n, bucket=bucket,
                                   sections=sections)


def _anchor_item(user: User, history: list[tuple[int, float]]) -> int | None:
    """Most recent item the user loved: latest app rating >= 4, else last highly-rated history item."""
    liked = sorted((r for r in user.ratings if r.rating >= 4), key=lambda r: r.created_at, reverse=True)
    if liked:
        return liked[0].item_id
    favs = sorted(user.favorites, key=lambda f: f.created_at, reverse=True)
    if favs:
        return favs[0].item_id
    high = [i for i, r in history if r >= 5] or [i for i, r in history if r >= 4]
    return high[-1] if high else None


def _top_genre(history: list[tuple[int, float]], engine: RecommendationEngine) -> str | None:
    counts: dict[str, int] = {}
    for iid, r in history:
        if r >= 4 and engine.has_item(iid):
            for g in engine.items.at[engine.item_index[iid], "genres"]:
                counts[g] = counts.get(g, 0) + 1
    return max(counts, key=counts.get) if counts else None
