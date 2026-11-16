# Broadcast design system: final acceptance report

Run 2026-11-14 18:37 in headless Chrome against the running app and API (real warehouse data). Each example was opened at desktop (1400px) and phone (390px) width.

## The five required examples

| Example | Emblem | Theme colour | Verified pictograms on page | Broadcast element | Real data on page | Desktop | Phone |
|---|---|---|---|---|---|---|---|
| Paris 2024 · Athletics · Men's 100 m results | Paris 2024 emblem | `#d6c278` | 45 | podium cards + results table | 3 cards | ok | ok |
| Tokyo 2020 · Swimming · medal results | Tokyo 2020 emblem | `#0240bd` | 83 | medal winners (medal chips) | 117 medal chips | ok | ok |
| Beijing 2022 · Ice Hockey · match scoreboard | Beijing 2022 emblem | `#1f4c97` | 60 | scoreboard cards | 58 cards | ok | ok |
| London 2012 · Basketball · match results | London 2012 emblem | `#cd0168` | 16 | match results table | 28 table rows | ok | ok |
| Milano Cortina 2026 · winter sports · edition page | Milan and Cortina d'Ampezzo 2026 emblem | `#06ae55` | 16 | sports table with pictograms | 17 table rows | ok | ok |

Every row checks: the selected edition id on the page background equals the requested edition, the edition emblem is in the page header, the sport pictograms come from that edition's own folder, no sideways scroll, no broken images, no failed requests or script errors.

## Switching editions
The vitest acceptance suite selects Paris 2024, then Tokyo 2020 in the sidebar switcher on the results page and asserts that the page background edition, the header emblem and the pictogram files all change (`broadcast.test.tsx`, 'switching the selected edition restyles the whole page').

## Tables
112 views (every route and every tab, plus sport pills on the team-sports page) were opened: **70 tables, 0 without a CSV button, 0 outside the broadcast frame.**

## Responsive
78 page loads (26 routes x phone, tablet, desktop): **0 with sideways scroll, broken images, script errors or unexpected failed requests.** `/edition/2028_summer` answers 404 for /api/games/2028_summer by design (those Games have no data) and the page handles it.

## What is and is not shown (data honesty)
- Scoreboards show only what the saved match page records: score, labelled periods / sets, team totals, goals (side from the line-ups or the running score), cards, line-ups, officials. No match clock, live status, shots or fouls are invented when the page does not have them.
- Football's 'Half #n' values are running scores after each half; basketball, handball, hockey, water polo and volleyball list per-half, per-period or per-set points. Each scoreboard labels its own convention.
- A record badge (WR/OR) appears only when the record book lists that athlete, event and value.
- A pictogram is shown only when its file name verifiably names the sport; otherwise a neutral icon is shown and marked unavailable.

