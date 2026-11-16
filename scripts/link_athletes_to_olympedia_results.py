#!/usr/bin/env python3
"""Second linking pass for warehouse athletes (identity 'athlete_events:<ID>') that link_athletes_to_bios.py could not link - mainly the
2020-2026 athletes of athlete_events_through_2026.csv, whose IDs are NOT Olympedia IDs. Candidates come from the scraped Olympedia
results (olympedia_athlete_results: Olympedia id + name + NOC + Games + sex for all 35 editions). Only unambiguous links are used:
  pass 1  normalised name + Games + NOC + sex      (unique on both sides)
  pass 2  normalised name + Games + sex            (unique on both sides; NOC missing/different)
  pass 3  normalised name + NOC + sex, any Games   (unique among ALL Olympedia athletes and among ALL unlinked warehouse athletes)
A warehouse athlete maps to one Olympedia id and an Olympedia id to one warehouse athlete. New links are appended to athlete_id_map
(rebuilt by link_athletes_to_bios.py, so this runs right after it) and DOB / DOD / birthplace / original name / measurements are
filled from the bios CSV into NULL fields only. Offline & idempotent."""
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / 'data/olympics_warehouse.db', timeout=300)
c.execute('PRAGMA busy_timeout=300000')


def norm(s):
    s = ''.join(ch for ch in unicodedata.normalize('NFKD', str(s or '')) if not unicodedata.combining(ch)).lower()
    s = re.sub(r'[^a-z ]', ' ', s.replace('•', ' '))
    return ' '.join(sorted(s.split()))


w = pd.read_sql("""SELECT a.athlete_id, substr(a.identity_key,16) kid, a.full_name, a.gender g, p.games_id, p.noc_code noc
                   FROM athletes a JOIN athlete_participations p USING(athlete_id)
                   WHERE a.identity_key LIKE 'athlete_events:%'""", c).drop_duplicates()
o = pd.read_sql("""SELECT DISTINCT athlete_id oid, athlete_name, noc, games_id,
                   CASE gender WHEN 'Men' THEN 'M' WHEN 'Women' THEN 'F' END g FROM olympedia_athlete_results""", c)
w['n'] = w.full_name.map(norm)
o['n'] = o.athlete_name.map(norm)
already = c.execute("SELECT kaggle_id, olympedia_athlete_id FROM athlete_id_map").fetchall()
mapped_k = {str(k) for k, _ in already}
mapped_o = {str(x) for _, x in already}
w = w[~w.kid.isin(mapped_k)]
o_free = o[~o.oid.astype(str).isin(mapped_o)]
print('unlinked warehouse athletes', w.athlete_id.nunique(), '| free Olympedia ids', o_free.oid.nunique())


def link(wk, ok, keys, o_all=None):
    wk = wk.copy(); ok = ok.copy()
    wk['k'] = wk[keys].astype(str).agg('|'.join, axis=1)
    ok['k'] = ok[keys].astype(str).agg('|'.join, axis=1)
    if o_all is not None:
        o_all = o_all.copy(); o_all['k'] = o_all[keys].astype(str).agg('|'.join, axis=1)
        bn = o_all.groupby('k').oid.nunique()
    else:
        bn = ok.groupby('k').oid.nunique()
    an = wk.groupby('k').athlete_id.nunique()
    good = set(an[an == 1].index) & set(bn[bn == 1].index)
    pr = wk[wk.k.isin(good)][['athlete_id', 'kid', 'k']].drop_duplicates().merge(
        ok[ok.k.isin(good)][['oid', 'k']].drop_duplicates(), on='k')[['athlete_id', 'kid', 'oid']].drop_duplicates()
    return pr


pairs = []
taken_a, taken_o = set(), set()
for label, keys, use_all in (('name+games+noc+sex', ['n', 'games_id', 'noc', 'g'], False),
                             ('name+games+sex', ['n', 'games_id', 'g'], False),
                             ('name+noc+sex (any games)', ['n', 'noc', 'g'], True)):
    wk = w[~w.athlete_id.isin(taken_a)]
    ok = o_free[~o_free.oid.isin(taken_o)]
    if keys[1] != 'games_id':
        wk = wk.drop(columns=['games_id']).drop_duplicates(); ok = ok.drop(columns=['games_id']).drop_duplicates()
    pr = link(wk, ok, keys, o_all=o.drop(columns=['games_id']).drop_duplicates() if use_all else None)
    pr = pr[~pr.athlete_id.duplicated(keep=False) & ~pr.oid.duplicated(keep=False)]
    print(label, 'adds', len(pr))
    taken_a |= set(pr.athlete_id); taken_o |= set(pr.oid)
    pairs.append(pr)
pairs = pd.concat(pairs).drop_duplicates()

c.executemany('INSERT OR IGNORE INTO athlete_id_map(kaggle_id, olympedia_athlete_id) VALUES (?,?)',
              [(str(k), str(x)) for k, x in zip(pairs.kid, pairs.oid)])
b = pd.read_sql('SELECT athlete_id, Born, Died, "Original name" orig, Measurements FROM src_athlete_bios', c).drop_duplicates('athlete_id').set_index('athlete_id')


def split(x):
    m = re.match(r'^(.*?) in (.*)$', x or '')
    return (m.group(1) or None, m.group(2)) if m else (x or None, None)


upd = 0
for kid, oid in zip(pairs.kid, pairs.oid):
    oid = str(oid)
    if oid not in b.index:
        continue
    r = b.loc[oid]
    born, bp = split(r.Born); died, _ = split(r.Died)
    m = re.match(r'^(\d+) cm(?: / (\d+) kg)?', r.Measurements or '')
    upd += c.execute(
        "UPDATE athletes SET date_of_birth=COALESCE(date_of_birth,?), date_of_death=COALESCE(date_of_death,?), original_name=COALESCE(original_name,?),"
        " biography=COALESCE(biography,?), height_cm=COALESCE(height_cm,?), weight_kg=COALESCE(weight_kg,?), source_url=? WHERE identity_key=?",
        (born, died, r.orig or None, ('Born in ' + bp) if bp else None, int(m.group(1)) if m else None,
         int(m.group(2)) if m and m.group(2) else None, f'https://www.olympedia.org/athletes/{oid}', f'athlete_events:{kid}')).rowcount
c.commit()
print('new links', len(pairs), '| athletes updated from bios', upd)
print(c.execute('SELECT count(*), sum(date_of_birth IS NOT NULL) FROM athletes').fetchone())
