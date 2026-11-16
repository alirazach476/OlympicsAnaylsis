# Responsive test: redesigned pages (phases 5, 7, 8 and 9)

Run 2026-11-14 17:11 in headless Chrome against the running app and API: 22 routes at phone (390px), tablet (768px) and desktop (1400px).

Checks per page: has a heading, no sideways scroll, no broken images, no failed requests or script errors.

| Route | Phone | Tablet | Desktop |
|---|---|---|---|
| `/` | ok | ok | ok |
| `/statistics` | ok | ok | ok |
| `/machine-learning` | ok | ok | ok |
| `/engineering` | ok | ok | ok |
| `/summer` | ok | ok | ok |
| `/winter` | ok | ok | ok |
| `/edition/2024_summer` | ok | ok | ok |
| `/edition/1964_winter` | ok | ok | ok |
| `/edition/2028_summer` | ok | ok | ok |
| `/countries` | ok | ok | ok |
| `/countries/GER` | ok | ok | ok |
| `/countries/URS` | ok | ok | ok |
| `/athletes` | ok | ok | ok |
| `/athletes/72064` | ok | ok | ok |
| `/sports` | ok | ok | ok |
| `/sports/1` | ok | ok | ok |
| `/team-sports` | ok | ok | ok |
| `/compare` | ok | ok | ok |
| `/assets` | ok | ok | ok |
| `/results` | ok | ok | ok |
| `/medals` | ok | ok | ok |
| `/records` | ok | ok | ok |

**66 page loads, 0 with a problem.** `/edition/2028_summer` requests /api/games/2028_summer, which correctly answers 404 because those Games have no data; the page handles it and shows a themed page with a note.
