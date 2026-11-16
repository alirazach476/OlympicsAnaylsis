# Olympedia-style platform rebuild: audit, changes, coverage, tests

Generated 2026-11-15 from the warehouse `data/olympics_warehouse.db`. Every number below was measured, not estimated.

## 1. Audit: what the warehouse already held

| Source table | Rows | What it is |
|---|---|---|
| `olympedia_pages` | 86,376 (5,577 events · 13,700 phases · 67,099 matches) | Every saved Olympedia results page: title, breadcrumb, header facts (`meta_json`: Date, Status, Location, Participants, Format, referees …), dropdowns |
| `olympedia_page_tables` | 211,403 | Every table of every page as it appears, with cell links (`athletes`, `results`, `countries`) |
| `olympedia_matches` | 67,100 | Team / duel summary per match page (teams, NOCs, score, periods) |
| `olympedia_round_results` | 885,761 | One row per competitor per ranking table (rounds, heats, pools) |
| `olympedia_country_results` | 182,302 | Country → Games → event → athlete → position / medal |
| `silver_medal_awards` | 16,730 | One podium place per NOC per event (the medal-table source) |

**What was missing:** the pages and tables were saved, but the app had no route for an event page, a match page or a heat page. Its "Match #" cells were plain text or linked out to Olympedia. Athlete cells linked to Olympedia because there was no map from Olympedia ids to warehouse ids. Medals by country could not be filtered by gender, medal or year range. There was no per-edition page for a country.

## 2. Schema changes (with provenance)

Both tables are built by `scripts/build_page_links.py`, pipeline stage `page_links`, which runs after `round_results`.

* **`olympedia_page_links`** has 94,489 rows. Each row is one link from a saved event or phase page to another results page. Columns: `parent_id`, `child_id`, `relation`, `table_index`, `row_index`, `section`, `label` (exactly as on the page), `child_kind`, `child_saved` and `source_url`. The `relation` column takes three values:
  * `table`: a Match # or heat cell (67,273)
  * `dropdown`: a Parts or Lift select (13,520)
  * `standings`: a phase page's parent (13,696)

  **All 94,489 links point to a saved page.**
* **`olympedia_athlete_xref`** has 124,926 rows. It maps each Olympedia athlete id to a warehouse `athletes.athlete_id`, using `identity_key` or the Kaggle id maps. It resolves **97.1 %** (124,914 of 128,626) of the distinct athlete ids that appear in the saved tables. The other 2.9 % still link to Olympedia, so no cell is a dead link.
* New validation check `olympedia_page_links_resolve`. The check total is now **37, and all 37 pass** (including `olympedia_event_descriptions`).

## 3. Routes (frontend)

| Route | Page |
|---|---|
| `/olympics`, `/olympics/summer`, `/olympics/winter` | Edition hub. Every edition links to its event index; editions from 2028 on are marked "not yet held" |
| `/games/:editionId` | Edition overview (existing page), now with links to all events and to the medal table |
| `/games/:editionId/results` | Event index: sports with pictograms, every event, search, sport, gender and sort, all kept in the URL |
| `/games/:editionId/sports/:sport` | The same index for one sport |
| `/games/:editionId/events/:eventId` | Event results page: header facts, podium, Stage dropdown and tabs (`?stage=`), Parts dropdowns, every table, previous and next event |
| `/games/:editionId/events/:eventId/matches/:matchId` | Team match: broadcast scoreboard, team stats, line-ups, officials, every table, previous/next with "n of N" |
| `/games/:editionId/events/:eventId/bouts/:boutId` | Bout or duel: competitors, score, every table (Match Result, techniques …), previous/next |
| `/games/:editionId/events/:eventId/heats/:heatId` | Heat, part or standings page, with its own Parts dropdown and previous/next |
| `/medals/countries` | Medals by country with filters for season, from and to year, edition, NOC, sport, gender and medal; sortable columns, paging and CSV export |
| `/medals/editions/:editionId` | The same table for one edition |
| `/countries/:noc/editions/:editionId` | One NOC at one edition: sport → event → athlete → position, status and medal. Includes every non-medal result, with filters and CSV |

Every routed page draws a full breadcrumb, for example Home › Olympic Games › Tokyo 2020 › 3x3 Basketball › 3 × 3 Basketball, Men › Round-Robin › Match #1. Every item but the last is a link.

