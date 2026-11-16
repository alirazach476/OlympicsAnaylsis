"""Section 8 - data-engineering charts: every number is counted live from the warehouse, the report files or the pipeline log."""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .core import Ctx, Unavailable, chart, df, need_rows, payload, scalar, series_defs, table_from

S = 8
ROOT = Path(__file__).resolve().parents[2]
LAYER_COLORS = {"Bronze (raw / staging)": "#CD7F32", "Silver (cleaned)": "#9AA3AF", "Gold (analytics-ready)": "#D4AF37"}


def _mtime(f: Path) -> float:
    """File modification time; the serverless bundle (whose file times are reset) records the originals in reports/_mtimes.json."""
    m = ROOT / "reports" / "_mtimes.json"
    if m.exists():
        rel = f.resolve().relative_to(ROOT).as_posix()
        recorded = json.loads(m.read_text(encoding="utf-8")).get(rel)
        if recorded:
            return float(recorded)
    return f.stat().st_mtime


def count(table: str) -> int:
    """Live row count. The slim deployment DB drops raw staging tables but keeps their exact counts in _table_counts."""
    try:
        return int(scalar(f"SELECT COUNT(*) FROM {table}") or 0)
    except Exception:  # noqa: BLE001
        return int(scalar("SELECT n FROM _table_counts WHERE name = :t", t=table) or 0)


@chart("de_etl_flow", S, "engineering", "ETL pipeline flow", "flow", "Warehouse tables", "sqlite_master + row counts",
       "Show how data moves from sources to the dashboard, with live record counts", (), ())
def etl_flow(ctx: Ctx):
    n = count
    sp = df("SELECT name, COUNT(sp.source_page_id) pages FROM sources s LEFT JOIN source_pages sp USING(source_id) GROUP BY s.source_id, name")
    pages = dict(zip(sp.name, sp.pages))
    nodes = [
        {"id": "src_oly", "label": "Olympedia", "sub": f"{pages.get('olympedia', 0):,} pages registered", "col": 0, "row": 0, "kind": "source"},
        {"id": "src_wiki", "label": "Wikipedia", "sub": f"{n('wikipedia_pages'):,} pages, {n('wikipedia_links'):,} links", "col": 0, "row": 1, "kind": "source"},
        {"id": "src_csv", "label": "Athlete CSV datasets", "sub": "Kaggle-style + through-2026 file", "col": 0, "row": 2, "kind": "source"},
        {"id": "src_off", "label": "olympics.com", "sub": "blocked for automated access", "col": 0, "row": 3, "kind": "blocked"},
        {"id": "br_oly", "label": "Olympedia raw tables", "sub": f"{n('olympedia_event_rows'):,} result rows, {n('olympedia_matches'):,} matches, {n('olympedia_rosters'):,} roster rows", "col": 1, "row": 0, "kind": "bronze"},
        {"id": "br_wiki", "label": "Wikipedia raw pages", "sub": f"{n('wikipedia_edition_tables'):,} edition tables, {n('wikipedia_graph_pages'):,} sport/country pages", "col": 1, "row": 1, "kind": "bronze"},
        {"id": "br_csv", "label": "src_* staging", "sub": f"{n('src_athlete_events'):,} events, {n('src_athlete_bios'):,} bios, {n('src_athlete_results'):,} results", "col": 1, "row": 2, "kind": "bronze"},
        {"id": "wh", "label": "Normalised warehouse", "sub": f"{n('athletes'):,} athletes, {n('athlete_participations'):,} participations, {n('events'):,} events", "col": 2, "row": 1, "kind": "core"},
        {"id": "silver", "label": "Silver layer", "sub": f"{n('silver_participations'):,} participations, {n('silver_medal_awards'):,} medal awards", "col": 3, "row": 0, "kind": "silver"},
        {"id": "gold", "label": "Gold layer", "sub": f"{n('gold_athlete_career'):,} careers, {n('gold_country_medals'):,} country-Games rows", "col": 3, "row": 2, "kind": "gold"},
        {"id": "analytics", "label": "Analytics & models", "sub": f"{n('analytics_results'):,} stored analyses, {n('analytics_hypothesis_tests')} tests", "col": 4, "row": 0, "kind": "analytics"},
        {"id": "api", "label": "FastAPI", "sub": "/api/* + /api/viz/*", "col": 4, "row": 1, "kind": "serve"},
        {"id": "exports", "label": "CSV / Parquet exports", "sub": "data/exports, data/exports/parquet", "col": 4, "row": 2, "kind": "serve"},
        {"id": "dash", "label": "Dashboard", "sub": "React visualization library", "col": 5, "row": 1, "kind": "serve"},
    ]
    edges = [("src_oly", "br_oly"), ("src_wiki", "br_wiki"), ("src_csv", "br_csv"), ("br_oly", "wh"), ("br_wiki", "wh"), ("br_csv", "wh"), ("wh", "silver"), ("wh", "gold"), ("silver", "gold"), ("silver", "analytics"), ("gold", "analytics"),
             ("gold", "api"), ("analytics", "api"), ("gold", "exports"), ("api", "dash")]
    return payload("de_etl_flow", "flow", {"nodes": nodes, "edges": [{"from": a, "to": b} for a, b in edges], "cols": 6, "rows": 4}, ctx=ctx,
                   table=table_from([{"stage": x["kind"], "node": x["label"], "records": x["sub"]} for x in nodes]),
                   interpretation="Record counts are read from the warehouse when the chart loads. The olympics.com source is shown as blocked: the site refuses automated requests, so the same information comes from Olympedia and Wikipedia.")


