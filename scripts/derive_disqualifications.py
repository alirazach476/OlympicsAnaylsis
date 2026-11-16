#!/usr/bin/env python3
"""Offline from cached Olympedia event pages: every 'DQ' row in a results table -> olympedia_disqualifications (with the page note sentence that
names that competitor / NOC and mentions doping, positive test, re-test, stripped, reallocation or disqualification, when one exists).
Then medals.reallocation_note is set for medallists of events where such a doping-type disqualification is documented (linked athletes only).
Olympedia shows CURRENT standings, so the medals table already reflects them; the note records that a reallocation/disqualification occurred."""
import glob, re, sqlite3
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT/'data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
c.executescript("""DROP TABLE IF EXISTS olympedia_disqualifications;
CREATE TABLE olympedia_disqualifications(id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, event_title TEXT, competitor TEXT, noc TEXT, context TEXT, is_doping_related INTEGER, source_url TEXT);""")
DOP = re.compile(r'doping|positive|re-?test|stripped|reallocat|steroid|banned substance|methylhexaneamine|tested|drug', re.I)
n = 0
for f in glob.glob(str(ROOT/'data/raw/olympedia/editions/*/events/*.html')):
    p = Path(f); gid, rid = p.parent.parent.name, p.stem
    h = p.read_text(encoding='utf-8', errors='replace')
    if 'DQ' not in h: continue
    s = BeautifulSoup(h, 'lxml'); title = s.h1.get_text(' ', strip=True) if s.h1 else None
    sents = [x for e in s.select('p') for x in re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', e.get_text(' ', strip=True)))]
    for t in s.select('table'):
        rows = t.select('tr')
        if not rows or 'Pos' not in [x.get_text(strip=True) for x in rows[0].select('th')]: continue
        hdr = [x.get_text(strip=True) for x in rows[0].select('th')]
        ic = next((i for i, x in enumerate(hdr) if x in ('Competitor', 'Competitors', 'Team', 'Pair', 'Crew')), None); inoc = hdr.index('NOC') if 'NOC' in hdr else None
        if ic is None: continue
        for tr in rows[1:]:
            td = tr.select('td')
            if len(td) > max(ic, inoc or 0) and td[0].get_text(strip=True) == 'DQ':
                comp = td[ic].get_text(' ', strip=True); noc = td[inoc].get_text(strip=True) if inoc is not None else None
                key = comp.split()[-1] if comp.split() else ''
                ctx = next((x for x in sents if DOP.search(x) and ((key and key in x) or (noc and noc in x))), None)
                c.execute('INSERT INTO olympedia_disqualifications(games_id,result_id,event_title,competitor,noc,context,is_doping_related,source_url) VALUES (?,?,?,?,?,?,?,?)',
                          (gid, rid, title, comp, noc, ctx, int(bool(ctx)), f'https://www.olympedia.org/results/{rid}')); n += 1
c.commit(); print('DQ rows', n, '| with doping/retest context', c.execute('select count(*) from olympedia_disqualifications where is_doping_related=1').fetchone()[0], flush=True)
m = pd.read_sql("SELECT m.medal_id, m.athlete_id, m.games_id, m.medal_type, a.identity_key FROM medals m JOIN athletes a ON a.athlete_id=m.athlete_id", c)
m['kid'] = m.identity_key.str.replace('athlete_events:', '', regex=False)
m = m.merge(pd.read_sql('SELECT kaggle_id kid, olympedia_athlete_id oid FROM athlete_id_map', c), on='kid')
ro = pd.read_sql("SELECT athlete_id oid, games_id, noc, event_result_id rid, medal FROM olympedia_rosters WHERE athlete_id IS NOT NULL", c); ro['rid'] = ro.rid.astype(str)
dq = pd.read_sql("SELECT result_id rid, competitor, noc dq_noc, context FROM olympedia_disqualifications WHERE is_doping_related=1", c)
j = m.merge(ro, on=['oid', 'games_id']).merge(dq, on='rid')
j = j[j.noc != j.dq_noc].drop_duplicates('medal_id')   # medallist is NOT the disqualified side -> benefited / event affected
c.execute("UPDATE medals SET reallocation_note=NULL WHERE reallocation_note LIKE 'Olympedia event note:%' OR reallocation_note LIKE 'Disqualification in event:%'")
c.executemany('UPDATE medals SET reallocation_note=? WHERE medal_id=?', [(f"Disqualification in event: {cp} ({dn}) - {cx}", int(i)) for i, cp, dn, cx in zip(j.medal_id, j.competitor, j.dq_noc, j.context)])
c.commit(); print('medals with reallocation note', c.execute('select count(*) from medals where reallocation_note is not null').fetchone()[0])
