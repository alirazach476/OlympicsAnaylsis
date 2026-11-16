#!/usr/bin/env python3
"""Fill athlete-stat gaps from data already in the warehouse (offline, idempotent, NULL/empty fields only, nothing invented):
  athletes.nationality           <- most frequent participation country of the athlete (NOC name when only a code is known)
  athletes.gender                <- bios CSV Sex / Olympedia results gender via the Olympedia link (M/F)
  athlete_participations         <- noc_code / country / team from olympedia_athlete_results (same Olympedia athlete + Games)
Run after link_athletes_to_olympedia_results.py."""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / 'data/olympics_warehouse.db', timeout=300)
c.execute('PRAGMA busy_timeout=300000')

# athlete -> Olympedia id (Kaggle-style link or roster-only identity)
link = pd.read_sql("""SELECT a.athlete_id, COALESCE(m.olympedia_athlete_id,
         CASE WHEN a.identity_key LIKE 'olympedia:%' THEN substr(a.identity_key,11) END) oid
       FROM athletes a LEFT JOIN athlete_id_map m ON m.kaggle_id=substr(a.identity_key,16)""", c)
link = link[link.oid.notna()]

# 1) participation NOC / country / team from Olympedia results
o = pd.read_sql("SELECT athlete_id oid, games_id, noc, country, team FROM olympedia_athlete_results", c)
o = o.sort_values(['oid', 'games_id']).drop_duplicates(['oid', 'games_id'])
p = pd.read_sql("""SELECT participation_id, athlete_id, games_id FROM athlete_participations
                   WHERE noc_code IS NULL OR country IS NULL OR team IS NULL""", c)
p = p.merge(link, on='athlete_id').merge(o, on=['oid', 'games_id'])
n_p = 0
for r in p.itertuples():
    n_p += c.execute("UPDATE athlete_participations SET noc_code=COALESCE(noc_code,?), country=COALESCE(country,?), team=COALESCE(team,?) WHERE participation_id=?",
                     (r.noc, r.country, r.team if r.team else None, r.participation_id)).rowcount
c.commit()

# 2) gender
bios = pd.read_sql("SELECT athlete_id oid, Sex FROM src_athlete_bios", c).drop_duplicates('oid')
bios['g'] = bios.Sex.map({'Male': 'M', 'Female': 'F'})
og = pd.read_sql("SELECT DISTINCT athlete_id oid, CASE gender WHEN 'Men' THEN 'M' WHEN 'Women' THEN 'F' END g FROM olympedia_athlete_results WHERE gender IN ('Men','Women')", c)
og = og[~og.oid.duplicated(keep=False)]
gmap = pd.concat([bios[['oid', 'g']].dropna(), og]).drop_duplicates('oid')
g = pd.read_sql("SELECT athlete_id FROM athletes WHERE gender IS NULL OR gender=''", c).merge(link, on='athlete_id').merge(gmap, on='oid')
n_g = sum(c.execute("UPDATE athletes SET gender=? WHERE athlete_id=?", (r.g, r.athlete_id)).rowcount for r in g.itertuples())
c.commit()

# 3) nationality = most frequent participation country, else NOC name
pc = pd.read_sql("SELECT athlete_id, country, noc_code FROM athlete_participations", c)
top = (pc[pc.country.notna() & (pc.country != '')].groupby(['athlete_id', 'country']).size().reset_index(name='n')
       .sort_values(['athlete_id', 'n'], ascending=[True, False]).drop_duplicates('athlete_id'))
names = dict(c.execute("SELECT noc_code, historical_name FROM historical_nocs").fetchall())
nat = dict(zip(top.athlete_id, top.country))
for r in pc[pc.noc_code.notna()].drop_duplicates('athlete_id').itertuples():
    if r.athlete_id not in nat and r.noc_code in names:
        nat[r.athlete_id] = names[r.noc_code]
n_n = 0
for aid, nv in nat.items():
    n_n += c.execute("UPDATE athletes SET nationality=? WHERE athlete_id=? AND (nationality IS NULL OR nationality='')", (nv, aid)).rowcount
c.commit()

q = lambda s: c.execute(s).fetchone()
print('participations filled', n_p, '| gender filled', n_g, '| nationality filled', n_n)
print('now missing: gender', q("SELECT COUNT(*) FROM athletes WHERE gender IS NULL OR gender=''")[0],
      '| nationality', q("SELECT COUNT(*) FROM athletes WHERE nationality IS NULL OR nationality=''")[0],
      '| participation noc/country/team', q("SELECT SUM(noc_code IS NULL), SUM(country IS NULL), SUM(team IS NULL) FROM athlete_participations"))
