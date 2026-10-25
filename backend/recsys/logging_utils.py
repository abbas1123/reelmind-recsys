"""Logging setup shared by the CLI, training scripts and the API."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: str | int = "INFO") -> None:
    root = logging.getLogger()
    if any(getattr(h, "_recsys", False) for h in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    handler._recsys = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)
    # Third-party libraries are noisy at INFO.
    for noisy in ("httpx", "urllib3", "matplotlib", "sentence_transformers", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


@contextmanager
def timed(logger: logging.Logger, what: str) -> Iterator[dict[str, float]]:
    """Log how long a block takes; the yielded dict receives ``seconds`` afterwards."""
    info: dict[str, float] = {}
    start = time.perf_counter()
    logger.info("%s ...", what)
    try:
        yield info
    finally:
        info["seconds"] = time.perf_counter() - start
        logger.info("%s done in %.1fs", what, info["seconds"])
