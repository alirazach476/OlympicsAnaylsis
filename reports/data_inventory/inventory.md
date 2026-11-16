# Data inventory (generated)

* SQLite tables: **111** (7,522,883 rows total)
* CSV/JSON/Parquet files outside raw caches: **160**
* In-scope Games: **35**; Games x dataset gaps: **31**
* Referential checks: **19/20** clean
* Findings: **29** (see reports/data_quality/quality_findings.csv)

## Largest datasets

| dataset | rows | cols | missing % | quality |
|---|---|---|---|---|
| olympedia_round_results | 885,761 | 20 | 13.42 | ok |
| olympedia_standings | 587,503 | 18 | 14.49 | duplicates present |
| olympedia_event_rows | 422,822 | 15 | 14.17 | duplicates present |
| src_athlete_results | 308,408 | 10 | 0.0 | duplicates present |
| wikipedia_links | 287,424 | 19 | 2.58 | ok |
| src_athlete_events | 271,116 | 15 | 0.0 | duplicates present |
| olympedia_match_players | 265,970 | 13 | 4.06 | ok |
| athlete_participations | 263,893 | 16 | 12.32 | ok |
| event_results | 263,893 | 25 | 26.27 | ok |
| silver_participations | 263,893 | 16 | 5.75 | ok |
| olympedia_athlete_results | 257,493 | 12 | 16.26 | duplicates present |
| olympedia_rosters | 257,493 | 13 | 15.01 | ok |
| gold_event_phases | 235,402 | 14 | 4.36 | duplicates present |
| match_statistics | 222,670 | 15 | 30.72 | duplicates present |
| olympedia_match_details | 214,048 | 5 | 0.0 | duplicates present |

## Empty tables


## Findings

* [medium] event_result_olympedia_map: duplicate rows (ignoring surrogate ids) 529 extra rows
* [medium] gold_event_phases: duplicate rows (ignoring surrogate ids) 525 extra rows
* [medium] gold_event_results: duplicate rows (ignoring surrogate ids) 1 extra rows
* [low] mascots: missing source_url 9 of 30 rows
* [medium] match_statistics: duplicate rows (ignoring surrogate ids) 19 extra rows
* [medium] medal_table_by_event: duplicate rows (ignoring surrogate ids) 4530 extra rows
* [medium] medal_table_by_sport: duplicate rows (ignoring surrogate ids) 4286 extra rows
* [medium] olympedia_athlete_gender: duplicate rows (ignoring surrogate ids) 398 extra rows
* [medium] olympedia_athlete_results: duplicate rows (ignoring surrogate ids) 56 extra rows
* [medium] olympedia_country_results: duplicate rows (ignoring surrogate ids) 1 extra rows
* [medium] olympedia_country_results_done: duplicate rows (ignoring surrogate ids) 2603 extra rows
* [medium] olympedia_disqualifications: duplicate rows (ignoring surrogate ids) 1355 extra rows
* [medium] olympedia_event_rows: duplicate rows (ignoring surrogate ids) 1 extra rows
* [medium] olympedia_match_details: duplicate rows (ignoring surrogate ids) 16 extra rows
* [medium] olympedia_match_done: duplicate rows (ignoring surrogate ids) 2 extra rows
* [medium] olympedia_match_events: duplicate rows (ignoring surrogate ids) 9317 extra rows
* [medium] olympedia_pages: duplicate rows (ignoring surrogate ids) 18207 extra rows
* [medium] olympedia_records_done: duplicate rows (ignoring surrogate ids) 134 extra rows
* [medium] olympedia_standings: duplicate rows (ignoring surrogate ids) 24 extra rows
* [medium] olympedia_venue_done: duplicate rows (ignoring surrogate ids) 1058 extra rows
* [medium] records: duplicate rows (ignoring surrogate ids) 8 extra rows
* [medium] ref_host_noc: duplicate rows (ignoring surrogate ids) 16 extra rows
* [medium] ref_noc_alias: duplicate rows (ignoring surrogate ids) 307 extra rows
* [medium] src_athlete_events: duplicate rows (ignoring surrogate ids) 1385 extra rows
* [medium] src_athlete_results: duplicate rows (ignoring surrogate ids) 110 extra rows
* [medium] src_olympics_medallists: duplicate rows (ignoring surrogate ids) 1 extra rows
* [low] teams: missing source_url 2506 of 20902 rows
* [medium] venues: duplicate rows (ignoring surrogate ids) 9 extra rows
* [medium] medal_tables: referential integrity: medal_tables.noc_code -> historical_nocs 57 orphan rows