"""FastAPI application factory.

The recommendation engine is loaded once at startup. If artifacts are missing the API
still starts (health reports ``degraded``) and model-dependent endpoints return 503 with
the command that fixes it.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import posters
from app.db import init_db, seed_items, session_factory
from app.deps import get_db
from app.routers import interactions, items, model_info, recommendations, users
from app.routers.users import count_items
from app.schemas import HealthOut
from recsys.config import Settings, get_settings
from recsys.inference.engine import ArtifactsMissing, RecommendationEngine
from recsys.logging_utils import setup_logging

log = logging.getLogger("app")


def create_app(settings: Settings | None = None, load_engine: bool = True) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.session_factory = session_factory(settings)
        app.state.engine = None
        app.state.engine_error = None
        init_db(settings)
        with app.state.session_factory() as s:
            if count_items(s) == 0 and (settings.p.processed_dir / "items.parquet").exists():
                log.info("Seeding items table: %d items", seed_items(settings))
        posters.load(settings.p.posters_dir)
        if load_engine:
            try:
                app.state.engine = RecommendationEngine.load(settings)
            except (ArtifactsMissing, FileNotFoundError) as exc:
                app.state.engine_error = str(exc)
                log.warning("Engine not loaded: %s", exc)
        yield

    app = FastAPI(
        title="Local AI Recommendation System",
        version="0.1.0",
        description="MovieLens-based recommendations computed entirely on this machine. "
                    "All metrics come from `artifacts/reports/model_comparison.json`.",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.api.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ArtifactsMissing)
    async def _missing(_: Request, exc: ArtifactsMissing) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/api/health", response_model=HealthOut, tags=["health"])
    def health(request: Request, db: Session = Depends(get_db)) -> HealthOut:
        engine = request.app.state.engine
        return HealthOut(
            status="ok" if engine is not None else "degraded",
            engine_loaded=engine is not None,
            semantic_search=bool(engine and engine.semantic_available),
            items_in_db=count_items(db),
            detail=request.app.state.engine_error,
        )

    for router in (users.router, recommendations.router, items.router, interactions.router, model_info.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
