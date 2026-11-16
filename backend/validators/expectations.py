"""Expectation-style data validation (stand-in for Great Expectations, which is not installed here).

Each check returns (name, passed, observed, detail). Run via scripts/run_validation.py; results are stored in data_quality_reports
and written to reports/quality/validation_results.csv. A failing check is a finding, never silently dropped.
"""
from __future__ import annotations

import sqlite3
from typing import Callable

Check = tuple[str, Callable[[sqlite3.Connection], tuple[bool, object, str]]]


def _zero(sql: str, detail: str):
    def run(c):
        n = c.execute(sql).fetchone()[0]
        return n == 0, n, detail
    return run


def _between(sql: str, lo: float, hi: float, detail: str):
    def run(c):
        n = c.execute(sql).fetchone()[0]
        return lo <= n <= hi, n, detail
    return run


CHECKS: list[Check] = [
    ("games_scope_35_in_range", _between("SELECT COUNT(*) FROM games WHERE year BETWEEN 1960 AND 2026 AND (season='summer' AND year<=2024 OR season='winter')", 35, 35, "35 Games 1960-2026 (summer<=2024)")),
    ("no_summer_2026", _zero("SELECT COUNT(*) FROM games WHERE season='summer' AND year=2026", "no invented Summer 2026")),
    ("tokyo_2020_dates_in_2021", _zero("SELECT COUNT(*) FROM games WHERE games_id='2020_summer' AND substr(opening_date,1,4)!='2021' AND substr(actual_event_start_date,1,4)!='2021'", "Tokyo 2020 keeps year 2020, dates in 2021")),
    ("participation_orphan_athletes", _zero("SELECT COUNT(*) FROM athlete_participations p WHERE NOT EXISTS (SELECT 1 FROM athletes a WHERE a.athlete_id=p.athlete_id)", "FK athlete_participations.athlete_id")),
    ("participation_orphan_games", _zero("SELECT COUNT(*) FROM athlete_participations p WHERE NOT EXISTS (SELECT 1 FROM games g WHERE g.games_id=p.games_id)", "FK games")),
    ("medals_orphan_events", _zero("SELECT COUNT(*) FROM medals m WHERE event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM events e WHERE e.event_id=m.event_id)", "FK medals.event_id")),
    ("duplicate_participations", _zero("SELECT COUNT(*) FROM (SELECT 1 FROM athlete_participations GROUP BY athlete_id,games_id,event_id HAVING COUNT(*)>1)", "unique athlete/games/event")),
    ("duplicate_athlete_identity", _zero("SELECT COUNT(*) FROM (SELECT 1 FROM athletes GROUP BY identity_key HAVING COUNT(*)>1)", "one profile per athlete identity")),
    ("athlete_birth_before_death", _zero("SELECT COUNT(*) FROM athletes WHERE date_of_birth GLOB '[0-9][0-9][0-9][0-9]*' AND date_of_death GLOB '[0-9][0-9][0-9][0-9]*' AND CAST(substr(date_of_birth,-4) AS INT) > CAST(substr(date_of_death,-4) AS INT)", "birth year <= death year")),
    ("height_plausible", _zero("SELECT COUNT(*) FROM athletes WHERE height_cm IS NOT NULL AND (height_cm<100 OR height_cm>250)", "100-250 cm")),
    ("weight_plausible", _zero("SELECT COUNT(*) FROM athletes WHERE weight_kg IS NOT NULL AND (weight_kg<25 OR weight_kg>250)", "25-250 kg")),
    ("medal_types_valid", _zero("SELECT COUNT(*) FROM medals WHERE medal_type NOT IN ('Gold','Silver','Bronze')", "Gold/Silver/Bronze only")),
    ("country_table_totals_add_up", _zero("SELECT COUNT(*) FROM medal_tables WHERE total != gold+silver+bronze", "total = G+S+B")),
    ("event_medal_table_consistent_with_sport_table",
     _zero("SELECT COUNT(*) FROM (SELECT games_id,sport_id,noc_code,SUM(total) t FROM medal_table_by_event GROUP BY 1,2,3) e JOIN medal_table_by_sport s USING (games_id,sport_id,noc_code) WHERE e.t!=s.total", "event tables sum to sport tables")),
    ("every_in_scope_game_has_results", _zero("SELECT COUNT(*) FROM games g WHERE g.year BETWEEN 1960 AND 2026 AND (g.season='winter' OR g.year<=2024) AND g.games_id NOT IN ('1960_summer','1960_winter','1964_winter') AND NOT EXISTS (SELECT 1 FROM event_results r WHERE r.games_id=g.games_id)", "no in-scope Games without results")),
    ("every_in_scope_game_has_matches", _zero("SELECT COUNT(*) FROM games g WHERE g.year BETWEEN 1960 AND 2026 AND (g.season='winter' OR g.year<=2024) AND g.games_id NOT IN ('1960_summer','1960_winter','1964_winter') AND NOT EXISTS (SELECT 1 FROM matches m WHERE m.games_id=g.games_id)", "team-sport matches exist for each Games")),
    ("records_have_source", _zero("SELECT COUNT(*) FROM records WHERE source_url IS NULL OR source_url=''", "provenance")),
    ("venues_coordinates_in_range", _zero("SELECT COUNT(*) FROM venues WHERE latitude IS NOT NULL AND (latitude<-90 OR latitude>90 OR longitude<-180 OR longitude>180)", "valid lat/lon")),
    ("pictograms_for_every_game", _zero("SELECT COUNT(*) FROM games g WHERE g.year BETWEEN 1960 AND 2026 AND (g.season='winter' OR g.year<=2024) AND g.games_id NOT IN ('1960_summer','1960_winter','1964_winter') AND NOT EXISTS (SELECT 1 FROM assets a WHERE a.games_id=g.games_id AND a.asset_type='sport_pictogram')", "pictograms present for every in-scope Games (official pictograms start 1964 Summer / 1968 Winter; user-supplied assets, see scripts/sync_assets.py)")),
    ("gold_country_noc_in_registry", _zero("SELECT COUNT(*) FROM gold_country_medals WHERE noc_code NOT IN (SELECT noc_code FROM historical_nocs)", "every medal NOC exists in historical_nocs")),
    ("gold_no_placeholder_or_footer_rows", _zero("SELECT COUNT(*) FROM gold_country_medals WHERE substr(noc_code,1,2)='X_' OR country_name GLOB '[0-9]*'", "Wikipedia footer/placeholder rows excluded")),
    ("gold_medal_totals_match_podiums", _zero("SELECT ABS((SELECT SUM(total) FROM gold_country_medals) - (SELECT COUNT(*) FROM silver_medal_awards))", "country totals = distinct podium results")),
    ("gold_paris_2024_official_totals", _zero("SELECT ABS(SUM(gold)-329)+ABS(SUM(silver)-330)+ABS(SUM(bronze)-385) FROM gold_country_medals WHERE games_id='2024_summer'", "reproduces the official Paris 2024 totals (regression fixture)")),
    ("gold_tied_ranks_share_gsb", _zero("SELECT COUNT(*) FROM (SELECT games_id, official_rank FROM gold_country_medals GROUP BY 1,2 HAVING COUNT(DISTINCT gold||'-'||silver||'-'||bronze)>1)", "equal rank implies equal gold/silver/bronze")),
    ("silver_participations_no_duplicates", _zero("SELECT COUNT(*) FROM (SELECT 1 FROM silver_participations GROUP BY athlete_id,games_id,event_id HAVING COUNT(*)>1)", "silver layer is de-duplicated")),
    ("gold_career_medals_match_silver", _zero("SELECT ABS((SELECT SUM(medals) FROM gold_athlete_career) - (SELECT SUM(is_medalist) FROM silver_participations))", "athlete career mart reconciles to silver")),
    ("unknown_noc_participations_flagged", _between("SELECT COUNT(*) FROM silver_participations WHERE noc_code='UNK'", 0, 15000, "participations with no NOC in the source (reported, excluded from NOC counts)")),
    ("event_result_values_are_marks", _zero("SELECT COUNT(*) FROM event_results WHERE result_value IS NOT NULL AND result_value!='' AND result_value GLOB '*[^0-9:.]*'", "stored result values are plain times / distances / scores (no '-', 'same time', '[DQ]', margins)")),
    ("event_result_value_has_unit", _zero("SELECT COUNT(*) FROM event_results WHERE result_value IS NOT NULL AND result_value!='' AND (result_unit IS NULL OR result_unit='')", "every stored result value states its unit (seconds, metres, points, kg)")),
    ("event_result_positions_match_medals", lambda c: (lambda ok, n: (n > 0 and ok / n >= 0.97, round(ok / max(n, 1), 4), "share of medal rows whose final position is 1 / 2 / 3 as the medal says (>= 97%)"))(
        *c.execute("SELECT SUM((medal='Gold' AND final_position=1) OR (medal='Silver' AND final_position=2) OR (medal='Bronze' AND final_position=3)), COUNT(*) FROM event_results WHERE medal IN ('Gold','Silver','Bronze') AND final_position IS NOT NULL").fetchone())),
    ("olympedia_round_results_loaded", _between("SELECT COUNT(*) FROM olympedia_round_results", 800000, 2000000, "one row for every competitor of every round, heat, pool and qualifying table of every event page (all columns kept)")),
    ("event_result_value_coverage", lambda c: (lambda n, d: (d > 0 and n / d >= 0.65, round(n / max(d, 1), 4), "share of event results with a recorded mark (time / distance / points / kg) - sports with no mark (bouts, goals) are the rest (>= 65%)"))(
        c.execute("SELECT COUNT(*) FROM event_results WHERE result_value IS NOT NULL AND result_value!=''").fetchone()[0], c.execute("SELECT COUNT(*) FROM event_results").fetchone()[0])),
    ("event_result_position_coverage", lambda c: (lambda n, d: (d > 0 and n / d >= 0.70, round(n / max(d, 1), 4), "share of event results with a place (>= 70%)"))(
        c.execute("SELECT COUNT(final_position) FROM event_results").fetchone()[0], c.execute("SELECT COUNT(*) FROM event_results").fetchone()[0])),
    ("olympedia_country_results_loaded", _between("SELECT COUNT(*) FROM olympedia_country_results", 150000, 400000, "rows from the Olympedia country -> Results route (every country x Games x event x athlete)")),
    ("olympedia_country_medals_match_table", lambda c: (lambda a, b: (a == b, a, f"medals from the country Results pages equal the medal table ({b})"))(
        c.execute("SELECT COUNT(*) FROM (SELECT DISTINCT noc, games_id, result_id, medal FROM olympedia_country_results WHERE medal IN ('Gold','Silver','Bronze'))").fetchone()[0],
        c.execute("SELECT SUM(total) FROM silver_country_medals").fetchone()[0])),
    ("olympedia_page_links_resolve", lambda c: (lambda n, s: (n > 90000 and n == s, f"{s}/{n}", "every Match # / heat / dropdown link points to a saved Olympedia page"))(
        *c.execute("SELECT COUNT(*), SUM(child_saved) FROM olympedia_page_links").fetchone())),
    ("olympedia_event_descriptions", lambda c: (lambda n, d: (d > 0 and n / d >= 0.99, f"{n}/{d}", "event pages with Olympedia's written description (>= 99%)"))(
        *c.execute("SELECT SUM(t.description_json IS NOT NULL AND t.description_json!='[]'), COUNT(*) FROM olympedia_pages p LEFT JOIN olympedia_page_text t USING(result_id) WHERE p.kind='events'").fetchone())),
]


def run_all(con: sqlite3.Connection) -> list[dict]:
    out = []
    for name, fn in CHECKS:
        try:
            ok, observed, detail = fn(con)
        except Exception as exc:  # a broken check is reported, not hidden
            ok, observed, detail = False, None, f"check error: {exc}"
        out.append({"check": name, "passed": bool(ok), "observed": observed, "detail": detail})
    return out