## 4. API (`backend/api/olympic.py`)

| Endpoint | Returns |
|---|---|
| `GET /api/games/{id}/events` (alias `/results`, `/sports/{sport}`) | Events grouped by sport; filters `sport`, `gender`, `q` |
| `GET /api/events/{id}` | Page, tables with routed links, stages, parts, siblings, medals, counts |
| `GET /api/events/{id}/stages`, `/results`, `/standings` | Slices of the event page |
| `GET /api/subpages/{id}`, `/api/bouts/{id}`, `/api/heats/{id}` | Match, bout or heat page, owning event, previous/next, scoreboard flag |
| `GET /api/matches/{id}` (existing) | Team scoreboard detail |
| `GET /api/medals/countries` | Filtered medal table, `format=csv`, with the counting convention |
| `GET /api/medals/editions/{id}` | One edition's medal table |
| `GET /api/countries/{noc}/editions` and `/countries/{noc}/editions/{id}` | A country's editions; a country at one edition |
| `GET /api/assets/editions/{id}` | Edition record from the asset registry |
| `GET /api/data-quality/coverage` | The per-edition coverage table below |

**Medal convention**, shown on the page and returned by the API: one medal per podium place per NOC per event (a team or crew medal counts once; tied places each count). Historical NOCs are kept as recorded and never merged: URS, EUN, RUS, ROC, OAR, AIN, GDR, FRG, EUA and GER are separate rows. Check: Paris 2024 gives USA 40 / 44 / 42, the official count.

## 5. Coverage per edition

| Edition | Event pages | Official events | Phase pages | Match pages | Tables | Sub-page links | Country rows | Medals |
|---|---|---|---|---|---|---|---|---|
| 1960_summer | 150 | 150 | 374 | 2962 | 7928 | 3710 | 5920 | 461 |
| 1960_winter | 27 | 27 | 73 | 30 | 294 | 176 | 935 | 81 |
| 1964_summer | 190 | 163 | 391 | 2500 | 7254 | 3282 | 5615 | 501 |
| 1964_winter | 38 | 34 | 105 | 64 | 537 | 274 | 1426 | 103 |
| 1968_summer | 187 | 172 | 399 | 2849 | 8269 | 3647 | 6578 | 527 |
| 1968_winter | 36 | 35 | 115 | 46 | 468 | 276 | 1476 | 104 |
| 1972_summer | 205 | 195 | 550 | 3250 | 9744 | 4351 | 7618 | 600 |
| 1972_winter | 35 | 35 | 133 | 31 | 367 | 297 | 1257 | 105 |
| 1976_summer | 198 | 198 | 521 | 3074 | 9132 | 4113 | 6197 | 613 |
| 1976_winter | 37 | 37 | 207 | 36 | 475 | 450 | 1407 | 111 |
| 1980_summer | 203 | 203 | 527 | 2238 | 7336 | 3289 | 4983 | 631 |
| 1980_winter | 38 | 38 | 209 | 35 | 474 | 453 | 1327 | 115 |
| 1984_summer | 228 | 221 | 567 | 3095 | 9598 | 4229 | 6950 | 685 |
| 1984_winter | 43 | 39 | 146 | 36 | 423 | 328 | 1664 | 117 |
| 1988_summer | 270 | 237 | 612 | 4813 | 13958 | 6036 | 8847 | 738 |
| 1988_winter | 68 | 46 | 165 | 106 | 800 | 436 | 2434 | 138 |
| 1992_summer | 286 | 257 | 582 | 4287 | 13416 | 5451 | 9369 | 813 |
| 1992_winter | 65 | 57 | 151 | 84 | 702 | 386 | 2878 | 171 |
| 1994_winter | 61 | 61 | 157 | 46 | 595 | 360 | 2455 | 183 |
| 1996_summer | 273 | 271 | 630 | 4144 | 12717 | 5404 | 9615 | 841 |
| 1998_winter | 68 | 68 | 168 | 118 | 866 | 454 | 2668 | 205 |
| 2000_summer | 302 | 300 | 836 | 3919 | 12877 | 5591 | 9565 | 925 |
| 2002_winter | 78 | 78 | 178 | 155 | 1086 | 511 | 3087 | 233 |
| 2004_summer | 303 | 301 | 811 | 4196 | 13371 | 5817 | 9343 | 926 |
| 2006_winter | 84 | 84 | 95 | 156 | 1084 | 346 | 3301 | 252 |
| 2008_summer | 317 | 302 | 815 | 4656 | 14189 | 6286 | 9595 | 957 |
| 2010_winter | 86 | 86 | 105 | 149 | 1087 | 359 | 3354 | 258 |
| 2012_summer | 302 | 302 | 884 | 4692 | 13193 | 6460 | 9091 | 961 |
| 2014_winter | 98 | 98 | 136 | 151 | 1202 | 423 | 3686 | 295 |
| 2016_summer | 306 | 306 | 860 | 4970 | 13504 | 6690 | 9568 | 972 |
| 2018_winter | 102 | 102 | 142 | 200 | 1356 | 481 | 3745 | 307 |
| 2020_summer | 339 | 339 | 866 | 4947 | 15751 | 6679 | 9563 | 1080 |
| 2022_winter | 109 | 109 | 170 | 220 | 1492 | 560 | 3787 | 328 |
| 2024_summer | 329 | 329 | 858 | 4639 | 14356 | 6355 | 9066 | 1044 |
| 2026_winter | 116 | 116 | 162 | 205 | 1502 | 529 | 3932 | 349 |