@chart("de_medallion_compare", S, "engineering", "Bronze / Silver / Gold record counts", "xy", "Warehouse tables", "src_* / silver_* / gold_*",
       "Show how record volume changes as data is cleaned and aggregated", (), ("table",))
def medallion_compare(ctx: Ctx):
    spec = [
        ("Athletes", "src_athlete_bios", "silver_athletes", "gold_athlete_career", "one row per athlete"),
        ("Participations", "olympedia_athlete_results", "silver_participations", "gold_sport_performance", "bronze/silver: athlete-event entries; gold: sport-Games aggregates"),
        ("Medal awards", "src_olympics_medallists", "silver_medal_awards", "gold_country_medals", "bronze/silver: medals awarded; gold: country-Games table rows"),
        ("Event results", "olympedia_event_rows", None, "gold_event_results", "bronze: all result rows; gold: podium rows with parsed values"),
        ("Records", "olympedia_records_history", "records", "gold_records", "record progression rows"),
        ("Team rosters", "olympedia_rosters", "team_members", "gold_team_sports", "bronze: roster rows; silver: linked team members; gold: team-Games summaries"),
    ]
    rows, tab = [], []
    for ent, b, s, g, grain in spec:
        r = {"entity": ent, "Bronze (raw / staging)": count(b), "Silver (cleaned)": count(s) if s else None, "Gold (analytics-ready)": count(g)}
        rows.append(r)
        tab.append({"entity": ent, "bronze table": b, "bronze rows": r["Bronze (raw / staging)"], "silver table": s or "(not materialised)", "silver rows": r["Silver (cleaned)"], "gold table": g, "gold rows": r["Gold (analytics-ready)"], "grain": grain})
    return payload("de_medallion_compare", "xy", {"x": "entity", "xType": "category", "rows": rows, "series": series_defs(list(LAYER_COLORS), colors=LAYER_COLORS), "variant": "grouped", "xLabel": None, "yLabel": "Rows (log scale)", "logY": True},
                   axes={"x": "Entity", "y": "Rows (log)"}, ctx=ctx, table=table_from(tab),
                   interpretation="Row counts of the principal table at each layer. Counts are not directly comparable across layers because the grain changes (gold tables are aggregates); the table states the grain. "
                                  "A drop from bronze to silver is cleaning and de-duplication; a missing silver bar means no cleaned copy is materialised for that entity.")


