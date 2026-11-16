#!/usr/bin/env python3
"""Visualization registry + coverage report (reads the warehouse; writes reports/visualization/* and docs/VISUALIZATION_REGISTRY.md).

Every registered chart is EXECUTED against the live warehouse with its default filters, and again with season / year-range filters to catch
filter-specific failures. Each planned item of the requirement (backend/viz/plan.py) is then classified:
  implemented  every mapped chart returns real data and its chart type has a frontend renderer
  unavailable  the collected data cannot support it (the builder says why)
  pending      no chart is registered for the item, a chart raised an error, or its renderer is missing
Usage: python scripts/build_viz_coverage.py [--chart ID]"""
import argparse, csv, datetime as dt, json, re, sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.viz import REGISTRY, SECTIONS, Unavailable, evaluate  # noqa: E402
from backend.viz.plan import PLAN  # noqa: E402

OUT = ROOT / "reports" / "visualization"
DOC = ROOT / "docs" / "VISUALIZATION_REGISTRY.md"
INDEX = ROOT / "frontend" / "src" / "viz" / "renderers" / "index.tsx"
XY_VIEWS = {"line", "area", "bar", "stacked", "grouped", "percent", "step", "stream", "donut", "treemap", "table"}

ap = argparse.ArgumentParser()
ap.add_argument("--chart")
args = ap.parse_args()


def frontend_kinds() -> set[str]:
    txt = INDEX.read_text(encoding="utf-8")
    block = re.search(r"export const RENDERERS.*?= \{(.*?)\n\};", txt, re.S).group(1)
    return set(re.findall(r"(\w+):", block))


KINDS = frontend_kinds()
VARIANTS = [("default", {}), ("summer", {"season": "summer"}), ("winter", {"season": "winter"}), ("since_2000", {"year_from": "2000"})]


def run(spec, params):
    t = time.time()
    try:
        p = evaluate(spec, params)
        rows = p["table"]["rows"]
        data = p["data"]
        empty = (isinstance(data.get("rows"), list) and not data["rows"]) or (data.get("frames") is not None and not any(f["rows"] for f in data["frames"]))
        return {"ok": not empty, "unavailable": None, "error": None if not empty else "empty data", "rows": len(rows), "seconds": round(time.time() - t, 2), "kind": p["kind"], "payload": p}
    except Unavailable as exc:
        return {"ok": False, "unavailable": str(exc), "error": None, "rows": 0, "seconds": round(time.time() - t, 2), "kind": spec.kind, "payload": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "unavailable": None, "error": f"{type(exc).__name__}: {exc}", "rows": 0, "seconds": round(time.time() - t, 2), "kind": spec.kind, "payload": None}


charts, by_id = [], {}
specs = [REGISTRY[args.chart]] if args.chart else list(REGISTRY.values())
for spec in specs:
    base = run(spec, {})
    p = base["payload"]
    status, reason = "implemented", ""
    if base["unavailable"]:
        status, reason = "unavailable", base["unavailable"]
    elif base["error"]:
        status, reason = "pending", base["error"]
    elif base["kind"] not in KINDS:
        status, reason = "pending", f"no frontend renderer for chart type '{base['kind']}'"
    warnings = []
    if status == "implemented":
        if not (p["interpretation"] or "").strip():
            warnings.append("missing interpretation text")
        bad_alt = [a for a in p["alternatives"] if a not in XY_VIEWS and a not in ("table",)]
        if bad_alt:
            warnings.append(f"alternatives without an adapter: {bad_alt}")
    robustness = {}
    for name, par in VARIANTS[1:]:
        if not (set(par) & set(spec.filters)) and not ("year_from" in par and "year_range" in spec.filters):
            continue
        r = run(spec, par)
        robustness[name] = "ok" if r["ok"] else ("unavailable: " + r["unavailable"] if r["unavailable"] else "ERROR: " + str(r["error"]))
    errs = {k: v for k, v in robustness.items() if v.startswith("ERROR")}
    if errs:
        warnings.append(f"errors under filters: {errs}")
    rec = {**spec.meta(), "status": status, "reason": reason, "rows": base["rows"], "seconds": base["seconds"], "warnings": warnings, "filter_checks": robustness}
    charts.append(rec)
    by_id[spec.id] = rec
    print(f"{status:12} {spec.id:30} {base['seconds']:5.1f}s rows={base['rows']:5} {reason[:80]} {'; '.join(warnings)[:100]}", flush=True)

if args.chart:
    sys.exit(0)