Every held edition has an event page for each official event. Where there are more event pages than official events (1964–1992, 2008), Olympedia also lists demonstration events and separate discipline pages; these carry their Status, for example "Demonstration", in the header.

## 6. Missing data

* **Event descriptions:** fixed on 2026-11-15. `scripts/load_olympedia_page_text.py` (pipeline stage `olympedia_page_text`) reads the `div.description` paragraphs from the Olympedia pages the crawler had already cached in `data/raw/olympedia/editions/`; nothing new was fetched. Results:
  * 5,572 of 5,577 event pages now show Olympedia's text word for word, in the new table `olympedia_page_text`. The 5 without one are tennis pages (90016742–90016770) that have no description on Olympedia either.
  * The same pass fixed a loader bug: each round's own Date and Format lines used to overwrite the event's header facts. Header facts were corrected on 4,062 pages, for example Tokyo 3x3 Men now shows "24 – 28 July 2021" instead of the final's start time.
  * Each round's own facts are now kept separately, on 4,206 pages, and shown above that round's tables.
  * New validation check `olympedia_event_descriptions`, which requires at least 99%.
* **Athlete links:** 3,712 Olympedia athlete ids (2.9 %) have no warehouse athlete. Their cells link to the Olympedia athlete page.
* **Bouts:** individual-sport match pages record what Olympedia shows, for example "bye", winner only, or Match Result rows. Score and technique tables appear only where the page has them.
* **Future editions** (2028 onwards) have no results. They appear in the hub as "not yet held" and never become the app-wide selection.

## 7. Test results

* **Browser acceptance:** 24 of 24 checks pass. The script is puppeteer driving Chrome against the live app.
  * **T1:** Tokyo 2020 → 3x3 Basketball → Men. The page has header facts, a 3-NOC podium, 6 tables and 34 linked Match # cells.
  * **T2:** Match #1 has a scoreboard, team stats and breadcrumbs; it shows "1 of 34", and next and back both work.
  * **T3:** a boxing bout routes to `/bouts/`.
  * **T4:** the Stage dropdown writes `?stage=`, survives a refresh, and Back restores it. The index filters read from the URL. The Parts dropdown opens the part page.
  * **T5:** Paris 2024 shows USA 40/44/42/126. Winter sorted by total puts NOR first. URS and RUS are separate.
  * **T6:** Germany at Tokyo 2020 shows 350 entries; the no-medal filter leaves 313.
  * **T7:** the event index loads for 1960 S and W, 1980 S, 1994 W, 2008 S and 2026 W.
  * **T8:** no horizontal scroll at 390 px.
  * **T9:** no console or runtime errors.
* **Backend:** pytest, 105 passed, including 8 new platform tests.
* **Frontend:** vitest, 232 passed, including the new `olympic.test.tsx`: ring colours and interlace, breadcrumbs, and Match # cells that link only when the target exists.
* **Warehouse validation:** 36 of 36 checks pass.

## 8. Limitations