COMPLETE_COLS = [("Athletes", "SELECT games_id, COUNT(DISTINCT athlete_id) n FROM silver_participations GROUP BY 1"),
                 ("Participations", "SELECT games_id, COUNT(*) n FROM athlete_participations GROUP BY 1"),
                 ("Events", "SELECT games_id, COUNT(*) n FROM events GROUP BY 1"),
                 ("Event results", "SELECT games_id, COUNT(*) n FROM event_results GROUP BY 1"),
                 ("Medal awards", "SELECT games_id, COUNT(*) n FROM silver_medal_awards GROUP BY 1"),
                 ("Medal table rows", "SELECT games_id, COUNT(*) n FROM gold_country_medals GROUP BY 1"),
                 ("Matches", "SELECT games_id, COUNT(*) n FROM olympedia_matches GROUP BY 1"),
                 ("Team members", "SELECT t.games_id, COUNT(*) n FROM team_members tm JOIN teams t USING(team_id) GROUP BY 1"),
                 ("Venues", "SELECT games_id, COUNT(*) n FROM venues GROUP BY 1"),
                 ("Sport/country wiki pages", "SELECT games_id, COUNT(*) n FROM wikipedia_graph_pages GROUP BY 1"),
                 ("Pictograms", "SELECT games_id, COUNT(*) n FROM assets WHERE asset_type='sport_pictogram' GROUP BY 1")]


@chart("de_completeness_heatmap", S, "engineering", "Data completeness heatmap", "heatmap", "Warehouse tables", "multiple (counts per Games)",
       "Show which data sets exist for which Games at a glance", (), ("table",))
def completeness_heatmap(ctx: Ctx):
    games = df("SELECT games_id FROM games WHERE year BETWEEN 1960 AND 2026 AND games_id IN (SELECT games_id FROM gold_edition_performance) ORDER BY year, season").games_id.tolist()
    rows, counts = [], {}
    for col, sql in COMPLETE_COLS:
        d = df(sql)
        m = dict(zip(d.games_id, d.n))
        counts[col] = m
        mx = max(m.values()) if m else 1
        for g in games:
            n = int(m.get(g, 0))
            rows.append({"r": g.replace("_", " ").title(), "c": col, "v": 0 if n == 0 else round(float(np.log10(n + 1) / np.log10(mx + 1)), 3), "n": n, "label": f"{g.replace('_', ' ')} / {col}: {n:,}" if n else f"{g.replace('_', ' ')} / {col}: MISSING"})
    missing = [r for r in rows if r["n"] == 0]
    return payload("de_completeness_heatmap", "heatmap", {"rows": rows, "rowOrder": [g.replace("_", " ").title() for g in games], "colOrder": [c for c, _ in COMPLETE_COLS], "scale": "seq", "vLabel": "Relative volume (log, per column)", "zeroColor": "#DF0024", "format": "pct0", "rotateCols": True},
                   axes={"x": "Data set", "y": "Games"}, ctx=ctx, table=table_from([{"games": r["r"], "dataset": r["c"], "records": r["n"]} for r in rows]),
                   interpretation=f"Red cells have no records at all ({len(missing)} of {len(rows)} Games-by-dataset cells); other cells are shaded by volume relative to that column's largest Games (log scale), so a pale cell is unusually small, not zero. "
                                  "Gaps such as pictograms before 1964 reflect that the source has none, not a collection failure.")


FIELD_SQL = """SELECT p.games_id, COUNT(*) n, SUM(p.age IS NULL) age, SUM(p.gender IS NULL OR p.gender='') gender, SUM(p.noc_code IS NULL OR p.noc_code='') noc, SUM(p.sport_name IS NULL) sport,
               SUM(a.date_of_birth IS NULL) dob, SUM(a.height_cm IS NULL) height, SUM(a.weight_kg IS NULL) weight, SUM(a.nationality IS NULL OR a.nationality='') nationality
               FROM silver_participations p JOIN athletes a USING(athlete_id) GROUP BY 1"""


@chart("de_missing_matrix", S, "engineering", "Missing-data matrix", "heatmap", "Silver participations x athletes x event results", "silver_participations, athletes, event_results",
       "Show which fields are incomplete, for which Games", (), ("table",))
