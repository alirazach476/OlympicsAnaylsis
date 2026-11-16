# CSV export audit and responsive test (interactions)

Run 2026-11-14 17:45 in headless Chrome against the running app.

## CSV on every table
Every route and every tab was opened and every `<table>` checked for a CSV button in its own scope: **85 views, 64 tables, 0 without CSV.**

| Route | Tab | Tables | Without CSV |
|---|---|---|---|
| `/` | (default) | 1 | 0 |
| `/medals` | (default) | 1 | 0 |
| `/medals` | All-time leaderboard | 1 | 0 |
| `/medals` | By edition | 1 | 0 |
| `/records` | (default) | 1 | 0 |
| `/records` | Record book | 1 | 0 |
| `/records` | Record progression | 1 | 0 |
| `/records` | Most decorated & careers | 2 | 0 |
| `/sports` | (default) | 1 | 0 |
| `/sports` | Sport catalogue | 1 | 0 |
| `/sports` | Sport science (results progression) | 1 | 0 |
| `/athletes` | (default) | 1 | 0 |
| `/athletes/72064` | (default) | 2 | 0 |
| `/countries` | (default) | 1 | 0 |
| `/results` | (default) | 1 | 0 |
| `/team-sports` | Standings | 1 | 0 |
| `/team-sports` | Historical performance | 1 | 0 |
| `/edition/2024_summer` | (default) | 1 | 0 |
| `/edition/2024_summer` | Medal standings | 1 | 0 |
| `/edition/2024_summer` | Sports & disciplines | 1 | 0 |
| `/edition/2024_summer` | Event results | 1 | 0 |
| `/edition/2024_summer` | Records | 1 | 0 |
| `/edition/2024_summer` | Venues | 1 | 0 |
| `/edition/1964_winter` | (default) | 1 | 0 |
| `/edition/1964_winter` | Medal standings | 1 | 0 |
| `/edition/1964_winter` | Sports & disciplines | 1 | 0 |
| `/edition/1964_winter` | Event results | 1 | 0 |
| `/edition/1964_winter` | Records | 1 | 0 |
| `/edition/1964_winter` | Venues | 1 | 0 |
| `/compare` | Countries | 1 | 0 |
| `/compare/countries` | (default) | 1 | 0 |
| `/compare/countries` | Countries | 1 | 0 |
| `/assets` | (default) | 1 | 0 |
| `/engineering` | (default) | 2 | 0 |
| `/engineering` | Pipeline & layers | 2 | 0 |
| `/engineering` | Validation | 1 | 0 |
| `/engineering` | Completeness | 1 | 0 |
| `/engineering` | Medal reconciliation | 1 | 0 |
| `/engineering` | Audit findings | 2 | 0 |
| `/statistics` | Interactive explorer | 1 | 0 |
| `/statistics` | Descriptive | 1 | 0 |
| `/statistics` | Correlation | 1 | 0 |
| `/statistics` | Regression | 4 | 0 |
| `/statistics` | Outliers | 1 | 0 |
| `/machine-learning` | (default) | 1 | 0 |
| `/machine-learning` | Country medal prediction | 1 | 0 |
| `/machine-learning` | Athlete medal probability | 1 | 0 |
| `/machine-learning` | Country clustering | 1 | 0 |
| `/machine-learning` | Sport specialisation | 2 | 0 |
| `/visualizations` | Registry & coverage | 2 | 0 |
| `/crawler` | (default) | 4 | 0 |

## Responsive
72 page loads (24 routes x phone 390px, tablet 768px, desktop 1400px), including `/compare/countries` and a filtered edition page: **0 with sideways scroll, broken images, script errors or failed requests.** `/edition/2028_summer` answers 404 for /api/games/2028_summer by design (no data yet) and the page handles it.