* **Scope of the rebuild:** these pages read data that was already saved. No new crawl was run, so the robots, rate-limit and access rules of the existing crawler still apply unchanged.
* **Team vs bout routing:** the split is a fixed list of team sports (`TEAM_SPORTS` in `olympic.py`). A match id opened under the wrong segment still renders correctly, because both routes use the same page.
* **Gender:** derived from the event title ("Men", "Women", "Mixed", or "Open" otherwise), as Olympedia names its events.

## 9. Broadcast boards, named tables and the all-edition visual check (2026-11-15)

**New components:** `frontend/src/components/tables/OlympediaTables.tsx`, with all names exported from `components/tables/broadcast.tsx`.

| Component | Used for |
|---|---|
| `BroadcastHeatTable` | Heats, rounds, semi- and quarter-finals: place discs, lane and bib chips, flags, the mark in display type, Q / q / QB / FA badges, an accent edge on qualified rows |
| `BroadcastResultsTable` | Final standings: place discs in medal colours, medal-coloured marks and row edges |
| `BroadcastRankingTable` | Other standings (pools, groups) |
| `BroadcastMatchTable` / `BroadcastBoutTable` | Match lists: Match # link, both sides with flags, a score box with the winner highlighted (bouts for individual sports) |
| `BroadcastBoutBoard` | Scoreboard on every bout page. It shows: both competitors with flags, corner colour and seed; the main score (judges favouring, games, sets, touches, set points, classification points or score, whichever the page has); a breakdown by judge, game, set, round or period; other numbers as bars; and the Match Result line. Byes show one competitor and no score |
| `BroadcastMedalTable` / `BroadcastCountryTable` / `BroadcastAthleteTable` | Medals by country, a country at one edition, athlete rankings |

Rules the renderers follow:
* Every saved column is kept; the renderers only change how cells look.
* Record badges (OR, WR, OB, =OR …) appear only where the Olympedia table prints them.
* A winner is highlighted only when both main scores are numbers and differ.

**Canonical URLs:** an event or match link containing the wrong edition or event id now redirects to the right address, so the edition theme always matches the data.

**Visual sweep** (puppeteer with Chrome, desktop 1440 px and phone 390 px), covering 464 pages:
* 35 editions × 6 pages: overview, event index, an event, a match / bout / heat, the medal table, a country at the edition.
* Plus 22 general pages.

Checks on every page: runtime errors, error boxes, horizontal overflow, broken images, and whether the edition theme applied matches the edition.

* **First run:** 62 issues, all fixed:
  * duplicate React keys: repeated stage names such as "Group A" on some event pages, and repeated palette colours on the edition and asset pages
  * a missing key on the world map
  * one Paris 2024 pictogram that was a WebP file named `.svg`; the registry now uses the real `.webp` and skips mislabelled copies
  * a 10 px phone overflow in the previous / next bar
* **Second run:** **0 issues.** 35 of 35 editions show their own palette colours.

Tests: backend 106 passed. Frontend 238 passed on two consecutive runs; one earlier run had 2 failures, timed with the API restart, which did not repeat. Browser acceptance 27 of 27.

## 10. Site redesign, navigation and "Coming soon" (2026-11-16)

**Menu (10 items):** Global Overview, Summer Olympics, Winter Olympics, Games & Results, Sports, Medal Statistics, Countries, Athletes, Analytics, Records.
Asset Completeness, Wikipedia Crawler and Data Engineering are no longer in the menu. Their routes (`/assets`, `/crawler`, `/engineering`) still work for admin use. The analytics sub-pages (visualization library, medal analytics, statistics, machine learning, team sports, compare, engineering) are linked from a strip on every Analytics page. An edition page highlights its season in the menu.

**Pages redesigned**
- **Overview:** large Olympic rings on a plain background (no photograph); 8 global stats; the full Summer and Winter edition galleries with emblems; titled chart sections shown directly, with no dropdowns.
- **Summer and Winter:** every edition of the season as a medium emblem tile (city, year, host flag, athletes, NOCs, events). Upcoming Games say **Coming soon**. The season's charts are shown directly; the old `href="#…"` timeline that made the page jump is removed.
- **Edition page:** hero with the large emblem, the edition background under an edition-colour overlay, and the mascot standing on the right. Seven sections in `?tab=`: Medal Standings, Participants, Sports & Disciplines, Event Results, Records, Venues, Gender Statistics. Mascot and Pictograms tabs are removed. Tables are complete and scroll inside a virtualized area; no rows are dropped.
  - **Participants:** every entry (Tokyo 2020: 14,884 entries, 11,868 athletes), with NOC, sport and gender filters kept in the URL.
  - **Event Results:** edition pictogram cards; a card shows that sport's events, each linking to its results page.
  - **Gender Statistics:** overall counts, the season's progression, and complete tables by sport, by NOC and by event.
