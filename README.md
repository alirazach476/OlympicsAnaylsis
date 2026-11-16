<div align="center">

# 🏅 Olympics Analysis

### Every Summer (1960–2024) and Winter (1960–2026) Olympic Games — results, matches, medals, countries and athletes, in broadcast style

[![Live site](https://img.shields.io/badge/Live%20site-olympicsanaylsis.vercel.app-0085C7?style=for-the-badge&logo=vercel&logoColor=white)](https://olympicsanaylsis.vercel.app)
&nbsp;
![React](https://img.shields.io/badge/React%2018-TypeScript-3178C6?style=for-the-badge&logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009F3D?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/Warehouse-SQLite%202.7%20GB-DF0024?style=for-the-badge&logo=sqlite&logoColor=white)

**👉 [olympicsanaylsis.vercel.app](https://olympicsanaylsis.vercel.app)**

<img src="docs/screenshots/overview.png" alt="Global overview" width="900" />

</div>

---

## ✨ What it is

A full Olympic history platform built on a hand-built data warehouse: **35 Games**, **132,901 athletes**, **230 NOCs**, **6,547 events**, **16,730 medals** and **67,099 matches**. Every Games looks like itself — its own emblem, artwork, colours, mascots and sport pictograms run through the whole interface, from the menu bar to every table header and scoreboard.

| | |
|---|---|
| 🎨 **Edition themes** | Each of the 39 editions (incl. LA 2028 → Salt Lake 2034, *Coming soon*) restyles the site with colours extracted from its own logo, its background artwork and its emblem. |
| 🏟️ **Games & Results** | Edition → sport pictogram → event → full results, with every round, heat, match and bout as its own page (previous / next navigation, real Olympedia ids). |
| 📺 **Broadcast scoreboards** | Sport-specific boards: football (HT/FT/ET, scorers), basketball line scores, volleyball sets, ice hockey periods, curling ends with the hammer, baseball R-H-E, boxing corners, and TV-style leaderboards for athletics, swimming and gymnastics. |
| 🌍 **Countries & Medal Statistics** | Complete medal table of all 231 NOCs (historical NOCs kept separate), filters for season, years, edition, sport, gender and medal, plus a Visuals page. |
| 🗂️ **Country profiles** | *Visuals* (10 charts) and *Results*: a sidebar of every Games with its logo, and the country's full Olympedia table for any edition. |
| 🧑‍🤝‍🧑 **Athletes & Records** | 132k athletes, career rankings, Olympic and world records — every name, country, sport, event and Games is a link. |
| 📊 **Analytics** | 100+ interactive charts (time series, medals, athletes, sports, statistics, machine-learning backtests, team sports, data engineering). |
| ♿ **Usability** | Filters in the URL (shareable, Back/Forward restore filters and scroll), keyboard-safe dropdowns, phone layouts, dark and light themes, reduced-motion support. |

## 🖼️ Screenshots

| Edition gallery | Event results (pictograms) |
|---|---|
| <img src="docs/screenshots/summer.png" alt="Summer Olympics" /> | <img src="docs/screenshots/sport-events.png" alt="Sport events" /> |
| **Broadcast scoreboard** | **Team standings (squads folded under +)** |
| <img src="docs/screenshots/scoreboard.png" alt="Scoreboard" /> | <img src="docs/screenshots/results-table.png" alt="Results table" /> |
| **Heat / final table** | **Country results by edition** |
| <img src="docs/screenshots/heat-table.png" alt="Heat table" /> | <img src="docs/screenshots/country-results.png" alt="Country results" /> |

## 🏗️ Architecture

```
            ┌──────────────────────────┐   /api/* (rewrite)   ┌───────────────────────────────────┐
 browser ──►│  Vercel · React SPA      │ ────────────────────►│  Vercel · Python function         │
            │  frontend/  (Vite build) │                      │  FastAPI backend/api              │
            └──────────────────────────┘                      │  slim warehouse loaded into RAM   │
                                                              └────────────────▲──────────────────┘
                                                                               │ cold start (~20 s)
                                                     Hugging Face dataset · 264 MB of gzipped SQLite shards
```

* **Frontend** — React 18 · TypeScript · Vite · Tailwind · TanStack Query/Table/Virtual · Recharts · Framer Motion. A central theme engine (`frontend/src/themes`) turns each edition's registry entry (logo, background, palette) into CSS variables used by every surface.
* **Backend** — FastAPI over a SQLite warehouse (`backend/api`): edition event index, event / match / bout / heat pages, medal tables, country results, participants, gender statistics, records, analytics and 100+ chart endpoints. Interactive docs at `/docs`.
* **Warehouse** — bronze → silver → gold layers loaded by the pipeline in `scripts/` and `backend/` from **Olympedia** (results pages, matches, country pages) and **Wikipedia** (editions, assets), with validation checks and provenance on every record. Nothing is invented: missing values stay empty.

## 🚀 Run locally

```bash
# backend (Python 3.12)
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# put the warehouse at data/olympics_warehouse.db (built by the pipeline, see below)
uvicorn backend.api.main:app --port 8000

# frontend
cd frontend
npm install
npm run dev            # http://127.0.0.1:5173  (proxies /api to :8000)
```

**Rebuilding the warehouse.** The 2.7 GB database is not stored in git. It is produced by the pipeline (`python scripts/run_pipeline.py`) which collects, cleans, validates and loads the sources; see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/SOURCE_COVERAGE.md](docs/SOURCE_COVERAGE.md).

## ☁️ Deployment

| Part | Where | How |
|---|---|---|
| Website | **Vercel** (free) — [olympicsanaylsis.vercel.app](https://olympicsanaylsis.vercel.app) | `cd frontend && vercel deploy --prod` · `frontend/vercel.json` rewrites `/api/*` to the API and serves the SPA |
| API | **Vercel** (free, serverless Python) — [olympicsanaylsis-api.vercel.app](https://olympicsanaylsis-api.vercel.app/docs) | `python deploy/vercel-api/prepare.py && cd deploy/vercel-api/build && vercel deploy --prod` |
| Data | **Hugging Face dataset** (free) — [alirazach/olympics-slim](https://huggingface.co/datasets/alirazach/olympics-slim) | `python scripts/build_slim_db.py --gzip`, then upload `data/olympics_slim_*.db.gz` + `data/manifest.json` to `slim/` |

**How the free API fits in Vercel's limits.** The 2.7 GB warehouse keeps every crawl artefact, but the site reads only part of it. `scripts/build_slim_db.py` copies just the tables the API serves, keeps exact row counts for the raw staging tables that are only counted, and zlib-compresses the large JSON columns. The result is about 1 GB of SQLite, split into four shards that gzip to 264 MB. On a cold start the function downloads the shards, deserializes them into one in-memory SQLite connection (the first as `main`, the others `ATTACH`ed) and serves every query from RAM. No value is changed: every API response was compared with the full warehouse, and they match.

## 🧪 Tests

```bash
pytest -q                     # backend API and data checks
cd frontend && npx vitest run # 238 frontend unit + live-API integration tests
```

## 📁 Project structure

```
backend/      FastAPI app, loaders, scrapers, validators, analytics
frontend/     React app (pages, broadcast tables & scoreboards, theme engine, charts)
scripts/      pipeline and build scripts (warehouse, asset registry, coverage)
deploy/       serverless API bundle (vercel-api/) and the older Docker Space files (huggingface/)
docs/         architecture, source coverage, screenshots
reports/      generated data-quality and coverage reports
```

## 📜 Data & credits

Results and biographical data come from [Olympedia](https://www.olympedia.org) and [Wikipedia](https://www.wikipedia.org); edition artwork belongs to its respective organising committees and is used here for a non-commercial, educational project. The Olympic rings are drawn in their official colours as an SVG. This project is not affiliated with the IOC.

<div align="center"><sub>Built with ❤️ for Olympic history · <a href="https://olympicsanaylsis.vercel.app">olympicsanaylsis.vercel.app</a></sub></div>
