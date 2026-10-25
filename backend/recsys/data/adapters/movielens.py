"""MovieLens 1M adapter with optional metadata enrichment from MovieLens 32M.

ML-1M provides ratings, titles and genres only. To give content-based models more
signal we attach community tags and IMDb/TMDB ids from ML-32M. The two releases share
movie ids for older titles; every id match is double-checked against the normalised
title + year, and unmatched movies simply get no tags (never invented ones).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from recsys.data.adapters.base import DatasetAdapter, RawDataset, register
from recsys.data.features import display_title, normalize_for_match, same_title, split_title_year

log = logging.getLogger(__name__)


def _read_dat(path: Path, names: list[str]) -> pd.DataFrame:
    """Read a '::'-separated latin-1 file quickly via the C parser."""
    text = path.read_bytes().decode("latin-1").replace("::", "\t")
    return pd.read_csv(io.StringIO(text), sep="\t", names=names, header=None, dtype=str, keep_default_na=False,
                       na_values=[""], quoting=3)


@register
class MovieLens1MAdapter(DatasetAdapter):
    name = "movielens-1m"
    domain = "movie"

    def __init__(self, enrich: bool = True, min_tag_users: int = 2, max_tags_per_item: int = 25) -> None:
        self.enrich = enrich
        self.min_tag_users = min_tag_users
        self.max_tags_per_item = max_tags_per_item

    # ------------------------------------------------------------------ public
    def load(self, raw_dir: Path) -> RawDataset:
        base = raw_dir / "ml-1m"
        if not (base / "ratings.dat").exists():
            raise FileNotFoundError(f"{base / 'ratings.dat'} missing. Run `uv run recsys download` first.")

        ratings = _read_dat(base / "ratings.dat", ["user_id", "item_id", "rating", "ts"])
        movies = _read_dat(base / "movies.dat", ["item_id", "raw_title", "genres_raw"])
        users = _read_dat(base / "users.dat", ["user_id", "gender", "age", "occupation", "zip"])

        # Keep raw strings for validation: conversion errors become NaN and are counted there.
        interactions = pd.DataFrame({
            "user_id": pd.to_numeric(ratings["user_id"], errors="coerce").astype("Int64"),
            "item_id": pd.to_numeric(ratings["item_id"], errors="coerce").astype("Int64"),
            "rating": pd.to_numeric(ratings["rating"], errors="coerce").astype("Float32"),
            "ts": pd.to_numeric(ratings["ts"], errors="coerce").astype("Int64"),
        })
        users = users.assign(user_id=pd.to_numeric(users["user_id"], errors="coerce").astype("Int64"),
                             age=pd.to_numeric(users["age"], errors="coerce").astype("Int64"),
                             occupation=pd.to_numeric(users["occupation"], errors="coerce").astype("Int64"))
        items = self._items(movies)
        info: dict = {"source": "MovieLens 1M (GroupLens)", "raw_ratings": len(ratings), "raw_movies": len(movies),
                      "raw_users": len(users)}

        if self.enrich:
            enrich_dir = raw_dir / "ml-32m"
            if (enrich_dir / "links.csv").exists():
                items, enrich_info = self._enrich(items, enrich_dir)
                info["enrichment"] = enrich_info
            else:
                log.warning("Enrichment requested but %s is missing; continuing without tags.", enrich_dir)
                info["enrichment"] = {"status": "skipped (ml-32m not downloaded)"}

        items["text"] = [self.build_text(t, y, g, tg) for t, y, g, tg in
                         zip(items["title"], items["year"], items["genres"], items["tags"], strict=True)]
        return RawDataset(items=items, interactions=interactions, users=users, info=info)

    # ----------------------------------------------------------------- helpers
    def _items(self, movies: pd.DataFrame) -> pd.DataFrame:
        parsed = [split_title_year(t) for t in movies["raw_title"].fillna("")]
        return pd.DataFrame({
            "item_id": pd.to_numeric(movies["item_id"], errors="coerce").astype("Int64"),
            "domain": self.domain,
            "title": [display_title(t) for t, _ in parsed],
            "raw_title": movies["raw_title"].fillna(""),
            "year": pd.array([y for _, y in parsed], dtype="Int64"),
            "genres": [[g for g in str(gs).split("|") if g and g != "(no genres listed)"]
                       for gs in movies["genres_raw"].fillna("")],
            "tags": [[] for _ in range(len(movies))],
            "external_ids": [{} for _ in range(len(movies))],
        })

    def _enrich(self, items: pd.DataFrame, enrich_dir: Path) -> tuple[pd.DataFrame, dict]:
        m32 = pd.read_csv(enrich_dir / "movies.csv", dtype={"movieId": np.int64, "title": str, "genres": str})
        links = pd.read_csv(enrich_dir / "links.csv", dtype={"movieId": np.int64, "imdbId": str, "tmdbId": "Int64"})

        def key(raw_title: str) -> tuple[str, int | None]:
            t, y = split_title_year(raw_title)
            return normalize_for_match(t), y

        m32_title = dict(zip(m32["movieId"], m32["title"], strict=True))
        m32_key = {mid: key(t) for mid, t in m32_title.items()}
        by_key: dict[tuple[str, int | None], list[int]] = {}
        for mid, k in m32_key.items():
            by_key.setdefault(k, []).append(mid)

        mapping: dict[int, int] = {}
        id_matches = title_matches = 0
        for iid, raw in zip(items["item_id"], items["raw_title"], strict=True):
            k = key(raw)
            if int(iid) in m32_title and same_title(raw, m32_title[int(iid)]):
                mapping[int(iid)] = int(iid)
                id_matches += 1
            elif len(by_key.get(k, [])) == 1:
                mapping[int(iid)] = by_key[k][0]
                title_matches += 1
        unmatched = len(items) - len(mapping)
        log.info("ML-32M mapping: %d by id (title verified), %d by title+year, %d unmatched",
                 id_matches, title_matches, unmatched)

        # Tags: count distinct users per (movie, tag); keep tags used by enough people.
        wanted = set(mapping.values())
        tag_counts: dict[tuple[int, str], int] = {}
        reader = pd.read_csv(enrich_dir / "tags.csv", usecols=["userId", "movieId", "tag"],
                             dtype={"userId": np.int64, "movieId": np.int64, "tag": str}, chunksize=500_000)
        for chunk in reader:
            chunk = chunk[chunk["movieId"].isin(wanted)].dropna(subset=["tag"])
            chunk["tag"] = chunk["tag"].str.strip().str.lower()
            chunk = chunk[chunk["tag"].str.len().between(2, 40)]
            grouped = chunk.drop_duplicates(["userId", "movieId", "tag"]).groupby(["movieId", "tag"]).size()
            for (mid, tag), n in grouped.items():
                tag_counts[(mid, tag)] = tag_counts.get((mid, tag), 0) + int(n)

        per_movie: dict[int, list[tuple[int, str]]] = {}
        for (mid, tag), n in tag_counts.items():
            if n >= self.min_tag_users:
                per_movie.setdefault(mid, []).append((n, tag))
        top_tags = {mid: [t for _, t in sorted(v, key=lambda x: (-x[0], x[1]))[: self.max_tags_per_item]]
                    for mid, v in per_movie.items()}

        link_by_id = links.set_index("movieId")
        tags_col, ext_col = [], []
        for iid in items["item_id"]:
            mid = mapping.get(int(iid))
            tags_col.append(top_tags.get(mid, []) if mid is not None else [])
            ext: dict = {}
            if mid is not None and mid in link_by_id.index:
                row = link_by_id.loc[mid]
                if pd.notna(row["imdbId"]):
                    ext["imdb_id"] = f"tt{str(row['imdbId']).zfill(7)}"
                if pd.notna(row["tmdbId"]):
                    ext["tmdb_id"] = int(row["tmdbId"])
                ext["ml32m_movie_id"] = int(mid)
            ext_col.append(ext)
        items = items.assign(tags=tags_col, external_ids=ext_col)
        with_tags = int(sum(1 for t in tags_col if t))
        info = {
            "status": "ok",
            "matched_by_id": id_matches,
            "matched_by_title_year": title_matches,
            "unmatched": unmatched,
            "items_with_tags": with_tags,
            "min_tag_users": self.min_tag_users,
            "max_tags_per_item": self.max_tags_per_item,
        }
        return items, info
