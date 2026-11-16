import sqlite3,re,sys,time,threading,urllib.request as ur,urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
DB='data/olympics_warehouse.db'
RAW=Path('data/raw/olympedia_athletes');RAW.mkdir(parents=True,exist_ok=True)
c=sqlite3.connect(DB,timeout=120);c.execute("PRAGMA busy_timeout=120000")
c.execute("CREATE TABLE IF NOT EXISTS olympedia_athlete_gender(athlete_id TEXT PRIMARY KEY,gender TEXT)")
ids=[r[0] for r in c.execute("select distinct athlete_id from olympedia_athlete_results where gender='Mixed' and athlete_id is not null and athlete_id not in (select athlete_id from olympedia_athlete_gender)")]
print(len(ids),'athletes to fetch',flush=True)
lock=threading.Lock();last=[0.0];DELAY=0.35
def get(i):
    f=RAW/f'{i}.html'
    if f.exists():return f.read_text(encoding='utf-8')
    for a in range(8):
        with lock:
            w=DELAY-(time.monotonic()-last[0])
            if w>0:time.sleep(w)
            last[0]=time.monotonic()
        try:
            h=ur.urlopen(ur.Request(f'https://www.olympedia.org/athletes/{i}',headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read().decode('utf-8','replace')
            f.write_text(h,encoding='utf-8');return h
        except urllib.error.HTTPError as e:
            if e.code==429:time.sleep(min(60,3*2**a));continue
            return None
        except Exception:time.sleep(2)
def work(i):
    h=get(i)
    if not h:return i,None
    m=re.search(r'<th>Sex</th>\s*<td>\s*(Male|Female)',h)
    return i,('Men' if m and m.group(1)=='Male' else 'Women' if m else 'Unknown')
n=0
with ThreadPoolExecutor(4) as ex:
    for i,g in ex.map(work,ids):
        if g:c.execute("insert or replace into olympedia_athlete_gender values(?,?)",(i,g))
        n+=1
        if n%200==0:c.commit();print(n,'/',len(ids),flush=True)
c.commit()
c.execute("update olympedia_athlete_results set gender=(select gender from olympedia_athlete_gender g where g.athlete_id=olympedia_athlete_results.athlete_id) where athlete_id in (select athlete_id from olympedia_athlete_gender where gender!='Unknown')")
c.commit()
print(c.execute("select gender,count(*) from olympedia_athlete_results group by 1").fetchall())
