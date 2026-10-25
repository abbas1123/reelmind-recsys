"""Index of locally cached posters (see `recsys download-posters`), loaded once at startup."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

log = logging.getLogger(__name__)

_FILES: dict[int, Path] = {}
_STATE: dict[str, object] = {"dir": None, "mtime": None, "checked": 0.0}


def load(posters_dir: Path) -> int:
    """(Re)load the manifest; missing files are skipped so a partial cache still works."""
    _FILES.clear()
    manifest = posters_dir / "manifest.json"
    _STATE.update(dir=posters_dir, mtime=manifest.stat().st_mtime if manifest.exists() else None,
                  checked=time.monotonic())
    if manifest.exists():
        for iid, entry in json.loads(manifest.read_text("utf-8")).get("files", {}).items():
            path = posters_dir / entry["file"]
            if path.exists():
                _FILES[int(iid)] = path
    log.info("Posters available: %d", len(_FILES))
    return len(_FILES)


def _refresh() -> None:
    """Pick up posters written by a running `recsys download-posters` (manifest checked every 15 s)."""
    posters_dir = _STATE["dir"]
    if posters_dir is None or time.monotonic() - float(_STATE["checked"]) < 15:  # type: ignore[arg-type]
        return
    _STATE["checked"] = time.monotonic()
    manifest = Path(posters_dir) / "manifest.json"  # type: ignore[arg-type]
    mtime = manifest.stat().st_mtime if manifest.exists() else None
    if mtime != _STATE["mtime"]:
        try:
            load(Path(posters_dir))  # type: ignore[arg-type]
        except (json.JSONDecodeError, OSError):  # caught the file mid-write; retry on the next check
            _STATE["mtime"] = None


def path_for(item_id: int) -> Path | None:
    _refresh()
    return _FILES.get(int(item_id))


def url_for(item_id: int) -> str | None:
    _refresh()
    return f"/api/items/{int(item_id)}/poster" if int(item_id) in _FILES else None
