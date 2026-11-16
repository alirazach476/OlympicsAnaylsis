# Olympics Historical Data Platform (1960–2026) — Architecture

## Goal

Build a resumable, source-provenance-first data warehouse for Summer (1960–2024) and Winter (1960–2026) Olympic Games. Every record carries source URLs, license metadata where applicable, and a verification status. Fake or hardcoded “collected” totals are forbidden.

## Scope rules

| Season | Years | Notes |
|--------|-------|-------|
| Summer | 1960–2024 | Tokyo 2020 keeps edition year 2020; actual dates 2021 |
| Winter | 1960–2026 | Includes Milano Cortina 2026 |
| — | — | No Summer 2026 edition |

Summer and Winter remain distinct (`season` + `games_id`) everywhere.

## Phases

### Phase 1 — Foundation (this implementation)
1. Project scaffold, Docker Compose (PostgreSQL), config
2. Normalized SQLAlchemy models + Alembic
3. Olympic editions master registry (seeds)
4. MediaWiki API client (etiquette, maxlag, backoff, cache)
5. Recursive BFS Wikipedia crawler (queue, visited, relevance, resume)
6. Generic table/link/infobox extraction → `data/raw/`
7. FastAPI monitoring API + React crawler dashboard
8. Smoke tests on a small seed set

### Phase 2 — Multi-source extract
- Olympedia connector
- olympics.com connector (structured pages where permitted)
- Historical CSV/JSON dataset importers (moderndive, dataful, etc.)
- Asset downloader (Commons + verified source pages)

### Phase 3 — Transform / validate / load
- Name/NOC/sport normalization
- Athlete identity resolution across editions
- Great Expectations / custom validators
- dbt staging → intermediate → marts
- Completeness & quality report generators

### Phase 4 — Domain collectors
- Event results, medals, venues, records
- Team sports match-level collectors
- Cross-source reconciliation

### Phase 5 — Hardening
- Dagster orchestration
- Full edition crawl + integration tests
- Coverage/limitations documentation

## Data layers (never mix)

```
data/raw/          # immutable source dumps (HTML/JSON/CSV)
data/staging/      # lightly typed, still source-shaped
data/processed/    # normalized intermediate
data/cleaned/      # validated, ready for warehouse load
data/exports/      # analytics extracts
```

## Wikipedia crawler design

```
Seeds (edition pages)
  → MediaWiki query (info, extracts, categories, links, images, revisions)
  → Relevance scorer (title/category/context + edition association)
  → BFS queue (depth, parent, edition, status)
  → Persist page + links + raw JSON
  → Discover children → enqueue if score ≥ threshold
  → Checkpoint after each page (resume-safe)
```

**Controls:** `max_depth`, `max_pages_per_edition`, `min_relevance_score`, include/exclude categories, retries, pause/resume.

**Safety:** identifiable User-Agent, sequential/low concurrency, Retry-After, exponential backoff on 429/503, `maxlag`, response cache, no access bypass.

## Database domains

- **Master:** games, countries, historical_nocs, sports, disciplines, events
- **People/teams:** athletes, athlete_participations, teams, team_members
- **Results:** event_results, medals, medal_tables, matches, match_results, match_statistics, records
- **Assets:** venues, mascots, assets
- **Provenance:** sources, source_pages, data_quality_reports
- **Crawl:** wikipedia_pages, wikipedia_links, crawl_queue, crawl_history

## Stack

Python · Requests · BeautifulSoup · MediaWiki API · Playwright (only if needed) · Pandas/Polars · PostgreSQL · SQLAlchemy · Alembic · Pydantic · FastAPI · React · dbt · Dagster (phase 5) · Great Expectations (phase 3)

## Verification status vocabulary

| Status | Meaning |
|--------|---------|
| `collected` | Retrieved from a source, not yet cross-checked |
| `verified` | Matches authoritative/official source or multi-source consensus |
| `partially_verified` | Some fields confirmed; gaps remain |
| `missing` | Expected but not yet collected |
| `unavailable` | Confirmed not present in available sources |
| `conflict` | Sources disagree; needs human review |

## Authority preference

1. Official Olympic records / olympics.com (results & medal standings)
2. Olympedia
3. Wikipedia / Commons (discovery, narrative, assets, structured tables)
4. Curated historical datasets (import + reconcile; never sole authority)
