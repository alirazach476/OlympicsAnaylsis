#!/usr/bin/env python3
"""Fast pictogram download via the MediaWiki API (batched, 50 titles/call) + parallel image downloads.
Output: data/pictograms/<year>_<season>/<sport>__<file>; table sport_pictograms. Resumable."""
import re, sqlite3, shutil, time, requests
from pathlib import Path
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor
OUT = Path('data/pictograms'); POOL = OUT/'_files'; POOL.mkdir(parents=True, exist_ok=True)
A = 'https://en.wikipedia.org/w/api.php'
S = requests.Session(); S.headers['User-Agent'] = 'OlympicsResearchBot/1.0 (educational data project)'
def q(**k):
    for a in range(8):
        try:
            r = S.get(A, params=dict(format='json', formatversion=2, **k), timeout=60)
            if r.status_code == 429: time.sleep(5*(a+1)); continue
            return r.json()
        except Exception: time.sleep(2)
    return {}
c = sqlite3.connect('data/olympics_warehouse.db', timeout=120); c.execute('PRAGMA busy_timeout=120000')
c.execute("""CREATE TABLE IF NOT EXISTS sport_pictograms(id INTEGER PRIMARY KEY AUTOINCREMENT,games_id TEXT,year INTEGER,season TEXT,
 sport TEXT,sport_page TEXT,source TEXT,file_name TEXT,image_url TEXT,local_path TEXT,UNIQUE(games_id,sport_page,file_name))""")
countries = {r[0].lower() for r in c.execute('select country from olympedia_country_medals')}
GAMES = [(y, 'Summer') for y in range(1960, 2025, 4)] + [(y, 'Winter') for y in [*range(1960, 1993, 4), 1994, *range(1998, 2027, 4)]]
def words(s): return [w for w in re.split(r'\W+', s.lower()) if len(w) > 3 and w not in ('events', 'event')]
def dl(job):
    url, f = job
    if f.exists() and f.stat().st_size: return f
    for a in range(6):
        try:
            r = S.get(url, timeout=60)
            if r.status_code == 200: f.write_bytes(r.content); return f
            if r.status_code == 429: time.sleep(5*(a+1)); continue
            return None
        except Exception: time.sleep(2)
def run(yr, season):
    gid = f'{yr}_{season.lower()}'
    r = q(action='parse', page=f'{yr}_{season}_Olympics', prop='links')
    pat = re.compile(rf'^(.+) at the {yr} {season} Olympics$')
    pages = {l['title']: pat.match(l['title']).group(1) for l in r.get('parse', {}).get('links', [])
             if pat.match(l['title']) and not re.search(r'concern|record|neutral|medal|nation|team', l['title'].lower())
             and pat.match(l['title']).group(1).lower() not in countries}
    cand = {}  # (page, file) -> sport
    titles = list(pages)
    for i in range(0, len(titles), 40):
        res = q(action='query', titles='|'.join(titles[i:i+40]), prop='images|pageimages', piprop='name', imlimit=500, pilimit=50)
        for p in res.get('query', {}).get('pages', []):
            sp = pages.get(p['title']); ws = words(sp or '')
            for im in p.get('images', []):
                n = im['title']
                if re.search(r'pictogram', n, re.I) and not re.search(r'Flag_of|Flag of', n) and any(w in n.lower() for w in ws):
                    cand[(p['title'], n)] = sp
            pi = p.get('pageimage')
            if pi and re.search(r'pictogram', pi, re.I) and any(w in pi.lower() for w in ws): cand[(p['title'], 'File:' + pi.replace('_', ' '))] = sp
    files = sorted({n for _, n in cand}); urls = {}
    for i in range(0, len(files), 50):
        res = q(action='query', titles='|'.join(files[i:i+50]), prop='imageinfo', iiprop='url')
        for p in res.get('query', {}).get('pages', []):
            ii = p.get('imageinfo')
            if ii: urls[p['title']] = ii[0]['url']
    jobs = {n: (u, POOL/re.sub(r'[^\w.\-]', '_', unquote(u.rsplit('/', 1)[-1]))) for n, u in urls.items()}
    with ThreadPoolExecutor(8) as ex: got = dict(zip(jobs, ex.map(dl, jobs.values())))
    d = OUT/gid; d.mkdir(exist_ok=True); k = 0
    for (page, n), sp in cand.items():
        f = got.get(n)
        if not f: continue
        dest = d/(re.sub(r'[^\w\-]', '_', sp) + '__' + f.name); shutil.copyfile(f, dest); k += 1
        c.execute('insert or replace into sport_pictograms(games_id,year,season,sport,sport_page,source,file_name,image_url,local_path) values(?,?,?,?,?,?,?,?,?)',
                  (gid, yr, season, sp, '/wiki/' + page.replace(' ', '_'), 'api', n[5:], urls[n], str(dest)))
    c.commit(); print(gid, len(pages), 'sport pages ->', k, 'pictograms', flush=True)
if __name__ == '__main__':
    t = time.time()
    for y, s in GAMES: run(y, s)
    print('DONE', round(time.time()-t), 's')
