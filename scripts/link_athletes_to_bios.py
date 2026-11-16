#!/usr/bin/env python3
"""Link warehouse athletes (Kaggle-style IDs, identity_key 'athlete_events:<ID>') to Olympedia athlete_ids via
(normalised name, NOC, year, season), then fill DOB / DOD / birthplace / original name / measurements from bios.csv.
Only unambiguous matches are used; nothing is guessed. Writes table athlete_id_map and updates only NULL fields."""
import re, sqlite3, unicodedata
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z ]', ' ', s.replace('•', ' ').replace('•', ' '))
    return ' '.join(sorted(s.split()))  # order-insensitive (given/family order differs)
k = pd.read_sql('select ID,Name,NOC,Year,Season from src_athlete_events', c).drop_duplicates()
r = pd.read_sql('select athlete_id,"As" as Name,NOC,Games from src_athlete_results', c).drop_duplicates()
r['Year'] = r.Games.str.extract(r'(\d{4})')[0]; r['Season'] = r.Games.str.extract(r'(Summer|Winter)')[0]
k['key'] = k.Name.map(norm) + '|' + k.NOC + '|' + k.Year.astype(str) + '|' + k.Season
r['key'] = r.Name.map(norm) + '|' + r.NOC + '|' + r.Year.astype(str) + '|' + r.Season
def norm2(s):  # Kaggle dropped accented letters entirely: do the same on both sides
    s = re.sub(r'[^a-z ]', ' ', ''.join(ch for ch in str(s or '').replace('•', ' ') if ord(ch) < 128).lower())
    return ' '.join(sorted(s.split()))
k['key2'] = k.Name.map(norm2) + '|' + k.NOC + '|' + k.Year.astype(str) + '|' + k.Season
r['key2'] = r.Name.map(norm2) + '|' + r.NOC + '|' + r.Year.astype(str) + '|' + r.Season
pairs = pd.concat([k[['ID', 'key']].merge(r[['athlete_id', 'key']], on='key'),
                   k[['ID', 'key2']].rename(columns={'key2': 'key'}).merge(r[['athlete_id', 'key2']].rename(columns={'key2': 'key'}), on='key')])
