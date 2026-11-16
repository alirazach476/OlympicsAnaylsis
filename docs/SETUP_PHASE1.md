# Olympics Historical Data Platform (1960–2026)

Professional data-collection and warehouse project for **Summer (1960–2024)** and **Winter (1960–2026)** Olympic Games, including Milano Cortina 2026. Tokyo 2020 retains its official edition year with actual 2021 dates. Summer and Winter remain distinct everywhere.

This is **Phase 1**: database schema, Olympic edition registry, MediaWiki client, resumable recursive Wikipedia BFS crawler, FastAPI monitor, React dashboard, and automated tests. Later phases add Olympedia/official connectors, ETL, validation, and match-level collectors.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/SOURCE_COVERAGE.md](docs/SOURCE_COVERAGE.md).

## Quick start

### 1. Python environment

```powershell
cd OlympicsAnaylsis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

### 2. PostgreSQL

```powershell
docker compose up -d postgres
python scripts\init_db.py
```

Or with Alembic:

```powershell
alembic upgrade head
python scripts\init_db.py
```

### 3. Smoke-crawl one edition (real Wikipedia API)

```powershell
python scripts\crawl_wikipedia.py --init-schema --games-id 1960_summer --max-depth 1 --max-pages 10
```

Raw JSON lands in `data/raw/wikipedia/pages/1960_summer/`. Reports in `reports/`.

Resume after interrupt: re-run the same command — queue/visited state is in PostgreSQL.

Pause / resume:

```powershell
python scripts\crawl_wikipedia.py --pause
python scripts\crawl_wikipedia.py --resume-clear-pause --games-id 1960_summer --max-depth 1 --max-pages 10
```

### 4. API + dashboard

```powershell
uvicorn backend.api.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — **Wikipedia Crawler** page controls seed/start/pause/resume against the live API.

API docs: http://localhost:8000/docs

### 5. Tests

```powershell
pytest backend/tests -q
```

## Wikipedia crawler (design)

1. Seed every edition page (e.g. `1960 Summer Olympics`).
2. MediaWiki `action=query` + `action=parse` (info, extracts, categories, links, images, revisions, HTML tables).
3. Score relevance; enqueue only Olympic-related links.
4. BFS with depth / pages-per-edition caps; persist queue, pages, links, history.
5. Save excluded links + reasons; never wipe prior data.
6. Identifiable User-Agent, delay, maxlag, Retry-After, exponential backoff, response cache.

## Project layout

See the tree under `backend/`, `frontend/`, `data/`, `assets/`, `reports/`, `dbt/`, `scripts/`, `docs/`.

## Rules of the road

- No fake medal totals or synthetic “complete” dashboards.
- No inventing athlete height/weight/DOB.
- Historical NOCs (URS, GDR, etc.) stay distinct from modern countries.
- Official sources preferred for standings; Wikipedia is discovery + structured extraction with CC BY-SA attribution.

---

# Olympic Sports Intelligence Platform (analytics layer)

Medallion architecture (Bronze -> Silver -> Gold), statistics, ML, a FastAPI backend and a React/TypeScript dashboard on top of the collected 1960-2026 data.
Metric definitions and methods: [docs/ANALYTICS_METRICS.md](docs/ANALYTICS_METRICS.md). Data audit: `reports/data_inventory/`, `reports/data_quality/`, `reports/data_completeness/`.

## One-time setup
```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-analytics.txt
cd frontend ; npm install ; cd ..
python scripts/sync_assets.py         # indexes your logos/backgrounds/pictograms into frontend/public/assets
```

## Build everything (restartable, idempotent)
```powershell
python scripts/audit_inventory.py      # Milestone 1: inventory + quality audit (read-only)
python scripts/fix_noc_registry.py     # registry repair (EUA/IOP/OAR, aliases)
python scripts/extract_podium_results.py   # podium result strings from cached Olympedia pages
python scripts/build_medallion.py      # Silver + Gold marts (incremental per Games; --full to force)
python scripts/run_analytics.py        # EDA, statistics, sports modules, ML  (--only eda,stats,sports,ml)
python scripts/optimize_db.py          # indexes + ANALYZE
python scripts/run_validation.py       # 20+ expectation checks -> reports/quality/validation_results.csv
# or all orchestrated as Dagster assets:
python scripts/run_dagster.py          # headless;   dagster dev -m backend.pipeline.dagster_defs   for the UI
```

## Run the platform
```powershell
uvicorn backend.api.main:app --port 8000      # API docs: http://127.0.0.1:8000/docs
cd frontend ; npm run dev                      # http://localhost:5173  (proxies /api)
mlflow ui --backend-store-uri mlruns           # experiment tracking
```

## Visualization library (111 interactive charts)
Open **Visualization Library** in the dashboard (`/visualizations?section=1..8`) or the collapsible section at the bottom of every dashboard page. Every chart is a registered builder in `backend/viz/` that reads
the Gold / Silver layers or a stored analysis (nothing is simulated) and returns a standard payload: data, axes, a how-to-read note, a data table and the filters it honoured. A chart the data cannot support
returns "unavailable" with the reason instead of a fake plot.
* Eight sections: time series, countries & medals, athletes, sports & events, statistics, machine learning, team sports, data engineering.
* Every card: hover tooltips, legend toggling, shared filters (season, year range, nations, sport, edition, athletes), zoom / pan (brush, map wheel + drag, 3D rotate), cross-filtering and drill-down to records, view switching
  where the same data has several valid forms, data-table toggle, CSV / PNG / SVG export, full-screen mode, and loading / error / no-data states.
* `python scripts/build_viz_coverage.py` executes every chart (default + Summer / Winter / since-2000 filters) and writes `reports/visualization/coverage_report.md|csv`, `visualization_registry.csv` and
  `docs/VISUALIZATION_REGISTRY.md` (chart ID, page, type, dataset, source table, purpose, filters, endpoint, status; each planned item is implemented, unavailable or pending).
* ML artifacts behind the curves, SHAP, learning curve, cross-validation, dendrogram and 3D PCA are produced by `python scripts/run_analytics.py --only ml`.

## Tests
```powershell
python -m pytest -q                     # data, statistics maths, ML leakage, API (needs the built warehouse)
cd frontend ; npm run typecheck ; npm test   # unit + live-API integration tests (start the API first; files run sequentially)
```

## Honest status
* **Database**: SQLite (`data/olympics_warehouse.db`). `scripts/migrate_sqlite_to_postgres.py` copies it to PostgreSQL (not run here - no Postgres server).
* **dbt**: models + tests are in `dbt/` (same logic as the Python marts) but have not been executed (dbt adapter not installed). The Python build is the executed path.
* **Great Expectations** is not installed: `backend/validators/expectations.py` provides equivalent expectation checks.
* ML results are **historical backtests**; nothing is a forecast of a future Games.
