# Source Coverage & Limitations

## In scope

| Season | Editions | Status |
|--------|----------|--------|
| Summer | 1960–2024 (17 editions) | Seed registry complete |
| Winter | 1960–2026 (18 editions, incl. Milano Cortina) | Seed registry complete |

Tokyo 2020 keeps official year **2020**; actual competition dates are **2021**.

There is **no** Summer Olympics 2026 edition in this project.

## Sources

| Source | Role | Phase status | Limitations |
|--------|------|--------------|-------------|
| Wikipedia / MediaWiki API | Discovery graph, narrative, tables, Commons assets | **Phase 1 active** — recursive BFS crawler | Community-edited; tables inconsistent; CC BY-SA attribution required; English Wikipedia only in Phase 1 |
| Wikimedia Commons | Logos, posters, venue/athlete images | Metadata via API; downloads gated | License varies per file; must verify edition association |
| olympics.com | Preferred official results & medal standings | Connector scaffolded (Phase 2) | Dynamic site; may need Playwright; ToS/rate limits |
| Olympedia | Athlete bios, results depth | Connector scaffolded (Phase 2) | HTML scrape; structure changes; respect ToS |
| olympic-moderndive-data | Bulk historical CSV | Importer scaffolded (Phase 2) | Third-party; must reconcile — not sole authority |
| dataful.in / other repos | Supplementary historical sets | Planned Phase 2 | Coverage gaps; quality varies |

## Verification vocabulary

- **collected** — retrieved, not cross-checked
- **verified** — matches official / multi-source consensus
- **partially_verified** — some fields confirmed
- **missing** — expected, not yet collected
- **unavailable** — confirmed absent from available sources
- **conflict** — sources disagree

Finishing a scrape does **not** mark an edition complete.

## Known Phase 1 gaps (intentional)

- Athlete identity resolution across editions — Phase 3
- Event results / medal table warehouse load from crawled tables — Phase 3
- Match-level team sport collectors — Phase 4
- Dagster orchestration & Great Expectations suites — Phase 3–5
- Full multi-edition production crawl — run deliberately with conservative rate limits

## Status update (warehouse build, Nov 2026)

| Source | Status | Notes |
|---|---|---|
| Olympedia | Collected | results, rosters (257k), matches (59k) + player stats (216k), venues (1,121, coordinates), Olympic records (2,141), event notes / disqualifications, athlete bios via CSV folder |
| Wikipedia | Collected | recursive BFS crawler (72k pages, 287k links), edition pages, medal tables, venues |
| `athlete_events.csv/` folder | Loaded as `src_*` tables | bios 145k, results 308k, athlete_events 271k, medallists 29k, NOC regions |
| ismayc / rgriffin datasets | Loaded | identical medal data in both (no reallocation signal) |
| olympics.com | **Not collected** | server closes the connection / times out for automated clients; logged in `reports/scraping/failed_pages.csv`, no bypass |
| dataful.in | Not collected | connector stub only |

### Known limitations
- Athlete bios (birth/death dates) exist for ~46% of athletes: the rest could not be matched to an Olympedia profile on name + birth year without guessing.
- `is_shared` only flags ties at 1st/2nd place (tied bronzes are indistinguishable from the two-bronze combat-sport format).
- `reallocation_note` comes from Olympedia event-page prose (doping/re-test disqualifications); ~20% are loose context, not athlete-level certainty.
- Continent is a static IOC-association mapping; ISO alpha-3 is a static IOC->ISO table; historical/neutral delegations have no ISO code.
- Assets (logos, flags, mascots, posters, athlete photos), pictograms for 31 of 35 Games, and the official website field are not collected.
- Database is SQLite; `scripts/migrate_sqlite_to_postgres.py` is provided but has not been run (no Postgres server available). Dagster / Great Expectations are not installed: `scripts/run_pipeline.py` and `backend/validators/expectations.py` are standalone equivalents.

### Reproduce
`python scripts/run_pipeline.py` (offline load/derive/validate/export stages, restartable with `--from STAGE`).