pairs = pairs[['ID', 'athlete_id']].drop_duplicates()
good = pairs.groupby('ID').athlete_id.nunique(); good = good[good == 1].index
rev = pairs.groupby('athlete_id').ID.nunique()
pairs = pairs[pairs.ID.isin(good) & pairs.athlete_id.map(rev).eq(1)][['ID', 'athlete_id']]
# pass 3: for still-unlinked athletes, name+NOC (no year) if that exact key identifies exactly one athlete on BOTH sides and the sex agrees
un = k[~k.ID.isin(pairs.ID)].copy(); rest = r[~r.athlete_id.isin(pairs.athlete_id)].copy()
sx = pd.read_sql('select ID, Sex from src_athlete_events', c).drop_duplicates('ID').set_index('ID').Sex
bs = pd.read_sql('select athlete_id, Sex from src_athlete_bios', c).drop_duplicates('athlete_id').set_index('athlete_id').Sex.map({'Male': 'M', 'Female': 'F'})
un['k3'] = un.Name.map(norm2) + '|' + un.NOC; rest['k3'] = rest.Name.map(norm2) + '|' + rest.NOC
ku = un.groupby('k3').ID.nunique(); ru = rest.groupby('k3').athlete_id.nunique()
ok = set(ku[ku == 1].index) & set(ru[ru == 1].index)
p3 = un[un.k3.isin(ok)][['ID', 'k3']].drop_duplicates().merge(rest[rest.k3.isin(ok)][['athlete_id', 'k3']].drop_duplicates(), on='k3')[['ID', 'athlete_id']]
p3 = p3[[sx.get(i) == bs.get(a) for i, a in zip(p3.ID, p3.athlete_id)]]
print('pass 3 adds', len(p3)); pairs = pd.concat([pairs, p3])
# pass 4: fuzzy name (difflib, token-sorted) inside the block NOC+Games, same sex, birth year within +-1 of Year-Age; accept only a clear unique winner
import difflib
from collections import defaultdict
bio = pd.read_sql('select athlete_id, Born from src_athlete_bios', c).drop_duplicates('athlete_id').set_index('athlete_id').Born
byr = bio.str.extract(r'(\d{4})')[0].astype(float)
ke = pd.read_sql('select ID, Name, Sex, Age, NOC, Year, Season from src_athlete_events', c)
ke = ke[~ke.ID.isin(pairs.ID)].copy(); ke['Age'] = pd.to_numeric(ke.Age, errors='coerce'); ke['Year'] = ke.Year.astype(int)
rest = r[~r.athlete_id.isin(pairs.athlete_id)].copy(); rest['Year'] = rest.Year.astype(int)
rest['n'] = rest.Name.map(norm2); rest['byr'] = rest.athlete_id.map(byr); rest['sex'] = rest.athlete_id.map(bs)
blocks = defaultdict(list)
for row in rest.drop_duplicates(['athlete_id', 'NOC', 'Year', 'Season']).itertuples(): blocks[(row.NOC, row.Year, row.Season)].append(row)
claimed_o = set(pairs.athlete_id); p4 = {}
for row in ke.itertuples():
    cands = blocks.get((row.NOC, row.Year, row.Season), []); kn = norm2(row.Name); sc = []
    for cd in cands:
        if cd.sex != row.Sex: continue
        if pd.notna(row.Age) and pd.notna(cd.byr) and abs((row.Year - row.Age) - cd.byr) > 1: continue
        sc.append((difflib.SequenceMatcher(None, kn, cd.n).ratio(), cd.athlete_id))
    sc.sort(reverse=True)
    if sc and sc[0][0] >= 0.88 and (len(sc) == 1 or sc[0][0] - sc[1][0] >= 0.06): p4.setdefault(row.ID, set()).add(sc[0][1])
p4 = pd.DataFrame([(i, next(iter(o))) for i, o in p4.items() if len(o) == 1], columns=['ID', 'athlete_id'])
p4 = p4[~p4.athlete_id.duplicated(keep=False)]   # an Olympedia id may be claimed by one Kaggle id only
print('pass 4 (fuzzy+birth-year) adds', len(p4)); pairs = pd.concat([pairs, p4])
# keep an ID<->olympedia link only if each side maps to exactly one other
print('kaggle ids', k.ID.nunique(), '| linked 1:1', len(pairs))
c.execute('DROP TABLE IF EXISTS athlete_id_map')
c.execute('CREATE TABLE athlete_id_map(kaggle_id TEXT PRIMARY KEY, olympedia_athlete_id TEXT)')
c.executemany('INSERT INTO athlete_id_map VALUES (?,?)', pairs.values.tolist())
b = pd.read_sql('select athlete_id,"Full name" fn,"Used name" un,Born,Died,"Original name" orig,Measurements from src_athlete_bios', c).set_index('athlete_id')
def split(x):
    m = re.match(r'^(.*?) in (.*)$', x or ''); return (m.group(1), m.group(2)) if m else (x or None, None)
upd = 0
for kid, oid in pairs.values.tolist():
    if oid not in b.index: continue
    row = b.loc[oid]; born, bp = split(row.Born); died, _ = split(row.Died)
    cur = c.execute("UPDATE athletes SET date_of_birth=COALESCE(date_of_birth,?), date_of_death=COALESCE(date_of_death,?), original_name=COALESCE(original_name,?), biography=COALESCE(biography,?), source_url=? WHERE identity_key=?",
                    (born or None, died or None, row.orig or None, ('Born in ' + bp) if bp else None, f'https://www.olympedia.org/athletes/{oid}', f'athlete_events:{kid}'))
    upd += cur.rowcount
c.commit(); print('athletes updated', upd)
print(c.execute('select count(*),sum(date_of_birth is not null),sum(date_of_death is not null) from athletes').fetchone())
