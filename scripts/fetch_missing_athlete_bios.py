#!/usr/bin/env python3
"""Fetch Olympedia athlete pages only for warehouse athletes that have an Olympedia id but no birth date and no row in the bios CSV
(mostly 2024/2026 athletes). Resumable (pages cached in data/raw/olympedia_athletes), backs off on HTTP 429, fills NULL fields only."""
import json
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request as ur
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/olympedia_athletes'
RAW.mkdir(parents=True, exist_ok=True)
c = sqlite3.connect(ROOT / 'data/olympics_warehouse.db', timeout=300)
c.execute('PRAGMA busy_timeout=300000')

targets = c.execute("""
SELECT a.athlete_id, m.olympedia_athlete_id FROM athletes a
  JOIN athlete_id_map m ON 'athlete_events:'||m.kaggle_id=a.identity_key
 WHERE a.date_of_birth IS NULL AND m.olympedia_athlete_id NOT IN (SELECT athlete_id FROM src_athlete_bios)
UNION
SELECT a.athlete_id, substr(a.identity_key,11) FROM athletes a
 WHERE a.identity_key LIKE 'olympedia:%' AND a.date_of_birth IS NULL AND substr(a.identity_key,11) NOT IN (SELECT athlete_id FROM src_athlete_bios)
""").fetchall()
oids = sorted({o for _, o in targets})
print(len(targets), 'athletes /', len(oids), 'Olympedia pages to fetch', flush=True)

lock = threading.Lock(); last = [0.0]; delay = [0.12]


def get(i):
    f = RAW / f'{i}.html'
    if f.exists():
        return f.read_text(encoding='utf-8')
    for a in range(8):
        with lock:
            w = delay[0] - (time.monotonic() - last[0])
            if w > 0:
                time.sleep(w)
            last[0] = time.monotonic()
        try:
            h = ur.urlopen(ur.Request(f'https://www.olympedia.org/athletes/{i}', headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read().decode('utf-8', 'replace')
            f.write_text(h, encoding='utf-8')
            return h
        except urllib.error.HTTPError as e:
            if e.code == 429:
                delay[0] = min(1.5, delay[0] * 1.5); time.sleep(min(60, 3 * 2 ** a)); continue
            return None
        except Exception:
            time.sleep(2)
    return None


def cl(t):
    return re.sub(r'\s+', ' ', t.replace('\xa0', ' ').replace('•', ' ')).strip()


def parse(h):
    s = BeautifulSoup(h, 'lxml'); d = {}
    for tr in s.select('table.biodata tr'):
        th, td = tr.select_one('th'), tr.select_one('td')
        if th and td:
            d[cl(th.get_text())] = cl(td.get_text(' '))
    return d


def split(x):
    m = re.match(r'^(.*?) in (.*)$', x or '')
    return (m.group(1) or None, m.group(2)) if m else (x or None, None)


pages = {}
n = 0; t0 = time.time()
with ThreadPoolExecutor(8) as ex:
    for i, h in zip(oids, ex.map(get, oids)):
        if h:
            pages[i] = parse(h)
        n += 1
        if n % 500 == 0:
            print(f'{n}/{len(oids)}  {n / (time.time() - t0):.1f}/s  delay {delay[0]:.2f}', flush=True)

upd = 0
for aid, oid in targets:
    d = pages.get(oid)
    if not d:
        continue
    born, bp = split(d.get('Born')); died, _ = split(d.get('Died'))
    m = re.match(r'^(\d+) cm(?: / (\d+) kg)?', d.get('Measurements') or '')
    c.execute("INSERT OR REPLACE INTO olympedia_athlete_info(athlete_id,full_name,used_name,gender,born,died,nationality,affiliations,height_cm,weight_kg,roles,all_fields_json,source_url)"
              " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (oid, d.get('Full name'), d.get('Used name'), {'Male': 'Men', 'Female': 'Women'}.get(d.get('Sex'), 'Unknown'), d.get('Born'), d.get('Died'),
               d.get('NOC'), d.get('Affiliations'), m.group(1) if m else None, m.group(2) if m and m.group(2) else None, d.get('Roles'),
               json.dumps(d, ensure_ascii=False), f'https://www.olympedia.org/athletes/{oid}'))
    upd += c.execute(
        "UPDATE athletes SET date_of_birth=COALESCE(date_of_birth,?), date_of_death=COALESCE(date_of_death,?), original_name=COALESCE(original_name,?),"
        " biography=COALESCE(biography,?), height_cm=COALESCE(height_cm,?), weight_kg=COALESCE(weight_kg,?), source_url=? WHERE athlete_id=?",
        (born, died, d.get('Original name'), ('Born in ' + bp) if bp else None, int(m.group(1)) if m else None,
         int(m.group(2)) if m and m.group(2) else None, f'https://www.olympedia.org/athletes/{oid}', aid)).rowcount
c.commit()
print('pages parsed', len(pages), '| athletes updated', upd)
print(c.execute('SELECT count(*), sum(date_of_birth IS NOT NULL) FROM athletes').fetchone())