- **Upcoming Games (2028, 2030, 2032, 2034):** a themed edition page with the emblem and background and a Coming soon panel. No data is invented.
- **Games & Results:** gallery of all 39 editions. An edition's results index shows pictogram cards, then a sport's events, then the event results, then match, bout and heat pages.
- **Sports:** pictogram cards grouped into Summer and Winter, then the full catalogue table and the results-progression module. A sport's page lists every edition it appeared in, each linking to that edition's events.
- **Medal Statistics:** the complete table (157 NOCs; paging removed), a clear-filters button, and every filter in the URL.

**Components:** `EditionGallery` and `ComingSoon`, `SportGrid` and `SportEventList`, `ResultLegend`, `ScrollManager`, and a rebuilt `EditionHero`. `ChartCard` and `BroadcastPageHeader` now wrap on phones.

**Navigation and history**
- `ScrollManager`: a new page starts at the top; Back and Forward restore each history entry's scroll position, waiting for its data to load; a filter change keeps the position.
- A filter change on the same endpoint keeps the current data on screen until the new data arrives, so the page no longer collapses to a spinner and jumps.
- Every discrete choice (dropdown, tab, chart click) is one history entry; typing replaces the entry.
- Internal navigation no longer uses `window.location`; tab buttons are `type="button"`.

**Result abbreviations:** `ResultLegend` lists only the codes that appear on the page, and only for sports where the meaning holds. These were surveyed in all 211,403 saved tables. Codes whose meaning the data does not establish (EQ and SH in ice hockey notes, NVL, QR in throws, p) are left unexplained rather than guessed.

**Pictograms:** the matcher now links "Canoe Slalom / Sprint" to Canoeing (by discipline) and "Trampolining" to Gymnastics (discipline trampoline). Verified pictogram coverage on the results indexes is 705/816 sports. A sport without verified artwork shows its initials, not a substitute icon.
Remaining gaps are missing artwork, not matching faults:
- 1960 has no pictogram files.
- The 19 files for 1964 have no recorded sport.
- Beijing 2008 has only 21 files.
- 1968–1988 have no Diving or Water Polo files.

**New API**
- `/games/{id}/participants` (also as CSV).
- `/games/{id}/gender`. The overall count reports `unrecorded`: one Tokyo 2020 athlete has no gender in the source.
- `/games?include_upcoming=1`.
- Venue rows now carry `venue_image`. It is empty for all 1,647 venues, so no photo column is shown.

**Tests**
- Browser acceptance: 28/28. Covers brief tests 1–10, the menu, no photo on the overview, Coming soon, participants, gender tables, a filter change without a page jump, and no phone overflow on 11 pages.
- Backend: 109 passed (3 new).
- Frontend: 237/238 in the full parallel run. The one failure is a `/statistics` render that exceeds its 20 s timeout under load; the same file passes 22/22 on its own.
- 7 old frontend tests were rewritten for the new design: menu count, Overview, gallery counts, edition tabs, and medal-row click.

## 11. Sport-specific broadcast scoreboards (2026-11-16)

All boards are in `components/broadcast/SportScoreboards.tsx` and share one edition-branded frame (`ScoreboardFrame`):
- **Top bar:** edition emblem and name, sport pictogram, event, date.
- **Stage ribbon:** gold or bronze colours for medal matches.
- **Background:** the edition's background artwork under its colour gradient.
- **Footer:** the venue.

Stage names use Olympedia's notation. "Match 1/2" is shown as **Gold medal match** and "Match 3/4" as **Bronze medal match**; the original text is kept as a tooltip and explained in the abbreviation legend.

