"""One-time poster download: IMDb id -> Wikidata -> English Wikipedia page image.

No API key is needed. Images are stored in ``artifacts/posters/<item_id>.<ext>`` with a
manifest, and the app serves them from disk afterwards (fully offline). Film posters are
copyrighted: they are fetched for local, educational use only and are never committed.
Films without a match fall back to the generated artwork in the frontend.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode, urlparse

import pandas as pd

from recsys.config import Settings
from recsys.data.download import _ssl_context

log = logging.getLogger(__name__)

USER_AGENT = "ReelMind-course-recommender/0.1 (local educational project; one-time poster cache)"
SPARQL_URL = "https://query.wikidata.org/sparql"
WIKI_API = "https://en.wikipedia.org/w/api.php"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _batches(seq: list, size: int) -> list[list]:
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def _fetch(url: str, data: dict[str, str] | None = None, accept: str = "*/*") -> bytes:
    """GET (or form POST) with polite retries on 429/5xx, honouring Retry-After.

    Uses the standard library on purpose: Wikimedia's bot protection rejects some HTTP client
    fingerprints (httpx gets 403 here), while urllib with a descriptive User-Agent is accepted.
    """
    body = urlencode(data).encode() if data is not None else None
    for attempt in range(40):  # the API may hold a client at ~1 request/minute for a while
        req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                raise
            wait = float(exc.headers.get("Retry-After") or min(90, 5 * 2 ** min(attempt, 4)))
            log.warning("%s -> %d, retrying in %.0fs", urlparse(url).netloc, exc.code, wait)
            time.sleep(wait)
    raise RuntimeError(f"Giving up on {urlparse(url).netloc} after repeated rate limiting")


def parse_sparql(payload: dict[str, Any]) -> dict[str, str]:
    """{imdb_id: wikipedia page title} from a Wikidata SPARQL JSON result (first article wins)."""
    out: dict[str, str] = {}
    for row in payload.get("results", {}).get("bindings", []):
        imdb, article = row["imdb"]["value"], row["article"]["value"]
        out.setdefault(imdb, unquote(article.rsplit("/wiki/", 1)[-1]).replace("_", " "))
    return out


def parse_pageimages(payload: dict[str, Any]) -> dict[str, str]:
    """{page title: image url} from a MediaWiki ``prop=pageimages`` response (follows normalisation)."""
    query = payload.get("query", {})
    alias = {n["to"]: n["from"] for n in query.get("normalized", [])}
    alias.update({r["to"]: alias.get(r["from"], r["from"]) for r in query.get("redirects", [])})
    out: dict[str, str] = {}
    for page in query.get("pages", {}).values():
        src = page.get("thumbnail", {}).get("source")
        if src:
            title = page["title"]
            out[title] = src.split("?", 1)[0]
            if title in alias:
                out[alias[title]] = out[title]
    return out


def _load_cache(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8")) if path.exists() else {"titles": {}, "urls": {}, "asked_imdb": [],
                                                                       "asked_titles": []}


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache), encoding="utf-8")


def _wikipedia_titles(imdb_ids: list[str], cache: dict[str, Any], cache_path: Path) -> dict[str, str]:
    """Few large POST queries: the Wikidata endpoint may be limited to ~1 request/minute."""
    asked = set(cache["asked_imdb"])
    for batch in _batches([i for i in imdb_ids if i not in asked], 800):
        values = " ".join(f'"{i}"' for i in batch)
        query = (f"SELECT ?imdb ?article WHERE {{ VALUES ?imdb {{ {values} }} ?item wdt:P345 ?imdb . "
                 "?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }")
        raw = _fetch(SPARQL_URL, data={"query": query}, accept="application/sparql-results+json")
        cache["titles"].update(parse_sparql(json.loads(raw)))
        cache["asked_imdb"].extend(batch)
        _save_cache(cache_path, cache)  # progress survives interruptions and rate limits
        log.info("  Wikidata: %d ids resolved", len(cache["titles"]))
    return cache["titles"]


def _image_urls(titles: list[str], cache: dict[str, Any], cache_path: Path) -> dict[str, str]:
    asked = set(cache["asked_titles"])
    todo = [t for t in titles if t not in asked]
    for n, batch in enumerate(_batches(todo, 50), 1):
        params = {"action": "query", "format": "json", "prop": "pageimages", "piprop": "thumbnail",
                  "pithumbsize": 342, "pilicense": "any", "redirects": 1, "titles": "|".join(batch)}
        cache["urls"].update(parse_pageimages(json.loads(_fetch(f"{WIKI_API}?{urlencode(params)}"))))
        cache["asked_titles"].extend(batch)
        _save_cache(cache_path, cache)
        log.info("  Wikipedia: batch %d/%d, %d image urls", n, (len(todo) + 49) // 50, len(cache["urls"]))
    return cache["urls"]


def download_posters(settings: Settings, workers: int = 1, pause: float = 0.4) -> dict[str, Any]:
    """Fetch posters for every catalog item with an IMDb id. Re-running only fetches what is missing."""
    out_dir = settings.p.posters_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    files: dict[str, dict[str, str]] = manifest.get("files", {})

    items = pd.read_parquet(settings.p.processed_dir / "items.parquet", columns=["item_id", "external_ids"])
    imdb_of = {int(i): json.loads(e).get("imdb_id") for i, e in zip(items["item_id"], items["external_ids"], strict=True)}
    todo = {iid: imdb for iid, imdb in imdb_of.items() if imdb and str(iid) not in files}
    log.info("Posters: %d already cached, %d to look up", len(files), len(todo))

    cache_path = out_dir / "lookup_cache.json"
    cache = _load_cache(cache_path)
    titles = _wikipedia_titles(sorted(set(todo.values())), cache, cache_path)
    urls = _image_urls(sorted(set(titles.values())), cache, cache_path)
    jobs = []
    for iid, imdb in todo.items():
        page = titles.get(imdb)
        url = urls.get(page) if page else None
        if url:
            ext = Path(urlparse(url).path).suffix.lower()
            jobs.append((iid, page, url, ext if ext in EXTENSIONS else ".jpg"))
    # Most-rated films first: they fill the carousels, so a partial (rate-limited) run already looks complete.
    counts = pd.read_parquet(settings.p.processed_dir / "interactions.parquet", columns=["item_id"])["item_id"].value_counts()
    jobs.sort(key=lambda job: -int(counts.get(job[0], 0)))
    log.info("Posters: %d Wikipedia pages, %d with an image; downloading", len(titles), len(jobs))

    def write_manifest() -> dict[str, Any]:
        manifest = {
            "source": "English Wikipedia lead images via Wikidata (IMDb id, P345)",
            "license_note": "Film posters are copyrighted; cached for local, educational use only. Do not redistribute.",
            "catalog_items": len(imdb_of),
            "with_poster": len(files),
            "files": files,
        }
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        return manifest

    def fetch(job: tuple[int, str, str, str]) -> tuple[int, dict[str, str] | None]:
        iid, page, url, ext = job
        target = out_dir / f"{iid}{ext}"
        if not (target.exists() and target.stat().st_size > 0):  # finished by an interrupted earlier run
            try:
                target.write_bytes(_fetch(url))
            except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
                log.warning("poster %s failed: %s", iid, exc)
                return iid, None
            time.sleep(pause)  # sequential and paced: bursts get throttled by upload.wikimedia.org
        return iid, {"file": target.name, "page": page, "url": url}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (iid, entry) in enumerate(pool.map(fetch, jobs), 1):
            if entry:
                files[str(iid)] = entry
            if n % 50 == 0:
                write_manifest()  # the running app picks up new posters as they arrive
            if n % 250 == 0:
                log.info("  %d/%d posters", n, len(jobs))

    manifest = write_manifest()
    log.info("Posters cached: %d of %d catalog items", len(files), len(imdb_of))
    return {k: v for k, v in manifest.items() if k != "files"}
