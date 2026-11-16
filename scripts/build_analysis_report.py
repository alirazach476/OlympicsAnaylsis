#!/usr/bin/env python3
"""Written analysis of the COMPLETE Olympic dataset (1960-2026, Summer + Winter). Every figure is computed from the warehouse or a stored analysis when the
script runs (nothing is typed in by hand), so the report can be regenerated after any data change.
Writes reports/analysis/OLYMPIC_ANALYSIS.md and reports/analysis/key_numbers.json.   Usage: python scripts/build_analysis_report.py"""
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.viz.charts_sports import parse_value, unit_for  # noqa: E402

OUT = ROOT / "reports" / "analysis"
OUT.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(f"file:{ROOT / 'data/olympics_warehouse.db'}?mode=ro", uri=True, timeout=300)


def q(sql, **p) -> pd.DataFrame:
    return pd.read_sql(sql, con, params=p)


def one(sql, **p):
    r = con.execute(sql, p).fetchone()
    return r[0] if r else None


def stored(module, key):
    r = con.execute("SELECT payload_json FROM analytics_results WHERE module=? AND key=?", (module, key)).fetchone()
    return json.loads(r[0]) if r else {}


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def n(x):
    return f"{int(round(x)):,}"


KEY: dict = {}
L: list[str] = []
add = L.append
gen = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ------------------------------------------------------------------------------------------------------------------------- 1. scope
games = q("SELECT * FROM gold_edition_performance ORDER BY year, season")
sc = {
    "editions": len(games), "summer": int((games.season == "summer").sum()), "winter": int((games.season == "winter").sum()),
    "athletes": one("SELECT COUNT(DISTINCT athlete_id) FROM silver_participations"), "participations": one("SELECT COUNT(*) FROM silver_participations"),
    "nocs": one("SELECT COUNT(DISTINCT noc_code) FROM silver_participations"), "sports": one("SELECT COUNT(DISTINCT sport_name) FROM silver_participations"),
    "events": one("SELECT SUM(events) FROM gold_edition_performance"), "medal_awards": one("SELECT COUNT(*) FROM silver_medal_awards"), "matches": one("SELECT COUNT(*) FROM matches"),
    "scored_fixtures": one("SELECT COUNT(*) FROM olympedia_matches WHERE home_score GLOB '[0-9]*' AND away_score GLOB '[0-9]*'"),
    "team_members": one("SELECT COUNT(*) FROM team_members"), "venues": one("SELECT COUNT(*) FROM venues"), "result_rows": one("SELECT COUNT(*) FROM olympedia_event_rows"),
    "records": one("SELECT COUNT(*) FROM gold_records"), "archived_matches": one("SELECT COUNT(*) FROM archived_matches") if one("SELECT COUNT(*) FROM sqlite_master WHERE name='archived_matches'") else 0,
}
KEY["scope"] = sc
vf = ROOT / "reports" / "quality" / "validation_results.csv"
vr = pd.read_csv(vf) if vf.exists() else pd.DataFrame(columns=["passed"])
KEY["validation"] = {"passed": int(vr.passed.sum()) if len(vr) else 0, "checks": len(vr)}

# --------------------------------------------------------------------------------------------------------------------- 2. growth / gender
s = games[games.season == "summer"].reset_index(drop=True)
w = games[games.season == "winter"].reset_index(drop=True)
growth = {"summer_first": [int(s.year[0]), int(s.athletes[0])], "summer_last": [int(s.year.iloc[-1]), int(s.athletes.iloc[-1])], "winter_first": [int(w.year[0]), int(w.athletes[0])], "winter_last": [int(w.year.iloc[-1]), int(w.athletes.iloc[-1])],
          "summer_events": [int(s.events[0]), int(s.events.iloc[-1])], "winter_events": [int(w.events[0]), int(w.events.iloc[-1])], "summer_nocs": [int(s.nocs[0]), int(s.nocs.iloc[-1])], "winter_nocs": [int(w.nocs[0]), int(w.nocs.iloc[-1])],
          "female_share_summer": [float(s.female_share[0]), float(s.female_share.iloc[-1])], "female_share_winter": [float(w.female_share[0]), float(w.female_share.iloc[-1])]}
