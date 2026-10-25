"""Model metadata and the measured evaluation results (served verbatim from the report files)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.deps import get_settings_dep
from recsys.config import Settings

router = APIRouter(prefix="/model", tags=["model"])

CHARTS = {"rating_distribution", "ratings_per_user", "item_long_tail", "genre_counts", "ratings_over_time"}


def _read_json(path: Path, hint: str) -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"{path.name} not found. {hint}")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/info")
def model_info(settings: Settings = Depends(get_settings_dep)) -> dict[str, Any]:
    manifest = _read_json(settings.p.models_dir / "serving" / "manifest.json", "Run `uv run recsys train`.")
    data_manifest = _read_json(settings.p.processed_dir / "manifest.json", "Run `uv run recsys preprocess`.")
    return {"serving": manifest, "dataset": {k: data_manifest.get(k) for k in (
        "dataset", "domain", "n_users", "n_items", "n_interactions", "split_strategy", "split_sizes",
        "adapter_info", "created_at")}}


@router.get("/evaluation")
def evaluation(settings: Settings = Depends(get_settings_dep)) -> dict[str, Any]:
    """The full comparison report produced by `recsys train` (no numbers are computed or altered here)."""
    return _read_json(settings.p.reports_dir / "model_comparison.json", "Run `uv run recsys train`.")


@router.get("/eda")
def eda(settings: Settings = Depends(get_settings_dep)) -> dict[str, Any]:
    out = _read_json(settings.p.reports_dir / "eda.json", "Run `uv run recsys preprocess`.")
    out["charts"] = sorted(c for c in CHARTS if (settings.p.reports_dir / "eda" / f"{c}.png").exists())
    return out


@router.get("/eda/charts/{name}.png", response_class=FileResponse)
def eda_chart(name: str, settings: Settings = Depends(get_settings_dep)) -> FileResponse:
    if name not in CHARTS:
        raise HTTPException(status_code=404, detail="Unknown chart")
    path = settings.p.reports_dir / "eda" / f"{name}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Chart not generated yet")
    return FileResponse(path, media_type="image/png")
