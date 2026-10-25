"""Item feature helpers: title normalisation, year parsing, genre encoding."""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
from scipy import sparse

# Articles that MovieLens moves to the end of a title: "Matrix, The" -> "The Matrix".
_ARTICLES = (
    "The", "A", "An", "Les", "La", "Le", "L'", "Il", "Das", "Der", "Die", "Den", "Det",
    "El", "Los", "Las", "Lo", "Un", "Une", "I", "O",
)
_YEAR_RE = re.compile(r"\s*\((\d{4})\)\s*$")
_ARTICLE_RE = re.compile(r"^(?P<body>.+), (?P<art>" + "|".join(re.escape(a) for a in _ARTICLES) + r")$")


def split_title_year(raw_title: str) -> tuple[str, int | None]:
    """'Toy Story (1995)' -> ('Toy Story', 1995). Titles without a year keep year=None."""
    m = _YEAR_RE.search(raw_title)
    if not m:
        return raw_title.strip(), None
    return raw_title[: m.start()].strip(), int(m.group(1))


def _fix_article(fragment: str) -> str:
    m = _ARTICLE_RE.match(fragment.strip())
    if not m:
        return fragment.strip()
    art = m.group("art")
    sep = "" if art.endswith("'") else " "
    return f"{art}{sep}{m.group('body')}"


def display_title(title_without_year: str) -> str:
    """Move trailing articles to the front, also inside an alternate title in parentheses.

    'Postman, The (Postino, Il)' -> 'The Postman (Il Postino)'
    """
    m = re.match(r"^(?P<main>.*?)(?P<alts>(\s*\([^()]*\))*)$", title_without_year)
    main = m.group("main") if m else title_without_year
    alts = re.findall(r"\(([^()]*)\)", m.group("alts")) if m else []
    out = _fix_article(main)
    for alt in alts:
        out += f" ({_fix_article(alt)})"
    return out


def normalize_for_match(title: str) -> str:
    """Aggressive normalisation used only to match titles across datasets."""
    t = unicodedata.normalize("NFKD", display_title(title)).encode("ascii", "ignore").decode()
    t = re.sub(r"\([^)]*\)", " ", t)  # drop alternate titles
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return " ".join(t.split())


def title_variants(raw_title: str) -> set[str]:
    """Normalised main + alternate titles: 'Postino, Il (The Postman) (1994)' -> {'il postino', 'the postman'}."""
    title, _ = split_title_year(raw_title)
    m = re.match(r"^(?P<main>.*?)(?P<alts>(\s*\([^()]*\))*)$", title)
    pieces = [m.group("main")] + re.findall(r"\(([^()]*)\)", m.group("alts")) if m else [title]
    out = set()
    for piece in pieces:
        piece = re.sub(r"^\s*a\.?k\.?a\.?\s+", "", piece, flags=re.IGNORECASE)
        t = unicodedata.normalize("NFKD", _fix_article(piece)).encode("ascii", "ignore").decode()
        t = " ".join(re.sub(r"[^a-z0-9]+", " ", t.lower()).split())
        if t:
            out.add(t)
    return out


def same_title(raw_a: str, raw_b: str, max_year_diff: int = 1) -> bool:
    """Tolerant check that two MovieLens titles describe the same film (used to verify id matches)."""
    _, ya = split_title_year(raw_a)
    _, yb = split_title_year(raw_b)
    if ya is not None and yb is not None and abs(ya - yb) > max_year_diff:
        return False
    va, vb = title_variants(raw_a), title_variants(raw_b)
    if va & vb:
        return True
    # Subtitle added in one release: "Interview with the Vampire" vs "...: The Vampire Chronicles".
    return any(len(min(a, b, key=len)) >= 8 and (a.startswith(b) or b.startswith(a)) for a in va for b in vb)


def genre_vocabulary(genres: pd.Series) -> list[str]:
    return sorted({g for gs in genres for g in gs})


def genre_matrix(genres: pd.Series, vocab: list[str]) -> sparse.csr_matrix:
    """Multi-hot encoding, rows aligned with ``genres``."""
    col = {g: j for j, g in enumerate(vocab)}
    rows, cols = [], []
    for i, gs in enumerate(genres):
        for g in gs:
            if g in col:
                rows.append(i)
                cols.append(col[g])
    data = np.ones(len(rows), dtype=np.float32)
    return sparse.csr_matrix((data, (rows, cols)), shape=(len(genres), len(vocab)))


def decade(year: float | int | None) -> str:
    if year is None or pd.isna(year):
        return "unknown"
    return f"{int(year) // 10 * 10}s"