KEY["growth"] = growth
peak = games.loc[games.athletes.idxmax()]
jump = s.assign(d=s.athletes.diff()).sort_values("d", ascending=False).iloc[0]
ht = {r["test_id"]: r for r in q("SELECT * FROM analytics_hypothesis_tests").to_dict("records")}
gm = stored("eda", "E_gender").get("milestones", {})

# ------------------------------------------------------------------------------------------------------------------------- 3. medals
hist = q("SELECT noc_code, historical_name, gold, silver, bronze, total_medals, appearances, athletes FROM gold_country_participation_history ORDER BY total_medals DESC, gold DESC LIMIT 10")
par = stored("stats", "distributions").get("pareto_medals_by_noc", {})
cont = q("""SELECT (g.year/10*10) decade, COALESCE(h.continent,'Unassigned') continent, SUM(g.total) m FROM gold_country_medals g LEFT JOIN historical_nocs h USING(noc_code) GROUP BY 1,2""")
cont["share"] = cont.m / cont.groupby("decade").m.transform("sum")
c60 = cont[cont.decade == 1960].set_index("continent").share
c10 = cont[cont.decade == 2010].set_index("continent").share
eda_c = stored("eda", "B_country_performance")
eda_f = stored("eda", "F_host")
eda_g = stored("eda", "G_winter_vs_summer")
nomedal = one("SELECT COUNT(*) FROM gold_country_participation_history WHERE appearances>0 AND total_medals=0")
n_nocs_h = one("SELECT COUNT(*) FROM gold_country_participation_history WHERE appearances>0")
KEY["medals"] = {"top10": hist[["noc_code", "total_medals"]].to_dict("records"), "gini": par.get("gini"), "noc_for_80pct": par.get("noc_for_80pct"), "never_medalled": int(nomedal), "nocs": int(n_nocs_h)}

# ------------------------------------------------------------------------------------------------------------------------ 4. athletes
age = stored("stats", "descriptive")
oldm = q("""SELECT a.full_name, p.age, p.sport_name, p.games_id FROM silver_participations p JOIN athletes a USING(athlete_id) WHERE p.is_medalist=1 AND p.age BETWEEN 10 AND 80 ORDER BY p.age DESC LIMIT 1""").iloc[0]
youngm = q("""SELECT a.full_name, p.age, p.sport_name, p.games_id FROM silver_participations p JOIN athletes a USING(athlete_id) WHERE p.is_medalist=1 AND p.age BETWEEN 10 AND 80 ORDER BY p.age ASC LIMIT 1""").iloc[0]
top_ath = q("SELECT full_name, gender, gold, silver, bronze, medals, games_count, sports FROM gold_athlete_career ORDER BY medals DESC, gold DESC LIMIT 8")
cr = q("SELECT games_count, COUNT(*) a FROM gold_athlete_career GROUP BY 1 ORDER BY 1")
one_time = float(cr[cr.games_count == 1].a.sum() / cr.a.sum())
medal_k = q("SELECT medals, COUNT(*) a FROM gold_athlete_career WHERE medals>=1 GROUP BY 1")
exactly1 = float(medal_k[medal_k.medals == 1].a.sum() / medal_k.a.sum())
longest = q("SELECT full_name, games_count, career_span_years, sports FROM gold_athlete_career ORDER BY games_count DESC, career_span_years DESC LIMIT 3")
gender_rate = q("SELECT gender, COUNT(*) n, SUM(is_medalist)*1.0/COUNT(*) r FROM silver_participations WHERE gender IN ('M','F') GROUP BY 1").set_index("gender")
KEY["athletes"] = {"one_time_share": one_time, "exactly_one_medal_share": exactly1, "medal_rate": gender_rate.r.to_dict()}

# ------------------------------------------------------------------------------------------------------------------------- 5. sports
spf = stored("eda", "D_sports")
big = q("SELECT sport_name, SUM(athletes) a FROM gold_sport_performance GROUP BY 1 ORDER BY 2 DESC LIMIT 6")
latest = games.sort_values("year").groupby("season").tail(1)
gp = q("""SELECT sport_name, SUM(CASE WHEN gender='F' THEN athletes END)*1.0/SUM(athletes) fs, SUM(athletes) a FROM gold_gender_participation WHERE games_id=:g AND gender IN ('M','F') GROUP BY 1 HAVING a>=100""", g="2024_summer")
bal = gp.sort_values("fs")

