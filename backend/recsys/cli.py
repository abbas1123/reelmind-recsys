"""Command line entry point: ``uv run recsys --help``."""

from __future__ import annotations

import json
import logging
from typing import Annotated

import typer

from recsys.config import get_settings
from recsys.logging_utils import setup_logging

app = typer.Typer(help="Local recommendation system: data, training, evaluation, serving.", no_args_is_help=True)
log = logging.getLogger("recsys.cli")


@app.callback()
def _main(verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging")] = False) -> None:
    setup_logging("DEBUG" if verbose else "INFO")


@app.command()
def version() -> None:
    """Print the package version."""
    from recsys import __version__

    typer.echo(__version__)


@app.command()
def download(force: Annotated[bool, typer.Option(help="Re-download even if verified")] = False) -> None:
    """Download MovieLens 1M (+ ML-32M metadata) once, verify MD5, extract needed files."""
    from recsys.data.download import download_all

    s = get_settings()
    download_all(s.p.raw_dir, enrich=s.dataset.enrich_with_ml32m, force=force)


@app.command("download-models")
def download_models() -> None:
    """Cache the sentence-transformers model locally for offline use."""
    from recsys.models.embeddings import download_model

    download_model(get_settings())


@app.command("download-posters")
def download_posters() -> None:
    """Cache film posters from Wikipedia (one time, no API key; needs processed data)."""
    from recsys.data.posters import download_posters as run

    typer.echo(json.dumps(run(get_settings())))


@app.command()
def preprocess() -> None:
    """Validate, index, split and save the dataset; write the EDA report."""
    from recsys.data.preprocess import run_preprocess

    manifest = run_preprocess(get_settings())
    typer.echo(json.dumps({k: manifest[k] for k in ("n_users", "n_items", "n_interactions", "split_sizes")}))


@app.command()
def train(
    quick: Annotated[bool, typer.Option(help="One configuration per model (smoke test)")] = False,
    only: Annotated[list[str] | None, typer.Option(help="Restrict to these models (repeatable)")] = None,
) -> None:
    """Tune on validation, evaluate on test, fit and save serving models, write the report."""
    from recsys.training.train import run_training

    report = run_training(get_settings(), quick=quick, only=only)
    typer.echo(f"Selected model: {report['selection']['selected']}")


@app.command()
def evaluate(check: Annotated[bool, typer.Option(help="Also verify the serving artifacts")] = True) -> None:
    """Print the stored comparison table and (by default) sanity-check the saved serving models."""
    from recsys.evaluation.report import write_markdown

    s = get_settings()
    path = s.p.reports_dir / "model_comparison.json"
    if not path.exists():
        raise typer.Exit(code=_fail("No report yet. Run `uv run recsys train`."))
    report = json.loads(path.read_text(encoding="utf-8"))
    write_markdown(report, s.p.reports_dir / "model_comparison.md")
    metric = report["protocol"]["primary_metric"]
    typer.echo(f"{'model':<18} {'val ' + metric:>12} {'test ' + metric:>12}")
    for row in report["selection"]["ranking"]:
        m = report["models"][row["model"]]
        typer.echo(f"{row['model']:<18} {m['val']['metrics'][metric]:>12.4f} {m['test']['metrics'][metric]:>12.4f}")
    typer.echo(f"Selected: {report['selection']['selected']}")
    if check:
        from recsys.inference.engine import RecommendationEngine

        result = RecommendationEngine.load(s).self_check()
        typer.echo(json.dumps(result, indent=2))


@app.command()
def recommend(
    user: Annotated[int, typer.Option(help="MovieLens user id")] = 1,
    k: Annotated[int, typer.Option(help="How many items")] = 10,
) -> None:
    """Print top-k recommendations for a real MovieLens user from the saved serving model."""
    from recsys.inference.engine import RecommendationEngine

    engine = RecommendationEngine.load(get_settings())
    history = engine.movielens_history(user)
    if not history:
        raise typer.Exit(code=_fail(f"MovieLens user {user} not found (valid ids: 1..6040)."))
    typer.echo(f"User {user}: {len(history)} ratings in history")
    for r in engine.recommend(history, k=k):
        typer.echo(f"  {r.score:6.3f}  {engine.title(r.item_id):<55} {r.reason}")


@app.command("seed-db")
def seed_db() -> None:
    """Create the SQLite app database and load the item catalog."""
    from app.db import init_db, seed_items

    s = get_settings()
    init_db(s)
    n = seed_items(s)
    typer.echo(f"Seeded {n} items into {s.p.db_path}")


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8010,
    reload: Annotated[bool, typer.Option()] = False,
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command()
def pipeline(
    quick: Annotated[bool, typer.Option(help="Quick training (smoke test)")] = False,
    skip_download: Annotated[bool, typer.Option(help="Use already downloaded files")] = False,
) -> None:
    """download -> download-models -> preprocess -> download-posters -> train -> seed-db, in order."""
    if not skip_download:
        download()
        try:
            download_models()
        except Exception as exc:  # embeddings are optional; the rest of the pipeline still works
            log.warning("Embedding model download failed (%s); continuing without semantic features.", exc)
    preprocess()
    if not skip_download:
        try:
            download_posters()
        except Exception as exc:  # posters are optional; the UI falls back to generated artwork
            log.warning("Poster download failed (%s); continuing with generated artwork.", exc)
    train(quick=quick, only=None)
    seed_db()


def _fail(msg: str) -> int:
    typer.secho(msg, fg=typer.colors.RED, err=True)
    return 1


if __name__ == "__main__":
    app()