items = []
for section, name, ids in PLAN:
    recs = [by_id[i] for i in ids if i in by_id]
    if not recs or len(recs) != len(ids):
        st, why = "pending", "no chart builder registered" if not recs else "some mapped charts are not registered"
    elif all(r["status"] == "implemented" for r in recs):
        st, why = "implemented", ""
    elif all(r["status"] == "unavailable" for r in recs):
        st, why = "unavailable", "; ".join(sorted({r["reason"] for r in recs}))
    elif any(r["status"] == "pending" for r in recs):
        st, why = "pending", "; ".join(r["reason"] for r in recs if r["status"] == "pending")
    else:
        st, why = "implemented", "partly: " + "; ".join(f"{r['id']} unavailable ({r['reason']})" for r in recs if r["status"] == "unavailable")
    items.append({"section": f"{section} {SECTIONS[section]}", "item": name, "charts": ", ".join(ids), "status": st, "reason": why})

planned_ids = {i for _, _, ids in PLAN for i in ids}
extras = [c["id"] for c in charts if c["id"] not in planned_ids]
summary = {"planned_items": len(items), "registered_charts": len(charts), "implemented": sum(i["status"] == "implemented" for i in items), "unavailable": sum(i["status"] == "unavailable" for i in items),
           "pending": sum(i["status"] == "pending" for i in items), "charts_with_warnings": sum(bool(c["warnings"]) for c in charts), "extra_charts_beyond_plan": extras,
           "chart_types_with_renderers": sorted(KINDS), "filter_variants_checked": [v for v, _ in VARIANTS]}