| Sport | Layout (only recorded fields) |
|---|---|
| Football, Rugby Sevens | score bug; HT / FT running score + extra-time halves (and shoot-out when recorded) with an "after extra time / penalties" note; scorers with minutes under each team; shots, fouls, cards |
| Basketball / 3x3 | line score by half (+ OT) and total; 3-pt / 2-pt FG, assists, steals, rebounds, blocks (3x3: 1P, 2P, FT%, FG%) |
| Volleyball, Beach Volleyball, Tennis | sets won; set-by-set boxes with the set winner highlighted; points, spikes / attacks, blocks, aces |
| Ice Hockey | P1–P3 (+ OT / SO) line score; scorers with power-play notes; shots on goal, saves, save %, PIM |
| Handball, Water Polo, Hockey | period line score; scorers; sport-specific attempts, penalties, cards and corners |
| Curling | 10 ends + extra ends, the hammer in end 1, shot percentage |
| Baseball, Softball | innings line score with R-H-E from the box score (the box score is the authority for runs) |
| Boxing, Taekwondo, Judo, Wrestling, Fencing, etc. (bouts) | the same frame; red / blue corner panels; judges / rounds / periods table; decision |
| Athletics, Swimming, Gymnastics, Diving, Weightlifting, winter timed sports | broadcast leaderboard (`ResultLeaderboard`): medal discs, lane / bib chip, flag and name, the mark in display type, the sport's breakdown columns (gymnastics D / E / penalty, weightlifting snatch / C&J, runs, reaction time) and Q / record badges. Shown for the final standings on an individual event page and on every heat / round page; the complete table stays below |

**Checks**
- 19 board types, desktop and phone: 38/38 render their sport-specific part, with the edition emblem and pictogram, no overflow and no console errors.
- Frontend tests: 238/238. Browser acceptance: 28/28.

## 12. Whole-site edition theming, clickable pictograms, Countries & Medal Statistics, country profile (2026-11-16)

**Theme engine** (`themes/olympicThemeEngine.ts` `themeVars`, one place for the whole site):
- **Surfaces:** the selected edition's colours are mixed into every neutral token (page `--bg`, `--surface`, `--surface2`, `--line`), so cards, tables, inputs, tabs and borders all take the edition's tone. Readability limits are kept.
- **Edition tokens:**
  - `--ed-stripe`: the edition's own extracted palette as a band, shown on the page top, the sidebar and dividers.
  - `--ed-wash`: a colour wash in the edition's primary and secondary colours.
  - `--ed-head`: the colour of every table header row, with an accent underline.
- **Background:** each edition's own background artwork covers the full page (`EditionBackground`) under a readable veil, with the wash, a glow and its emblem watermark.
- **Sidebar:** carries the edition gradient and palette band.

All 39 editions have a theme extracted from their own logo or background, and the registry is unchanged. No colours were invented, and no edition's artwork is shown for another edition.

**Global Overview:** has its own Olympic-wide background (`OverviewBackground`), not an edition theme. It uses `frontend/public/assets/backgrounds/overview.(webp|jpg|png)` when that file is present; the reference image mentioned in the brief was not in the project. Without the file, it shows a treatment in the five ring colours.

**Pictogram navigation:** the Summer and Winter pages show one panel per edition. The header opens the edition page, and every sport is that edition's own pictogram, linking to `/games/{edition}/sports/{sport}`.
- **Resolution:** sports come from the new endpoint `/api/sports-by-edition` (the saved event index) and are resolved in the context of the edition clicked.
- **Scale:** 588 links on the Summer page.
- **Sport page:** shows a strip of the edition's pictograms with the selected sport highlighted, followed by that sport's events. Switching sport adds a history entry, so Back and Forward work.

**Countries & Medal Statistics** (one menu item, `/countries`; `/medals/countries` redirects with its filters):
- **Table:** all 231 NOCs. Medal holders are ranked; NOCs that took part without a medal follow with no rank. Columns: rank, flag, country, G, S, B, total, appearances (filter-aware), medal editions, medal sports.
- **Filters:** season, year range, edition, sport, gender and medal (all in the URL), plus an instant country search, sortable headers (mouse and keyboard) and CSV export.
- **Historical NOCs:** kept separate.
- **Carried over from the former Countries page:** the world map and the comparison link.

