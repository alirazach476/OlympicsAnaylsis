#!/usr/bin/env python3
"""Every table of every saved Olympedia results page, as it appears on the page (offline): events/, phases/ and matches/ of all 35 Games.
olympedia_page_tables : one row per table - page (result_id), games, kind, table_index, section (nearest heading / caption), headers_json, rows_json (cell text) and links_json (athlete / result / country ids per cell)
olympedia_pages       : one row per page - title, breadcrumb, key/value lines under the title (Date, Location, ...), dropdown options.
Idempotent (tables are rebuilt).   Usage: python scripts/load_olympedia_page_tables.py"""
import json, re, sqlite3
from multiprocessing import Pool
from pathlib import Path
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/olympedia/editions"
cl = lambda t: re.sub(r"\s+", " ", (t or "").replace("\xa0", " ")).strip()


def cell_links(td):
    out = []
    for a in td.select("a[href]"):
        m = re.match(r"/(athletes|results|countries|editions|venues|sports)/([^/?#]+)", a["href"])
        if m: out.append({m.group(1): m.group(2), "text": cl(a.get_text(" "))[:80]})
    return out


def _kv(table):
    out = {}
    for tr in table.select("tr"):
        th, td = tr.select_one("th"), tr.select_one("td")
        if th and td: out[cl(th.get_text())] = cl(td.get_text(" "))
    return out


def page_text(s):
    """Header facts, written description and per-round facts of one page.
    header : the FIRST biodata table (under the title) - Date, Status, Location, Participants, Format of the whole event
    description : the paragraphs of div.description, as Olympedia wrote them (empty list when the page has none)
    section_meta : every later biodata table keyed by its heading (e.g. 'Round-Robin': {Date, Format}); these used to overwrite the header facts"""
    bios = s.select("table.biodata")
    header = _kv(bios[0]) if bios else {}
    d = s.select_one("div.description")
    desc = [cl(p.get_text(" ")) for p in (d.select("p") or [d])] if d else []
    desc = [x for x in desc if x]
    smeta = {}
    for t in bios[1:]:
        head = t.find_previous(["h2", "h3", "h4"])
        key = cl(head.get_text(" ")) if head else ""
        if key: smeta.setdefault(key, {}).update(_kv(t))
    return header, desc, smeta


def parse(path_s):
    p = Path(path_s)
    games, kind, rid = p.parts[-3], p.parts[-2], p.stem
    s = BeautifulSoup(p.read_text(encoding="utf-8", errors="replace"), "lxml")
    title = cl(s.h1.get_text(" ")) if s.h1 else ""
    crumbs = [cl(li.get_text(" ")) for li in s.select(".breadcrumb li")]
    meta, _desc, _smeta = page_text(s)
    opts = [{"select": sel.get("id") or sel.get("name"), "value": o.get("value"), "label": cl(o.get_text(" "))} for sel in s.select("select") for o in sel.select("option") if (sel.get("id") or "") not in ("same_games_select", "other_games_select")]
    tabs = []
    for i, t in enumerate(s.select("table")):
        if "biodata" in (t.get("class") or []): continue
        head = t.find_previous(["h1", "h2", "h3", "h4"])
        cap = t.select_one("caption")
        section = cl(cap.get_text(" ")) if cap else (cl(head.get_text(" ")) if head and head is not s.h1 else "")
        rows, links, headers = [], [], None
        for tr in t.select("tr"):
            cells = tr.select("th,td")
            if not cells: continue
            texts = [cl(c.get_text(" ")) for c in cells]
            if headers is None and all(c.name == "th" for c in cells) and (tr.parent.name == "thead" or not rows):
                headers = texts; continue
            rows.append(texts); links.append([cell_links(c) for c in cells])
        if rows or headers: tabs.append((i, section, headers, rows, links))
    return (rid, games, kind, title, crumbs, meta, opts), [(rid, games, kind, i, sec, json.dumps(h, ensure_ascii=False), json.dumps(r, ensure_ascii=False), json.dumps(l, ensure_ascii=False)) for i, sec, h, r, l in tabs]


def main():
    files = [str(f) for g in sorted(RAW.iterdir()) if g.is_dir() for k in ("events", "phases", "matches") for f in (g / k).glob("*.html")]
    print(len(files), "pages", flush=True)
    c = sqlite3.connect(ROOT / "data/olympics_warehouse.db", timeout=300)
    c.executescript("""DROP TABLE IF EXISTS olympedia_page_tables; DROP TABLE IF EXISTS olympedia_pages;
      CREATE TABLE olympedia_pages (result_id TEXT PRIMARY KEY, games_id TEXT, kind TEXT, title TEXT, breadcrumb TEXT, meta_json TEXT, dropdowns_json TEXT);
      CREATE TABLE olympedia_page_tables (id INTEGER PRIMARY KEY, result_id TEXT, games_id TEXT, kind TEXT, table_index INTEGER, section TEXT, headers_json TEXT, rows_json TEXT, links_json TEXT);""")
    n = nt = 0
    with Pool(4) as pool:
        for page, tabs in pool.imap_unordered(parse, files, chunksize=200):
            rid, games, kind, title, crumbs, meta, opts = page
            c.execute("INSERT OR REPLACE INTO olympedia_pages VALUES (?,?,?,?,?,?,?)", (rid, games, kind, title, " > ".join(crumbs), json.dumps(meta, ensure_ascii=False), json.dumps(opts, ensure_ascii=False)))
            c.executemany("INSERT INTO olympedia_page_tables (result_id,games_id,kind,table_index,section,headers_json,rows_json,links_json) VALUES (?,?,?,?,?,?,?,?)", tabs)
            n += 1; nt += len(tabs)
            if n % 5000 == 0: c.commit(); print(n, "pages", nt, "tables", flush=True)
    c.execute("CREATE INDEX ix_opt_res ON olympedia_page_tables(result_id)"); c.execute("CREATE INDEX ix_opt_games ON olympedia_page_tables(games_id, kind)")
    c.commit(); print("done:", n, "pages,", nt, "tables")


if __name__ == "__main__":
    main()
