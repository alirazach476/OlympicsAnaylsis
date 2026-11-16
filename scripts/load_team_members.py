#!/usr/bin/env python3
"""team_members <- olympedia_rosters (team entries). Offline & idempotent.

1. teams: one row per (games, sport, NOC, team) found in the rosters (relays, rowing, sailing ... not only ball sports).
2. athletes: roster athletes with no Kaggle-style link get an 'olympedia:<id>' athlete row (name/sex/NOC from the roster + bios);
   nothing is merged into existing athletes, so no false identity matches.
3. team_members: every roster team row, resolved through athlete_id_map (Kaggle link) or the 'olympedia:<id>' identity.
"""
import sqlite3
from pathlib import Path

c = sqlite3.connect(Path(__file__).resolve().parents[1] / 'data/olympics_warehouse.db', timeout=300)
c.execute('PRAGMA busy_timeout=300000')

c.executescript("""
DROP TABLE IF EXISTS _sport_canon;
CREATE TEMP TABLE _sport_canon AS SELECT lower(sport_name) AS n, MIN(sport_id) AS sport_id FROM sports GROUP BY 1;
""")

c.execute("""INSERT OR IGNORE INTO teams(games_id,sport_id,noc_code,team_name,source_url,verification_status,created_at,updated_at)
SELECT DISTINCT r.games_id, s.sport_id, r.noc, r.team, 'https://www.olympedia.org', 'collected', datetime('now'), datetime('now')
FROM olympedia_rosters r JOIN _sport_canon s ON s.n=lower(r.sport)
WHERE r.team IS NOT NULL AND r.team!='' AND r.games_id IS NOT NULL""")

c.execute("""INSERT OR IGNORE INTO athletes(full_name,gender,nationality,identity_key,source_url,verification_status,created_at,updated_at)
SELECT r.athlete_name,
       CASE b.Sex WHEN 'Male' THEN 'M' WHEN 'Female' THEN 'F' END,
       COALESCE(b.NOC, r.noc),
       'olympedia:'||r.athlete_id, 'https://www.olympedia.org/athletes/'||r.athlete_id, 'olympedia_roster',
       datetime('now'), datetime('now')
FROM (SELECT athlete_id, MIN(athlete_name) athlete_name, MIN(noc) noc FROM olympedia_rosters
      WHERE team IS NOT NULL AND team!='' AND athlete_id IS NOT NULL AND athlete_id!='' GROUP BY athlete_id) r
LEFT JOIN athlete_id_map m ON m.olympedia_athlete_id=r.athlete_id
LEFT JOIN athletes ak ON ak.identity_key='athlete_events:'||m.kaggle_id
LEFT JOIN src_athlete_bios b ON b.athlete_id=r.athlete_id
WHERE ak.athlete_id IS NULL AND r.athlete_name IS NOT NULL AND r.athlete_name!=''""")

# bio fields for roster-only athletes straight from the bios CSV (same Olympedia id, no matching needed)
import re
def _split(x):
    m = re.match(r'^(.*?) in (.*)$', x or ''); return (m.group(1) or None, m.group(2)) if m else (x or None, None)
rows = c.execute("""SELECT a.athlete_id, b.Born, b.Died, b."Original name", b.Measurements, b.athlete_id
                    FROM athletes a JOIN src_athlete_bios b ON 'olympedia:'||b.athlete_id=a.identity_key
                    WHERE a.verification_status='olympedia_roster' AND a.date_of_birth IS NULL""").fetchall()
for aid, born, died, orig, meas, oid in rows:
    d1, bp = _split(born); d2, _ = _split(died)
    m = re.match(r'^(\d+) cm(?: / (\d+) kg)?', meas or '')
    c.execute("UPDATE athletes SET date_of_birth=COALESCE(date_of_birth,?), date_of_death=COALESCE(date_of_death,?), original_name=COALESCE(original_name,?),"
              " biography=COALESCE(biography,?), height_cm=COALESCE(height_cm,?), weight_kg=COALESCE(weight_kg,?) WHERE athlete_id=?",
              (d1, d2, orig or None, ('Born in ' + bp) if bp else None, int(m.group(1)) if m else None, int(m.group(2)) if m and m.group(2) else None, aid))
c.commit()

c.execute('DELETE FROM team_members')
c.execute("""INSERT OR IGNORE INTO team_members(team_id,athlete_id,role,jersey_number,verification_status,created_at,updated_at)
SELECT t.team_id, a.athlete_id, MIN(r.position), NULL, 'collected', datetime('now'), datetime('now')
FROM olympedia_rosters r
JOIN _sport_canon s ON s.n=lower(r.sport)
JOIN teams t ON t.sport_id=s.sport_id AND t.games_id=r.games_id AND t.noc_code=r.noc AND t.team_name=r.team
LEFT JOIN athlete_id_map m ON m.olympedia_athlete_id=r.athlete_id
LEFT JOIN athletes ak ON ak.identity_key='athlete_events:'||m.kaggle_id
JOIN athletes a ON a.athlete_id=COALESCE(ak.athlete_id, (SELECT athlete_id FROM athletes WHERE identity_key='olympedia:'||r.athlete_id))
WHERE r.team IS NOT NULL AND r.team!=''
GROUP BY t.team_id, a.athlete_id""")
c.commit()

tot = c.execute("select count(*) from (select distinct games_id,noc,team,sport,athlete_id from olympedia_rosters where team!='')").fetchone()[0]
print('team_members', c.execute('select count(*) from team_members').fetchone()[0], 'of', tot, 'distinct roster team entries',
      '| teams', c.execute('select count(*) from teams').fetchone()[0],
      '| olympedia_roster athletes', c.execute("select count(*) from athletes where verification_status='olympedia_roster'").fetchone()[0])