def missing_matrix(ctx: Ctx):
    d = df(FIELD_SQL)
    er = df("SELECT games_id, COUNT(*) n, SUM(final_position IS NULL) pos, SUM(result_value IS NULL OR result_value='') val FROM event_results GROUP BY 1")
    d = d.merge(er[["games_id", "pos", "val", "n"]].rename(columns={"n": "n_er"}), on="games_id")
    order = df("SELECT games_id FROM games WHERE games_id IN (SELECT games_id FROM gold_edition_performance) ORDER BY year, season").games_id.tolist()
    fields = [("age", "Age at competition", "n"), ("gender", "Gender", "n"), ("noc", "NOC", "n"), ("nationality", "Athlete nationality", "n"), ("dob", "Date of birth", "n"), ("height", "Height", "n"), ("weight", "Weight", "n"),
              ("pos", "Final position (results)", "n_er"), ("val", "Result value (results)", "n_er")]
    rows = []
    for r in d.itertuples():
        for k, lab, den in fields:
            pct = 100 * getattr(r, k) / getattr(r, den)
            rows.append({"r": lab, "c": r.games_id.replace("_", " ").title(), "v": round(float(pct), 1), "label": f"{lab} in {r.games_id.replace('_', ' ')}: {pct:.1f}% missing"})
    tot = {lab: 100 * d[k].sum() / d[den].sum() for k, lab, den in fields}
    worst = max(tot, key=tot.get)
    return payload("de_missing_matrix", "heatmap", {"rows": rows, "rowOrder": [lab for _, lab, _ in fields], "colOrder": [g.replace("_", " ").title() for g in order if g in set(d.games_id)], "scale": "seq", "vLabel": "Share of records missing (%)",
                   "format": "pct0", "domain": [0, 100], "rotateCols": True}, axes={"x": "Games", "y": "Field"}, ctx=ctx, table=table_from([{"field": k, "overall_missing_pct": round(v, 1)} for k, v in tot.items()]),
                   interpretation=f"Brighter = more records missing that field. Overall, {worst.lower()} is the sparsest field ({tot[worst]:.0f}% missing). Medal is not listed: it is empty for non-medalists by definition, not missing. "
                                  "Date of birth, height and weight come from biographical sources that do not cover every athlete.")


@chart("de_duplicates", S, "engineering", "Duplicate records by entity", "xy", "Warehouse tables", "athlete_participations, event_results, matches, athletes",
       "Surface duplicated records so they can be reviewed", (), ("table",))
def duplicates(ctx: Ctx):
    checks = [
        ("Participations (athlete, Games, event, NOC)", "SELECT COUNT(*) FROM (SELECT 1 FROM athlete_participations GROUP BY athlete_id,games_id,event_id,noc_code HAVING COUNT(*)>1)", "SELECT COUNT(*) FROM athlete_participations"),
        ("Event results (athlete, Games, event)", "SELECT COUNT(*) FROM (SELECT 1 FROM event_results GROUP BY athlete_id,games_id,event_id HAVING COUNT(*)>1)", "SELECT COUNT(*) FROM event_results"),
        ("Athletes (identity key)", "SELECT COUNT(*) FROM (SELECT 1 FROM athletes GROUP BY identity_key HAVING COUNT(*)>1)", "SELECT COUNT(*) FROM athletes"),
        ("Athletes (same name and birth date)", "SELECT COUNT(*) FROM (SELECT 1 FROM athletes WHERE date_of_birth IS NOT NULL GROUP BY full_name,date_of_birth HAVING COUNT(*)>1)", "SELECT COUNT(*) FROM athletes WHERE date_of_birth IS NOT NULL"),
        ("Matches (Games, date, home team, away team)", "SELECT COUNT(*) FROM (SELECT 1 FROM matches WHERE match_date IS NOT NULL GROUP BY games_id,match_date,home_team_id,away_team_id HAVING COUNT(*)>1)", "SELECT COUNT(*) FROM matches WHERE match_date IS NOT NULL"),
    ]
    rows, tab = [], []
    for name, dsql, tsql in checks:
        d, t = int(scalar(dsql) or 0), int(scalar(tsql) or 0)
        rows.append({"entity": name, "Duplicate groups": d})
        tab.append({"entity": name, "duplicate groups": d, "records checked": t, "share": f"{100 * d / max(t, 1):.2f}%"})
    top = max(rows, key=lambda r: r["Duplicate groups"])
    return payload("de_duplicates", "xy", {"x": "entity", "xType": "category", "rows": rows, "series": [{"key": "Duplicate groups", "color": "#DF0024"}], "variant": "bar", "horizontal": True, "yLabel": "Groups of records sharing the same key", "yAuto": True},
                   axes={"x": "Duplicate groups", "y": "Entity"}, ctx=ctx, table=table_from(tab),
                   interpretation=("No duplicates were found in participations, results or athlete identity. " if all(r["Duplicate groups"] == 0 for r in rows[:4]) else "") +
                                  f"Match duplicates are the open issue ({top['Duplicate groups']} groups): football fixtures were loaded from both Wikipedia and Olympedia, and the Wikipedia copies also carry kickoff times in the score columns. "
                                  "Charts in this library therefore use the Olympedia fixtures only.")