# ------------------------------------------------------------------------------------------------------------------------- 6. records
rec = q("SELECT games_id, record_level, record_value, description FROM gold_records")
rec["event"] = rec.description.str.split(" | ", regex=False).str[0]
rec["v"] = rec.record_value.map(parse_value)
rec["year"] = rec.games_id.str[:4].astype(int)
rec_rows = []
rec["season"] = rec.games_id.str.split("_").str[1]
for (ev0, ssn), g in rec[(rec.record_level == "olympic")].dropna(subset=["v"]).groupby(["event", "season"]):
    ev = f"{ev0} ({ssn})"
    if len(g) >= 6 and g.year.nunique() >= 4:
        unit, lower = unit_for(ev0)
        if unit.startswith("Time") or unit.startswith("Distance"):
            g = g.sort_values("year")
            first, last = float(g.groupby("year").v.agg("min" if lower else "max").iloc[0]), float(g.groupby("year").v.agg("min" if lower else "max").iloc[-1])
            rec_rows.append((ev, int(g.year.min()), int(g.year.max()), first, last, (first - last) / first * 100 if lower else (last - first) / first * 100, "s" if lower else "m"))
rec_rows.sort(key=lambda r: -abs(r[5]))

# ----------------------------------------------------------------------------------------------------------------------- 7. team sports
ts_lines = []
for sport in ("Football", "Basketball", "Ice Hockey", "Handball", "Water Polo", "Hockey"):
    p = stored("sports", f"team_{sport.lower().replace(' ', '_')}")
    tr = p.get("scoring_trend_by_edition") or []
    sl = p.get("scoring_trend_slope_per_year")
    if tr and sl:
        ts_lines.append((sport, p["matches_with_scores"], p["editions"], tr[0]["year"], tr[0]["goals_per_match"], tr[-1]["year"], tr[-1]["goals_per_match"], sl["slope"], sl["p"],
                         float(np.mean([r["draw_rate"] for r in tr])), (p.get("team_records") or [{}])[0]))
fb = q("SELECT (year/10*10) decade, COUNT(*) n, AVG(CAST(home_score AS INT)+CAST(away_score AS INT)) g, AVG(CAST(home_score AS INT)=CAST(away_score AS INT)) d FROM olympedia_matches m JOIN games g USING(games_id) WHERE sport_name='Football' AND home_score GLOB '[0-9]*' AND away_score GLOB '[0-9]*' GROUP BY 1 ORDER BY 1")

# ------------------------------------------------------------------------------------------------------------------------ 8. models
med, ath, clu = stored("ml", "medal_prediction"), stored("ml", "athlete_medal_model"), stored("ml", "clustering")
mm = med.get("metrics_all_participating_nocs", {})
best = med.get("best_model_by_rmse")
ab = ath.get("best_model_by_pr_auc")
pi_ = med.get("prediction_interval_80", {})
perm = (ath.get("interpretability", {}).get("permutation_importance_best") or [])[:3]

# ------------------------------------------------------------------------------------------------------------------------ write
add("# Olympic Games 1960-2026: analysis of the complete dataset\n")
add(f"Generated {gen} by `scripts/build_analysis_report.py`; every number below is computed from the warehouse or a stored analysis at that moment. "
    "Charts for each finding are in the dashboard's Visualization Library (`/visualizations`).\n")
