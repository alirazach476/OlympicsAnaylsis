#!/usr/bin/env python3
"""Offline: parse the cached Olympedia event pages (data/raw/olympedia/editions/*/events/*.html) and keep every medal-bearing row of the main
results table with its ORIGINAL result string (time / distance / points ...). Fixes podium results that olympedia_standings left empty
(Athletics, Swimming, Rowing ...). Writes table olympedia_podium_results. Idempotent; raw pages are never modified."""
import glob, json, re, sqlite3, sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
c.executescript("""DROP TABLE IF EXISTS olympedia_event_rows;
CREATE TABLE olympedia_event_rows(id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, sport_name TEXT, event_name TEXT, table_index INTEGER, phase TEXT, is_main INTEGER,
  position TEXT, competitor TEXT, noc TEXT, medal TEXT, result_text TEXT, result_header TEXT, source_url TEXT);
CREATE INDEX ix_oer ON olympedia_event_rows(games_id, result_id, is_main);
DROP TABLE IF EXISTS olympedia_podium_results;
CREATE TABLE olympedia_podium_results(id INTEGER PRIMARY KEY AUTOINCREMENT, games_id TEXT, result_id TEXT, sport_name TEXT, event_name TEXT, position TEXT,
  competitor TEXT, noc TEXT, medal TEXT, result_text TEXT, result_header TEXT, source_url TEXT);
CREATE INDEX ix_opr ON olympedia_podium_results(games_id, result_id);""")
RES_HDR = re.compile(r"^(Time|Result|Distance|Height|Points|Score|Final|Total|Mark|Time \(Automatic\)|Time \(Hand\)|Weight|Total Points|Score|Points)\b", re.I)
MEDALS = ("Gold", "Silver", "Bronze")
n = pages = 0
for f in glob.glob(str(ROOT / "data/raw/olympedia/editions/*/events/*.html")):
    p = Path(f)
    gid, rid = p.parent.parent.name, p.stem
    meta = {}
    jf = p.with_suffix(".json")
    if jf.exists():
        try:
            meta = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            pass
    html = p.read_text(encoding="utf-8", errors="replace")
    s = BeautifulSoup(html, "lxml")
    got = 0
    pod_done = False
    for ti, t in enumerate(s.select("table")):
        rows = t.select("tr")
        if not rows:
            continue
        hdr = [x.get_text(" ", strip=True) for x in rows[0].select("th")]
        if "Pos" not in hdr:
            continue
        ic = next((i for i, h in enumerate(hdr) if h in ("Competitor", "Competitors", "Team", "Pair", "Crew", "Athlete", "Rider", "Name")), None)
        inoc = hdr.index("NOC") if "NOC" in hdr else None
        cand = [i for i, h in enumerate(hdr) if RES_HDR.match(h)]
        head = t.find_previous(["h2", "h3", "h4"])
        phase = head.get_text(" ", strip=True) if head else None
        has_med = False
        for tr in rows[1:]:
            td = tr.select("td")
            if not td:
                continue
            cells = [x.get_text(" ", strip=True) for x in td]
            comp = cells[ic] if ic is not None and ic < len(cells) else None
            noc = cells[inoc] if inoc is not None and inoc < len(cells) else None
            if not cells[0] and not (comp and noc):
                continue          # roster sub-row of a team entry (members listed under the team row)
            med = next((x for x in cells if x in MEDALS), None)
            rtxt = rh = None
            for i in reversed(cand):
                if i < len(cells) and cells[i] and cells[i] not in ("", "–", "-"):
                    rtxt, rh = cells[i], hdr[i]
                    break
            c.execute("INSERT INTO olympedia_event_rows(games_id,result_id,sport_name,event_name,table_index,phase,is_main,position,competitor,noc,medal,result_text,result_header,source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (gid, rid, meta.get("sport_name"), meta.get("event_name"), ti, phase, 0, cells[0], comp, noc, med, rtxt, rh, f"https://www.olympedia.org/results/{rid}"))
            if med:
                has_med = True
            if med and not pod_done:
                c.execute("INSERT INTO olympedia_podium_results(games_id,result_id,sport_name,event_name,position,competitor,noc,medal,result_text,result_header,source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (gid, rid, meta.get("sport_name"), meta.get("event_name"), cells[0], comp, noc, med, rtxt, rh, f"https://www.olympedia.org/results/{rid}"))
                n += 1
            got += 1
        if has_med:
            pod_done = True
    pages += bool(got)
# main table = the table holding the medal marks (final standings); events without medals: the first results table
c.execute("UPDATE olympedia_event_rows SET is_main=0")
c.execute("""UPDATE olympedia_event_rows SET is_main=1 WHERE (result_id, table_index) IN (
    SELECT result_id, COALESCE(MIN(CASE WHEN medal IS NOT NULL THEN table_index END), MIN(table_index)) FROM olympedia_event_rows GROUP BY result_id)""")
c.commit()
print("event pages with result tables", pages, "| podium rows", n, "| all rows", c.execute("SELECT COUNT(*) FROM olympedia_event_rows").fetchone()[0])

print(c.execute("SELECT is_main, COUNT(*), SUM(result_text IS NOT NULL), SUM(medal IS NULL) FROM olympedia_event_rows GROUP BY 1").fetchall())
