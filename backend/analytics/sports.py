"""PHASE 6 - sport-specific analytics. Each sport uses only the fields that exist for it; scoring systems are never forced to match."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats

from .store import save

TEAM = ["Football", "Basketball", "Ice Hockey", "Handball", "Volleyball", "Water Polo", "Hockey", "Baseball", "Softball", "Rugby Sevens", "Beach Volleyball", "Curling"]


def parse_perf(txt: str):
    """'1:07.27' -> 67.27 s | '9.58' -> 9.58 | '8.90 m' -> 8.90 m | '2,616' -> 2616. Returns (value, kind). kind in s / number."""
    if not isinstance(txt, str) or not txt:
        return None, None
    s = re.sub(r"\(.*?\)", "", txt).replace(",", "").strip()
    s = re.sub(r"\s*(WR|OR|AR|NR|PB|SB|DQ)\b.*$", "", s).strip()
    if re.fullmatch(r"\d+:\d+(:\d+)?(\.\d+)?", s):
        t = 0.0
        for p in s.split(":"):
            t = t * 60 + float(p)
        return t, "s"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:\s*(?:m|cm|pts?|points?|kg))?", s)
    return (float(m.group(1)), "number") if m else (None, None)


def _prog(df: pd.DataFrame) -> dict:
    """df: year, medal, value -> progression summary for one event."""
    g = df[df.medal == "Gold"].groupby("year").value.first().sort_index()
    if len(g) < 5:
        return {}
    x = g.index.values.astype(float)
    lr = stats.linregress(x, g.values)
    return {"years": g.index.tolist(), "gold": g.values.tolist(), "silver": df[df.medal == "Silver"].groupby("year").value.first().reindex(g.index).tolist(),
            "bronze": df[df.medal == "Bronze"].groupby("year").value.first().reindex(g.index).tolist(), "slope_per_year": float(lr.slope), "slope_p": float(lr.pvalue), "r2": float(lr.rvalue ** 2),
            "first": float(g.iloc[0]), "last": float(g.iloc[-1]), "change_pct_first_to_last": float((g.iloc[-1] / g.iloc[0] - 1) * 100), "editions": int(len(g))}


FIELD = re.compile(r"jump|throw|put|vault|decathlon|heptathlon|pentathlon|points|all-around|score", re.I)


def lower_is_better(sport: str, event: str, kind: str) -> bool:
    """Times are better when lower. Olympedia stores track/swimming times as bare numbers, so the event type decides."""
    if kind == "s":
        return True
    if sport in ("Swimming", "Speed Skating", "Rowing", "Canoe Sprint", "Cycling Track"):
        return not FIELD.search(event)
    if sport == "Athletics":
        return not FIELD.search(event)
    return False


def individual_progression(con, sport: str, key: str, title: str, min_editions: int = 6):
    d = pd.read_sql("SELECT p.games_id, g.year, p.event_name, p.medal, p.result_text, p.noc, p.competitor FROM olympedia_podium_results p JOIN games g USING(games_id) "
                    "WHERE p.sport_name=? AND g.year BETWEEN 1960 AND 2026", con, params=(sport,))
    if d.empty:
        save(con, "sports", key, title, {"status": "no podium result strings for this sport in the cached Olympedia event pages"}); return
    pv = d.result_text.map(parse_perf)
    d["value"], d["kind"] = [v[0] for v in pv], [v[1] for v in pv]
    ok = d[d.value.notna() & (d.value > 0)]
    events = {}
    for ev, g in ok.groupby("event_name"):
        if g.year.nunique() >= min_editions:
            pr = _prog(g)
            if pr:
                lib = lower_is_better(sport, ev, "s" if (g.kind == "s").all() else "number")
                pr["lower_is_better"] = lib
                pr["unit"] = "seconds" if lib else "metres / points (see event)"
                events[ev] = pr
    med = pd.read_sql("SELECT a.noc_code, a.medal_type, COUNT(*) n FROM silver_medal_awards a WHERE LOWER(a.sport_name)=LOWER(?) GROUP BY 1,2", con, params=(sport,))
    ct = med.pivot_table(index="noc_code", columns="medal_type", values="n", aggfunc="sum", fill_value=0)
    for c in ("Gold", "Silver", "Bronze"):
        if c not in ct:
            ct[c] = 0
    ct["Total"] = ct[["Gold", "Silver", "Bronze"]].sum(axis=1)
    ev_med = pd.read_sql("SELECT a.event_name, a.medal_type, COUNT(*) n FROM silver_medal_awards a WHERE LOWER(a.sport_name)=LOWER(?) GROUP BY 1,2", con, params=(sport,))
    top_ath = pd.read_sql("SELECT a.full_name, a.gender, c.gold, c.silver, c.bronze, c.medals, c.games_count, c.nocs FROM gold_athlete_career c JOIN silver_athletes a USING(athlete_id) "
                          "WHERE c.sports LIKE ? ORDER BY c.medals DESC, c.gold DESC LIMIT 15", con, params=(f"%{sport}%",))
    payload = {"sport": sport, "podium_rows": int(len(d)), "podium_rows_with_numeric_result": int(len(ok)), "events_with_progression": len(events), "event_progression": events,
               "country_medals": ct.sort_values(["Gold", "Total"], ascending=False).head(20).reset_index(), "event_medal_distribution_rows": int(len(ev_med)),
               "top_athletes": top_ath, "coverage_note": f"{len(ok)} of {len(d)} podium rows have a parseable numeric result; progression needs >= {min_editions} editions of the same event."}
    # gender comparison of matching events (e.g. 100 m: Men vs Women gold times)
    pairs = {}
    for ev, pr in events.items():
        if ev.endswith(", Women"):
            m = ev.replace(", Women", ", Men")
            if m in events and pr["lower_is_better"]:
                yrs = sorted(set(pr["years"]) & set(events[m]["years"]))
                if len(yrs) >= 4:
                    w = dict(zip(pr["years"], pr["gold"])); mm = dict(zip(events[m]["years"], events[m]["gold"]))
                    pairs[ev.replace(", Women", "")] = {"years": yrs, "women_over_men_time_ratio": [w[y] / mm[y] for y in yrs]}
    if pairs:
        payload["gender_gap_time_ratio"] = pairs
    save(con, "sports", key, title, payload, f"How have results, medals and countries evolved in {sport}?")


def team_sport(con, sport: str):
    ms = pd.read_sql("SELECT m.games_id, g.year, m.stage, m.home_team, m.home_noc, m.away_team, m.away_noc, CAST(m.home_score AS INT) hs, CAST(m.away_score AS INT) a_s, m.period_scores "
                     "FROM olympedia_matches m JOIN games g USING(games_id) WHERE m.sport_name=? AND m.home_score GLOB '[0-9]*' AND m.away_score GLOB '[0-9]*'", con, params=(sport,))
    if ms.empty:
        save(con, "sports", f"team_{sport.lower().replace(' ', '_')}", f"{sport} (team)", {"status": "no scored matches in the warehouse"}); return
    ms["goals"] = ms.hs + ms.a_s
    ms["margin"] = (ms.hs - ms.a_s).abs()
    trend = ms.groupby("year").agg(matches=("goals", "size"), goals_per_match=("goals", "mean"), mean_margin=("margin", "mean"), draw_rate=("margin", lambda s: float((s == 0).mean()))).reset_index()
    lr = stats.linregress(trend.year, trend.goals_per_match) if len(trend) > 3 else None
    ts = pd.read_sql("SELECT team, noc, SUM(played) played, SUM(won) won, SUM(drawn) drawn, SUM(lost) lost, SUM(goals_for) gf, SUM(goals_against) ga, SUM(goal_diff) gd, COUNT(DISTINCT games_id) editions "
                     "FROM gold_team_sports WHERE sport_name=? GROUP BY team, noc HAVING SUM(played)>=10", con, params=(sport,))
    ts["win_pct"] = (ts.won / ts.played).round(3)
    ts["points_per_game_3_1_0"] = ((3 * ts.won + ts.drawn) / ts.played).round(3)
    ko = ms[ms.stage.fillna("").str.contains("Final|Semi|Quarter|Bronze|Gold", case=False)]
    kos = pd.concat([ko.assign(team=ko.home_team, noc=ko.home_noc, w=(ko.hs > ko.a_s)), ko.assign(team=ko.away_team, noc=ko.away_noc, w=(ko.a_s > ko.hs))])
    kn = kos.groupby(["team", "noc"]).agg(knockout_matches=("w", "size"), knockout_wins=("w", "sum")).reset_index().sort_values(["knockout_wins", "knockout_matches"], ascending=False).head(15)
    med = pd.read_sql("SELECT a.noc_code, a.medal_type, g.year FROM silver_medal_awards a JOIN games g USING(games_id) WHERE LOWER(a.sport_name)=LOWER(?)", con, params=(sport,))
    ct = med.pivot_table(index="noc_code", columns="medal_type", values="year", aggfunc="count", fill_value=0).reset_index() if not med.empty else pd.DataFrame()
    payload = {"sport": sport, "matches_with_scores": int(len(ms)), "editions": int(ms.year.nunique()), "scoring_trend_by_edition": trend,
               "scoring_trend_slope_per_year": None if lr is None else {"slope": float(lr.slope), "p": float(lr.pvalue), "r2": float(lr.rvalue ** 2)},
               "team_records": ts.sort_values("points_per_game_3_1_0", ascending=False).head(25), "knockout_performance": kn, "medal_history": ct,
               "note": "Scores are sport-specific (goals, points, ...). Draw rate is only meaningful where draws are possible."}
    # period scores (basketball quarters/halves, etc.)
    ps = ms.dropna(subset=["period_scores"])
    if len(ps):
        rows = []
        cumulative = sport in ("Football", "Hockey", "Rugby Sevens")  # their recorded P-scores are running totals (last period = full time); other sports record per-period points
        for yr, s in zip(ps.year, ps.period_scores):
            prev = 0
            for pm in re.finditer(r"P(\d+)\s+(\d+)-(\d+)", s):
                tot = int(pm.group(2)) + int(pm.group(3))
                rows.append((yr, int(pm.group(1)), tot - prev if cumulative else tot))
                prev = tot
        if rows:
            pp = pd.DataFrame(rows, columns=["year", "period", "total_points"])
            payload["period_scoring"] = pp.groupby(["year", "period"]).total_points.mean().round(2).reset_index()
    save(con, "sports", f"team_{sport.lower().replace(' ', '_')}", f"{sport} - team analytics", payload, f"How have {sport} results, scoring and teams evolved?")


def records_progression(con):
    r = pd.read_sql("SELECT games_id, noc_code, record_type, record_value, record_date, description FROM records WHERE games_id IS NOT NULL", con)
    r["event"] = r.description.str.split(" | ").str[0]
    r["value"] = [parse_perf(v)[0] for v in r.record_value]
    r["year"] = r.games_id.str[:4].astype(int)
    out = {}
    for ev, g in r.dropna(subset=["value"]).groupby("event"):
        g = g.sort_values("year")
        if len(g) >= 4:
            out[ev] = {"years": g.year.tolist(), "values": g.value.tolist(), "record_types": g.record_type.tolist(), "noc": g.noc_code.tolist()}
    save(con, "sports", "records_progression", "Olympic and world record progression",
         {"events": dict(list(out.items())[:120]), "n_events": len(out), "note": "From Olympedia records pages (8 disciplines: archery, athletics, canoe sprint, modern pentathlon, rowing, short track, ski jumping, speed skating). Swimming records are not in the source."})


def run(con):
    individual_progression(con, "Athletics", "athletics", "Athletics")
    individual_progression(con, "Swimming", "swimming", "Swimming")
    individual_progression(con, "Artistic Gymnastics", "gymnastics", "Gymnastics (artistic)", min_editions=5)
    individual_progression(con, "Speed Skating", "speed_skating", "Speed skating")
    individual_progression(con, "Rowing", "rowing", "Rowing")
    for s in TEAM:
        team_sport(con, s)
    records_progression(con)
    return "ok"
