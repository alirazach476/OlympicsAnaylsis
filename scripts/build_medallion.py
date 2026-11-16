#!/usr/bin/env python3
"""MILESTONE 2 - Bronze / Silver / Gold architecture inside the warehouse (idempotent, incremental per Games).

BRONZE  = everything already collected, never modified: src_* (CSV folder), olympedia_* (raw scrapes), wikipedia_*, plus data/raw files.
SILVER  = cleaned, standardised, de-duplicated, provenance-carrying tables (silver_*).
GOLD    = analytical marts (gold_*), 12 of them. Per-Games marts are rebuilt ONLY for Games whose source fingerprint changed
          (table gold_build_state); global marts are cheap full rebuilds.

Source priority for medal totals: Olympedia event podiums (verified against official totals) > Wikipedia medal tables (cross-check only; parse errors) > CSV snapshots.
Historical NOCs are never merged into successors. Usage: python scripts/build_medallion.py [--full]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "olympics_warehouse.db"

# Reference facts: host NOC of each Games (IOC codes as used in this warehouse). Not collected data - documented in docs/ANALYTICS_METRICS.md.
HOST_NOC = {
    "1960_summer": "ITA", "1960_winter": "USA", "1964_summer": "JPN", "1964_winter": "AUT", "1968_summer": "MEX", "1968_winter": "FRA",
    "1972_summer": "FRG", "1972_winter": "JPN", "1976_summer": "CAN", "1976_winter": "AUT", "1980_summer": "URS", "1980_winter": "USA",
    "1984_summer": "USA", "1984_winter": "YUG", "1988_summer": "KOR", "1988_winter": "CAN", "1992_summer": "ESP", "1992_winter": "FRA",
    "1994_winter": "NOR", "1996_summer": "USA", "1998_winter": "JPN", "2000_summer": "AUS", "2002_winter": "USA", "2004_summer": "GRE",
    "2006_winter": "ITA", "2008_summer": "CHN", "2010_winter": "CAN", "2012_summer": "GBR", "2014_winter": "RUS", "2016_summer": "BRA",
    "2018_winter": "KOR", "2020_summer": "JPN", "2022_winter": "CHN", "2024_summer": "FRA", "2026_winter": "ITA",
}
TEAM_SPORTS = ("Football", "Basketball", "Hockey", "Volleyball", "Handball", "Water Polo", "Ice Hockey", "Rugby Sevens", "Rugby", "Baseball",
               "Softball", "Beach Volleyball", "Curling", "3x3 Basketball", "Field Hockey", "Cricket", "Lacrosse")


def fp(con, g):
    """Fingerprint of everything a Games' marts depend on."""
    parts = []
    for t in ("athlete_participations", "medals", "events", "event_results", "matches", "olympedia_standings", "olympedia_podium_results", "olympedia_event_rows", "olympedia_matches", "records", "venues"):
        parts.append(con.execute(f"SELECT COUNT(*), COALESCE(MAX(rowid),0) FROM {t} WHERE games_id=?", (g,)).fetchone())
    parts.append(con.execute("SELECT COUNT(*) FROM athletes").fetchone())
    return hashlib.sha1(json.dumps(parts).encode()).hexdigest()