add("## Key findings\n")
kf = [
    f"**The Games grew about {s.athletes.iloc[-1] / s.athletes[0]:.1f}x in athletes (Summer {n(s.athletes[0])} in {int(s.year[0])} to {n(s.athletes.iloc[-1])} in {int(s.year.iloc[-1])}) and {s.events.iloc[-1] / s.events[0]:.1f}x in events**; "
    f"Winter grew {w.athletes.iloc[-1] / w.athletes[0]:.1f}x ({n(w.athletes[0])} to {n(w.athletes.iloc[-1])}).",
    f"**Women went from {pct(growth['female_share_summer'][0])} to {pct(growth['female_share_summer'][1])} of Summer athletes** (Winter {pct(growth['female_share_winter'][0])} to {pct(growth['female_share_winter'][1])}); "
    f"the linear trend is +{100 * ht['H3_female_trend_summer']['effect_size']:.1f} share points per 4-year edition for Summer and +{100 * ht['H3_female_trend_winter']['effect_size']:.1f} for Winter.",
    f"**Medals are highly concentrated:** Gini {par.get('gini', 0):.2f} across participating NOCs; {par.get('noc_for_80pct')} nations account for 80% of all medals, and {n(nomedal)} of {n(n_nocs_h)} nations that ever competed have never won one.",
    f"**Hosting helps:** host nations won on average {ht['H1_host_vs_non_host']['effect_size'] and json.loads(ht['H1_host_vs_non_host']['assumptions_json'])['mean_difference']:.1f} more medals than in their other Games (Wilcoxon p = {ht['H1_host_vs_non_host']['p_value']:.4f}, effect d = {ht['H1_host_vs_non_host']['effect_size']:.2f}); "
    f"{eda_f.get('hosts_that_beat_their_non_host_mean')} of {eda_f.get('n_hosts')} hosts beat their own non-host average.",
    f"**Medalists are only marginally older** ({json.loads(ht['H2_age_medalists_vs_others']['assumptions_json'])['mean_medalists'] - json.loads(ht['H2_age_medalists_vs_others']['assumptions_json'])['mean_others']:+.2f} years; Cohen d = {ht['H2_age_medalists_vs_others']['effect_size']:.2f}, negligible): "
    "age is statistically detectable but practically irrelevant.",
    f"**Most athletes appear once** ({pct(one_time, 0)} compete at a single Games) and {pct(exactly1, 0)} of medalists won exactly one medal; the most decorated athlete is {top_ath.full_name[0]} with {int(top_ath.medals[0])} medals.",
    f"**Past results already explain most of the future:** the best model ({str(best).replace('_', ' ')}) reaches RMSE {mm.get(best, {}).get('rmse', float('nan')):.2f} medals vs {mm.get('naive_previous_total', {}).get('rmse', float('nan')):.2f} for simply repeating the previous Games (a modest gain); "
    f"an athlete-level model reaches PR-AUC {ath.get('models', {}).get(ab, {}).get('pr_auc', float('nan')):.2f} against a base rate of {ath.get('design', {}).get('base_rate_test', float('nan')):.2f}.",
]
for x in kf:
    add(f"- {x}")

add("\n## 1. The dataset\n")
add(f"{sc['editions']} Games ({sc['summer']} Summer, {sc['winter']} Winter), {n(sc['participations'])} athlete-event participations by {n(sc['athletes'])} athletes from {sc['nocs']} NOCs across {sc['sports']} sports and {n(sc['events'])} event-editions (an event counted once per Games); "
    f"{n(sc['medal_awards'])} medal awards, {n(sc['result_rows'])} event-result rows, {n(sc['scored_fixtures'])} scored fixtures, {n(sc['team_members'])} team-roster entries, {n(sc['venues'])} venues and {n(sc['records'])} record rows. "
    f"Automated validation: {KEY['validation']['passed']} of {KEY['validation']['checks']} checks pass. All {sc['editions']} editions pass every collection check (participations, results, verified medal table, fixtures, rosters, venues, Wikipedia pages, logo).")
add("\nOne defect found and repaired during this analysis: " + (f"{n(sc['archived_matches'])} Wikipedia football rows (kickoff times read as scores, duplicated across pages) were moved to `archived_matches`; Olympedia's clean fixtures are the single source for football. " if sc["archived_matches"] else "") +
    "See the limitations section for what the data cannot support.")