**Country profile:** exactly two tabs in `?tab=`.
- **Visuals:**
  - **Charts:** medal distribution, progression, Summer vs Winter, medals by sport, top sports, best Games, participation, medal-table rank, entries by gender category, and medal composition. All use the country's own data.
  - **Season filter:** updates the per-edition charts. Medals-by-sport is all-time and is labelled so.
- **Results:** one table and its filters, with no charts or stat cards.
  - **Coverage:** every entry from the saved Olympedia country results, medal or not. Germany has 5,902 entries and the USA 10,366.
  - **Columns:** edition, sport, event (linked to its results page), category, athlete or team (linked), result (where the saved results table lists it; otherwise "—"), position, status (DNS, DNF, DQ and so on) and medal.
  - **Filters:** edition, season, year, sport, event, athlete, medal and status, all in `r_*` URL parameters. "Clear all" resets them in one step.

New endpoint: `/api/countries/{noc}/results`.

**Filters and history:**
- **URL updates:** several updates in one handler (sort plus order, Clear all) now compose (`lib/urlState.ts`); previously the second update overwrote the first, so sorting by a column lost the column. One click is one history entry.
- **Medal table:** the country search filters in the browser and is instant (it used to take about 3 s per keystroke).
- **Appearances:** the counts are cached on the server.

**Checks:**
- New browser workflow suite: 26/26. Covers the 13 required workflows, including Rio 2016, Paris 2024 and Beijing 2022 theme consistency across connected pages, the pictogram flows, Germany Visuals and Results, the filters, Back restoring country, tab and filters, refresh, keyboard and mouse use of 25 dropdowns, and no phone overflow.
- Previous suite: 28/28. Scoreboards: 38/38. Frontend: 238/238. Backend: 112 (3 new).

## 13. Corrections from review (2026-11-16)

- **Season pages, Events & Results:** a section inside the Summer and Winter pages. Pick an edition by its emblem (latest by default), and its sports appear as that edition's pictograms. Clicking a pictogram shows that sport's events on the same page, highlights the pictogram and scrolls to the events.
  - The pictograms in each edition panel open the same section (`/summer?ed=2020_summer&sport=Basketball`).
  - Direct links, refresh, Back and Forward all work, and Back restores the scroll position.
