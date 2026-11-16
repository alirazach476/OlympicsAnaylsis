#!/usr/bin/env python3
"""olympedia_round_results: one row for EVERY competitor row of EVERY ranking table (round, heat, pool, qualifying, final ...) of every saved Olympedia event and dropdown page (offline).

It reads olympedia_page_tables (all tables of all pages as they appear), keeps tables that rank competitors (a Pos column plus Competitor / Competitors / Team) and stores per row:
the round (section), its stage rank, the place in that round, status (DNF / DQ ...), competitor, NOC, the Olympedia athlete id (from the cell link), the mark (time, points, distance ... taken from the
first mark column present) and EVERY column of the row as saved (columns_json), so nothing of a table is lost (fencing touches, judo wins, per-shot scores, splits ...).
Idempotent: the table is rebuilt.   Usage: python scripts/build_round_results.py"""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
MARK_HEADERS = ["time (automatic)", "time", "result", "distance", "points", "total points", "score", "net points", "height", "best height cleared", "weight (kg)", "final"]
STATUS = re.compile(r"^(DNF|DNS|DQ|DSQ|AC|NM|NP|DNQ|WD|NR|NC|DQB)\b", re.I)


def stage_rank(section: str) -> int:
    s = (section or "").lower()
    if not s:
        return 0
    if re.search(r"semi", s):
        return 80
    if re.search(r"quarter", s):
        return 70
    if re.search(r"final|medal|gold|bronze", s):
        return 100
    if re.search(r"round of|last \d+|1/\d+", s):
        return 65
    if re.search(r"third round|round three|round 3", s):
        return 60
    if re.search(r"second round|round two|round 2", s):
        return 50
    if re.search(r"first round|round one|round 1", s):
        return 40
    if re.search(r"repechage", s):
        return 35
    if re.search(r"heat|qualif|pool|group|prelim|elimination", s):
        return 30
    return 20


c.executescript("""DROP TABLE IF EXISTS olympedia_round_results;
CREATE TABLE olympedia_round_results (id INTEGER PRIMARY KEY, result_id TEXT, games_id TEXT, page_kind TEXT, sport_name TEXT, event_name TEXT, table_index INTEGER, section TEXT, stage_rank INTEGER,
  pos_text TEXT, pos_int INTEGER, status TEXT, competitor TEXT, noc TEXT, athlete_id TEXT, mark_text TEXT, mark_header TEXT, columns_json TEXT, source_url TEXT, team_entry TEXT);""")
pages = {}
for rid, title, crumb, games, kind in c.execute("SELECT result_id, title, breadcrumb, games_id, kind FROM olympedia_pages WHERE kind IN ('events','phases')"):
    parts = [p for p in dict.fromkeys((crumb or "").split(" > ")) if p]
    i = next((k for k, p in enumerate(parts) if re.search(r"Olympics$|Olympic Games$", p)), None)
    sport = parts[i + 1] if i is not None and i + 1 < len(parts) else None
    pages[rid] = (title, sport, games, kind)
n_tables = n_rows = 0
batch = []
cur = c.execute("SELECT result_id, table_index, section, headers_json, rows_json, links_json FROM olympedia_page_tables WHERE kind IN ('events','phases') ORDER BY result_id, table_index")
for rid, ti, section, hj, rj, lj in cur:
    try:
        h = json.loads(hj) or []
        rows = json.loads(rj) or []
        links = json.loads(lj) or []
    except Exception:  # noqa: BLE001
        continue
    hl = [str(x).strip().lower() for x in h]
    if "pos" not in hl or "match" in hl:
        continue
    ip = hl.index("pos")
    ic = next((hl.index(k) for k in ("competitor", "competitors", "team") if k in hl), None)
    if ic is None:
        continue
    inoc = hl.index("noc") if "noc" in hl else None
    title, sport, games, kind = pages.get(rid, (None, None, None, None))
    n_tables += 1
    rank = stage_rank(section)
    prev = None   # the last ENTRY row (country / crew label): a crew entry is followed by a row that names its athletes
    for ri, r in enumerate(rows):
        if ic >= len(r) or not str(r[ic]).strip():
            continue
        pos = str(r[ip]).strip() if ip < len(r) else ""
        cell_links = links[ri] if ri < len(links) else []
        members = [x for cl in cell_links for x in cl if "athletes" in x]
        if prev is not None and not pos and members and not any(x.get("athletes") for x in ([] if prev[0] is None else [])):
            # continuation row 'A * B * C': every named athlete gets the entry's place, mark and columns (the crew's result belongs to each member)
            for mem in members:
                batch.append((rid, games, kind, sport, title, ti, section, rank, prev[1], prev[2], prev[3], mem["text"], prev[4], mem["athletes"], prev[5], prev[6], prev[7], f"https://www.olympedia.org/results/{rid}", prev[8]))
                n_rows += 1
            prev = None
            continue
        m = re.search(r"\d+", pos)
        st = STATUS.match(pos)
        oid = next((x["athletes"] for cl in cell_links[ic:ic + 1] for x in cl if "athletes" in x), None)
        mark_text = mark_header = None
        for mh in MARK_HEADERS:
            if mh in hl:
                k = hl.index(mh)
                if k < len(r) and str(r[k]).strip() not in ("", "–", "-"):
                    mark_text, mark_header = str(r[k]).strip(), h[k]
                    break
        cols = json.dumps({(h[k] or f"col{k}"): r[k] for k in range(min(len(h), len(r)))}, ensure_ascii=False)
        noc_v = (r[inoc] if inoc is not None and inoc < len(r) else None) or None
        pint = int(m.group(0)) if m and not st else None
        stat = st.group(1).upper() if st else None
        batch.append((rid, games, kind, sport, title, ti, section, rank, pos, pint, stat, r[ic], noc_v, oid, mark_text, mark_header, cols, f"https://www.olympedia.org/results/{rid}", None))
        n_rows += 1
        # remember an entry (no athlete id) so the next row's athletes can inherit it
        prev = (None, pos, pint, stat, noc_v, mark_text, mark_header, cols, r[ic]) if oid is None and pos else None
        if len(batch) >= 20000:
            c.executemany("INSERT INTO olympedia_round_results (result_id,games_id,page_kind,sport_name,event_name,table_index,section,stage_rank,pos_text,pos_int,status,competitor,noc,athlete_id,mark_text,mark_header,columns_json,source_url,team_entry) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            batch = []
if batch:
    c.executemany("INSERT INTO olympedia_round_results (result_id,games_id,page_kind,sport_name,event_name,table_index,section,stage_rank,pos_text,pos_int,status,competitor,noc,athlete_id,mark_text,mark_header,columns_json,source_url,team_entry) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
c.execute("CREATE INDEX ix_orr_ath ON olympedia_round_results(games_id, athlete_id)")
c.execute("CREATE INDEX ix_orr_res ON olympedia_round_results(result_id)")
c.execute("CREATE INDEX ix_orr_ev ON olympedia_round_results(games_id, sport_name, event_name)")
c.commit()
q = lambda s: c.execute(s).fetchone()[0]
print(f"{n_tables:,} ranking tables -> {n_rows:,} competitor rows | with a mark {q('SELECT COUNT(*) FROM olympedia_round_results WHERE mark_text IS NOT NULL'):,} | with an athlete id {q('SELECT COUNT(*) FROM olympedia_round_results WHERE athlete_id IS NOT NULL'):,} | events {q('SELECT COUNT(DISTINCT games_id||event_name) FROM olympedia_round_results'):,}")