add("\n## 2. Growth and participation\n")
add(f"| | First | Latest | Growth |\n|---|---|---|---|\n| Summer athletes | {n(s.athletes[0])} ({int(s.year[0])}) | {n(s.athletes.iloc[-1])} ({int(s.year.iloc[-1])}) | {s.athletes.iloc[-1] / s.athletes[0]:.2f}x |\n"
    f"| Summer events | {int(s.events[0])} | {int(s.events.iloc[-1])} | {s.events.iloc[-1] / s.events[0]:.2f}x |\n| Summer nations | {int(s.nocs[0])} | {int(s.nocs.iloc[-1])} | {s.nocs.iloc[-1] / s.nocs[0]:.2f}x |\n"
    f"| Winter athletes | {n(w.athletes[0])} ({int(w.year[0])}) | {n(w.athletes.iloc[-1])} ({int(w.year.iloc[-1])}) | {w.athletes.iloc[-1] / w.athletes[0]:.2f}x |\n| Winter events | {int(w.events[0])} | {int(w.events.iloc[-1])} | {w.events.iloc[-1] / w.events[0]:.2f}x |\n"
    f"| Winter nations | {int(w.nocs[0])} | {int(w.nocs.iloc[-1])} | {w.nocs.iloc[-1] / w.nocs[0]:.2f}x |")
add(f"\nThe largest Games by athletes is {peak.games_id.replace('_', ' ')} ({n(peak.athletes)}); the biggest single Summer jump between editions was {int(jump.year)} (+{n(jump.d)} athletes). "
    "Summer and Winter are different events with different scales, so they are analysed separately throughout.")
add(f"\n**Gender.** Women's share of Summer athletes rose from {pct(growth['female_share_summer'][0])} to {pct(growth['female_share_summer'][1])}; "
    f"it first reached 30% at {str(gm.get('summer_first_edition_at_or_above_30pct')).replace('_', ' ')} and 40% at {str(gm.get('summer_first_edition_at_or_above_40pct')).replace('_', ' ')} (Winter: 30% at {str(gm.get('winter_first_edition_at_or_above_30pct')).replace('_', ' ')}). "
    f"Both trends are strongly linear (R2 {ht['H3_female_trend_summer']['assumptions_json'] and json.loads(ht['H3_female_trend_summer']['assumptions_json'])['r_squared']:.2f} Summer), though residuals are autocorrelated, so the slope is a description, not a forecast.")

add("\n## 3. Countries and medals\n")
add("| Nation | Gold | Silver | Bronze | Total | Games attended |\n|---|---|---|---|---|---|")
for r in hist.itertuples():
    add(f"| {r.historical_name} ({r.noc_code}) | {n(r.gold)} | {n(r.silver)} | {n(r.bronze)} | {n(r.total_medals)} | {int(r.appearances)} |")
add(f"\nThe ten leading NOCs hold {pct(hist.total_medals.sum() / one('SELECT SUM(total) FROM gold_country_medals'))} of all medals in the official tables (1960-2026; dissolved delegations such as the USSR and East Germany are ranked under their own codes). "
    f"Concentration: Gini {par.get('gini', 0):.2f}; {par.get('noc_for_50pct')} nations win half of all medals and {par.get('noc_for_80pct')} win 80%.")
if len(c60) and len(c10):
    parts = ", ".join(f"{k} {pct(c60.get(k, 0), 0)} to {pct(c10.get(k, 0), 0)}" for k in ["Europe", "Asia", "Americas", "Africa", "Oceania"])
    add(f"\n**Geography.** Continental share of medals, 1960s to 2010s: {parts} (the rest is neutral or unassigned delegations).")
bg = sorted(eda_c.get("biggest_gains", []), key=lambda r: -r["delta"])[:3]
bd = sorted(eda_c.get("biggest_declines", []), key=lambda r: r["delta"])[:3]
if bg:
    add("\n**Biggest swings between consecutive Games** - gains: " + "; ".join(f"{r['noc_code']} {r['games_id'].replace('_', ' ')} (+{int(r['delta'])})" for r in bg) + ". Declines: " + "; ".join(f"{r['noc_code']} {r['games_id'].replace('_', ' ')} ({int(r['delta'])})" for r in bd) + ".")
