# API Documentation

Base URL: `http://localhost:8000`

Interactive docs: `/docs` (Swagger) · `/redoc`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Liveness |
| GET | `/api/overview` | Warehouse + crawl counters |
| GET | `/api/games?season=` | Edition list (`summer` / `winter`) |
| GET | `/api/games/{games_id}` | Single edition |
| GET | `/api/crawler/summary?games_id=` | Queue / page / link totals |
| POST | `/api/crawler/seed` | Insert games + seed Wikipedia URLs |
| POST | `/api/crawler/start` | Start background BFS crawl |
| POST | `/api/crawler/pause` | Write pause file (stops between pages) |
| POST | `/api/crawler/resume` | Clear pause + start |
| GET | `/api/crawler/pages` | Discovered/crawled pages |
| GET | `/api/crawler/links` | Link graph rows |
| GET | `/api/crawler/queue` | Pending/failed queue |
| GET | `/api/crawler/history` | Crawl log |

### Visualization endpoints (`/api/viz`, see `docs/VISUALIZATION_REGISTRY.md`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/viz/registry?section=&page=` | Every chart: id, page, type, dataset, source table, purpose, filters, endpoint, status |
| GET | `/api/viz/chart/{chart_id}?season=&year_from=&year_to=&noc=&nocs=&sport=&games_id=&event=&athlete_ids=&top=&metric=&a=&b=` | Chart payload (`status: ok` or `unavailable` + `reason`); `&format=csv` returns its data table |
| GET | `/api/viz/options` | Filter option lists (editions, nations, sports, record events, team-sport events) |
| GET | `/api/viz/search/athletes?q=` | Athlete picker for career / comparison charts |
| GET | `/api/viz/drilldown?type=country\|sport\|games\|athlete&key=` | Records behind a clicked chart element (`&format=csv` available) |
| GET | `/api/viz/coverage` | Planned-item coverage (implemented / unavailable / pending) from `scripts/build_viz_coverage.py` |

### Start crawl body

```json
{
  "games_ids": ["1960_summer"],
  "max_depth": 2,
  "max_pages_per_edition": 25,
  "min_relevance_score": 0.45
}
```
