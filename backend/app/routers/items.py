"""Catalog: discovery, search, details, similar items."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Favorite, Item, Rating
from app.deps import get_db, get_engine, get_item, item_out, items_by_ids, scored
from app.schemas import ItemDetail, ItemOut, PageOut, ScoredItem, SearchResponse
from recsys.inference.engine import ArtifactsMissing, RecommendationEngine

router = APIRouter(tags=["catalog"])


@router.get("/items/trending", response_model=list[ItemOut])
def trending(k: int = Query(20, ge=1, le=100), genre: str | None = None, db: Session = Depends(get_db),
             engine: RecommendationEngine = Depends(get_engine)) -> list[ItemOut]:
    ids = engine.trending(k=k, genre=genre)
    lookup = items_by_ids(db, ids)
    return [item_out(lookup[i], engine) for i in ids if i in lookup]


@router.get("/items/top-rated", response_model=list[ItemOut])
def top_rated(k: int = Query(20, ge=1, le=100), genre: str | None = None,
              min_ratings: int = Query(50, ge=1), db: Session = Depends(get_db),
              engine: RecommendationEngine = Depends(get_engine)) -> list[ItemOut]:
    ids = engine.top_rated(k=k, genre=genre, min_ratings=min_ratings)
    lookup = items_by_ids(db, ids)
    return [item_out(lookup[i], engine) for i in ids if i in lookup]


@router.get("/genres/{genre}/items", response_model=PageOut)
def genre_items(genre: str, sort: Literal["popular", "top_rated", "newest", "title"] = "popular",
                limit: int = Query(24, ge=1, le=100), offset: int = Query(0, ge=0),
                db: Session = Depends(get_db), engine: RecommendationEngine = Depends(get_engine)) -> PageOut:
    if genre not in engine.genre_vocab:
        raise HTTPException(status_code=404, detail=f"Unknown genre '{genre}'")
    items = [i for i in db.scalars(select(Item)).all() if genre in (i.genres or [])]
    if sort in ("popular", "top_rated"):
        key = "n_ratings" if sort == "popular" else "bayes_rating"
        items.sort(key=lambda i: -engine.item_stats(i.id)[key] if engine.has_item(i.id) else 0)
    elif sort == "newest":
        items.sort(key=lambda i: (-(i.year or 0), i.title))
    else:
        items.sort(key=lambda i: i.title)
    page = items[offset:offset + limit]
    return PageOut(total=len(items), items=[item_out(i, engine) for i in page])


@router.get("/search", response_model=SearchResponse)
def search(q: str = Query(..., min_length=1, max_length=200), mode: Literal["keyword", "semantic"] = "keyword",
           genre: str | None = None, year_from: int | None = None, year_to: int | None = None,
           k: int = Query(30, ge=1, le=100), db: Session = Depends(get_db),
           engine: RecommendationEngine = Depends(get_engine)) -> SearchResponse:
    """Keyword search (title match + TF-IDF over title/genres/tags) or semantic search (local embeddings)."""
    # Keyword search returns only real matches, so take all of them: filtering a truncated pool loses matches
    # (and under-reports `total`). Semantic scores every item, so it keeps a top-N pool.
    pool = max(k * 5, 150) if mode == "semantic" else engine.n_items
    try:
        hits = engine.semantic_search(q, pool) if mode == "semantic" else engine.keyword_search(q, pool)
    except ArtifactsMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    lookup = items_by_ids(db, [i for i, _ in hits])

    def keep(item: Item) -> bool:
        if genre and genre not in (item.genres or []):
            return False
        if year_from is not None and (item.year is None or item.year < year_from):
            return False
        return not (year_to is not None and (item.year is None or item.year > year_to))

    results = [(i, s) for i, s in hits if i in lookup and keep(lookup[i])]
    rows = [(i, s, None, mode, None) for i, s in results[:k]]
    return SearchResponse(query=q, mode=mode, total=len(results), results=scored(db, engine, rows))


@router.get("/items/{item_id}", response_model=ItemDetail)
def item_detail(item_id: int, user_id: int | None = None, db: Session = Depends(get_db),
                engine: RecommendationEngine = Depends(get_engine)) -> ItemDetail:
    item = get_item(item_id, db)
    base = item_out(item, engine, max_tags=25)
    rating = fav = None
    if user_id is not None:
        rating = db.get(Rating, (user_id, item_id))
        fav = db.get(Favorite, (user_id, item_id))
    return ItemDetail(**base.model_dump(), user_rating=rating.rating if rating else None, is_favorite=fav is not None)


@router.get("/items/{item_id}/similar", response_model=list[ScoredItem])
def similar(item_id: int, k: int = Query(12, ge=1, le=50),
            mode: Literal["hybrid", "collaborative", "content"] = "hybrid", db: Session = Depends(get_db),
            engine: RecommendationEngine = Depends(get_engine)) -> list[ScoredItem]:
    get_item(item_id, db)
    if not engine.has_item(item_id):
        raise HTTPException(status_code=404, detail=f"Item {item_id} not in the model catalog")
    sims = engine.similar_items(item_id, k=k, mode=mode)
    return scored(db, engine, [(i, s, f"{src} similarity", src, item_id) for i, s, src in sims])