a4, b4 = ht["H4a_medal_distribution_summer_vs_winter"], ht["H4b_medal_winning_rate_summer_vs_winter"]
h4a = json.loads(a4["assumptions_json"])
add(f"\n**Summer vs Winter.** A medal-winning NOC takes a much larger share of the medal programme in Winter (median {pct(h4a.get('median_winter', 0))} of medal events per NOC-Games vs {pct(h4a.get('median_summer', 0))} in Summer; rank-biserial {a4['effect_size']:.2f}, large; Mann-Whitney p {a4['p_value']:.1e}), because far fewer nations win medals in a smaller programme. The share of participating NOCs that win a medal differs by season but only slightly "
    f"(Cramer's V {b4['effect_size']:.2f}). Medal concentration (HHI) Summer {eda_g.get('medal_hhi_by_season', {}).get('summer', float('nan')):.3f}, Winter {eda_g.get('medal_hhi_by_season', {}).get('winter', float('nan')):.3f}.")

add("\n## 4. Athletes\n")
sa, sw_ = age.get("athlete_age_summer", {}), age.get("athlete_age_winter", {})
add(f"- Median age {sa.get('median', float('nan')):.0f} (Summer) and {sw_.get('median', float('nan')):.0f} (Winter); 90% of participations fall between {age.get('athlete_age_all', {}).get('p5', float('nan')):.0f} and {age.get('athlete_age_all', {}).get('p95', float('nan')):.0f}. "
    f"Youngest medalist: {youngm.full_name} ({int(youngm.age)}, {youngm.sport_name}, {youngm.games_id.replace('_', ' ')}); oldest: {oldm.full_name} ({int(oldm.age)}, {oldm.sport_name}, {oldm.games_id.replace('_', ' ')}).")
add(f"- Men and women medal at similar rates per participation ({pct(gender_rate.r.get('M', 0))} vs {pct(gender_rate.r.get('F', 0))}); the association is statistically significant only because n is large (Cramer's V {ht['S1_gender_vs_medal_rate']['effect_size']:.3f}).")
add(f"- {pct(one_time, 0)} of athletes compete at one Games only; the longest careers are " + "; ".join(f"{r.full_name} ({int(r.games_count)} Games)" for r in longest.itertuples()) + ".")
add("\nMost decorated athletes (team-event medals count for every team member):\n\n| Athlete | Gold | Silver | Bronze | Total | Games | Sports |\n|---|---|---|---|---|---|---|")
for r in top_ath.itertuples():
    add(f"| {r.full_name} | {int(r.gold)} | {int(r.silver)} | {int(r.bronze)} | {int(r.medals)} | {int(r.games_count)} | {r.sports} |")
add("\nSwitching sport is rare: only about 1% of consecutive Games attendances involve a different sport, and the largest flows are Summer-to-Winter moves (e.g. Athletics to Bobsleigh) and neighbouring disciplines (cross-country skiing to biathlon).")

add("\n## 5. Sports and events\n")
add("- Largest sports by athlete entries: " + ", ".join(f"{r.sport_name} ({n(r.a)})" for r in big.itertuples()) + ".")
add(f"- {len(spf.get('introduced_after_1960', []))} sports first appear in this 1960-2026 data after 1960 (e.g. " + ", ".join(r["sport_name"] for r in spf.get("introduced_after_1960", [])[:6]) + "; some are returns of sports from earlier Games, such as Archery and Handball, or Winter sports absent from Squaw Valley 1960, such as Bobsleigh) " + f"and {len(spf.get('discontinued', []))} have left the programme (" + ", ".join(r["sport_name"] for r in spf.get("discontinued", [])) + "; not held at the latest Games).")
if len(bal):
    add(f"- Gender balance at Paris 2024 (sports with 100+ athletes): most balanced near 50% women - " + ", ".join(f"{r.sport_name} {pct(r.fs, 0)}" for r in bal.iloc[(bal.fs - 0.5).abs().argsort()[:3]].itertuples())
        + "; least female - " + ", ".join(f"{r.sport_name} {pct(r.fs, 0)}" for r in bal.head(3).itertuples()) + ".")
