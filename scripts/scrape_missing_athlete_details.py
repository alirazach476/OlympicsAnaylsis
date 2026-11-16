#!/usr/bin/env python3
"""Fetch the Olympedia athlete page for every athlete that has no height or weight in the warehouse (22k), save it to data/raw/olympedia_athletes/<id>.html (cached, resumable),
store the bio table in olympedia_athlete_info and fill NULL fields of athletes (height, weight, original name, born/died dates, biography text).  No images are downloaded."""
import json, re, sqlite3, sys, threading, time, urllib.error, urllib.request as ur
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/olympedia_athletes"; RAW.mkdir(parents=True, exist_ok=True)
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300, check_same_thread=False); c.execute("PRAGMA busy_timeout=300000")
cl = lambda t: re.sub(r"\s+", " ", (t or "").replace("\xa0", " ").replace("•", " ")).strip()
todo = c.execute("""SELECT a.athlete_id, COALESCE(m.olympedia_athlete_id, CASE WHEN a.identity_key LIKE 'olympedia:%' THEN substr(a.identity_key,11) END) oid FROM athletes a
  LEFT JOIN athlete_id_map m ON m.kaggle_id=substr(a.identity_key,16)
  WHERE (a.height_cm IS NULL OR a.weight_kg IS NULL) AND EXISTS(SELECT 1 FROM silver_participations p WHERE p.athlete_id=a.athlete_id)""").fetchall()
todo = [(a, str(o)) for a, o in todo if o]
print(len(todo), "athletes with a missing height/weight and an Olympedia id", flush=True)
lock = threading.Lock(); last = [0.0]; delay = [0.2]
def get(oid):
    f = RAW / f"{oid}.html"
    if f.exists() and f.stat().st_size > 500: return f.read_text(encoding="utf-8")
    for a in range(8):
        with lock:
            w = delay[0] - (time.monotonic() - last[0])
            if w > 0: time.sleep(w)
            last[0] = time.monotonic()
        try:
            h = ur.urlopen(ur.Request(f"https://www.olympedia.org/athletes/{oid}", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8", "replace")
            f.write_text(h, encoding="utf-8"); return h
        except urllib.error.HTTPError as e:
            if e.code == 429: delay[0] = min(1.5, delay[0] * 1.5); time.sleep(min(60, 3 * 2 ** a)); continue
            return None
        except Exception: time.sleep(3)
    return None
def date(t):
    m = re.search(r"(\d{1,2}) (\w+) (\d{4})", t or "")
    if m:
        try: d = datetime.strptime(" ".join(m.groups()), "%d %B %Y"); return f"{d.day} {d:%B %Y}"  # same style as the rest of athletes.date_of_birth
        except ValueError: pass
    m = re.search(r"\b(\d{4})\b", t or "")
    return None
def parse(oid, h):
    s = BeautifulSoup(h, "lxml"); d = {}
    for tr in s.select("table.biodata tr"):
        th, td = tr.select_one("th"), tr.select_one("td")
        if th and td: d[cl(th.get_text())] = cl(td.get_text(" "))
    bio = " ".join(cl(p.get_text(" ")) for p in s.select(".athlete-bio p, .biography p, div.col-md-12 > p")[:6])
    return d, bio
def work(t):
    return t, get(t[1])
n = 0; t0 = time.time(); filled = 0
with ThreadPoolExecutor(6) as ex:
    for (aid, oid), h in ex.map(work, todo):
        n += 1
        if h:
            d, bio = parse(oid, h)
            g = {"Male": "Men", "Female": "Women"}.get(d.get("Sex"), "Unknown")
            m = re.search(r"(\d+)\s*cm", d.get("Measurements", "") or ""); w = re.search(r"(\d+)\s*kg", d.get("Measurements", "") or "")
            c.execute("INSERT OR REPLACE INTO olympedia_athlete_info VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (oid, d.get("Full name"), d.get("Used name"), g, d.get("Born"), d.get("Died"), d.get("NOC"), d.get("Affiliations"), m.group(1) if m else None, w.group(1) if w else None, d.get("Roles"), json.dumps(d, ensure_ascii=False), f"https://www.olympedia.org/athletes/{oid}"))
            c.execute("""UPDATE athletes SET height_cm=COALESCE(height_cm,?), weight_kg=COALESCE(weight_kg,?), original_name=COALESCE(original_name,?), date_of_birth=COALESCE(date_of_birth,?),
                         date_of_death=COALESCE(date_of_death,?), biography=COALESCE(biography,?) WHERE athlete_id=?""",
                      (int(m.group(1)) if m else None, int(w.group(1)) if w else None, d.get("Original name"), date(d.get("Born")), date(d.get("Died")), bio or None, aid))
            filled += 1
        if n % 25 == 0:
            c.commit()
        if n % 500 == 0:
            print(f"{n}/{len(todo)} {n/(time.time()-t0):.1f}/s delay {delay[0]:.2f}", flush=True)
c.commit(); print("DONE", n, filled)