@chart("de_source_coverage", S, "engineering", "Source coverage by entity", "xy", "Warehouse tables", "athletes, matches, events, venues (source_url)",
       "Show which source each kind of record comes from", (), ("percent", "table"))
def source_coverage(ctx: Ctx):
    def bucket(col):
        return (f"CASE WHEN {col} LIKE '%github.com%' THEN 'CSV datasets (GitHub)' WHEN {col} LIKE '%olympedia.org%' THEN 'Olympedia' WHEN {col} LIKE '%wikipedia.org%' THEN 'Wikipedia' "
                f"WHEN {col} IS NULL OR {col}='' THEN 'No source recorded' ELSE 'Other' END")
    ents = [("Athletes", "athletes"), ("Participations", "athlete_participations"), ("Event results", "event_results"), ("Events", "events"), ("Matches", "matches"), ("Venues", "venues"), ("Medals", "medals")]
    rows, tab = [], []
    for name, t in ents:
        d = df(f"SELECT {bucket('source_url')} src, COUNT(*) n FROM {t} GROUP BY 1")
        r = {"entity": name, **{s: int(n) for s, n in zip(d.src, d.n)}}
        rows.append(r)
        tab += [{"entity": name, "source": s, "records": int(n)} for s, n in zip(d.src, d.n)]
    keys = sorted({k for r in rows for k in r if k != "entity"})
    for r in rows:
        for k in keys:
            r.setdefault(k, 0)
    colors = {"Olympedia": "#009F3D", "Wikipedia": "#0085C7", "CSV datasets (GitHub)": "#F4A300", "No source recorded": "#B0B7C3", "Other": "#8E6BBF"}
    return payload("de_source_coverage", "xy", {"x": "entity", "xType": "category", "rows": rows, "series": series_defs(keys, colors=colors), "variant": "stacked", "xLabel": None, "yLabel": "Records"}, axes={"x": "Entity", "y": "Records"}, ctx=ctx, table=table_from(tab),
                   interpretation="Each bar splits an entity's records by the source URL stored with them. Athlete-level facts come mainly from the CSV datasets and Olympedia, fixtures from Olympedia, venues from both Olympedia and Wikipedia. "
                                  "Switch to percent to compare shares. This reflects loading provenance, not independent cross-verification (that is in the medal-table reconciliation).")


@chart("de_quality_scorecard", S, "engineering", "Data quality scorecard", "scorecard", "Validation results", "reports/quality/validation_results.csv",
       "Show which automated data-quality checks pass", (), ("table",))
def quality_scorecard(ctx: Ctx):
    f = ROOT / "reports" / "quality" / "validation_results.csv"
    if not f.exists():
        raise Unavailable("no validation report yet - run scripts/run_validation.py")
    rows = list(csv.DictReader(f.open(encoding="utf-8")))
    ok = sum(r["passed"] == "True" for r in rows)
    tiles = [{"label": "Checks passed", "value": f"{ok} / {len(rows)}", "hint": f"{100 * ok / len(rows):.0f}% of automated expectations", "status": "ok" if ok == len(rows) else "warn"}]
    fails = [r for r in rows if r["passed"] != "True"]
    tiles.append({"label": "Failing checks", "value": str(len(fails)), "hint": ", ".join(r["check"] for r in fails) or "none", "status": "ok" if not fails else "bad"})
    ts = dt.datetime.fromtimestamp(_mtime(f)).strftime("%Y-%m-%d %H:%M")
    tiles.append({"label": "Report generated", "value": ts, "hint": "scripts/run_validation.py", "status": "ok"})
    tab = [{"check": r["check"], "result": "PASS" if r["passed"] == "True" else "FAIL", "observed": r["observed"], "detail": r["detail"]} for r in rows]
    return payload("de_quality_scorecard", "scorecard", {"tiles": tiles, "tables": [{"title": "All checks", "columns": ["check", "result", "observed", "detail"], "rows": tab}]}, ctx=ctx, table=table_from(tab),
                   interpretation="Each row is an automated expectation (row counts, reconciliation of medal totals against the official tables, absence of placeholders, completeness). Failing checks are findings to act on, not silent errors.")


