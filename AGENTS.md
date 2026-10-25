# AGENTS.md — install & run guide for AI coding agents

You were probably given only this repository's URL and asked to "install it" or "run it".
Follow the steps below in order. Every step has a check — verify it before moving on.
Human-oriented docs (in Azerbaijani) are in `README.md` and `docs/`.

**What this is:** ReelMind, a fully local movie recommender trained on MovieLens 1M
(Python/FastAPI backend in `backend/`, React/Vite frontend in `frontend/`). The repository
contains code and reports only: the dataset, trained models and posters are **not** committed
(licence and size) and are recreated by the commands below.

## Requirements

| Tool | Version | Check |
|---|---|---|
| git | any | `git --version` |
| uv (Python manager) | ≥ 0.5 — install: https://docs.astral.sh/uv/getting-started/installation/ | `uv --version` |
| Python | 3.11–3.13 (uv downloads one automatically if missing) | — |
| Node.js + npm | Node ≥ 22.22 | `node --version` |

Resources: ~3 GB free RAM, ~1.5 GB disk, internet for the one-time downloads (~250 MB data,
~90 MB embedding model). CPU only; no GPU, Docker, API keys or accounts are needed.
Ports used: 8010 (backend) and 5173 (frontend).

## Steps

Commands are the same in PowerShell and bash unless noted. Run backend commands inside `backend/`
and frontend commands inside `frontend/`.

1. **Clone** (on Windows into a short path, e.g. `C:\src` — see "If something fails")
   ```bash
   git clone https://github.com/abbas1123/reelmind-recsys
   cd reelmind-recsys
   ```

2. **Backend dependencies** (`backend/`)
   ```bash
   uv sync --extra embeddings
   ```
   Check: `uv run recsys --help` lists `download`, `preprocess`, `train`, `serve`.

3. **Data, embedding model, preprocessing, training, database** (`backend/`, ~10 min on a laptop CPU)
   ```bash
   uv run recsys pipeline
   ```
   This downloads MovieLens 1M + ML-32M metadata (MD5-verified), caches the local
   `all-MiniLM-L6-v2` model, validates/splits the data, tunes and evaluates 11 models
   (~8 min) and saves the serving models.
   For a faster smoke test use `uv run recsys pipeline --quick` (one configuration per model, ~5 min;
   the report is then marked "quick mode").
   Checks:
   - the log contains `Preprocessing finished: 6040 users, 3883 items, 1000209 interactions`;
   - the last line is `Selected model: hybrid`;
   - `uv run recsys evaluate` ends with `"ok": true`.

4. **Backend tests** (`backend/`, optional but recommended)
   ```bash
   uv run pytest -q
   ```
   Expected: all pass after a full (non-quick) `pipeline` run. After `--quick`, one integration test
   fails on purpose (`test_report_contains_real_metrics` rejects quick-mode reports); run
   `uv run pytest tests/unit -q` instead.

5. **Frontend dependencies** (`frontend/`)
   ```bash
   npm install
   ```

6. **Run the app** — two terminals:
   ```bash
   # terminal 1, in backend/
   uv run recsys serve
   # terminal 2, in frontend/
   npm run dev
   ```
   On Windows `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1` starts both.
   Checks: `http://127.0.0.1:8010/api/health` returns `"status":"ok"`; open `http://127.0.0.1:5173`.

7. **Optional extras**
   - Real posters (one-time, keyless, from Wikipedia; Wikimedia rate-limits it, so it can take
     hours; resumable; the UI uses generated artwork meanwhile): `uv run recsys download-posters` in `backend/`.
   - End-to-end tests (`frontend/`, stop the dev backend on 8010 first): `npx playwright test`.
     They use the installed Microsoft Edge; elsewhere run `npx playwright install chromium` and set
     `PW_CHANNEL=chromium`.
   - Temporary public demo link (Windows, needs `cloudflared`): `scripts\demo.ps1`.

## If something fails

| Symptom | Fix |
|---|---|
| `Port 8010 is already in use` / `5173` | Another program uses the port: `uv run recsys serve --port 8020`, then start the frontend with `VITE_API_PROXY=http://127.0.0.1:8020 npm run dev` (PowerShell: `$env:VITE_API_PROXY="http://127.0.0.1:8020"; npm run dev`). |
| `SSL: CERTIFICATE_VERIFY_FAILED` during download | Corporate proxy. The code already uses the OS trust store; see `docs/TROUBLESHOOTING.md`. Do **not** disable TLS verification. |
| Embedding model download fails | The pipeline continues without semantic search; retry later with `uv run recsys download-models`. |
| `FileNotFoundError` from `transformers`, or "sentence-transformers unavailable" (Windows) | The clone path is too long for Windows' 260-character limit (the venv's `transformers` files exceed it). Clone into a short path such as `C:\src\reelmind-recsys`, delete `backend\.venv`, and repeat from step 2. Everything except semantic search still works meanwhile. |
| `failed to remove file ... recsys.exe` (Windows) | A running `recsys` process holds the file: stop it or use `uv run --no-sync ...`. |
| API returns 503 "engine not loaded" | Training has not finished: run step 3. |

## Rules for agents working in this repo

- Never commit `data/`, `artifacts/models/`, `artifacts/posters/` or `.db` files (they are git-ignored for licence and size reasons).
- Never invent metrics: every number shown in the UI and docs comes from `artifacts/reports/model_comparison.json`, written by `recsys train`.
- Keep the TLS verification and the Wikimedia rate-limit handling as they are.
- Gates before proposing a change: `uv run ruff check recsys app tests` and `uv run pytest -q` in `backend/`; `npx tsc -b --noEmit` in `frontend/`.