gen = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "coverage.json").write_text(json.dumps({"generated_at": gen, "summary": summary, "items": items, "charts": charts}, indent=1, ensure_ascii=False), encoding="utf-8")
with (OUT / "coverage_report.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, ["section", "item", "charts", "status", "reason"]); w.writeheader(); w.writerows(items)
REG_COLS = ["id", "page", "name", "kind", "dataset", "source_table", "purpose", "filters", "endpoint", "status"]
with (OUT / "visualization_registry.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["Chart ID", "Dashboard page", "Visualization name", "Chart type", "Dataset", "Source table", "Analytical purpose", "Filters", "Backend endpoint", "Implementation status"])
    for c in charts:
        w.writerow([c["id"], c["page"], c["name"], c["kind"], c["dataset"], c["source_table"], c["purpose"], " ".join(c["filters"]), c["endpoint"], c["status"]])

md = [f"# Visualization coverage report\n", f"Generated {gen} by `scripts/build_viz_coverage.py`. Every chart is executed against the live warehouse (default filters, then Summer / Winter / since-2000 variants).\n",
      f"| Planned items | Implemented | Unavailable (missing data) | Pending | Registered charts | Extra charts |\n|---|---|---|---|---|---|\n| {summary['planned_items']} | {summary['implemented']} | {summary['unavailable']} | {summary['pending']} | {summary['registered_charts']} | {len(extras)} |\n"]
for sec in SECTIONS:
    md.append(f"\n## {sec}. {SECTIONS[sec]}\n\n| Planned item | Chart(s) | Status | Note |\n|---|---|---|---|")
    for i in items:
        if i["section"].startswith(f"{sec} "):
            md.append(f"| {i['item']} | {i['charts']} | **{i['status']}** | {i['reason']} |")
if extras:
    md.append(f"\n## Extra charts beyond the plan\n\n" + ", ".join(extras))
warn = [c for c in charts if c["warnings"]]
md.append("\n## Warnings\n\n" + ("\n".join(f"- `{c['id']}`: {'; '.join(c['warnings'])}" for c in warn) if warn else "None."))
unav = [c for c in charts if c["filter_checks"] and any(v.startswith("unavailable") for v in c["filter_checks"].values())]
md.append("\n## Filter-dependent availability\n\nCharts that legitimately have no data under some filters (shown to users as a 'not available' state with the reason):\n\n" +
          ("\n".join(f"- `{c['id']}`: " + ", ".join(f"{k} -> {v}" for k, v in c["filter_checks"].items() if v.startswith("unavailable")) for c in unav) if unav else "None."))
(OUT / "coverage_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

doc = ["# Visualization registry\n", f"Generated {gen}. {len(charts)} charts; served by `GET /api/viz/chart/{{chart_id}}` (JSON, or `?format=csv` for the data table). Registry: `GET /api/viz/registry`; coverage: `GET /api/viz/coverage`.\n",
       "Common query filters: `season`, `year_from`, `year_to`, `noc` / `nocs`, `sport`, `games_id`, `event`, `athlete_ids`, `top`, `metric`, `a`, `b` (each chart honours only the filters listed for it).\n"]
for sec in SECTIONS:
    doc.append(f"\n## {sec}. {SECTIONS[sec]}\n\n| Chart ID | Dashboard page | Visualization | Chart type | Dataset | Source table | Analytical purpose | Filters | Backend endpoint | Status |\n|---|---|---|---|---|---|---|---|---|---|")
    for c in charts:
        if c["section"] == sec:
            doc.append(f"| `{c['id']}` | {c['page']} | {c['name']} | {c['kind']} | {c['dataset']} | `{c['source_table']}` | {c['purpose']} | {' '.join(c['filters'])} | `{c['endpoint']}` | {c['status']} |")
DOC.write_text("\n".join(doc) + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------------------------- data limitations (live numbers)
from backend.viz.core import df, scalar  # noqa: E402

lim = []
tot_er = scalar("SELECT COUNT(*) FROM event_results")
n_val = scalar("SELECT COUNT(*) FROM event_results WHERE result_value IS NOT NULL AND result_value!=''")
n_pos = scalar("SELECT COUNT(final_position) FROM event_results")
lim.append(f"Event-result values: {100 * n_val / tot_er:.0f}% of {tot_er:,} result rows have a result value and {100 * n_pos / tot_er:.0f}% a final position; the event-result charts (`s_result_hist`, `s_result_decades`) "
           "therefore use the Olympedia main results tables (mostly finals), not every heat.")
rec = df("SELECT description FROM gold_records")
rec["event"] = rec.description.str.split(" | ", regex=False).str[0]
lim.append(f"Records: {rec.event.nunique()} events have record rows, from 8 disciplines only (archery, athletics, canoe sprint, modern pentathlon, rowing, short track, ski jumping, speed skating); swimming records are not in the source, "
           "so `s_record_progression` and `s_or_vs_wr` cover only those events.")
ts = df("SELECT sport_name, COUNT(*) n FROM olympedia_matches WHERE home_score GLOB '[0-9]*' AND away_score GLOB '[0-9]*' GROUP BY 1 HAVING n>=100 ORDER BY n DESC")
lim.append("Fixture charts (team sports and head-to-head sports) use only sports with scored fixtures (>=100 matches): " + ", ".join(f"{r.sport_name} ({r.n:,})" for r in ts.itertuples()) +
           ". Period scores are additive for basketball / water polo, cumulative for football / hockey / rugby sevens and set scores for volleyball / tennis, so score-progression charts are offered only for the first two groups.")
lim.append("Knockout structure: fixtures carry stage labels only for medal matches ('Match 1/2', 'Match 3/4'); earlier rounds are reconstructed from dates (`t_bracket`, `t_knockout_tree`), and no official group tables exist (`t_standings` is one table per event).")
arch = scalar("SELECT COUNT(*) FROM archived_matches") if scalar("SELECT COUNT(*) FROM sqlite_master WHERE name='archived_matches'") else 0
bad = scalar("SELECT COUNT(*) FROM archived_matches WHERE length(home_score)=2 AND away_score IN ('00','15','30','45')") if arch else 0
left = scalar("SELECT COUNT(*) FROM matches m JOIN sports s ON s.sport_id=m.sport_id WHERE s.sport_name='Football' AND length(m.home_score)=2 AND m.away_score IN ('00','15','30','45')")
lim.append(f"Data issue found and repaired: the Wikipedia football parser read kickoff times (e.g. 17:00) as scores and loaded each match from several pages on top of the Olympedia fixtures. {arch:,} Wikipedia football rows "
           f"({bad:,} with a clock time as score) are archived in `archived_matches`; `matches` now holds the clean Olympedia football fixtures ({left:,} clock-time scores remain). The parser is fixed and covered by a regression test.")
dob = scalar("SELECT 100.0*COUNT(date_of_birth)/COUNT(*) FROM athletes")
lim.append(f"Athlete birth dates cover {dob:.0f}% of athletes; no chart depends on them (ages come from the age recorded at each Games).")
lim.append("olympics.com refuses automated requests, so no chart uses it; the same facts come from Olympedia and Wikipedia.")
lim.append("Correlation and regression charts treat NOC-Games observations as independent, which they are not (the same NOC repeats); the stored analyses use cluster-robust errors where it matters and say so.")
summary["data_limitations"] = lim
cj = json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))
cj["summary"] = summary
(OUT / "coverage.json").write_text(json.dumps(cj, indent=1, ensure_ascii=False), encoding="utf-8")
mdp = OUT / "coverage_report.md"
mdp.write_text(mdp.read_text(encoding="utf-8") + "\n## Data limitations that shape the implemented charts\n\n" + "\n".join(f"- {x}" for x in lim) + "\n", encoding="utf-8")
print(f"\nplanned {summary['planned_items']}: implemented {summary['implemented']}, unavailable {summary['unavailable']}, pending {summary['pending']}; charts {len(charts)} (+{len(extras)} extra); warnings {summary['charts_with_warnings']}")