- **Country profile, Results:** a prominent "Olympic edition" selector lists the editions the NOC entered (from saved Olympedia pages; USA 1980 is absent because of the boycott). Choosing one shows the country's full Olympedia edition table (`olympedia.org/countries/{NOC}/editions/{id}`).
  - The table keeps sport headings (with that edition's pictograms), event rows, team-member rows, positions and medals, with CSV export and a source link. USA at Tokyo 2020: 631 rows.
  - Events link to their results pages and athletes to their profiles.
  - The table carries its own edition's branding.
  - "All editions" keeps the every-entry table with its filters.
  - New endpoints: `/api/countries/{noc}/olympedia/{games_id}` and `/api/countries/{noc}/olympedia-editions`.
- **Dropdowns and arrow keys** (`SelectKeyGuard`): a focused but closed dropdown no longer changes the filter on arrow, Page or Home/End keys; those keys scroll the page. Once a dropdown is opened (click, Space, F4 or Alt+Down), the keys move through its options as usual.
- **Menu bar and tables:** both carry the edition's own artwork.
  - The menu bar shows the selected edition's background image under a colour veil, with its emblem as a watermark (`.ed-nav`).
  - Every table header band (DataTable and TableFrame, so medal, participant, results, Olympedia, line-up and analytics tables) shows the edition's background artwork and emblem (`.ed-table-head`).
  - Both come from `--ed-bg-img` and `--ed-logo-img`, which `themeVars` sets from the registry assets.
- **Global overview background:** the picture supplied by the user (`frontend/public/assets/backgrounds/overview.png`, 674×360), full page under a light veil. The menu bar on the overview uses it too.
- **Checks:**
  - New suite: 17/17. Covers the in-page pictogram flow on Summer and Winter, the panel pictograms, Back with scroll, USA Tokyo 2020 at 631 rows with links and Tokyo branding, arrow keys scrolling rather than filtering, the menu-bar and table-head artwork for Rio and Beijing, the overview image, and phone layouts.
  - Earlier browser suites updated to the corrected behaviour: 26/26 and 28/28. Scoreboards: 38/38.
  - Backend: 112 passed. Frontend: 237/238. The failure is the known `/statistics` 20 s load timeout in the full parallel run; the test passes on its own.

## 14. Second review corrections (2026-11-16)

- **Summer / Winter pages:** edition logos and charts only (`EditionLogoWall`). Each edition gets a large card with its emblem on white over its own background artwork, the year badge in the edition colour, city, flag and numbers; upcoming Games say Coming soon. The in-page Events & Results section and the per-edition pictogram panels are removed.
- **Edition page → Event Results:** the sport pictograms sit on the left. The chosen sport's events show in a panel on the right that stays in view (sticky), so clicking any pictogram, even one low in the grid, shows its events right there. On narrow screens the page jumps to the events.
  - The panel uses compact rows (title and gender, then date and size).
  - The URL is `?tab=results&sport=`, so Back, Forward and refresh work.
- **Medal statistics table:** every NOC has a rank number. NOCs that took part without winning a medal share the next rank (158), as ties do in a medal table.
- **Country → Results:** the Olympic editions the country entered appear as a strip of emblems with ◀ ▶ arrows (`EditionLogoStrip`), plus an "All editions" tile. Clicking an emblem shows the country's full Olympedia table for that edition.
- **Checks:**
  - New suite: 12/12.
  - Scoreboards: 38/38.
  - Backend: 112 passed.
  - Frontend: 236/238 in the parallel run. The two failures are the `/statistics` 20 s load timeouts; the file passes 22/22 on its own.

## 15. Result pages, team standings, medal numbering, tables, overview hero (2026-11-16)

- **Result pages:** the "About this event" text is no longer shown on any result, match, bout or heat page. The data stays in the warehouse.
- **Team-sport standings:** one row per country, like Olympedia. This covers football, volleyball, basketball, handball, water polo, hockey, baseball and others.
  - Each team's squad rows (no NOC, a playing position in the Pos column) are folded under a **+** button on the team row. A "Show all squads" button opens them all.
  - Example: Paris 2024 Football, Men shows the 16 teams; "+" on Spain shows its 23 players.
  - Individual events are unchanged.
- **Medal statistics:** NOCs without a medal continue the numbering after the medal winners (158, 159, 160 …), most appearances first.
- **Tables:**
  - Virtualized tables now stretch their columns to the full width of the frame.
  - All tables get striped rows in the edition tint, a hover and focus row, a lifted frame and a stronger header band.
- **Global overview:** the supplied pattern picture (`frontend/public/assets/backgrounds/overview-hero.png`) sits behind the Olympic rings, with the title on a soft panel so it stays readable.
- **Checks:**
  - New suite: 13/13. Covers six team sports folded and unfolded, no About section, individual events unchanged, numbering 158 … 231, the hero picture and full-width tables.
  - Previous round: 12/12. Scoreboards: 38/38.
  - Backend: 112 passed.
  - Frontend: 236/238. The two failures are the known `/statistics` load timeouts.

## 16. Editions sidebar and site-wide table style (2026-11-16)

- **Country → Results:** a sticky left sidebar lists ALL 35 held Olympic Games, grouped Summer and Winter, each with its emblem, city and year, plus an "All editions" entry.
  - Games the NOC entered open its full Olympedia edition table beside the sidebar.
  - Games it did not enter are greyed and marked "did not take part": Moscow 1980 for USA, and 12 editions for GER, whose earlier Games belong to the separate NOCs FRG, GDR and EUA.
  - On phones the sidebar sits above the table.
  - It replaces the horizontal logo strip.
- **Tables everywhere:** a browser audit of 29 pages found every table inside the broadcast frame. The look itself was improved:
  - Every header row is a deep band in the edition's darkest palette colour (`--ed-deep`: Paris 2024 crimson, Tokyo 2020 navy, Rio 2016 blue), with white lettering, an accent underline and the active sort column marked in the accent colour.
  - The first column is bold; rows are striped, with hover.
  - Cards that only wrap a table drop their outer frame, so there is no box inside a box.
- **Checks:**
  - New suite: 8/8. Covers the sidebar (36 entries with logos, greyed editions, Tokyo 2020 at 631 rows beside it, sticky while scrolling) and the header band on all tables across 12 pages, with no nested frames.
  - Round 15: 13/13. Scoreboards: 38/38.
  - Frontend: 238/238.
