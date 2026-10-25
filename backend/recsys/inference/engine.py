"""Inference engine: loads saved artifacts once and answers recommendation queries.

Independent from the web layer — the FastAPI app, the CLI and the tests all use this class.
Histories are lists of ``(item_id, rating)``; brand-new users are served by fold-in
(no retraining), users with no history by the cold-start module.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from functools import cached_property
from typing import Any

import numpy as np
from scipy import sparse

from recsys.config import Settings
from recsys.data.dataset import ProcessedData, history_vector
from recsys.inference import cold_start
from recsys.models.base import Recommender
from recsys.models.content import ContentTFIDF
from recsys.models.hybrid import Hybrid, minmax_rows

log = logging.getLogger(__name__)


@dataclass
class Recommendation:
    item_id: int
    score: float
    reason: str
    source: str
    because_item_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtifactsMissing(RuntimeError):
    pass


class RecommendationEngine:
    def __init__(self, settings: Settings, data: ProcessedData, hybrid: Hybrid, item_item: Recommender,
                 tfidf: ContentTFIDF, embeddings: np.ndarray | None, manifest: dict[str, Any]):
        self.settings = settings
        self.data = data
        self.hybrid = hybrid
        self.item_item = item_item
        self.tfidf = tfidf
        self.embeddings = embeddings
        self.manifest = manifest
        self.items = data.items
        self.n_items = data.n_items
        self._idx_to_item = self.items["item_id"].to_numpy()
        pop = hybrid.components["pop"]
        self._cold_base = cold_start.base_cold_scores(pop.scores_, pop.bayes_avg, pop.counts)

    # ----------------------------------------------------------------- loading
    @classmethod
    def load(cls, settings: Settings) -> RecommendationEngine:
        d = settings.p.models_dir / "serving"
        if not (d / "manifest.json").exists():
            raise ArtifactsMissing(f"No serving artifacts in {d}. Run `uv run recsys pipeline` (or `recsys train`).")
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        data = ProcessedData.load(settings.p.processed_dir)
        hybrid = Recommender.load(d / "hybrid.joblib")
        item_item = Recommender.load(d / "item_item.joblib")
        tfidf = Recommender.load(d / "content_tfidf.joblib")
        emb = None
        if manifest.get("embeddings_file") and (d / manifest["embeddings_file"]).exists():
            emb = np.load(d / manifest["embeddings_file"])
        log.info("Engine loaded: selected=%s cf=%s cb=%s items=%d", manifest.get("selected_model"),
                 manifest.get("cf_model"), manifest.get("content_model"), data.n_items)
        return cls(settings, data, hybrid, item_item, tfidf, emb, manifest)  # type: ignore[arg-type]

    # ----------------------------------------------------------------- catalog
    @cached_property
    def item_index(self) -> dict[int, int]:
        return self.data.item_id_to_idx

    @cached_property
    def genre_vocab(self) -> list[str]:
        return self.data.genre_vocab

    def has_item(self, item_id: int) -> bool:
        return int(item_id) in self.item_index

    def title(self, item_id: int) -> str:
        return str(self.items.at[self.item_index[int(item_id)], "title"])

    def item_ids(self, idx: np.ndarray | list[int]) -> list[int]:
        return [int(self._idx_to_item[i]) for i in idx]

    def genre_mask(self, genre: str | None) -> np.ndarray | None:
        if not genre:
            return None
        if genre not in self.genre_vocab:
            return np.zeros(self.n_items, dtype=bool)
        col = self.genre_vocab.index(genre)
        return np.asarray(self.data.genre_matrix[:, col].toarray()).ravel() > 0

    def item_stats(self, item_id: int) -> dict[str, Any]:
        pop = self.hybrid.components["pop"]
        i = self.item_index[int(item_id)]
        return {"n_ratings": int(pop.counts[i]), "mean_rating": float(pop.mean_rating[i]) if pop.counts[i] else None,
                "bayes_rating": float(pop.bayes_avg[i])}

    @cached_property
    def _ml_histories(self) -> dict[int, list[tuple[int, float]]]:
        df = self.data.interactions[["user_id", "item_id", "rating"]]
        out: dict[int, list[tuple[int, float]]] = {}
        for uid, iid, r in df.itertuples(index=False):
            out.setdefault(int(uid), []).append((int(iid), float(r)))
        return out

    def movielens_history(self, user_id: int) -> list[tuple[int, float]]:
        return list(self._ml_histories.get(int(user_id), []))

    def movielens_user_ids(self) -> list[int]:
        return sorted(self._ml_histories)

    # ---------------------------------------------------------- recommendation
    def _to_vector(self, history: list[tuple[int, float]]) -> sparse.csr_matrix:
        ratings = {self.item_index[int(i)]: float(r) for i, r in history if int(i) in self.item_index}
        return history_vector(ratings, self.n_items)

    def recommend(self, history: list[tuple[int, float]], k: int = 20, preferred_genres: list[str] | None = None,
                  genre: str | None = None, exclude: set[int] | None = None, strategy: str = "hybrid",
                  ml_user_id: int | None = None) -> list[Recommendation]:
        """Top-k items for a history. ``strategy``: hybrid | cf | content | popularity."""
        exclude_idx = {self.item_index[int(i)] for i in (exclude or set()) if int(i) in self.item_index}
        vec = self._to_vector(history)
        seen = set(vec.indices.tolist()) | exclude_idx
        allowed = self.genre_mask(genre)

        if vec.nnz == 0:
            # CF and content scores are constant for an empty history, so every strategy falls back to cold start.
            picks = cold_start.recommend_new_user(self._cold_base, self.data.genre_matrix, self.genre_vocab,
                                                  preferred_genres, k, seen, allowed)
            return [Recommendation(self.item_ids([i])[0], s, reason, "cold_start") for i, s, reason in picks]

        # Use the stored training row only when the history is exactly the MovieLens user's training history.
        user_idx = None
        if ml_user_id is not None and len(history) == len(self._ml_histories.get(int(ml_user_id), [])):
            uidx = self.data.user_id_to_idx.get(int(ml_user_id))
            user_idx = np.array([uidx]) if uidx is not None else None

        raw = self.hybrid.component_scores(vec, user_idx)
        if strategy == "hybrid":
            scores = self.hybrid.combine_scores(raw, np.array([vec.nnz]))[0]
            if preferred_genres and vec.nnz < self.hybrid.warm_min_history:
                boost = self.settings.hybrid.genre_pref_boost
                scores = scores + boost * cold_start.genre_affinity(self.data.genre_matrix, self.genre_vocab,
                                                                    preferred_genres)
        elif strategy in ("cf", "content", "popularity"):
            key = {"cf": "cf", "content": "cb", "popularity": "pop"}[strategy]
            scores = minmax_rows(raw[key])[0]
        else:
            raise ValueError(f"Unknown strategy '{strategy}'")

        scores = scores.astype(np.float64)
        if allowed is not None:
            scores[~allowed] = -np.inf
        if seen:
            scores[list(seen)] = -np.inf
        top = np.argsort(-scores, kind="stable")[:k]
        top = [i for i in top if np.isfinite(scores[i])]
        return [self._explain(i, float(scores[i]), vec, strategy) for i in top]

    def _explain(self, j: int, score: float, vec: sparse.csr_matrix, strategy: str) -> Recommendation:
        """Attribute item j to the history item that contributes most (CF item-item + content similarity)."""
        item_id = int(self._idx_to_item[j])
        hist, ratings = vec.indices, vec.data
        liked = hist[ratings >= 4]  # never explain with a film the user rated low
        # The popularity ranking ignores the history, so a "because you liked" attribution would be false.
        if len(liked) and strategy != "popularity":
            contrib = np.zeros(len(liked))
            ii = self._item_item_column(j)
            if ii is not None:
                contrib += _safe_norm(ii[liked])
            cb = self._content_similarity_row(j)
            if cb is not None:
                contrib += _safe_norm(cb[liked])
            if contrib.max() > 0:
                src = int(liked[int(np.argmax(contrib))])
                src_id = int(self._idx_to_item[src])
                return Recommendation(item_id, score, f"Because you liked {self.title(src_id)}", strategy, src_id)
        genres = self.items.at[j, "genres"]
        reason = f"Trending in {genres[0]}" if len(genres) else "Trending"
        return Recommendation(item_id, score, reason, strategy)

    def _item_item_column(self, j: int) -> np.ndarray | None:
        m = self.item_item
        mat = getattr(m, "W", None)
        if mat is None:
            mat = getattr(m, "sim", None)
        if mat is None:
            return None
        col = mat[:, j]
        return np.asarray(col.toarray()).ravel() if sparse.issparse(col) else np.asarray(col).ravel()

    def _content_similarity_row(self, j: int) -> np.ndarray | None:
        if self.embeddings is not None:
            return self.embeddings @ self.embeddings[j]
        F = self.tfidf.item_matrix
        return np.asarray((F @ F[j].T).toarray()).ravel()

    # ------------------------------------------------------------ discovery
    def similar_items(self, item_id: int, k: int = 12, mode: str = "hybrid") -> list[tuple[int, float, str]]:
        """Items similar to ``item_id``: collaborative (co-ratings), content (text/tags) or both."""
        j = self.item_index[int(item_id)]
        parts = {}
        if mode in ("hybrid", "collaborative"):
            cf = self._item_item_column(j)
            row = self._item_item_row(j)
            if cf is not None and row is not None:
                parts["collaborative"] = np.maximum(cf, row)
        if mode in ("hybrid", "content"):
            parts["content"] = self._content_similarity_row(j)
        normed = {name: _safe_norm(v) for name, v in parts.items() if v is not None}
        if not normed:
            return []
        scores = sum(normed.values())
        scores[j] = -np.inf
        top = np.argsort(-scores, kind="stable")[:k]
        out = []
        for i in top:
            if scores[i] <= 0:  # no evidence left (e.g. collaborative mode for an unrated film): don't pad
                break           # the list with the first catalog ids at score 0
            dominant = max(normed, key=lambda name: normed[name][i])
            out.append((int(self._idx_to_item[i]), float(scores[i]), dominant))
        return out

    def _item_item_row(self, j: int) -> np.ndarray | None:
        mat = getattr(self.item_item, "W", None)
        if mat is None:
            mat = getattr(self.item_item, "sim", None)
        if mat is None:
            return None
        row = mat[j]
        return np.asarray(row.toarray()).ravel() if sparse.issparse(row) else np.asarray(row).ravel()

    def trending(self, k: int = 20, genre: str | None = None, exclude: set[int] | None = None) -> list[int]:
        """Time-decayed popularity at the end of the dataset (or all-time counts if decay is off)."""
        scores = self.hybrid.components["pop"].scores_.astype(np.float64).copy()
        return self._rank(scores, k, genre, exclude)

    def top_rated(self, k: int = 20, genre: str | None = None, min_ratings: int = 50,
                  exclude: set[int] | None = None) -> list[int]:
        pop = self.hybrid.components["pop"]
        scores = np.where(pop.counts >= min_ratings, pop.bayes_avg, -np.inf).astype(np.float64)
        return self._rank(scores, k, genre, exclude)

    def onboarding_candidates(self, genres: list[str], k: int = 24) -> list[int]:
        """Well-known movies from the chosen genres for the user to rate during onboarding."""
        picks = cold_start.recommend_new_user(self._cold_base, self.data.genre_matrix, self.genre_vocab, genres, k,
                                              set(), None)
        return [int(self._idx_to_item[i]) for i, _, _ in picks]

    def _rank(self, scores: np.ndarray, k: int, genre: str | None, exclude: set[int] | None) -> list[int]:
        allowed = self.genre_mask(genre)
        if allowed is not None:
            scores[~allowed] = -np.inf
        for iid in exclude or set():
            if int(iid) in self.item_index:
                scores[self.item_index[int(iid)]] = -np.inf
        top = np.argsort(-scores, kind="stable")[:k]
        return [int(self._idx_to_item[i]) for i in top if np.isfinite(scores[i])]

    # ---------------------------------------------------------------- search
    def keyword_search(self, query: str, k: int = 30) -> list[tuple[int, float]]:
        q = query.strip().lower()
        if not q:
            return []
        titles = self.items["title"].str.lower()
        exact = titles.str.contains(q, regex=False).to_numpy()
        qv = self.tfidf.vectorizer.transform([query])
        tfidf_scores = np.asarray((self.tfidf.item_matrix @ qv.T).toarray()).ravel()
        pop = np.log1p(self.hybrid.components["pop"].counts) / np.log1p(self.hybrid.components["pop"].counts.max())
        scores = tfidf_scores + 1.0 * exact + 0.05 * pop
        scores[(tfidf_scores == 0) & ~exact] = -np.inf
        top = np.argsort(-scores, kind="stable")[:k]
        return [(int(self._idx_to_item[i]), float(scores[i])) for i in top if np.isfinite(scores[i])]

    @property
    def semantic_available(self) -> bool:
        from recsys.models import embeddings as E

        return self.embeddings is not None and E.is_available(self.settings)

    def semantic_search(self, query: str, k: int = 30) -> list[tuple[int, float]]:
        """Natural-language search with the local embedding model (e.g. 'funny space adventure')."""
        if not self.semantic_available:
            raise ArtifactsMissing("Semantic search needs the cached embedding model (`recsys download-models`).")
        if not query.strip():
            return []
        from recsys.models import embeddings as E

        qv = E.encode([query], self.settings)[0]
        scores = self.embeddings @ qv
        top = np.argsort(-scores, kind="stable")[:k]
        return [(int(self._idx_to_item[i]), float(scores[i])) for i in top]

    # ------------------------------------------------------------- self-check
    def self_check(self, n_users: int = 20) -> dict[str, Any]:
        """Verify that saved artifacts give valid recommendations for real users and a new user."""
        rng = np.random.default_rng(self.settings.seed)
        users = rng.choice(self.movielens_user_ids(), size=min(n_users, len(self._ml_histories)), replace=False)
        problems = []
        for uid in users:
            hist = self.movielens_history(int(uid))
            recs = self.recommend(hist, k=10, ml_user_id=int(uid))
            seen = {i for i, _ in hist}
            ids = [r.item_id for r in recs]
            if len(ids) != 10 or len(set(ids)) != 10:
                problems.append(f"user {uid}: expected 10 unique items, got {ids}")
            if seen & set(ids):
                problems.append(f"user {uid}: recommended already-seen items {seen & set(ids)}")
            if not all(self.has_item(i) for i in ids):
                problems.append(f"user {uid}: unknown item ids")
        cold = self.recommend([], k=10, preferred_genres=["Comedy", "Animation"])
        new_user = self.recommend([(1, 5.0), (2355, 5.0), (3114, 4.0)], k=10)  # Toy Story, A Bug's Life, Toy Story 2
        return {
            "checked_users": len(users),
            "problems": problems,
            "ok": not problems and len(cold) == 10 and len(new_user) == 10,
            "cold_start_example": [self.title(r.item_id) for r in cold[:5]],
            "fold_in_example": [f"{self.title(r.item_id)} — {r.reason}" for r in new_user[:5]],
        }


def _safe_norm(v: np.ndarray) -> np.ndarray:
    v = np.nan_to_num(np.asarray(v, dtype=np.float64), neginf=0.0, posinf=0.0)
    hi = v.max() if len(v) else 0.0
    return v / hi if hi > 0 else np.zeros_like(v)
