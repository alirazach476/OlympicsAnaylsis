import sqlite3,re,json,time,threading,urllib.request as ur,urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup
DB='data/olympics_warehouse.db'
RAW=Path('data/raw/olympedia_athletes');RAW.mkdir(parents=True,exist_ok=True)
c=sqlite3.connect(DB,timeout=120);c.execute("PRAGMA busy_timeout=120000")
c.execute("""CREATE TABLE IF NOT EXISTS olympedia_athlete_info(athlete_id TEXT PRIMARY KEY,full_name TEXT,used_name TEXT,gender TEXT,born TEXT,died TEXT,nationality TEXT,affiliations TEXT,height_cm TEXT,weight_kg TEXT,roles TEXT,all_fields_json TEXT,source_url TEXT)""")
# each ID exactly once; team-roster players first
ids=[r[0] for r in c.execute("""select athlete_id from olympedia_athlete_results where athlete_id is not null
 group by athlete_id order by max(team is not null and team!='') desc, athlete_id""")
 ]
have={r[0] for r in c.execute("select athlete_id from olympedia_athlete_info")}
ids=[i for i in ids if i not in have]
print(len(ids),'unique athletes to fetch',flush=True)
lock=threading.Lock();last=[0.0];delay=[0.2]
def get(i):
    f=RAW/f'{i}.html'
    if f.exists():return f.read_text(encoding='utf-8')
    for a in range(8):
        with lock:
            w=delay[0]-(time.monotonic()-last[0])
            if w>0:time.sleep(w)
            last[0]=time.monotonic()
        try:
            h=ur.urlopen(ur.Request(f'https://www.olympedia.org/athletes/{i}',headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read().decode('utf-8','replace')
            f.write_text(h,encoding='utf-8');return h
        except urllib.error.HTTPError as e:
            if e.code==429:
                delay[0]=min(1.5,delay[0]*1.5);time.sleep(min(60,3*2**a));continue
            return None
        except Exception:time.sleep(2)
def cl(t):return re.sub(r'\s+',' ',t.replace('\xa0',' ').replace('•',' ')).strip()
def parse(i,h):
    s=BeautifulSoup(h,'lxml');d={}
    for tr in s.select('table.biodata tr'):
        th,td=tr.select_one('th'),tr.select_one('td')
        if th and td:d[cl(th.get_text())]=cl(td.get_text(' '))
    sex=d.get('Sex')
    g={'Male':'Men','Female':'Women'}.get(sex,'Unknown')
    num=lambda k:re.search(r'\d+',d.get(k,'') or '')
    return (i,d.get('Full name') or cl((s.h1 or s).get_text()),d.get('Used name'),g,d.get('Born'),d.get('Died'),d.get('NOC'),d.get('Affiliations'),
        num('Measurements') and num('Measurements').group(0),None,d.get('Roles'),json.dumps(d,ensure_ascii=False),f'https://www.olympedia.org/athletes/{i}')
def work(i):
    h=get(i);return (i,h)
n=0;t0=time.time()
with ThreadPoolExecutor(6) as ex:
    for i,h in ex.map(work,ids):
        if h:c.execute("insert or replace into olympedia_athlete_info values(?,?,?,?,?,?,?,?,?,?,?,?,?)",parse(i,h))
        n+=1
        if n%200==0:
            c.commit();print(f'{n}/{len(ids)}  {n/(time.time()-t0):.1f}/s  delay {delay[0]:.2f}',flush=True)
c.commit()
c.execute("update olympedia_athlete_results set gender=(select gender from olympedia_athlete_info g where g.athlete_id=olympedia_athlete_results.athlete_id) where athlete_id in (select athlete_id from olympedia_athlete_info where gender!='Unknown')")
c.commit();print('DONE')
