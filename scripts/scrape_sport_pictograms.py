#!/usr/bin/env python3
"""Sport pictograms from Wikipedia: Games page -> Sports section -> every sport page -> infobox/sidebar pictograms.
Files saved to data/pictograms/<games_id>/<sport>__<file>; table sport_pictograms. Resumable."""
import re,sqlite3,time,shutil,requests,sys
from pathlib import Path
from urllib.parse import unquote
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
ROOT=Path('.');DB='data/olympics_warehouse.db';OUT=ROOT/'data'/'pictograms';POOL=OUT/'_files'
POOL.mkdir(parents=True,exist_ok=True)
H={'User-Agent':'OlympicsResearchBot/1.0 (educational data project)'}
S=requests.Session();S.headers.update(H)
c=sqlite3.connect(DB,timeout=120);c.execute("PRAGMA busy_timeout=120000")
c.execute("""CREATE TABLE IF NOT EXISTS sport_pictograms(id INTEGER PRIMARY KEY AUTOINCREMENT,games_id TEXT,year INTEGER,season TEXT,
 sport TEXT,sport_page TEXT,source TEXT,file_name TEXT,image_url TEXT,local_path TEXT,UNIQUE(games_id,sport_page,file_name))""")
countries={r[0].lower() for r in c.execute("select country from olympedia_country_medals")}
def api(t):
    for a in range(10):
        try:
            time.sleep(0.4)
            r=S.get('https://en.wikipedia.org/wiki/'+t,timeout=60)
            if r.status_code==429:time.sleep(int(r.headers.get('retry-after',10))+5*a);continue
            if r.status_code!=200:return None
            return BeautifulSoup(r.text,'lxml')
        except Exception:time.sleep(2)
def orig(src):
    src=('https:'+src if src.startswith('//') else src).split('?')[0]
    m=re.match(r'(https://)thumb\.wikimedia\.org/(wikipedia/\w+)/thumb/(\w/\w\w/[^/]+)/',src) or re.match(r'(https://)upload\.wikimedia\.org/(wikipedia/\w+)/thumb/(\w/\w\w/[^/]+)/',src)
    return f'https://upload.wikimedia.org/{m.group(2)}/{m.group(3)}' if m else src
def sports_links(s,yr,season):
    h=next((x for x in (s.find(id=i) for i in ('Sports','Sport_competitions','Sports_competitions','Sports_and_events','Disciplines','Events')) if x),None)
    pat=re.compile(rf'^/wiki/([^#]+)_at_the_{yr}_{season}_Olympics$')
    out={}
    if not h:return out
    start=h if h.name in('h2','h3') else (h.find(['h2','h3']) or h)
    lvl=start.name
    for el in start.find_all_next():
        if el.name=='h2' or (lvl=='h3' and el.name=='h3'):
            if el is not start:break
        if el.name=='a' and el.get('href'):
            m=pat.match(re.sub(r'^https?://en\.wikipedia\.org','',el['href']))
            if m:out['/wiki/'+m.group(1)+f'_at_the_{yr}_{season}_Olympics']=unquote(m.group(1)).replace('_',' ')
    return out

def pictos(sp):
    s=api(unquote(sp[6:]))
    if not s:return []
    res=[]
    for img in s.select('table.infobox img, table.sidebar-games-events img'):
        w=int(img.get('width') or 0);src=img.get('src','')
        name=unquote(src.split('/thumb/')[-1].split('/')[1]) if '/thumb/' in src else unquote(src.rsplit('/',1)[-1])
        if w<40 or re.search(r'Flag_of|Olympic_rings|Commons-logo|Edit-|Symbol_|Question_book|Ambox|Wiki',name):continue
        t=img.find_parent('table')
        res.append(('sidebar' if 'sidebar' in ' '.join(t.get('class',[])) else 'infobox',name,orig(src)))
    return res
def download(url):
    f=POOL/re.sub(r'[^\w.\-]','_',unquote(url.rsplit('/',1)[-1]))
    if f.exists() and f.stat().st_size>0:return f
    for a in range(6):
        time.sleep(0.3);r=S.get(url,timeout=60)
        if r.status_code==200:f.write_bytes(r.content);return f
        if r.status_code==429:time.sleep(int(r.headers.get('retry-after',10))+5*a)
        else:break
    return None
def edition(yr,season):
    gid=f'{yr}_{season.lower()}'
    s=api(f'{yr}_{season}_Olympics')
    if not s:print('no page',gid,flush=True);return
    links=sports_links(s,yr,season)
    links={k:v for k,v in links.items() if v.lower() not in countries and not re.search(r'concern|record|neutral|medal|nation|team',v.lower())}
    n=0
    with ThreadPoolExecutor(2) as ex:
        found=list(ex.map(pictos,links))
    for (href,sport),pl in zip(links.items(),found):
        for src,name,url in pl:
            f=download(url)
            if not f:continue
            d=OUT/gid;d.mkdir(exist_ok=True)
            dest=d/(re.sub(r'[^\w\-]','_',sport)+'__'+f.name);shutil.copyfile(f,dest)
            c.execute("insert or replace into sport_pictograms(games_id,year,season,sport,sport_page,source,file_name,image_url,local_path) values(?,?,?,?,?,?,?,?,?)",
                      (gid,yr,season,sport,'https://en.wikipedia.org'+href,src,name,url,str(dest)));n+=1
        c.commit()
    print(f'{gid}: {len(links)} sports, {n} pictograms',flush=True)
eds=[(y,'Summer') for y in range(1960,2025,4)]+[(y,'Winter') for y in (1960,1964,1968,1972,1976,1980,1984,1988,1992,1994,1998,2002,2006,2010,2014,2018,2022,2026)]
only=sys.argv[1:] 
for y,se in sorted(eds):
    if only and f'{y}_{se.lower()}' not in only:continue
    edition(y,se)
print('DONE')







