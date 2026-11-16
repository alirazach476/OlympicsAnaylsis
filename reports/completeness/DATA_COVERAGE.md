# Data coverage report (1960–2026)

Interpreted request range: **1960–2026** (not 19260–20206).

## Loaded into warehouse (`data/olympics_warehouse.db`)

Source: `athlete_events_through_2026.csv` (Olympedia-derived curated dataset via [ismayc/olympic-moderndive-data](https://github.com/ismayc/olympic-moderndive-data)).

| Entity | Count | Status |
|--------|------:|--------|
| Games (Summer+Winter editions) | 35 | collected |
| Athletes | 125,500 | collected |
| Athlete participations / event results | 253,050 | collected |
| Sports | 54 | collected |
| Events | 5,383 | collected |
| Medal awards (athlete-level) | 32,715 | collected |
| NOC medal table aggregates | 1,472 | collected (athlete-event aggregate; **not** official IOC standings) |
| Historical NOCs | 228 | collected |

All editions from **1960 Summer** through **2024 Summer** and **2026 Winter (Milano Cortina)** have athlete/event rows.

CSV exports: `data/exports/*.csv`

## Still missing / incomplete

- Official IOC / olympics.com verified medal tables (current tables are athlete-event aggregates; team sports over-count)
- Match-level team sport fixtures/lineups
- Venues, mascots, logos/assets library
- Full round/heat result values (times/distances) — CSV has placements/medals, not all timed marks
- Wikipedia page graph for every edition (crawl in progress / partial)
- Live Olympedia HTML scrape reconciliation
- 2026 Winter: dataset includes entries, but Games may still be incomplete vs final official results depending on scrape date

Verification status of loaded rows: **`collected`** (not auto-marked `verified`).
