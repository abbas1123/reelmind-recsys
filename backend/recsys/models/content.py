"""Content-based filtering from item text (title, year, genres, community tags).

Both variants build an item-item content similarity S and score a user as a weighted sum
of the similarities to the items in their history. Because S covers the whole catalog,
items with zero ratings can still be recommended (item cold start).
"""

from __future__ import annotations

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from recsys.models.base import ItemSide, Recommender, keep_top_k_per_column, l2_normalize_rows


def history_weights(history: sparse.csr_matrix, weighting: str) -> sparse.csr_matrix:
    """binary: every rated item counts 1. centered: rating - 3, so 1-2 stars push similar items down."""
    W = history.copy().astype(np.float32).tocsr()
    if weighting == "binary":
        W.data[:] = 1.0
    elif weighting == "centered":
        W.data = W.data - 3.0
    else:
        raise ValueError(f"Unknown weighting: {weighting}")
    return W


class _ContentSimilarity(Recommender):
    item_vectors_kind = ""

    def _item_vectors(self, items: ItemSide) -> np.ndarray | sparse.csr_matrix:  # pragma: no cover
        raise NotImplementedError

    def fit(self, X: sparse.csr_matrix, items: ItemSide | None = None,
            ts: sparse.csr_matrix | None = None) -> _ContentSimilarity:
        if items is None:
            raise ValueError(f"{self.name} needs item side information")
        k = int(self.params.get("k", 200))
        F = self._item_vectors(items)
        S = F @ F.T
        S = S.toarray() if sparse.issparse(S) else np.asarray(S)
        S = S.astype(np.float32)
        np.fill_diagonal(S, 0.0)
        self.sim = keep_top_k_per_column(S, k).astype(np.float32)
        return self

    def score(self, history: sparse.csr_matrix, user_idx: np.ndarray | None = None) -> np.ndarray:
        W = history_weights(history, str(self.params.get("weighting", "binary")))
        return np.asarray((W @ self.sim).todense(), dtype=np.float32)


class ContentTFIDF(_ContentSimilarity):
    name = "content_tfidf"

    def _item_vectors(self, items: ItemSide) -> sparse.csr_matrix:
        self.vectorizer = TfidfVectorizer(min_df=2, ngram_range=(1, 2), sublinear_tf=True, stop_words="english",
                                          token_pattern=r"(?u)\b[\w'-]{2,}\b")
        F = self.vectorizer.fit_transform(items.texts)
        self.item_matrix = F.astype(np.float32).tocsr()  # kept for keyword search in the inference engine
        return self.item_matrix


class ContentEmbedding(_ContentSimilarity):
    """Semantic similarity from a locally cached sentence-transformers model."""

    name = "content_embedding"

    def _item_vectors(self, items: ItemSide) -> np.ndarray:
        if items.embeddings is None:
            raise ValueError("content_embedding needs item embeddings (run `recsys download-models`)")
        return l2_normalize_rows(items.embeddings.astype(np.float32))
