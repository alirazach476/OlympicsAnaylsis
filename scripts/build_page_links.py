#!/usr/bin/env python3
"""Link index of the saved Olympedia pages (offline, idempotent).

olympedia_page_links: every link from a saved event / phase page to another results page, with provenance:
  parent_id -> child_id, relation ('table' = a 'Match #' / heat cell in a table, 'dropdown' = a Parts / Standings select, 'standings' = phase page parent from olympedia_standings),
  table_index, row_index, section and label as they appear, the child's kind (matches / phases / events) and whether the child page is saved (child_saved).
olympedia_athlete_xref: Olympedia athlete id -> warehouse athletes.athlete_id (via identity_key 'olympedia:<id>' or the Kaggle id maps), so table cells can link to athlete profiles.

Nothing is invented: links come from the saved links_json / dropdowns_json / olympedia_standings only.
Usage: python scripts/build_page_links.py"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
c.execute("PRAGMA busy_timeout=300000")
kinds = dict(c.execute("SELECT result_id, kind FROM olympedia_pages"))

c.executescript("""DROP TABLE IF EXISTS olympedia_page_links;
CREATE TABLE olympedia_page_links (id INTEGER PRIMARY KEY, games_id TEXT, parent_id TEXT, child_id TEXT, relation TEXT, table_index INTEGER, row_index INTEGER,
  section TEXT, label TEXT, child_kind TEXT, child_saved INTEGER, source_url TEXT);""")
batch, seen = [], set()


def add(g, p, ch, rel, ti, ri, sec, lab):
    key = (p, ch, rel, ti, ri)
    if key in seen or p == ch:
        return
    seen.add(key)
    batch.append((g, p, ch, rel, ti, ri, sec, lab, kinds.get(ch), int(ch in kinds), f"https://www.olympedia.org/results/{p}"))


for rid, g, ti, sec, lj in c.execute("SELECT result_id, games_id, table_index, section, links_json FROM olympedia_page_tables WHERE kind IN ('events','phases')"):
    try:
        links = json.loads(lj) or []
    except Exception:  # noqa: BLE001
        continue
    for ri, row in enumerate(links):
        for cell in row or []:
            for x in cell or []:
                if x.get("results"):
                    add(g, rid, str(x["results"]), "table", ti, ri, sec, x.get("text"))
for rid, g, dj in c.execute("SELECT result_id, games_id, dropdowns_json FROM olympedia_pages WHERE dropdowns_json NOT IN ('', '[]')"):
    try:
        dd = json.loads(dj) or []
    except Exception:  # noqa: BLE001
        continue
    for i, d in enumerate(dd):
        if d.get("value"):
            add(g, rid, str(d["value"]), "dropdown", None, i, d.get("select"), d.get("label"))
for g, p, ch, lab in c.execute("SELECT DISTINCT games_id, parent_result_id, result_id, phase_label FROM olympedia_standings WHERE is_phase=1 AND parent_result_id IS NOT NULL"):
    add(g, str(p), str(ch), "standings", None, None, None, lab)
c.executemany("INSERT INTO olympedia_page_links (games_id,parent_id,child_id,relation,table_index,row_index,section,label,child_kind,child_saved,source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch)
c.execute("CREATE INDEX ix_opl_parent ON olympedia_page_links(parent_id)")
c.execute("CREATE INDEX ix_opl_child ON olympedia_page_links(child_id)")

c.executescript("""DROP TABLE IF EXISTS olympedia_athlete_xref;
CREATE TABLE olympedia_athlete_xref (olympedia_id TEXT PRIMARY KEY, athlete_id INTEGER, via TEXT);
INSERT OR IGNORE INTO olympedia_athlete_xref SELECT substr(identity_key, 11), athlete_id, 'identity_key' FROM athletes WHERE identity_key LIKE 'olympedia:%';
INSERT OR IGNORE INTO olympedia_athlete_xref SELECT m.olympedia_athlete_id, a.athlete_id, 'athlete_id_map' FROM athlete_id_map m JOIN athletes a ON a.identity_key='athlete_events:'||m.kaggle_id;
INSERT OR IGNORE INTO olympedia_athlete_xref SELECT m.olympedia_athlete_id, a.athlete_id, 'athlete_id_map_added' FROM athlete_id_map_added m JOIN athletes a ON a.identity_key='athlete_events:'||m.kaggle_id;""")
c.commit()
q = lambda s: c.execute(s).fetchone()
print("links", q("SELECT COUNT(*), SUM(child_saved), COUNT(DISTINCT parent_id) FROM olympedia_page_links"), "by relation", c.execute("SELECT relation, COUNT(*), SUM(child_saved) FROM olympedia_page_links GROUP BY 1").fetchall())
print("athlete xref", q("SELECT COUNT(*) FROM olympedia_athlete_xref"))
