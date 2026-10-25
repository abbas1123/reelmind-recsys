"""Local sentence-transformers embeddings with offline caching.

``download_model`` fetches the model once into ``artifacts/hf_cache/<slug>`` (a plain
folder). Afterwards everything loads from that folder with the Hugging Face hub in
offline mode, so inference never touches the network.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import numpy as np

from recsys.config import Settings

log = logging.getLogger(__name__)


def _slug(model_name: str) -> str:
    return model_name.replace("/", "__")


def local_model_dir(settings: Settings) -> Path:
    return settings.p.hf_cache_dir / _slug(settings.embeddings.model_name)


def _offline() -> None:
    """Hugging Face reads these flags once, at import time: set them before the first import."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def is_available(settings: Settings) -> bool:
    if (local_model_dir(settings) / "config.json").exists():
        _offline()
    try:
        import sentence_transformers  # noqa: F401
    except Exception as exc:  # ImportError, or e.g. Windows MAX_PATH errors inside transformers: stay optional
        log.warning("sentence-transformers unavailable (%s: %s); semantic features disabled.", type(exc).__name__, exc)
        return False
    return (local_model_dir(settings) / "config.json").exists()


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:  # pragma: no cover
        return "cpu"


def download_model(settings: Settings) -> Path:
    """One-time download (needs internet). Uses the OS trust store for TLS verification."""
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:  # pragma: no cover
        pass
    from sentence_transformers import SentenceTransformer

    target = local_model_dir(settings)
    if (target / "config.json").exists():
        log.info("Embedding model already cached at %s", target)
        return target
    log.info("Downloading %s (one time)", settings.embeddings.model_name)
    model = SentenceTransformer(settings.embeddings.model_name, cache_folder=str(settings.p.hf_cache_dir / "hub"),
                                device="cpu")
    model.save(str(target))
    log.info("Saved embedding model to %s", target)
    return target


_MODEL_CACHE: dict[str, object] = {}


def load_model(settings: Settings):
    """Load the cached model strictly offline."""
    _offline()
    path = local_model_dir(settings)
    if not (path / "config.json").exists():
        raise FileNotFoundError(f"Embedding model not cached at {path}. Run `uv run recsys download-models`.")
    key = f"{path}|{settings.embeddings.device}"
    if key not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        device = resolve_device(settings.embeddings.device)
        log.info("Loading embedding model from %s on %s", path, device)
        _MODEL_CACHE[key] = SentenceTransformer(str(path), device=device)
    return _MODEL_CACHE[key]


def encode(texts: list[str], settings: Settings, normalize: bool = True) -> np.ndarray:
    model = load_model(settings)
    vecs = model.encode(texts, batch_size=settings.embeddings.batch_size, show_progress_bar=False,
                        normalize_embeddings=normalize, convert_to_numpy=True)
    return np.asarray(vecs, dtype=np.float32)


def item_embeddings(texts: list[str], settings: Settings) -> np.ndarray:
    """Encode item documents, cached on disk by a hash of the texts and model name."""
    digest = hashlib.sha256(("\n".join(texts) + settings.embeddings.model_name).encode()).hexdigest()[:16]
    path = settings.p.embeddings_dir / f"items_{_slug(settings.embeddings.model_name)}_{digest}.npy"
    if path.exists():
        return np.load(path)
    log.info("Encoding %d item documents with %s", len(texts), settings.embeddings.model_name)
    vecs = encode(texts, settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, vecs)
    return vecs