@chart("de_pipeline_timeline", S, "engineering", "Pipeline execution timeline", "timeline", "Pipeline run log", "pipeline_runs",
       "Show when each pipeline stage ran, how long it took and whether it succeeded", (), ("table",))
def pipeline_timeline(ctx: Ctx):
    d = df("SELECT run_id, stage, started_at, finished_at, status FROM pipeline_runs WHERE started_at IS NOT NULL AND finished_at IS NOT NULL ORDER BY started_at")
    need_rows(d, "pipeline runs")
    d["s"] = pd.to_datetime(d.started_at, utc=True, errors="coerce"); d["e"] = pd.to_datetime(d.finished_at, utc=True, errors="coerce")
    d = d.dropna(subset=["s", "e"])
    d = d.tail(120)
    t0 = d.s.min()
    colors = {"success": "#009F3D", "failed": "#DF0024"}
    rows = [{"lane": r.stage, "start": round((r.s - t0).total_seconds() / 60, 2), "end": round(max((r.e - t0).total_seconds() / 60, (r.s - t0).total_seconds() / 60 + 0.15), 2),
             "label": f"{r.stage}: {r.s:%Y-%m-%d %H:%M} -> {r.e:%H:%M} ({(r.e - r.s).total_seconds():.0f}s, {r.status})", "color": colors.get(r.status, "#9AA3AF"), "group": r.status} for r in d.itertuples()]
    order = d.groupby("stage").s.min().sort_values().index.tolist()
    return payload("de_pipeline_timeline", "timeline", {"rows": rows, "laneOrder": order, "xLabel": f"Minutes since {t0:%Y-%m-%d %H:%M} UTC", "unit": "min", "legend": [{"name": k, "color": v} for k, v in colors.items()]}, axes={"x": "Minutes", "y": "Stage"}, ctx=ctx,
                   table=table_from([{"stage": r.stage, "started": f"{r.s:%Y-%m-%d %H:%M:%S}", "seconds": round((r.e - r.s).total_seconds(), 1), "status": r.status} for r in d.itertuples()]),
                   interpretation="Each block is one recorded stage run (most recent 120). Stage runs started via scripts/run_pipeline.py are logged automatically; earlier runs of the medallion build were logged by that script alone, so older history is sparse.")


@chart("de_scrape_status", S, "engineering", "Scraping success and failure", "xy", "Crawl queue and history", "crawl_queue, crawl_history, failed_pages.csv",
       "Show how much of the crawl succeeded, failed or is still pending", (), ("donut", "table"))