def parse_perf(v):
    """Result string -> (value, unit). 1:07.27 -> 67.27 s ; 8.90 m -> 8.90 m ; plain number -> points. Original string is always kept."""
    if not v:
        return None, None
    s = re.sub(r"\(.*?\)", "", v).strip().replace(",", "")
    s = re.sub(r"\s*(WR|OR|AR|NR|PB|SB|CR|ER).*$", "", s).strip()
    m = re.fullmatch(r"(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)", s)
    if m and ":" in s:
        h, mi, sec = m.groups()
        parts = [float(x) for x in s.split(":")]
        t = 0.0
        for p in parts:
            t = t * 60 + p
        return round(t, 3), "s"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(m|cm|kg|pts?)?", s)
    if m:
        return float(m.group(1)), (m.group(2) or "number")
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="ignore fingerprints and rebuild everything")
    a = ap.parse_args()
    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout=300000")
    run = dt.datetime.now(dt.timezone.utc).isoformat()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS gold_build_state(mart TEXT, games_id TEXT, fingerprint TEXT, built_at TEXT, PRIMARY KEY(mart, games_id));
    CREATE TABLE IF NOT EXISTS pipeline_runs(run_id INTEGER PRIMARY KEY AUTOINCREMENT, stage TEXT, started_at TEXT, finished_at TEXT, status TEXT, detail TEXT);
    CREATE TABLE IF NOT EXISTS ref_host_noc(games_id TEXT PRIMARY KEY, host_noc TEXT, note TEXT);
    """)
    con.execute("DELETE FROM ref_host_noc")
    con.executemany("INSERT INTO ref_host_noc VALUES (?,?,?)", [(g, n, "reference fact (IOC host nation)") for g, n in HOST_NOC.items()])
    cur = con.execute("INSERT INTO pipeline_runs(stage,started_at,status) VALUES ('medallion',?, 'running')", (run,))
    rid = cur.lastrowid
    q = lambda s, *p: con.execute(s, p).fetchall()
    games = [r[0] for r in q("SELECT games_id FROM games WHERE year BETWEEN 1960 AND 2026 AND (season='winter' OR year<=2024) ORDER BY year, season")]

    # ======================= SILVER (full rebuild, cheap & deterministic) =======================
    con.executescript("""
    DROP TABLE IF EXISTS silver_athletes;
    CREATE TABLE silver_athletes AS
      SELECT athlete_id, TRIM(REPLACE(REPLACE(full_name,'  ',' '),'  ',' ')) AS full_name,
             CASE WHEN gender IN ('M','Men','Male') THEN 'M' WHEN gender IN ('F','Women','Female') THEN 'F' END AS gender,
             date_of_birth, date_of_death, height_cm, weight_kg, identity_key, source_url, verification_status
      FROM athletes;
    CREATE UNIQUE INDEX ix_sa ON silver_athletes(athlete_id);

    DROP TABLE IF EXISTS silver_participations;
    CREATE TABLE silver_participations AS
      SELECT p.participation_id, p.athlete_id, p.games_id, g.year, g.season, p.sport_id, s.sport_name, p.event_id, e.event_name,
             COALESCE(al.standard_code, NULLIF(p.noc_code,''), 'UNK') AS noc_code, a.gender, p.age_at_competition AS age,
             CASE WHEN p.medal IN ('Gold','Silver','Bronze') THEN p.medal END AS medal,
             CASE WHEN p.medal IN ('Gold','Silver','Bronze') THEN 1 ELSE 0 END AS is_medalist,
             CASE WHEN COALESCE(al.standard_code, p.noc_code) = h.host_noc THEN 1 ELSE 0 END AS is_host_noc,
             p.source_url
      FROM (SELECT * FROM athlete_participations GROUP BY athlete_id, games_id, event_id) p   -- de-duplicate
      JOIN games g ON g.games_id=p.games_id LEFT JOIN sports s ON s.sport_id=p.sport_id LEFT JOIN events e ON e.event_id=p.event_id
      LEFT JOIN silver_athletes a ON a.athlete_id=p.athlete_id LEFT JOIN ref_host_noc h ON h.games_id=p.games_id
      LEFT JOIN ref_noc_alias al ON al.games_id=p.games_id AND al.source='athletes' AND al.source_code=p.noc_code
      WHERE g.year BETWEEN 1960 AND 2026;
    CREATE INDEX ix_sp_g ON silver_participations(games_id); CREATE INDEX ix_sp_a ON silver_participations(athlete_id); CREATE INDEX ix_sp_n ON silver_participations(noc_code);

    DROP TABLE IF EXISTS silver_medal_awards;   -- ONE row per event result x NOC x medal (team medals counted once) from Olympedia event podiums
    CREATE TABLE silver_medal_awards AS
      SELECT DISTINCT p.games_id, sp.sport_id, p.sport_name, p.event_name, p.result_id, COALESCE(al.standard_code, p.noc) AS noc_code, p.medal AS medal_type
      FROM (SELECT games_id, result_id, sport_name, event_name, noc, medal FROM olympedia_podium_results WHERE medal IN ('Gold','Silver','Bronze') AND noc IS NOT NULL AND noc!=''
            UNION
            SELECT s.games_id, s.result_id, s.sport_name, s.event_name, s.noc, s.medal FROM olympedia_standings s
              WHERE s.is_phase=0 AND s.medal IN ('Gold','Silver','Bronze') AND s.noc IS NOT NULL AND s.noc!='' AND s.result_id NOT IN (SELECT result_id FROM olympedia_podium_results)) p
      JOIN games g ON g.games_id=p.games_id
      LEFT JOIN (SELECT LOWER(sport_name) lname, MIN(sport_id) sport_id FROM sports GROUP BY LOWER(sport_name)) sp ON sp.lname=LOWER(p.sport_name)
      LEFT JOIN ref_noc_alias al ON al.games_id=p.games_id AND al.source='athletes' AND al.source_code=p.noc
      WHERE g.year BETWEEN 1960 AND 2026;
    CREATE INDEX ix_sma ON silver_medal_awards(games_id, noc_code); CREATE INDEX ix_sma_s ON silver_medal_awards(sport_id);

    DROP TABLE IF EXISTS silver_medal_table_totals;   -- the 'Total' footer rows of the Wikipedia tables (parsed as noc X_UNK) - NOT countries (their columns are shifted)
    CREATE TABLE silver_medal_table_totals AS
      SELECT games_id, gold, silver, bronze, total, 'wikipedia table footer (X_UNK), columns unreliable' AS source FROM medal_tables WHERE table_scope='wikipedia_country_medal_table' AND noc_code='X_UNK';

    DROP TABLE IF EXISTS silver_country_medals;  -- AUTHORITY: distinct Olympedia event podiums (matches official totals, e.g. Paris 2024 = 329/330/385).
    CREATE TABLE silver_country_medals AS                -- The Wikipedia tables are kept only as a cross-check (their parse is wrong for ~25% of rows).
      SELECT a.games_id, a.noc_code, COALESCE(h.historical_name, a.noc_code) AS country_name, a.gold, a.silver, a.bronze, a.total,
             RANK() OVER (PARTITION BY a.games_id ORDER BY a.gold DESC, a.silver DESC, a.bronze DESC) AS official_rank,
             w.gold AS wikipedia_gold, w.silver AS wikipedia_silver, w.bronze AS wikipedia_bronze, w.total AS wikipedia_total,
             'Olympedia event podiums (distinct team/individual results)' AS source
      FROM (SELECT games_id, noc_code, SUM(medal_type='Gold') gold, SUM(medal_type='Silver') silver, SUM(medal_type='Bronze') bronze, COUNT(*) total FROM silver_medal_awards GROUP BY 1,2) a
      LEFT JOIN historical_nocs h ON h.noc_code=a.noc_code
      LEFT JOIN (SELECT m.games_id, COALESCE(al.standard_code, m.noc_code) noc_code, m.gold, m.silver, m.bronze, m.total FROM medal_tables m
                 LEFT JOIN ref_noc_alias al ON al.games_id=m.games_id AND al.source='medal_table' AND al.source_code=m.noc_code
                 WHERE m.table_scope='wikipedia_country_medal_table' AND m.noc_code!='X_UNK') w ON w.games_id=a.games_id AND w.noc_code=a.noc_code;
    CREATE INDEX ix_scm ON silver_country_medals(games_id, noc_code);
    """)
    silver = {t: q(f"SELECT COUNT(*) FROM {t}")[0][0] for t in ("silver_athletes", "silver_participations", "silver_medal_awards", "silver_country_medals", "silver_medal_table_totals")}

    # ======================= GOLD - global marts =======================
    con.executescript("""
    DROP TABLE IF EXISTS gold_athlete_career;
    CREATE TABLE gold_athlete_career AS
      SELECT p.athlete_id, a.full_name, a.gender, COUNT(DISTINCT p.games_id) AS games_count, MIN(p.year) AS first_year, MAX(p.year) AS last_year,
             MAX(p.year)-MIN(p.year) AS career_span_years, COUNT(DISTINCT p.sport_id) AS sports_count, COUNT(DISTINCT p.event_id) AS events_count,
             SUM(p.medal='Gold') AS gold, SUM(p.medal='Silver') AS silver, SUM(p.medal='Bronze') AS bronze, SUM(p.is_medalist) AS medals,
             MIN(p.age) AS min_age, MAX(p.age) AS max_age, GROUP_CONCAT(DISTINCT p.noc_code) AS nocs, GROUP_CONCAT(DISTINCT p.sport_name) AS sports,
             (SELECT COUNT(DISTINCT x.games_id) FROM silver_participations x WHERE x.athlete_id=p.athlete_id AND x.is_medalist=1) AS medal_games
      FROM silver_participations p JOIN silver_athletes a ON a.athlete_id=p.athlete_id GROUP BY p.athlete_id;
    CREATE UNIQUE INDEX ix_gac ON gold_athlete_career(athlete_id); CREATE INDEX ix_gac_m ON gold_athlete_career(medals DESC);

    DROP TABLE IF EXISTS gold_country_participation_history;
    CREATE TABLE gold_country_participation_history AS
      SELECT h.noc_code, h.historical_name, h.continent, h.iso_alpha3, h.is_unified_or_neutral,
             MIN(p.year) AS first_year, MAX(p.year) AS last_year, COUNT(DISTINCT p.games_id) AS appearances,
             COUNT(DISTINCT CASE WHEN p.season='summer' THEN p.games_id END) AS summer_appearances,
             COUNT(DISTINCT CASE WHEN p.season='winter' THEN p.games_id END) AS winter_appearances,
             COUNT(DISTINCT p.athlete_id) AS athletes,
             COALESCE((SELECT SUM(gold) FROM silver_country_medals c WHERE c.noc_code=h.noc_code),0) AS gold,
             COALESCE((SELECT SUM(silver) FROM silver_country_medals c WHERE c.noc_code=h.noc_code),0) AS silver,
             COALESCE((SELECT SUM(bronze) FROM silver_country_medals c WHERE c.noc_code=h.noc_code),0) AS bronze,
             COALESCE((SELECT SUM(total) FROM silver_country_medals c WHERE c.noc_code=h.noc_code),0) AS total_medals,
             (SELECT MIN(c.games_id) FROM silver_country_medals c WHERE c.noc_code=h.noc_code AND c.total>0) AS first_medal_games
      FROM historical_nocs h LEFT JOIN silver_participations p ON p.noc_code=h.noc_code GROUP BY h.noc_code;

    DROP TABLE IF EXISTS gold_athlete_age_performance;
    CREATE TABLE gold_athlete_age_performance AS
      SELECT season, age_band, COUNT(*) AS participations, SUM(is_medalist) AS medalists, ROUND(1.0*SUM(is_medalist)/COUNT(*),4) AS medal_rate, ROUND(AVG(age),2) AS mean_age
      FROM (SELECT season, is_medalist, age, CASE WHEN age<18 THEN '<18' WHEN age<22 THEN '18-21' WHEN age<26 THEN '22-25' WHEN age<30 THEN '26-29' WHEN age<35 THEN '30-34' WHEN age<40 THEN '35-39' ELSE '40+' END AS age_band
            FROM silver_participations WHERE age IS NOT NULL) GROUP BY season, age_band;

    DROP TABLE IF EXISTS gold_season_comparison;
    CREATE TABLE gold_season_comparison AS
      SELECT g.season, COUNT(DISTINCT g.games_id) AS editions, SUM(ge.athletes) AS athlete_participations, SUM(ge.nocs) AS noc_entries,
             ROUND(AVG(ge.athletes),1) AS mean_athletes_per_edition, ROUND(AVG(ge.events),1) AS mean_events_per_edition, ROUND(AVG(ge.nocs),1) AS mean_nocs_per_edition,
             ROUND(AVG(ge.female_share),4) AS mean_female_share, SUM(ge.medal_awards) AS medal_awards,
             ROUND(1.0*SUM(ge.medal_awards)/SUM(ge.events),3) AS medal_awards_per_event, ROUND(1.0*SUM(ge.medal_awards)/SUM(ge.athletes),4) AS medal_awards_per_athlete
      FROM games g JOIN (SELECT games_id, COUNT(DISTINCT athlete_id) athletes, COUNT(DISTINCT CASE WHEN noc_code!='UNK' THEN noc_code END) nocs, COUNT(DISTINCT event_id) events,
                         1.0*COUNT(DISTINCT CASE WHEN gender='F' THEN athlete_id END)/NULLIF(COUNT(DISTINCT CASE WHEN gender IN ('M','F') THEN athlete_id END),0) female_share,
                         (SELECT COUNT(*) FROM silver_medal_awards a WHERE a.games_id=sp.games_id) medal_awards FROM silver_participations sp GROUP BY games_id) ge ON ge.games_id=g.games_id
      GROUP BY g.season;

    DROP TABLE IF EXISTS gold_records;
    CREATE TABLE gold_records AS
      SELECT r.record_id, r.games_id, r.noc_code, r.record_type, r.record_value, r.record_date, r.description, r.athlete_id, r.source_url,
             CASE WHEN r.record_type LIKE '%WR%' OR r.record_type='WB' THEN 'world' ELSE 'olympic' END AS record_level
      FROM records r WHERE r.games_id IS NOT NULL;
    """)

    # ======================= GOLD - per-Games marts, incremental =======================
    per_games = {
        "gold_edition_performance": """
          SELECT g.games_id, g.year, g.season, g.host_city, g.host_country, (SELECT host_noc FROM ref_host_noc h WHERE h.games_id=g.games_id) AS host_noc,
                 COUNT(DISTINCT p.athlete_id) AS athletes, COUNT(DISTINCT CASE WHEN p.noc_code!='UNK' THEN p.noc_code END) AS nocs, COUNT(DISTINCT p.sport_id) AS sports, COUNT(DISTINCT p.event_id) AS events,
                 (SELECT COUNT(*) FROM silver_medal_awards a WHERE a.games_id=g.games_id) AS medal_awards,
                 (SELECT COUNT(DISTINCT result_id) FROM silver_medal_awards a WHERE a.games_id=g.games_id) AS medal_events,
                 COUNT(DISTINCT CASE WHEN p.gender='M' THEN p.athlete_id END) AS male_athletes, COUNT(DISTINCT CASE WHEN p.gender='F' THEN p.athlete_id END) AS female_athletes,
                 ROUND(1.0*COUNT(DISTINCT CASE WHEN p.gender='F' THEN p.athlete_id END)/NULLIF(COUNT(DISTINCT CASE WHEN p.gender IN ('M','F') THEN p.athlete_id END),0),4) AS female_share,
                 ROUND(AVG(p.age),2) AS mean_age, g.opening_date, g.closing_date
          FROM games g LEFT JOIN silver_participations p ON p.games_id=g.games_id WHERE g.games_id=:g GROUP BY g.games_id""",
        "gold_country_medals": """
          SELECT c.games_id, g.year, g.season, c.noc_code, c.country_name, c.gold, c.silver, c.bronze, c.total, c.official_rank,
                 ROUND(1.0*c.gold/NULLIF(c.total,0),4) AS gold_ratio,
                 ROUND(1.0*c.total/NULLIF((SELECT SUM(total) FROM silver_country_medals x WHERE x.games_id=c.games_id),0),4) AS medal_share,
                 (SELECT COUNT(DISTINCT athlete_id) FROM silver_participations p WHERE p.games_id=c.games_id AND p.noc_code=c.noc_code) AS athletes,
                 (SELECT COUNT(DISTINCT sport_id) FROM silver_participations p WHERE p.games_id=c.games_id AND p.noc_code=c.noc_code) AS sports,
                 CASE WHEN c.noc_code=(SELECT host_noc FROM ref_host_noc h WHERE h.games_id=c.games_id) THEN 1 ELSE 0 END AS is_host,
                 c.wikipedia_total, c.total-COALESCE(c.wikipedia_total,0) AS reconciliation_diff,
                 (SELECT COUNT(*)+1 FROM silver_country_medals y WHERE y.games_id=c.games_id AND (y.gold>c.gold OR (y.gold=c.gold AND y.silver>c.silver) OR (y.gold=c.gold AND y.silver=c.silver AND y.bronze>c.bronze))) AS rank_by_gold_silver_bronze
          FROM silver_country_medals c JOIN games g ON g.games_id=c.games_id WHERE c.games_id=:g""",
        "gold_sport_performance": """
          SELECT p.games_id, p.year, p.season, p.sport_id, p.sport_name, COUNT(DISTINCT p.athlete_id) AS athletes, COUNT(DISTINCT CASE WHEN p.noc_code!='UNK' THEN p.noc_code END) AS nocs, COUNT(DISTINCT p.event_id) AS events,
                 (SELECT COUNT(*) FROM silver_medal_awards a WHERE a.games_id=p.games_id AND a.sport_id=p.sport_id) AS medal_awards,
                 COUNT(DISTINCT CASE WHEN p.gender='F' THEN p.athlete_id END) AS female_athletes, COUNT(DISTINCT CASE WHEN p.gender='M' THEN p.athlete_id END) AS male_athletes,
                 (SELECT COUNT(DISTINCT noc_code) FROM silver_medal_awards a WHERE a.games_id=p.games_id AND a.sport_id=p.sport_id) AS medal_winning_nocs
          FROM silver_participations p WHERE p.games_id=:g AND p.sport_id IS NOT NULL GROUP BY p.games_id, p.sport_id""",
        "gold_gender_participation": """
          SELECT p.games_id, p.year, p.season, p.sport_name, p.gender, COUNT(DISTINCT p.athlete_id) AS athletes, SUM(p.is_medalist) AS medal_participations
          FROM silver_participations p WHERE p.games_id=:g AND p.gender IN ('M','F') GROUP BY p.games_id, p.sport_name, p.gender""",
    }
    changed = []
    if a.full:   # --full also recreates the per-Games tables so a changed mart schema can never be silently mis-filled
        for t in (*per_games, 'gold_event_results', 'gold_team_sports'):
            con.execute(f'DROP TABLE IF EXISTS {t}')
        con.execute("DELETE FROM gold_build_state")
    for g in games:
        f = fp(con, g)
        old = con.execute("SELECT fingerprint FROM gold_build_state WHERE mart='per_games' AND games_id=?", (g,)).fetchone()
        if old and old[0] == f and not a.full:
            continue
        changed.append(g)
        for t, sql in per_games.items():
            if con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone():
                con.execute(f"DELETE FROM {t} WHERE games_id=?", (g,))
                con.execute(f"INSERT INTO {t} {sql}", {"g": g})
            else:
                con.execute(f"CREATE TABLE {t} AS {sql}", {"g": g})
        # event results mart (podiums with parsed performance) - Olympedia standings
        con.execute("CREATE TABLE IF NOT EXISTS gold_event_results(games_id TEXT, year INT, season TEXT, sport_name TEXT, event_name TEXT, result_id TEXT, position TEXT, competitor TEXT, noc TEXT, medal TEXT, result_text TEXT, result_value REAL, result_unit TEXT, source_url TEXT)")
        con.execute("DELETE FROM gold_event_results WHERE games_id=?", (g,))
        # ALL finishers of every event (not just medallists): the final-standings table of each cached Olympedia event page (olympedia_event_rows, is_main=1),
        # falling back to olympedia_standings for events whose page is not cached. Rounds (heats, semi-finals ...) go to gold_event_phases.
        rows = con.execute("SELECT e.games_id, gm.year, gm.season, COALESCE(e.sport_name,''), COALESCE(e.event_name,''), e.result_id, e.position, e.competitor, e.noc, e.medal, e.result_text, e.source_url "
                           "FROM olympedia_event_rows e JOIN games gm ON gm.games_id=e.games_id WHERE e.games_id=? AND e.is_main=1", (g,)).fetchall()
        have = {r[5] for r in rows}
        rows += [r for r in con.execute("SELECT s.games_id, gm.year, gm.season, s.sport_name, s.event_name, s.result_id, s.position, s.competitor, s.noc, NULLIF(s.medal,''), s.result_value, s.source_url "
                                        "FROM olympedia_standings s JOIN games gm ON gm.games_id=s.games_id WHERE s.games_id=? AND s.is_phase=0", (g,)).fetchall() if r[5] not in have]
        con.executemany("INSERT INTO gold_event_results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [(*r[:10], r[10], *parse_perf(r[10]), r[11]) for r in rows])
        con.execute("CREATE TABLE IF NOT EXISTS gold_event_phases(games_id TEXT, year INT, season TEXT, sport_name TEXT, event_name TEXT, result_id TEXT, phase TEXT, position TEXT, competitor TEXT, noc TEXT, result_text TEXT, result_value REAL, result_unit TEXT, source_url TEXT)")
        con.execute("DELETE FROM gold_event_phases WHERE games_id=?", (g,))
        ph = con.execute("SELECT e.games_id, gm.year, gm.season, COALESCE(e.sport_name,''), COALESCE(e.event_name,''), e.result_id, e.phase, e.position, e.competitor, e.noc, e.result_text, e.source_url "
                         "FROM olympedia_event_rows e JOIN games gm ON gm.games_id=e.games_id WHERE e.games_id=? AND e.is_main=0", (g,)).fetchall()
        con.executemany("INSERT INTO gold_event_phases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [(*r[:10], r[10], *parse_perf(r[10]), r[11]) for r in ph])
        # team sports mart
        con.execute("CREATE TABLE IF NOT EXISTS gold_team_sports(games_id TEXT, sport_name TEXT, team TEXT, noc TEXT, played INT, won INT, drawn INT, lost INT, goals_for INT, goals_against INT, goal_diff INT, points_per_game REAL)")
        con.execute("DELETE FROM gold_team_sports WHERE games_id=?", (g,))
        ph = ",".join("?" * len(TEAM_SPORTS))
        con.execute(f"""INSERT INTO gold_team_sports
          SELECT games_id, sport_name, team, noc, COUNT(*), SUM(w), SUM(d), SUM(l), SUM(gf), SUM(ga), SUM(gf-ga), ROUND(AVG(CASE WHEN w=1 THEN 3.0 WHEN d=1 THEN 1.0 ELSE 0 END),3) FROM (
            SELECT games_id, sport_name, home_team team, home_noc noc, CAST(home_score AS INT) gf, CAST(away_score AS INT) ga, home_score>away_score w, home_score=away_score d, home_score<away_score l FROM olympedia_matches
              WHERE games_id=? AND sport_name IN ({ph}) AND home_score GLOB '[0-9]*' AND away_score GLOB '[0-9]*'
            UNION ALL
            SELECT games_id, sport_name, away_team, away_noc, CAST(away_score AS INT), CAST(home_score AS INT), away_score>home_score, away_score=home_score, away_score<home_score FROM olympedia_matches
              WHERE games_id=? AND sport_name IN ({ph}) AND home_score GLOB '[0-9]*' AND away_score GLOB '[0-9]*') GROUP BY games_id, sport_name, team, noc""", (g, *TEAM_SPORTS, g, *TEAM_SPORTS))
        con.execute("INSERT OR REPLACE INTO gold_build_state VALUES ('per_games',?,?,?)", (g, f, run))
    con.commit()

    # ---- host performance mart (needs several Games at once -> full rebuild)
    con.executescript("""
    DROP TABLE IF EXISTS gold_host_performance;
    CREATE TABLE gold_host_performance AS
      SELECT h.games_id, g.year, g.season, h.host_noc,
             COALESCE((SELECT total FROM silver_country_medals c WHERE c.games_id=h.games_id AND c.noc_code=h.host_noc),0) AS host_medals,
             COALESCE((SELECT gold FROM silver_country_medals c WHERE c.games_id=h.games_id AND c.noc_code=h.host_noc),0) AS host_gold,
             (SELECT total FROM silver_country_medals c JOIN games gp ON gp.games_id=c.games_id WHERE c.noc_code=h.host_noc AND gp.season=g.season AND gp.year<g.year ORDER BY gp.year DESC LIMIT 1) AS prev_edition_medals,
             (SELECT total FROM silver_country_medals c JOIN games gn ON gn.games_id=c.games_id WHERE c.noc_code=h.host_noc AND gn.season=g.season AND gn.year>g.year ORDER BY gn.year ASC LIMIT 1) AS next_edition_medals,
             (SELECT ROUND(AVG(total),2) FROM silver_country_medals c JOIN games gx ON gx.games_id=c.games_id WHERE c.noc_code=h.host_noc AND gx.season=g.season AND gx.games_id!=h.games_id) AS mean_non_host_medals,
             (SELECT official_rank FROM silver_country_medals c WHERE c.games_id=h.games_id AND c.noc_code=h.host_noc) AS host_rank,
             (SELECT athletes FROM gold_edition_performance e WHERE e.games_id=h.games_id) AS edition_athletes,
             (SELECT COUNT(DISTINCT athlete_id) FROM silver_participations p WHERE p.games_id=h.games_id AND p.noc_code=h.host_noc) AS host_athletes
      FROM ref_host_noc h JOIN games g ON g.games_id=h.games_id;
    """)
    marts = [r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'gold_%' AND name!='gold_build_state' ORDER BY name")]
    summary = {m: q(f"SELECT COUNT(*) FROM {m}")[0][0] for m in marts}
    con.execute("UPDATE pipeline_runs SET finished_at=?, status='success', detail=? WHERE run_id=?",
                (dt.datetime.now(dt.timezone.utc).isoformat(), json.dumps({"silver": silver, "gold": summary, "games_rebuilt": changed}), rid))
    con.commit()
    print("silver:", silver)
    print("gold:", summary)
    print("Games rebuilt this run:", len(changed), "of", len(games))


if __name__ == "__main__":
    main()
