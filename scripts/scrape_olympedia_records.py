#!/usr/bin/env python3
"""Olympedia /records -> /records/sport/<CODE> (current records per event) -> /records/event_name/... (full record progression).
Tables: olympedia_records_current, olympedia_records_history (raw, source URL on every row).
Then maps rows into the warehouse `records` table. Resumable (HTML cached, pages skipped when done). Polite 1 req/s."""
import json, re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup
from crawl_olympedia_site import DB, Fetcher, clean, parse_page
BASE = 'https://www.olympedia.org'
c = sqlite3.connect(DB, timeout=120); c.execute('PRAGMA busy_timeout=120000')
c.executescript("""
CREATE TABLE IF NOT EXISTS olympedia_records_current(id INTEGER PRIMARY KEY AUTOINCREMENT, sport_code TEXT, event TEXT, record_value TEXT, record_flag TEXT,
 athletes TEXT, athlete_ids TEXT, noc TEXT, games TEXT, edition_id INTEGER, record_date TEXT, phase TEXT, rank TEXT, result_url TEXT, event_page TEXT, source_url TEXT, UNIQUE(sport_code,event,record_value,athletes,games,phase));
CREATE TABLE IF NOT EXISTS olympedia_records_history(id INTEGER PRIMARY KEY AUTOINCREMENT, event_page TEXT, event TEXT, seq INTEGER, record_value TEXT, record_flag TEXT,
 athletes TEXT, athlete_ids TEXT, noc TEXT, games TEXT, edition_id INTEGER, record_date TEXT, phase TEXT, rank TEXT, result_url TEXT, source_url TEXT, UNIQUE(event_page,seq,athletes,games));
CREATE TABLE IF NOT EXISTS olympedia_records_done(path TEXT PRIMARY KEY, rows INTEGER);""")
fx = Fetcher(1.0)
def cells(tr):
    tds = tr.select('td')
    ids = [a['href'].rsplit('/', 1)[1] for a in tr.select("a[href^='/athletes/']")]
    ed = tr.select_one("a[href^='/editions/']"); res = tr.select_one("a[href^='/results/']")
    return tds, ids, (int(ed['href'].rsplit('/', 1)[1]) if ed else None), (BASE + res['href'] if res else None)
def split_val(v):
    m = re.match(r'^(.*?)\s+((?:WR|OR|WB|=?WR|=?OR)(?:\s*\w+)*)$', clean(v)); return (m.group(1), m.group(2)) if m else (clean(v), None)
def get(path):
    h = fx.get(path)
    if h: parse_page(c, path, h); c.commit()
    return h
index = get('/records'); assert index, 'cannot fetch /records'
sport_pages = sorted({a['href'] for a in BeautifulSoup(index, 'lxml').select("a[href^='/records/sport/']")})
print(len(sport_pages), 'discipline pages', flush=True)
event_pages = {}
for sp in sport_pages:
    h = get(sp)
    if not h: continue
    code = sp.rsplit('/', 1)[1]; s = BeautifulSoup(h, 'lxml'); n = 0
    for t in s.select('table'):
        for tr in t.select('tr')[1:]:
            tds, ids, ed, res = cells(tr)
            if len(tds) < 8: continue
            val, flag = split_val(tds[1].get_text(' '))
            ev_link = tr.select_one("a[href^='/records/event_name/']")
            ep = ev_link['href'] if ev_link else None
            if ep: event_pages[ep] = clean(tds[0].get_text(' '))
            c.execute('INSERT OR REPLACE INTO olympedia_records_current(sport_code,event,record_value,record_flag,athletes,athlete_ids,noc,games,edition_id,record_date,phase,rank,result_url,event_page,source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (code, clean(tds[0].get_text(' ')), val, flag, clean(tds[2].get_text(' ')), ','.join(ids), clean(tds[3].get_text(' ')), clean(tds[4].get_text(' ')), ed, clean(tds[5].get_text(' ')), clean(tds[6].get_text(' ')), clean(tds[7].get_text(' ')), res, ep, BASE + sp)); n += 1
    c.commit(); print(sp, n, 'current records', flush=True)
done = {r[0] for r in c.execute('select path from olympedia_records_done')}
todo = [p for p in sorted(event_pages) if p not in done]
print(len(event_pages), 'event record pages,', len(todo), 'to fetch', flush=True)
for i, ep in enumerate(todo, 1):
    h = fx.get(ep)
    if not h: continue
    s = BeautifulSoup(h, 'lxml'); title = clean(s.h1.get_text(' ')) if s.h1 else event_pages[ep]; n = 0
    for t in s.select('table'):
        hdr = [clean(x.get_text(' ')) for x in t.select('tr')[0].select('th,td')]
        if 'Performance' not in hdr: continue
        for tr in t.select('tr')[1:]:
            tds, ids, ed, res = cells(tr)
            if len(tds) < 8: continue
            val, flag = split_val(tds[1].get_text(' '))
            c.execute('INSERT OR REPLACE INTO olympedia_records_history(event_page,event,seq,record_value,record_flag,athletes,athlete_ids,noc,games,edition_id,record_date,phase,rank,result_url,source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (ep, title, int(clean(tds[0].get_text())) if clean(tds[0].get_text()).isdigit() else None, val, flag, clean(tds[2].get_text(' ')), ','.join(ids), clean(tds[3].get_text(' ')), clean(tds[4].get_text(' ')), ed, clean(tds[5].get_text(' ')), clean(tds[6].get_text(' ')), clean(tds[7].get_text(' ')), res, BASE + ep)); n += 1
    c.execute('INSERT OR REPLACE INTO olympedia_records_done VALUES (?,?)', (ep, n)); c.commit()
    if i % 25 == 0: print(f'  {i}/{len(todo)} event pages', flush=True)
print('DONE records: current', c.execute('select count(*) from olympedia_records_current').fetchone()[0], 'history', c.execute('select count(*) from olympedia_records_history').fetchone()[0], flush=True)