def scrape_status(ctx: Ctx):
    q = df("SELECT status, COUNT(*) n FROM crawl_queue GROUP BY 1 ORDER BY 2 DESC")
    h = df("SELECT status, COUNT(*) n FROM crawl_history GROUP BY 1 ORDER BY 2 DESC")
    need_rows(q, "crawl queue")
    keys = sorted(set(q.status) | set(h.status))
    qm, hm = dict(zip(q.status, q.n)), dict(zip(h.status, h.n))
    rows = [{"view": "Discovery queue (all discovered pages)", **{k: int(qm.get(k, 0)) for k in keys}}, {"view": "Crawl history (fetch attempts)", **{k: int(hm.get(k, 0)) for k in keys}}]
    failed = ROOT / "reports" / "scraping" / "failed_pages.csv"
    nf = max(sum(1 for _ in failed.open(encoding="utf-8")) - 1, 0) if failed.exists() else 0
    colors = {"crawled": "#009F3D", "failed": "#DF0024", "pending": "#B0B7C3", "in_progress": "#F4A300", "skipped": "#8E6BBF"}
    total_q = int(q.n.sum()); pend = int(qm.get("pending", 0)); done = int(qm.get("crawled", 0))
    return payload("de_scrape_status", "xy", {"x": "view", "xType": "category", "rows": rows, "series": series_defs(keys, colors=colors), "variant": "stacked", "horizontal": True, "yLabel": "Pages", "xLabel": None},
                   axes={"x": "Pages", "y": "View"}, ctx=ctx, table=table_from([{"view": r["view"], **{k: r[k] for k in keys}} for r in rows] + [{"view": "Unfetchable pages listed in failed_pages.csv", **{k: (nf if k == 'failed' else 0) for k in keys}}]),
                   interpretation=f"Of {total_q:,} pages discovered by the recursive Wikipedia crawl, {done:,} were fetched and {pend:,} are still queued (the queue holds mostly low-relevance linked pages, deliberately not all fetched). "
                                  f"{nf} page(s) are recorded as unfetchable (olympics.com refuses automated access). The Olympedia scrape is tracked by its own checkpoint and is complete for all 35 editions.")


EDITION_CHECKS = [("Participations loaded", "SELECT games_id, COUNT(*) n FROM athlete_participations GROUP BY 1"), ("Event results", "SELECT games_id, COUNT(*) n FROM event_results GROUP BY 1"),
                  ("Verified medal table", "SELECT games_id, COUNT(*) n FROM gold_country_medals GROUP BY 1"), ("Fixtures", "SELECT games_id, COUNT(*) n FROM olympedia_matches GROUP BY 1"),
                  ("Team rosters", "SELECT t.games_id, COUNT(*) n FROM team_members tm JOIN teams t USING(team_id) GROUP BY 1"), ("Venues", "SELECT games_id, COUNT(*) n FROM venues GROUP BY 1"),
                  ("Sport/country pages (Wikipedia)", "SELECT games_id, COUNT(*) n FROM wikipedia_graph_pages GROUP BY 1"), ("Edition logo", "SELECT games_id, COUNT(*) n FROM assets WHERE asset_type='edition_logo' GROUP BY 1")]


@chart("de_edition_progress", S, "engineering", "Historical edition collection progress", "xy", "Warehouse tables", "multiple (counts per Games)",
       "Track how complete the collection is for every edition", (), ("table",))
def edition_progress(ctx: Ctx):
    games = df("SELECT games_id FROM games WHERE year BETWEEN 1960 AND 2026 AND games_id IN (SELECT games_id FROM gold_edition_performance) ORDER BY year, season").games_id.tolist()
    present = {c: set(df(sql).games_id) for c, sql in EDITION_CHECKS}
    rows, tab = [], []
    for g in games:
        got = [c for c, _ in EDITION_CHECKS if g in present[c]]
        rows.append({"games": g.replace("_", " ").title(), "Checks passed": len(got), "Missing": len(EDITION_CHECKS) - len(got)})
        tab.append({"games": g, "passed": len(got), "of": len(EDITION_CHECKS), "missing": ", ".join(c for c, _ in EDITION_CHECKS if c not in got) or "-"})
    full = sum(r["Missing"] == 0 for r in rows)
    return payload("de_edition_progress", "xy", {"x": "games", "xType": "category", "rows": rows, "series": [{"key": "Checks passed", "color": "#009F3D"}, {"key": "Missing", "color": "#DF0024"}], "variant": "stacked", "xLabel": None,
                   "yLabel": f"Collection checks (of {len(EDITION_CHECKS)})", "rotateX": True}, axes={"x": "Games", "y": "Checks"}, ctx=ctx, table=table_from(tab),
                   interpretation=f"{full} of {len(rows)} editions pass all {len(EDITION_CHECKS)} presence checks (participations, results, medal table, fixtures, rosters, venues, Wikipedia sport/country pages, logo). "
                                  "A check passes when at least one record exists, so this shows coverage of data sets, not completeness within them; see the completeness heatmap for volumes.")
