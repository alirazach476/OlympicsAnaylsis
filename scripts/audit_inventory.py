#!/usr/bin/env python3
"""MILESTONE 1 - read-only audit of everything in the repository's data layer.

Writes:
  reports/data_inventory/{dataset_inventory.csv, column_profile.csv, file_inventory.csv, raw_store_inventory.csv, image_assets.csv, relationships.csv, inventory.md}
  reports/data_quality/{id_consistency.csv, quality_findings.csv}
  reports/data_completeness/{edition_dataset_matrix.csv}
Nothing in data/ is modified.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "olympics_warehouse.db"
OUT_INV, OUT_Q, OUT_C = (ROOT / "reports" / d for d in ("data_inventory", "data_quality", "data_completeness"))
for d in (OUT_INV, OUT_Q, OUT_C):
    d.mkdir(parents=True, exist_ok=True)
SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache", "dist"}


def write(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def applications(name: str, cols: list[str]) -> str:
    n = name.lower()
    table = [
        ("medal", "medal analytics, country performance, concentration, host effect"), ("athlete", "athlete career, age, gender, participation analytics"),
        ("participation", "athlete careers, participation growth, age-performance"), ("result", "event-result explorer, record progression, performance trends"),
        ("match", "team-sport analytics: scores, standings, goal difference"), ("record", "Olympic/world record progression"),
        ("venue", "geographic maps, host-city analytics"), ("games", "edition-level KPIs, time series"), ("noc", "country history, NOC transitions"),
        ("countr", "country performance, choropleth maps"), ("sport", "sport evolution, specialization, gender by sport"), ("event", "event growth, gender balance of events"),
        ("team", "team-sport rosters, team medals"), ("wikipedia", "provenance, link graph, edition context"), ("standing", "tournament standings, knockout stages"),
        ("src_", "raw third-party snapshots for cross-source reconciliation"),
    ]
    return "; ".join(v for k, v in table if k in n) or "reference / provenance"


def year_range(con, t: str, cols: list[str]):
    if "year" in cols:
        r = con.execute(f'SELECT MIN(CAST("year" AS INT)), MAX(CAST("year" AS INT)) FROM "{t}" WHERE "year" GLOB \'[0-9]*\'').fetchone()
        return f"{r[0]}-{r[1]}" if r and r[0] else None
    if "games_id" in cols:
        r = con.execute(f'SELECT MIN(substr(games_id,1,4)), MAX(substr(games_id,1,4)), COUNT(DISTINCT games_id) FROM "{t}" WHERE games_id GLOB \'[0-9][0-9][0-9][0-9]_*\'').fetchone()
        return f"{r[0]}-{r[1]} ({r[2]} Games)" if r and r[0] else None
    return None


def source_of(con, t: str, cols: list[str]):
    for c in ("source_url", "source"):
        if c in cols:
            rows = con.execute(f'SELECT substr({c},1,45), COUNT(*) FROM "{t}" WHERE {c} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 2').fetchall()
            return "; ".join(f"{a} ({b})" for a, b in rows) or "source column empty"
    if t.startswith("src_"):
        return "athlete_events.csv/ folder"
    if t.startswith("olympedia_"):
        return "Olympedia (olympedia.org)"
    if t.startswith("wikipedia_"):
        return "Wikipedia (MediaWiki API/HTML)"
    return "not recorded in table"


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    inv, prof, findings = [], [], []
    for t in tables:
        info = con.execute(f'PRAGMA table_info("{t}")').fetchall()
        cols = [c[1] for c in info]
        pk = [c[1] for c in info if c[5]]
        n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        miss_total = 0
        if n:
            sel = ", ".join(f'COUNT("{c}"), COUNT(DISTINCT "{c}")' for c in cols)
            vals = con.execute(f'SELECT {sel} FROM "{t}"').fetchone()
        else:
            vals = [0] * (2 * len(cols))
        for i, (c, ci) in enumerate(zip(cols, info)):
            nn, nd = vals[2 * i], vals[2 * i + 1]
            miss_total += n - nn
            prof.append({"table": t, "column": c, "declared_type": ci[2], "rows": n, "non_null": nn, "missing": n - nn,
                         "missing_pct": round(100 * (n - nn) / n, 2) if n else None, "distinct": nd})
        nonpk = [c for c in cols if c not in pk and c not in ("created_at", "updated_at", "id")]
        dup = 0
        if n and nonpk and n <= 700_000:
            q = ",".join(f'"{c}"' for c in nonpk)
            dup = con.execute(f'SELECT COALESCE(SUM(k-1),0) FROM (SELECT COUNT(*) k FROM "{t}" GROUP BY {q} HAVING COUNT(*)>1)').fetchone()[0]
        mp = round(100 * miss_total / (n * len(cols)), 2) if n and cols else None
        inv.append({"dataset": t, "kind": "sqlite_table", "rows": n, "columns": len(cols), "column_names": ", ".join(cols), "missing_cells_pct": mp,
                    "duplicate_rows_excluding_ids": dup, "historical_coverage": year_range(con, t, cols), "source": source_of(con, t, cols),
                    "quality": "empty" if n == 0 else ("duplicates present" if dup else ("sparse (>40% missing)" if mp and mp > 40 else "ok")),
                    "analytical_use": applications(t, cols)})
        if n == 0:
            findings.append({"severity": "high", "dataset": t, "finding": "table is empty", "detail": ""})
        if dup:
            findings.append({"severity": "medium", "dataset": t, "finding": "duplicate rows (ignoring surrogate ids)", "detail": f"{dup} extra rows"})
        for c in cols:
            if c.endswith("source_url") or c == "source_url":
                nn = vals[2 * cols.index(c)]
                if n and nn < n:
                    findings.append({"severity": "low", "dataset": t, "finding": "missing source_url", "detail": f"{n - nn} of {n} rows"})
    write(OUT_INV / "dataset_inventory.csv", inv)
    write(OUT_INV / "column_profile.csv", prof)

    # ---- files on disk
    files = []
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and p.suffix.lower() in (".csv", ".json", ".parquet"):
            rel = p.relative_to(ROOT)
            if rel.parts[:2] in (("data", "raw"),) and p.suffix.lower() == ".json" and len(rel.parts) > 4:
                continue  # per-page raw JSON is summarised in raw_store_inventory
            rows = cols = None
            try:
                if p.suffix.lower() == ".csv" and p.stat().st_size < 120_000_000:
                    with p.open(encoding="utf-8-sig", errors="replace", newline="") as f:
                        rd = csv.reader(f)
                        header = next(rd, [])
                        rows = sum(1 for _ in rd)
                        cols = len(header)
                elif p.suffix.lower() == ".json" and p.stat().st_size < 30_000_000:
                    d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                    rows = len(d) if isinstance(d, (list, dict)) else None
            except Exception as e:  # noqa: BLE001
                rows = f"unreadable: {type(e).__name__}"
            files.append({"path": str(rel).replace("\\", "/"), "type": p.suffix.lower(), "size_mb": round(p.stat().st_size / 1e6, 3), "rows_or_keys": rows, "columns": cols})
    write(OUT_INV / "file_inventory.csv", files)

    # ---- raw store (HTML/JSON caches): counts only
    raw = []
    rr = ROOT / "data" / "raw"
    for d in sorted(x for x in rr.iterdir() if x.is_dir()):
        cnt, size, ext = 0, 0, {}
        for p in d.rglob("*"):
            if p.is_file():
                cnt += 1
                size += p.stat().st_size
                ext[p.suffix.lower()] = ext.get(p.suffix.lower(), 0) + 1
        raw.append({"folder": f"data/raw/{d.name}", "files": cnt, "size_mb": round(size / 1e6, 1), "by_extension": json.dumps(ext)})
    write(OUT_INV / "raw_store_inventory.csv", raw)

    # ---- images
    imgs = []
    for base in ("assets", "Olympics Editions Logo", "data/pictograms", "frontend/src"):
        b = ROOT / base
        if b.exists():
            c, s = {}, 0
            for p in b.rglob("*"):
                if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"):
                    c[p.suffix.lower()] = c.get(p.suffix.lower(), 0) + 1
                    s += p.stat().st_size
            imgs.append({"folder": base, "images": sum(c.values()), "by_type": json.dumps(c), "size_mb": round(s / 1e6, 1)})
    write(OUT_INV / "image_assets.csv", imgs)

    # ---- relationships / id consistency
    checks = [
        ("athlete_participations.athlete_id -> athletes", "SELECT COUNT(*) FROM athlete_participations p WHERE NOT EXISTS(SELECT 1 FROM athletes a WHERE a.athlete_id=p.athlete_id)"),
        ("athlete_participations.games_id -> games", "SELECT COUNT(*) FROM athlete_participations p WHERE NOT EXISTS(SELECT 1 FROM games g WHERE g.games_id=p.games_id)"),
        ("athlete_participations.event_id -> events", "SELECT COUNT(*) FROM athlete_participations p WHERE event_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM events e WHERE e.event_id=p.event_id)"),
        ("athlete_participations.sport_id -> sports", "SELECT COUNT(*) FROM athlete_participations p WHERE sport_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM sports s WHERE s.sport_id=p.sport_id)"),
        ("athlete_participations.noc_code -> historical_nocs", "SELECT COUNT(*) FROM athlete_participations p WHERE noc_code IS NOT NULL AND NOT EXISTS(SELECT 1 FROM historical_nocs h WHERE h.noc_code=p.noc_code)"),
        ("event_results.event_id -> events", "SELECT COUNT(*) FROM event_results r WHERE event_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM events e WHERE e.event_id=r.event_id)"),
        ("event_results.athlete_id -> athletes", "SELECT COUNT(*) FROM event_results r WHERE athlete_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM athletes a WHERE a.athlete_id=r.athlete_id)"),
        ("event_results.noc_code -> historical_nocs", "SELECT COUNT(*) FROM event_results r WHERE noc_code IS NOT NULL AND NOT EXISTS(SELECT 1 FROM historical_nocs h WHERE h.noc_code=r.noc_code)"),
        ("medals.event_id -> events", "SELECT COUNT(*) FROM medals m WHERE event_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM events e WHERE e.event_id=m.event_id)"),
        ("medals.athlete_id -> athletes", "SELECT COUNT(*) FROM medals m WHERE athlete_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM athletes a WHERE a.athlete_id=m.athlete_id)"),
        ("medals.noc_code -> historical_nocs", "SELECT COUNT(*) FROM medals m WHERE noc_code IS NOT NULL AND NOT EXISTS(SELECT 1 FROM historical_nocs h WHERE h.noc_code=m.noc_code)"),
        ("medal_tables.noc_code -> historical_nocs", "SELECT COUNT(*) FROM medal_tables m WHERE noc_code IS NOT NULL AND NOT EXISTS(SELECT 1 FROM historical_nocs h WHERE h.noc_code=m.noc_code)"),
        ("events.sport_id -> sports", "SELECT COUNT(*) FROM events e WHERE NOT EXISTS(SELECT 1 FROM sports s WHERE s.sport_id=e.sport_id)"),
        ("events.games_id -> games", "SELECT COUNT(*) FROM events e WHERE NOT EXISTS(SELECT 1 FROM games g WHERE g.games_id=e.games_id)"),
        ("teams.games_id -> games", "SELECT COUNT(*) FROM teams t WHERE NOT EXISTS(SELECT 1 FROM games g WHERE g.games_id=t.games_id)"),
        ("team_members.team_id -> teams", "SELECT COUNT(*) FROM team_members t WHERE NOT EXISTS(SELECT 1 FROM teams x WHERE x.team_id=t.team_id)"),
        ("matches.home_team_id -> teams", "SELECT COUNT(*) FROM matches m WHERE home_team_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM teams t WHERE t.team_id=m.home_team_id)"),
        ("match_statistics.match_id -> matches", "SELECT COUNT(*) FROM match_statistics s WHERE NOT EXISTS(SELECT 1 FROM matches m WHERE m.match_id=s.match_id)"),
        ("records.games_id -> games", "SELECT COUNT(*) FROM records r WHERE games_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM games g WHERE g.games_id=r.games_id)"),
        ("venues.games_id -> games", "SELECT COUNT(*) FROM venues v WHERE NOT EXISTS(SELECT 1 FROM games g WHERE g.games_id=v.games_id)"),
    ]
    rel = []
    for name, sql in checks:
        bad = con.execute(sql).fetchone()[0]
        rel.append({"relationship": name, "orphan_rows": bad, "status": "OK" if bad == 0 else "ORPHANS"})
        if bad:
            findings.append({"severity": "medium", "dataset": name.split(".")[0], "finding": f"referential integrity: {name}", "detail": f"{bad} orphan rows"})
    write(OUT_INV / "relationships.csv", rel)

    # ---- ID formats / name consistency
    idc = []
    q = lambda s: con.execute(s).fetchall()
    idc.append({"check": "games_id format (YYYY_season)", "result": q("SELECT COUNT(*) FROM games WHERE games_id NOT GLOB '[0-9][0-9][0-9][0-9]_[sw]*'")[0][0], "note": "rows violating"})
    idc.append({"check": "NOC codes in medals not in historical_nocs", "result": q("SELECT GROUP_CONCAT(DISTINCT noc_code) FROM medals m WHERE noc_code IS NOT NULL AND noc_code NOT IN (SELECT noc_code FROM historical_nocs)")[0][0], "note": ""})
    idc.append({"check": "athletes: duplicate identity_key", "result": q("SELECT COUNT(*) FROM (SELECT 1 FROM athletes GROUP BY identity_key HAVING COUNT(*)>1)")[0][0], "note": ""})
    idc.append({"check": "athlete_id types", "result": json.dumps(dict(q("SELECT typeof(athlete_id), COUNT(*) FROM athletes GROUP BY 1"))), "note": "surrogate integer; Olympedia ids linked through athlete_id_map"})
    idc.append({"check": "athletes linked to an Olympedia bio", "result": q("SELECT COUNT(*) FROM athlete_id_map")[0][0], "note": f"of {q('SELECT COUNT(*) FROM athletes')[0][0]} athletes"})
    idc.append({"check": "country names: same NOC with several historical names", "result": q("SELECT COUNT(*) FROM (SELECT noc_code FROM historical_nocs GROUP BY noc_code HAVING COUNT(DISTINCT historical_name)>1)")[0][0], "note": ""})
    idc.append({"check": "medal_tables country names that differ from historical_nocs", "result": q("SELECT COUNT(DISTINCT m.noc_code) FROM medal_tables m JOIN historical_nocs h ON h.noc_code=m.noc_code WHERE m.country_name IS NOT NULL AND m.country_name!=h.historical_name AND m.table_scope='wikipedia_country_medal_table'")[0][0], "note": "naming variants between Wikipedia tables and the NOC registry"})
    idc.append({"check": "invalid dates (games opening after closing)", "result": q("SELECT COUNT(*) FROM games WHERE opening_date>closing_date")[0][0], "note": ""})
    idc.append({"check": "duplicate medals (same athlete+event+type)", "result": q("SELECT COUNT(*) FROM (SELECT 1 FROM medals GROUP BY athlete_id,event_id,medal_type HAVING COUNT(*)>1)")[0][0], "note": ""})
    idc.append({"check": "result_unit values", "result": json.dumps(dict(q("SELECT COALESCE(result_unit,'NULL'), COUNT(*) FROM event_results GROUP BY 1 ORDER BY 2 DESC LIMIT 8"))), "note": "inconsistent / missing result units"})
    write(OUT_Q / "id_consistency.csv", idc)
    for r in idc:
        if r["check"].startswith(("invalid", "duplicate medals", "athletes: dup")) and r["result"]:
            findings.append({"severity": "high", "dataset": r["check"], "finding": "check failed", "detail": str(r["result"])})
    if idc[-1]["result"].startswith('{"NULL"'):
        findings.append({"severity": "medium", "dataset": "event_results", "finding": "result_unit is empty for most rows", "detail": idc[-1]["result"]})
    write(OUT_Q / "quality_findings.csv", findings)

    # ---- completeness matrix: dataset x edition
    games = [r[0] for r in q("SELECT games_id FROM games WHERE year BETWEEN 1960 AND 2026 AND (season='winter' OR year<=2024) ORDER BY year, season")]
    spec = {"events": "events", "event_results": "event_results", "participations": "athlete_participations", "medals": "medals", "medal_tables": "medal_tables",
            "matches": "matches", "teams": "teams", "venues": "venues", "olympedia_rosters": "olympedia_rosters", "olympedia_standings": "olympedia_standings",
            "match_statistics": "match_statistics", "sport_pictograms": "sport_pictograms"}
    sqls = {"match_statistics": "SELECT m.games_id, COUNT(*) FROM match_statistics s JOIN matches m ON m.match_id=s.match_id GROUP BY 1"}
    cnt = {k: dict(q(sqls.get(k) or f"SELECT games_id, COUNT(*) FROM {t} WHERE games_id IS NOT NULL GROUP BY 1")) for k, t in spec.items()}
    mat = [{"games_id": g, **{k: cnt[k].get(g, 0) for k in spec}} for g in games]
    write(OUT_C / "edition_dataset_matrix.csv", mat)
    miss = [(g, k) for g in games for k in spec if cnt[k].get(g, 0) == 0]
    write(OUT_C / "missing_edition_datasets.csv", [{"games_id": g, "dataset": k} for g, k in miss])

    # ---- markdown summary
    top = sorted(inv, key=lambda r: -r["rows"])[:15]
    md = ["# Data inventory (generated)", "", f"* SQLite tables: **{len(inv)}** ({sum(r['rows'] for r in inv):,} rows total)",
          f"* CSV/JSON/Parquet files outside raw caches: **{len(files)}**", f"* In-scope Games: **{len(games)}**; Games x dataset gaps: **{len(miss)}**",
          f"* Referential checks: **{sum(r['status'] == 'OK' for r in rel)}/{len(rel)}** clean", f"* Findings: **{len(findings)}** (see reports/data_quality/quality_findings.csv)", "",
          "## Largest datasets", "", "| dataset | rows | cols | missing % | quality |", "|---|---|---|---|---|"]
    md += [f"| {r['dataset']} | {r['rows']:,} | {r['columns']} | {r['missing_cells_pct']} | {r['quality']} |" for r in top]
    md += ["", "## Empty tables", ""] + [f"* {r['dataset']}" for r in inv if r["rows"] == 0]
    md += ["", "## Findings", ""] + [f"* [{f['severity']}] {f['dataset']}: {f['finding']} {f['detail']}" for f in findings[:60]]
    (OUT_INV / "inventory.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:12]))
    print(f"findings: {len(findings)}; empty tables: {[r['dataset'] for r in inv if r['rows'] == 0]}")
    print("orphans:", [r for r in rel if r["orphan_rows"]])


if __name__ == "__main__":
    main()
