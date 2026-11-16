#!/usr/bin/env python3
"""Olympedia venues: /venues embeds every venue (coordinates, capacity, type) as JSON -> olympedia_venues;
each /venues/<id> page lists Games/sport/event usage -> olympedia_venue_usage (1960-2026 Games only).
Then updates warehouse `venues` (coordinates/capacity/source) and inserts venues missing from it. Resumable, 1 req / 1.5 s."""
import json, re, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup
from crawl_olympedia_site import DB, SCOPE_EDITION_IDS, Fetcher, clean, parse_page
from backend.scrapers.olympedia.editions import OLYMPEDIA_EDITION_IDS
by_ed = {v: k for k, v in OLYMPEDIA_EDITION_IDS.items()}
c = sqlite3.connect(DB, timeout=120); c.execute('PRAGMA busy_timeout=120000')
c.executescript("""
CREATE TABLE IF NOT EXISTS olympedia_venues(venue_id INTEGER PRIMARY KEY, name TEXT, english_name TEXT, place TEXT, latitude REAL, longitude REAL, accuracy INTEGER,
 games_capacity TEXT, temporary INTEGER, indoor INTEGER, opened TEXT, demolished TEXT, dimensions TEXT, surface TEXT, altitude TEXT, also_known TEXT, other_names TEXT, notes TEXT, details TEXT, source_url TEXT);
CREATE TABLE IF NOT EXISTS olympedia_venue_usage(id INTEGER PRIMARY KEY AUTOINCREMENT, venue_id INTEGER, games_id TEXT, edition_id INTEGER, sport TEXT, event TEXT, held TEXT, result_id TEXT, source_url TEXT, UNIQUE(venue_id,result_id));
CREATE TABLE IF NOT EXISTS olympedia_venue_done(venue_id INTEGER PRIMARY KEY, rows INTEGER);""")
fx = Fetcher(1.5)
h = fx.get('/venues'); parse_page(c, '/venues', h)
i = h.find('VenuesMap(') + len('VenuesMap('); data = json.JSONDecoder().raw_decode(h[i:])[0]
for d in data:
    c.execute('INSERT OR REPLACE INTO olympedia_venues VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (d['id'], d['name'], d.get('english_name'), d.get('place'), d.get('lat'), d.get('lon'), d.get('accuracy'), d.get('games_capacity'), int(bool(d.get('temporary'))),
               int(bool(d.get('indoor'))), d.get('opened'), d.get('demolished'), d.get('dimensions'), d.get('surface'), d.get('altitude'), d.get('also_known'), d.get('other_names'),
               d.get('notes'), d.get('details'), f"https://www.olympedia.org/venues/{d['id']}"))
c.commit(); print(len(data), 'venues from map JSON', flush=True)
done = {r[0] for r in c.execute('select venue_id from olympedia_venue_done')}
todo = [d['id'] for d in data if d['id'] not in done]; print(len(todo), 'venue pages to fetch', flush=True)
for n, vid in enumerate(todo, 1):
    h = fx.get(f'/venues/{vid}')
    if not h: continue
    s = BeautifulSoup(h, 'lxml'); k = 0
    for t in s.select('table:not(.biodata)'):
        hdr = [clean(x.get_text(' ')) for x in t.select('tr')[0].select('th,td')]
        if hdr[:2] != ['Games', 'Sport']: continue
        for tr in t.select('tr')[1:]:
            tds = tr.select('td')
            ed = tr.select_one("a[href^='/editions/']"); res = tr.select_one("a[href^='/results/']")
            if len(tds) < 4 or not ed: continue
            eid = int(ed['href'].rsplit('/', 1)[1])
            if eid not in SCOPE_EDITION_IDS: continue
            c.execute('INSERT OR IGNORE INTO olympedia_venue_usage(venue_id,games_id,edition_id,sport,event,held,result_id,source_url) VALUES (?,?,?,?,?,?,?,?)',
                      (vid, by_ed.get(eid), eid, clean(tds[1].get_text(' ')), clean(tds[2].get_text(' ')), clean(tds[3].get_text(' ')), res['href'].rsplit('/', 1)[1] if res else None, f'https://www.olympedia.org/venues/{vid}')); k += 1
    c.execute('INSERT OR REPLACE INTO olympedia_venue_done VALUES (?,?)', (vid, k)); c.commit()
    if n % 50 == 0: print(f'  {n}/{len(todo)}', flush=True)
print('DONE venues; usage rows', c.execute('select count(*) from olympedia_venue_usage').fetchone()[0], flush=True)