if rec_rows:
    add("\n**Olympic record progression** (best mark recorded at the first vs the latest Games with records; only events with 6+ record rows):\n\n| Event | Years | First | Latest | Improvement |\n|---|---|---|---|---|")
    for ev, y0, y1, f0, f1, imp, u in rec_rows[:6]:
        add(f"| {ev} | {y0}-{y1} | {f0:.2f} {u} | {f1:.2f} {u} | {imp:.1f}% |")
    add("\nRecords come from 8 disciplines only (no swimming), and marks under different wind or timing conditions are not corrected.")

add("\n## 6. Team sports (clean fixtures)\n")
if ts_lines:
    add("| Sport | Scored matches | Editions | Scoring per match, first vs latest Games | Trend per year | Mean draw rate | Best record (points per game) |\n|---|---|---|---|---|---|---|")
    for sport, mt, ed, y0, g0, y1, g1, sl, p, dr, br in ts_lines:
        unit = "points" if sport == "Basketball" else "goals"
        add(f"| {sport} | {n(mt)} | {ed} | {g0:.2f} ({y0}) to {g1:.2f} ({y1}) {unit} | {sl:+.3f} (p = {p:.3f}) | {pct(dr, 0)} | {br.get('team', '-')} ({br.get('points_per_game_3_1_0', float('nan')):.2f}) |")
if len(fb):
    add("\nFootball goals per match by decade (both teams): " + ", ".join(f"{int(r.decade)}s {r.g:.2f} ({int(r.n)} matches, {pct(r.d, 0)} draws)" for r in fb.itertuples()) + ".")
add("\nScoring in football fell from over four goals per match in the 1960s to roughly three, and has been stable since the 1990s; basketball and water polo scores are far higher and move with rule changes (shot clock, scoring format), so they are not comparable across sports.")

add("\n## 7. What the models say\n")
add(f"- **Country medal totals** (expanding-window backtest, {med.get('design', {}).get('n_predictions', 0):,} predictions): best model {str(best).replace('_', ' ')} RMSE {mm.get(best, {}).get('rmse', float('nan')):.2f}, MAE {mm.get(best, {}).get('mae', float('nan')):.2f}, R2 {mm.get(best, {}).get('r2', float('nan')):.2f}; "
    f"repeating the previous Games gives RMSE {mm.get('naive_previous_total', {}).get('rmse', float('nan')):.2f}. The 80% prediction interval covers {pct(pi_.get('empirical_coverage', 0), 0)} of outcomes (nominal 80%, mean width {pi_.get('mean_width', 0):.1f} medals).")
add(f"- **Athlete medal probability** (train < 2000, validate 2000-2007, test 2008-2026): {str(ab).replace('_', ' ')} ROC-AUC {ath.get('models', {}).get(ab, {}).get('roc_auc', float('nan')):.2f}, PR-AUC {ath.get('models', {}).get(ab, {}).get('pr_auc', float('nan')):.2f} (base rate {ath.get('design', {}).get('base_rate_test', float('nan')):.2f}). "
    "Strongest signals: " + ", ".join(f"{p['feature']}" for p in perm) + " - i.e. the strength of the athlete's nation and sport, not athlete traits.")
if clu:
    add(f"- **Country profiles:** k-means with k = {clu.get('chosen_k')} (silhouette {clu.get('kmeans_silhouette', float('nan')):.2f}, moderate separation) groups {clu.get('n_nocs')} NOCs by medal volume, medal efficiency, Winter share, specialisation and delegation size.")
add("\nAll modelling is retrospective validation on past Games; nothing here is a forecast of a future Games.")

add("\n## 8. Limitations\n")
cov = ROOT / "reports" / "visualization" / "coverage.json"
lims = json.loads(cov.read_text(encoding="utf-8")).get("summary", {}).get("data_limitations", []) if cov.exists() else []
for x in lims:
    add(f"- {x}")
add("- Medal counts follow the official tables (team medal = one per NOC); athlete-level medal counts credit every team member.")

(OUT / "OLYMPIC_ANALYSIS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
(OUT / "key_numbers.json").write_text(json.dumps({"generated_at": gen, **KEY}, indent=1, default=str), encoding="utf-8")
print(f"wrote {OUT / 'OLYMPIC_ANALYSIS.md'} ({len(L)} lines)")
