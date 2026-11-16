#!/usr/bin/env python3
"""Fill master-spec fields that can be DERIVED from data already in the warehouse (offline, idempotent, nothing invented):
sports first/last appearance + latest-edition event counts + discontinued flag; historical_nocs appearance/athlete/medal totals;
games.olympedia_url; sources / source_pages provenance; sport-wise and event-wise medal tables (team medals counted once)."""
import sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS
c = sqlite3.connect(ROOT/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
G = "CASE WHEN {g} IN ('M','Men') THEN 'm' WHEN {g} IN ('F','Women') THEN 'w' WHEN {g} IN ('X','Mixed') THEN 'x' END"
# --- sports
c.execute("""CREATE TEMP TABLE sp AS SELECT e.sport_id, g.season, MIN(g.year) first_y, MAX(g.year) last_y FROM events e JOIN games g ON g.games_id=e.games_id
  WHERE g.year BETWEEN 1960 AND 2026 AND e.sport_id IS NOT NULL AND e.event_id IN (SELECT event_id FROM event_results) GROUP BY e.sport_id, g.season""")
c.execute("""UPDATE sports SET first_appearance=(SELECT MIN(first_y) FROM sp WHERE sp.sport_id=sports.sport_id), last_appearance=(SELECT MAX(last_y) FROM sp WHERE sp.sport_id=sports.sport_id)""")
last_ed = """(SELECT e.event_id, e.event_gender FROM events e JOIN games g ON g.games_id=e.games_id WHERE e.sport_id=sports.sport_id AND g.year=sports.last_appearance
   AND e.event_id IN (SELECT event_id FROM event_results))"""
c.execute(f"""UPDATE sports SET number_of_events=(SELECT COUNT(*) FROM {last_ed}) WHERE last_appearance IS NOT NULL""")
for col, k in (('mens_events', 'm'), ('womens_events', 'w'), ('mixed_events', 'x')):
    c.execute(f"UPDATE sports SET {col}=(SELECT COUNT(*) FROM {last_ed} WHERE {G.format(g='event_gender')}='{k}') WHERE last_appearance IS NOT NULL")
c.execute("""UPDATE sports SET is_discontinued=CASE WHEN last_appearance IS NULL THEN is_discontinued
  WHEN season='winter' AND last_appearance<2026 THEN 1 WHEN season='summer' AND last_appearance<2024 THEN 1 ELSE 0 END""")
# --- historical NOCs
c.execute("""UPDATE historical_nocs SET
 first_olympic_appearance=(SELECT MIN(g.year) FROM athlete_participations p JOIN games g ON g.games_id=p.games_id WHERE p.noc_code=historical_nocs.noc_code AND g.year<=2026),
 last_olympic_appearance=(SELECT MAX(g.year) FROM athlete_participations p JOIN games g ON g.games_id=p.games_id WHERE p.noc_code=historical_nocs.noc_code AND g.year<=2026),
 olympic_appearances=(SELECT COUNT(DISTINCT p.games_id) FROM athlete_participations p WHERE p.noc_code=historical_nocs.noc_code),
 total_athletes=(SELECT COUNT(DISTINCT p.athlete_id) FROM athlete_participations p WHERE p.noc_code=historical_nocs.noc_code),
 total_medals=(SELECT COUNT(*) FROM (SELECT DISTINCT event_id, medal_type FROM medals m WHERE m.noc_code=historical_nocs.noc_code))""")
c.execute("UPDATE historical_nocs SET valid_from_year=first_olympic_appearance, valid_to_year=CASE WHEN last_olympic_appearance>=2024 THEN NULL ELSE last_olympic_appearance END WHERE first_olympic_appearance IS NOT NULL")
# --- games.olympedia_url
for gid, eid in OLYMPEDIA_EDITION_IDS.items():
    c.execute("UPDATE games SET olympedia_url=? WHERE games_id=?", (f'https://www.olympedia.org/editions/{eid}', gid))
# --- sources / source_pages
srcs = [('olympedia', 'https://www.olympedia.org', 'Olympedia terms (check before redistribution)', 10, 'Primary results, rosters, matches, venues, records, athlete bios.'),
        ('wikipedia', 'https://en.wikipedia.org', 'CC BY-SA 4.0', 30, 'Edition pages, medal tables, venues; text needs attribution.'),
        ('kaggle_style_athlete_events_csv', 'local:athlete_events.csv/', 'See upstream', 50, 'athlete_events.csv, bios.csv, results.csv, olympics.csv, noc_regions.csv (athlete_events.csv/ folder).'),
        ('olympics_official', 'https://www.olympics.com', 'IOC terms', 1, 'NOT collected yet (connector is a stub).')]
for n, u, l, r, note in srcs:
    if not c.execute('select 1 from sources where name=?', (n,)).fetchone():
        c.execute("INSERT INTO sources(name,base_url,license,authority_rank,notes,created_at,updated_at) VALUES (?,?,?,?,?,datetime('now'),datetime('now'))", (n, u, l, r, note))
sid = c.execute("select source_id from sources where name='olympedia'").fetchone()[0]
c.execute("DELETE FROM source_pages WHERE source_id=?", (sid,))
c.execute("""INSERT INTO source_pages(source_id,url,title,fetched_at,http_status,content_hash,raw_path,verification_status,created_at,updated_at)
 SELECT ?, 'https://www.olympedia.org'||path, title, fetched_at, 200, NULL, 'data/raw/olympedia_site', 'collected', datetime('now'), datetime('now') FROM olympedia_site_pages""", (sid,))
# --- sport / event medal tables (medal_tables is unique per games+noc+scope, so these get their own tables; team medals counted once)
c.executescript("""DROP TABLE IF EXISTS medal_table_by_sport; DROP TABLE IF EXISTS medal_table_by_event;
CREATE TABLE medal_table_by_sport(games_id TEXT, sport_id INTEGER, noc_code TEXT, country_name TEXT, gold INTEGER, silver INTEGER, bronze INTEGER, total INTEGER, source TEXT, PRIMARY KEY(games_id,sport_id,noc_code));
CREATE TABLE medal_table_by_event(games_id TEXT, sport_id INTEGER, event_id INTEGER, noc_code TEXT, country_name TEXT, gold INTEGER, silver INTEGER, bronze INTEGER, total INTEGER, source TEXT, PRIMARY KEY(event_id,noc_code));""")
base = "FROM (SELECT DISTINCT m.games_id, e.sport_id, m.event_id, m.noc_code, m.medal_type FROM medals m JOIN events e ON e.event_id=m.event_id) x"
nm = "(SELECT historical_name FROM historical_nocs h WHERE h.noc_code=x.noc_code LIMIT 1)"
agg = "SUM(medal_type='Gold'), SUM(medal_type='Silver'), SUM(medal_type='Bronze'), COUNT(*), 'derived:warehouse medals'"
c.execute(f"INSERT INTO medal_table_by_sport SELECT games_id, sport_id, noc_code, {nm}, {agg} {base} GROUP BY games_id, sport_id, noc_code")
c.execute(f"INSERT INTO medal_table_by_event SELECT games_id, sport_id, event_id, noc_code, {nm}, {agg} {base} GROUP BY event_id, noc_code")
c.commit()
q = lambda s: c.execute(s).fetchall()
print('sports w/ first_appearance', q('select count(*) from sports where first_appearance is not null'), 'discontinued', q('select count(*) from sports where is_discontinued=1'))
print('nocs filled', q('select count(*),sum(total_medals>0) from historical_nocs where first_olympic_appearance is not null'))
print('by_sport', q('select count(*) from medal_table_by_sport'), 'by_event', q('select count(*) from medal_table_by_event'), 'sources', q('select count(*) from sources'), 'source_pages', q('select count(*) from source_pages'))
print(q("select sport_name,first_appearance,last_appearance,number_of_events,mens_events,womens_events,mixed_events,is_discontinued from sports where first_appearance is not null order by last_appearance limit 6"))
