"""Section 7 - team-sport charts. Source: olympedia_matches (clean fixtures with numeric scores). Sport-specific statistics are only produced
where the collected fields support them (e.g. period scores are additive for basketball / water polo, cumulative for football / hockey /
rugby sevens, and set scores for volleyball / tennis, so each is handled explicitly)."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy import stats as sps

from .core import Ctx, Unavailable, chart, df, need_rows, payload, series_defs, table_from

S = 7
DEFAULT_SPORT, DEFAULT_GAMES, DEFAULT_EVENT = "Football", "2024_summer", "Football, Men"
ADDITIVE_PERIODS = {"Basketball", "Water Polo"}
CUMULATIVE_PERIODS = {"Football", "Hockey", "Rugby Sevens"}
RES_COLORS = {"Win": "#009F3D", "Draw": "#B0B7C3", "Loss": "#DF0024"}


def _date(s):
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", str(s or ""))
    if not m:
        return pd.NaT
    return pd.to_datetime(f"{m.group(1)} {m.group(2)} {m.group(3)}", format="%d %B %Y", errors="coerce")


def scored(sport: str, games_id: str | None = None, event: str | None = None, ctx: Ctx | None = None) -> pd.DataFrame:
    sql = ("SELECT m.id, m.games_id, g.year, g.season, m.event_name, m.stage, m.match_date, m.location, m.home_team, m.home_noc, m.away_team, m.away_noc, "
           "CAST(m.home_score AS INT) hs, CAST(m.away_score AS INT) a_s, m.period_scores FROM olympedia_matches m JOIN games g USING(games_id) "
           "WHERE m.sport_name=:s AND m.home_score GLOB '[0-9]*' AND m.away_score GLOB '[0-9]*' AND m.home_noc IS NOT NULL AND m.away_noc IS NOT NULL")
    par: dict = {"s": sport}
    if games_id:
        sql += " AND m.games_id=:g"; par["g"] = games_id
    if event:
        sql += " AND m.event_name=:e"; par["e"] = event
    if ctx is not None:
        w, p = ctx.where("g"); sql += w; par.update(p)
    d = df(sql, **par)
    d["date"] = d.match_date.map(_date)
    return d


def team_rows(m: pd.DataFrame) -> pd.DataFrame:
    h = m.assign(team=m.home_team, noc=m.home_noc, gf=m.hs, ga=m.a_s, opp=m.away_team, opp_noc=m.away_noc, home=1)
    a = m.assign(team=m.away_team, noc=m.away_noc, gf=m.a_s, ga=m.hs, opp=m.home_team, opp_noc=m.home_noc, home=0)
    t = pd.concat([h, a], ignore_index=True)
    t["res"] = np.where(t.gf > t.ga, "Win", np.where(t.gf < t.ga, "Loss", "Draw"))
    return t.drop(columns=["home_team", "home_noc", "away_team", "away_noc", "hs", "a_s"])


def _sport(ctx: Ctx) -> str:
    return ctx.sport or DEFAULT_SPORT


def _default_event(sport: str, games_id: str) -> str | None:
    d = df("SELECT event_name, COUNT(*) n FROM olympedia_matches WHERE sport_name=:s AND games_id=:g AND home_score GLOB '[0-9]*' GROUP BY 1 ORDER BY (event_name LIKE '%Men%') DESC, n DESC", s=sport, g=games_id)
    return d.event_name.iloc[0] if len(d) else None


def _scope(ctx: Ctx):
    sport = _sport(ctx)
    gid = ctx.games_id or DEFAULT_GAMES
    ev = ctx.event or (DEFAULT_EVENT if sport == DEFAULT_SPORT and gid == DEFAULT_GAMES else _default_event(sport, gid))
    if not ev:
        raise Unavailable(f"no scored {sport} matches in {gid}")
    return sport, gid, ev


def _final_matches(m: pd.DataFrame) -> pd.DataFrame:
    return m[m.stage.fillna("").str.fullmatch(r"(?:.* – )?Match (1/2|3/4|5/6)")]


def _bracket(m: pd.DataFrame):
    """Final + bronze match, and the semi-finals reconstructed as each medal-match team's previous match."""
    t = team_rows(m)
    fin = m[m.stage.fillna("").str.contains(r"Match 1/2")]
    bro = m[m.stage.fillna("").str.contains(r"Match 3/4")]
    if fin.empty:
        raise Unavailable("no gold-medal match (stage 'Match 1/2') recorded for this event")
    f = fin.sort_values("date").iloc[-1]
    teams_f = [f.home_noc, f.away_noc]
    b = bro.sort_values("date").iloc[-1] if len(bro) else None
    teams_b = [b.home_noc, b.away_noc] if b is not None else []
    prev = {}
    for noc in teams_f + teams_b:
        cut = f.date if noc in teams_f else b.date
        tm = t[(t.noc == noc) & (t.date <= cut) & ~t.id.isin([f.id] + ([b.id] if b is not None else []))].sort_values(["date", "id"])
        prev[noc] = tm.iloc[-1] if len(tm) else None
    return f, b, prev, t


def _match_node(r, label=None):
    return {"label": label, "a": r.home_team, "b": r.away_team, "sa": int(r.hs), "sb": int(r.a_s), "noc_a": r.home_noc, "noc_b": r.away_noc,
            "winner": r.home_team if r.hs > r.a_s else (r.away_team if r.a_s > r.hs else None), "date": None if pd.isna(r.date) else r.date.strftime("%Y-%m-%d")}


@chart("t_bracket", S, "team-sports", "Tournament bracket (medal rounds)", "bracket", "Olympedia matches", "olympedia_matches",
       "Show how the finalists reached the medal matches", ("sport", "games_id", "event"), ("tree",))
def bracket(ctx: Ctx):
    sport, gid, ev = _scope(ctx)
    m = scored(sport, gid, ev)
    need_rows(m, "scored matches")
    f, b, prev, t = _bracket(m)
    ids = {int(r.id) for r in prev.values() if r is not None}
    medal_nocs = {f.home_noc, f.away_noc} | ({b.home_noc, b.away_noc} if b is not None else set())
    sm = []
    for mid in ids:
        r = m[m.id == mid].iloc[0]
        if {r.home_noc, r.away_noc} <= medal_nocs:  # a semi-final is credible only when both of its teams are medal-match teams
            sm.append(r)
    sm.sort(key=lambda r: (r.date, r.id))
    rounds = []
    if len(sm) >= 2:
        rounds.append({"name": "Semi-finals (reconstructed)", "matches": [_match_node(r) for r in sm[:2]]})
    rounds.append({"name": "Final (gold-medal match)", "matches": [_match_node(f, "Gold")]})
    if b is not None:
        rounds.append({"name": "Bronze-medal match", "matches": [_match_node(b, "Bronze")]})
    tab = [{"round": rd["name"], "team A": x["a"], "score A": x["sa"], "score B": x["sb"], "team B": x["b"], "date": x["date"]} for rd in rounds for x in rd["matches"]]
    return payload("t_bracket", "bracket", {"rounds": rounds, "title": f"{ev} - {gid.replace('_', ' ')}"}, ctx=ctx, table=table_from(tab),
                   interpretation=f"{ev}, {gid.replace('_', ' ')}. The final and bronze match come directly from the recorded fixtures; the semi-finals are reconstructed as the last match each medal-match team played before them "
                                  "(the data does not label earlier knockout rounds). Where the reconstruction does not yield two clean semi-finals, only the medal matches are shown.",
                   notes=["Choose sport, Games and event with the filters (events with a recorded 'Match 1/2')."])


@chart("t_knockout_tree", S, "team-sports", "Knockout tree: the finalists' paths", "tree", "Olympedia matches", "olympedia_matches",
       "Trace each finalist back through its preceding matches", ("sport", "games_id", "event"), ("bracket",))
def knockout_tree(ctx: Ctx):
    sport, gid, ev = _scope(ctx)
    m = scored(sport, gid, ev)
    need_rows(m, "scored matches")
    t = team_rows(m)
    fin = m[m.stage.fillna("").str.contains(r"Match 1/2")]
    if fin.empty:
        raise Unavailable("no gold-medal match recorded for this event")
    f = fin.sort_values("date").iloc[-1]

    def node(r, depth, seen):
        res = _match_node(r)
        label = f"{res['a']} {res['sa']}-{res['sb']} {res['b']}"
        n = {"name": label, "meta": res["date"], "winner": res["winner"], "children": []}
        if depth == 0:
            return n
        for noc in (r.home_noc, r.away_noc):
            prev = t[(t.noc == noc) & (t.date < r.date) & ~t.id.isin(seen)].sort_values(["date", "id"])
            if len(prev):
                p = prev.iloc[-1]
                full = m[m.id == p.id].iloc[0]
                n["children"].append(node(full, depth - 1, seen | {int(p.id)}))
        return n
    tree = node(f, 3, {int(f.id)})
    return payload("t_knockout_tree", "tree", {"root": tree, "orientation": "rtl", "note": "Root = gold-medal match; each child = the previous match of one participating team"}, ctx=ctx,
                   table=table_from([{"match": f"{f.home_team} {int(f.hs)}-{int(f.a_s)} {f.away_team}", "date": None if pd.isna(f.date) else f.date.strftime('%Y-%m-%d')}]),
                   interpretation=f"{ev}, {gid.replace('_', ' ')}: starting at the gold-medal match, each branch follows one team back to the match it played immediately before. Because round names are not recorded for most fixtures, "
                                  "the path is derived from dates and may include group-stage matches at its deepest level.")


@chart("t_standings", S, "team-sports", "Tournament standings table", "table", "Olympedia matches", "olympedia_matches",
       "Rank teams by results over one event", ("sport", "games_id", "event"), ())
def standings(ctx: Ctx):
    sport, gid, ev = _scope(ctx)
    m = scored(sport, gid, ev)
    need_rows(m, "scored matches")
    t = team_rows(m)
    g = t.groupby(["noc"]).agg(team=("team", "first"), P=("res", "size"), W=("res", lambda s: int((s == "Win").sum())), D=("res", lambda s: int((s == "Draw").sum())), L=("res", lambda s: int((s == "Loss").sum())),
                               GF=("gf", "sum"), GA=("ga", "sum")).reset_index()
    g["GD"] = g.GF - g.GA
    draws_possible = g.D.sum() > 0
    g["Pts (3-1-0)"] = 3 * g.W + g.D if draws_possible else None
    g = g.sort_values(["W", "GD", "GF"], ascending=False).reset_index(drop=True)
    g.insert(0, "Rank", range(1, len(g) + 1))
    cols = ["Rank", "team", "noc", "P", "W", "D", "L", "GF", "GA", "GD"] + (["Pts (3-1-0)"] if draws_possible else [])
    rows = g[cols].rename(columns={"team": "Team", "noc": "NOC"}).to_dict("records")
    return payload("t_standings", "table", {"columns": [{"key": c, "label": c} for c in [("Team" if c == "team" else "NOC" if c == "noc" else c) for c in cols]], "rows": rows}, ctx=ctx, drill={"type": "country", "key": "NOC"},
                   interpretation=f"{ev}, {gid.replace('_', ' ')}: all recorded matches ({len(m)}), ranked by wins, then goal difference, then goals scored. Group labels are not recorded, so this is one table for the whole tournament, not the official group standings; "
                                  "it does not reproduce the official final ranking (knockout elimination order is not used).")


@chart("t_match_timeline", S, "team-sports", "Match result timeline by team", "timeline", "Olympedia matches", "olympedia_matches",
       "Show each team's results across the days of the tournament", ("sport", "games_id", "event"), ("table",))
def match_timeline(ctx: Ctx):
    sport, gid, ev = _scope(ctx)
    m = scored(sport, gid, ev)
    need_rows(m, "scored matches")
    t = team_rows(m).dropna(subset=["date"])
    need_rows(t, "dated matches")
    d0 = t.date.min()
    t["day"] = (t.date - d0).dt.days
    rows = [{"lane": f"{r.team} ({r.noc})", "start": int(r.day), "end": int(r.day) + 0.9, "label": f"{r.date:%d %b}: {r.team} {int(r.gf)}-{int(r.ga)} {r.opp} ({r.res})", "color": RES_COLORS[r.res], "group": r.res} for r in t.itertuples()]
    order = t.groupby(["team", "noc"]).day.min().reset_index().sort_values("day")
    wins = t.assign(w=(t.res == "Win")).groupby("noc").w.sum()
    lanes = [f"{r.team} ({r.noc})" for r in order.assign(w=order.noc.map(wins)).sort_values("w", ascending=False).itertuples()]
    return payload("t_match_timeline", "timeline", {"rows": rows, "laneOrder": lanes, "xLabel": f"Day of the tournament (day 0 = {d0:%d %b %Y})", "unit": "day", "legend": [{"name": k, "color": v} for k, v in RES_COLORS.items()]},
                   ctx=ctx, table=table_from([{"team": r["lane"], "day": r["start"], "match": r["label"]} for r in rows]),
                   interpretation=f"{ev}, {gid.replace('_', ' ')}: one row per team (ordered by wins), one block per match coloured by result from that team's view. Long runs of green show a team's path; the last block is its final match.")


@chart("t_score_progression", S, "team-sports", "Score progression within a match", "xy", "Olympedia matches", "olympedia_matches",
       "Show how the score built up period by period in one match", ("sport", "games_id", "event"), ("bar",))
def score_progression(ctx: Ctx):
    sport = ctx.sport or "Basketball"
    if sport not in ADDITIVE_PERIODS | CUMULATIVE_PERIODS:
        raise Unavailable(f"period scores of {sport} are set/game scores, not cumulative points, so score progression is not defined")
    gid = ctx.games_id or DEFAULT_GAMES
    ev = ctx.event or _default_event(sport, gid)
    m = scored(sport, gid, ev)
    m = m[m.period_scores.notna() & (m.period_scores != "")]
    need_rows(m, "matches with period scores")
    fin = m[m.stage.fillna("").str.contains("Match 1/2")]
    r = (fin if len(fin) else m).sort_values("date").iloc[-1]
    per = [(int(i), int(a), int(b)) for i, a, b in re.findall(r"P(\d+)\s+(\d+)-(\d+)", r.period_scores)]
    if sport in ADDITIVE_PERIODS:
        ca, cb = np.cumsum([a for _, a, _ in per]), np.cumsum([b for _, _, b in per])
    else:
        ca, cb = np.array([a for _, a, _ in per]), np.array([b for _, _, b in per])
    rows = [{"period": 0, r.home_team: 0, r.away_team: 0}] + [{"period": i, r.home_team: int(x), r.away_team: int(y)} for (i, _, _), x, y in zip(per, ca, cb)]
    note = "per-period points are summed" if sport in ADDITIVE_PERIODS else "recorded period scores are already cumulative"
    return payload("t_score_progression", "xy", {"x": "period", "xType": "number", "rows": rows, "series": [{"key": r.home_team, "color": "#0085C7"}, {"key": r.away_team, "color": "#DF0024"}], "variant": "step", "dot": True,
                   "xLabel": "End of period", "yLabel": f"Cumulative score ({'points' if sport == 'Basketball' else 'goals'})"}, axes={"x": "Period", "y": "Score"}, ctx=ctx,
                   interpretation=f"{r.home_team} {int(r.hs)}-{int(r.a_s)} {r.away_team} ({ev}, {gid.replace('_', ' ')}, {r.stage}); {note}. The final score is {'higher than the last period if extra time was played' if sport in CUMULATIVE_PERIODS else 'the sum of the periods'}.",
                   notes=["Available for basketball, water polo (additive periods) and football, hockey, rugby sevens (cumulative). Volleyball and tennis record sets, which have no running score."])


@chart("t_scoring_by_period", S, "team-sports", "Scoring by period across Games", "xy", "Olympedia matches", "olympedia_matches",
       "Show in which period most scoring happens and how that changed", ("sport",), ("line",))
def scoring_by_period(ctx: Ctx):
    sport = ctx.sport if ctx.sport in ADDITIVE_PERIODS | CUMULATIVE_PERIODS else "Basketball"
    m = scored(sport, None, None, ctx)
    m = m[m.period_scores.notna() & (m.period_scores != "")]
    need_rows(m, "matches with period scores")
    recs = []
    for r in m.itertuples():
        per = [(int(i), int(a), int(b)) for i, a, b in re.findall(r"P(\d+)\s+(\d+)-(\d+)", r.period_scores)]
        prev = 0
        for i, a, b in per:
            tot = a + b
            recs.append((r.year, f"Period {i}", tot if sport in ADDITIVE_PERIODS else tot - prev))
            prev = tot
    d = pd.DataFrame(recs, columns=["year", "period", "points"])
    g = d.groupby(["year", "period"]).points.mean().reset_index()
    pv = g.pivot(index="year", columns="period", values="points").reset_index()
    unit = "points" if sport == "Basketball" else "goals"
    return payload("t_scoring_by_period", "xy", {"x": "year", "xType": "number", "rows": pv.round(2).to_dict("records"), "series": series_defs([c for c in pv.columns if c != "year"]), "variant": "line", "dot": True,
                   "xLabel": "Games year", "yLabel": f"Mean total {unit} (both teams) per period per match"}, axes={"x": "Games year", "y": f"Mean {unit} per period"}, ctx=ctx,
                   interpretation=f"{sport}: mean combined {unit} of both teams in each period, per Games. " + ("Period scores here are additive. " if sport in ADDITIVE_PERIODS else "Recorded period scores are cumulative, so each period's value is the increase over the previous one. ") +
                                  "Extra-time periods are included where recorded, so late periods have few matches.")


@chart("t_wdl", S, "team-sports", "Win / draw / loss distribution", "xy", "Olympedia matches", "olympedia_matches",
       "Compare teams' results profile over all Games in the window", ("sport", "season", "year_range", "top"), ("grouped",))
def wdl(ctx: Ctx):
    sport = _sport(ctx)
    m = scored(sport, None, None, ctx)
    need_rows(m, "scored matches")
    t = team_rows(m)
    g = t.groupby("noc").agg(team=("team", "first"), P=("res", "size"), Win=("res", lambda s: int((s == "Win").sum())), Draw=("res", lambda s: int((s == "Draw").sum())), Loss=("res", lambda s: int((s == "Loss").sum()))).reset_index()
    g = g.sort_values("P", ascending=False).head(ctx.top or 14)
    g = g.sort_values("Win", ascending=False)
    rows = [{"name": r.noc, "full": r.team, "Win": int(r.Win), "Draw": int(r.Draw), "Loss": int(r.Loss)} for r in g.itertuples()]
    keys = ["Win", "Draw", "Loss"] if g.Draw.sum() else ["Win", "Loss"]
    return payload("t_wdl", "xy", {"x": "name", "xType": "category", "rows": rows, "series": series_defs(keys, colors=RES_COLORS), "variant": "stacked", "xLabel": "NOC (the 14 with most matches)", "yLabel": "Matches", "pickKey": "name"},
                   axes={"x": "NOC", "y": "Matches"}, ctx=ctx, drill={"type": "country", "key": "name"},
                   interpretation=f"{sport}: results of the teams with the most recorded matches in the window ({len(m):,} matches). Men's and women's teams of one NOC are pooled. Draw bars only appear for sports where draws occur. Use the percent view to compare win rates.")


@chart("t_goal_dist", S, "team-sports", "Distribution of goals per team per match", "xy", "Olympedia matches", "olympedia_matches",
       "Compare the scoring distribution with a Poisson model", ("sport", "season", "year_range"), ("area",))
def goal_dist(ctx: Ctx):
    sport = _sport(ctx)
    m = scored(sport, None, None, ctx)
    need_rows(m, "scored matches")
    g = pd.concat([m.hs, m.a_s])
    if g.max() > 25:
        cap = int(g.quantile(.99))
        gg = g.clip(upper=cap)
        labs = [str(i) for i in range(cap)] + [f"{cap}+"]
        obs = [int((gg == i).sum()) for i in range(cap + 1)]
        mean = float(g.mean())
        pois = [float(sps.poisson.pmf(i, mean) * len(g)) if i < cap else float(sps.poisson.sf(cap - 1, mean) * len(g)) for i in range(cap + 1)]
        note = "Score counts are large (points), so a Poisson comparison is shown only as a reference."
    else:
        mx = int(g.max())
        labs = [str(i) for i in range(mx + 1)]
        obs = [int((g == i).sum()) for i in range(mx + 1)]
        mean = float(g.mean())
        pois = [float(sps.poisson.pmf(i, mean) * len(g)) for i in range(mx + 1)]
        note = "Poisson reference with the same mean."
    rows = [{"goals": labs[i], "Observed team scores": obs[i], "Poisson expectation": round(pois[i], 1)} for i in range(len(labs))]
    var = float(g.var())
    return payload("t_goal_dist", "xy", {"x": "goals", "xType": "category", "rows": rows, "series": [{"key": "Observed team scores", "color": "#0085C7"}, {"key": "Poisson expectation", "color": "#DF0024", "type": "line"}], "variant": "bar",
                   "xLabel": "Score of one team in one match", "yLabel": "Team-matches"}, axes={"x": "Score", "y": "Team-matches"}, ctx=ctx,
                   interpretation=f"{sport}: {len(g):,} team scores from {len(m):,} matches; mean {mean:.2f}, variance {var:.2f} (variance/mean = {var / mean:.2f}; 1 would be exactly Poisson). {note} Scores are in the sport's own units (goals or points).")


RADAR_T = ["Win rate", "Scored per match", "Conceded per match (lower is better)", "Points per game (3-1-0)", "Matches played"]


@chart("t_team_radar", S, "team-sports", "Team comparison radar", "radar", "Olympedia matches", "olympedia_matches",
       "Compare teams on several performance dimensions", ("sport", "nocs", "season", "year_range"), ("table",))
def team_radar(ctx: Ctx):
    sport = _sport(ctx)
    m = scored(sport, None, None, ctx)
    need_rows(m, "scored matches")
    t = team_rows(m)
    g = t.groupby("noc").agg(team=("team", "first"), P=("res", "size"), W=("res", lambda s: int((s == "Win").sum())), D=("res", lambda s: int((s == "Draw").sum())), gf=("gf", "mean"), ga=("ga", "mean")).reset_index()
    g = g[g.P >= 10]
    sel = ctx.nocs or g.sort_values("W", ascending=False).head(4).noc.tolist()
    g = g[g.noc.isin(sel)]
    need_rows(g, "teams with at least 10 matches")
    g["win"] = g.W / g.P; g["ppg"] = (3 * g.W + g.D) / g.P
    cols = {"win": RADAR_T[0], "gf": RADAR_T[1], "ga": RADAR_T[2], "ppg": RADAR_T[3], "P": RADAR_T[4]}
    series, table = [], []
    for r in g.itertuples():
        series.append({"name": f"{r.team} ({r.noc})", "values": {lab: float(getattr(r, k)) / float(g[k].max()) * 100 if g[k].max() else 0 for k, lab in cols.items()}})
        table.append({"team": f"{r.team} ({r.noc})", **{lab: round(float(getattr(r, k)), 3) for k, lab in cols.items()}})
    return payload("t_team_radar", "radar", {"axes": list(cols.values()), "series": series, "max": 100}, ctx=ctx, table=table_from(table),
                   interpretation=f"{sport}: teams with at least 10 recorded matches in the window; default = the 4 with most wins. Each axis is scaled to 100 for the largest value among the teams shown (raw values in the table). "
                                  "On the 'conceded' axis a larger value is worse, unlike the others.")


@chart("t_h2h", S, "team-sports", "Head-to-head record", "xy", "Olympedia matches", "olympedia_matches",
       "Compare two nations' direct results across the Games", ("sport", "a", "b"), ("table",))
def h2h(ctx: Ctx):
    sport = _sport(ctx)
    m = scored(sport, None, None, ctx)
    need_rows(m, "scored matches")
    if not (ctx.a and ctx.b):
        pairs = m.assign(k=m.apply(lambda r: tuple(sorted([r.home_noc, r.away_noc])), axis=1)).k.value_counts()
        a, b = pairs.index[0]
    else:
        a, b = ctx.a, ctx.b
    x = m[((m.home_noc == a) & (m.away_noc == b)) | ((m.home_noc == b) & (m.away_noc == a))].copy()
    need_rows(x, f"matches between {a} and {b}")
    x["ga"] = np.where(x.home_noc == a, x.hs, x.a_s); x["gb"] = np.where(x.home_noc == a, x.a_s, x.hs)
    wa, wb, dr = int((x.ga > x.gb).sum()), int((x.gb > x.ga).sum()), int((x.ga == x.gb).sum())
    rows = [{"name": "Wins", a: wa, b: wb}] + ([{"name": "Draws", a: dr, b: dr}] if dr else [])
    tab = [{"games": r.games_id.replace("_", " "), "event": r.event_name, "stage": r.stage, f"{a} score": int(r.ga), f"{b} score": int(r.gb)} for r in x.sort_values("date").itertuples()]
    return payload("t_h2h", "xy", {"x": "name", "xType": "category", "rows": rows, "series": [{"key": a, "color": "#0085C7"}, {"key": b, "color": "#DF0024"}], "variant": "grouped", "xLabel": None, "yLabel": "Count"}, axes={"x": "Measure", "y": "Count"},
                   ctx=ctx, table=table_from(tab), interpretation=f"{sport}: {len(x)} recorded matches between {a} and {b} at the Games: {a} won {wa}, {b} won {wb}, {dr} drawn. Only Olympic meetings are counted, not their full history. "
                                                                  "Pick the two nations with the a and b filters (NOC codes); the default is the most frequent pairing. Total goals or points scored ("+f"{a} {int(x.ga.sum())}, {b} {int(x.gb.sum())}) are listed in the data table, not on this count axis.")


@chart("t_score_heatmap", S, "team-sports", "Scoreline frequency heatmap", "heatmap", "Olympedia matches", "olympedia_matches",
       "Show which final scores occur most often", ("sport", "season", "year_range"), ())
def score_heatmap(ctx: Ctx):
    sport = _sport(ctx)
    m = scored(sport, None, None, ctx)
    need_rows(m, "scored matches")
    hi, lo = np.maximum(m.hs, m.a_s), np.minimum(m.hs, m.a_s)
    cap = 8 if hi.quantile(.99) <= 12 else int(hi.quantile(.99))
    if cap > 40:
        raise Unavailable(f"{sport} scores span too many values for a scoreline heatmap")
    c = pd.DataFrame({"hi": hi.clip(upper=cap), "lo": lo.clip(upper=cap)}).groupby(["hi", "lo"]).size().reset_index(name="n")
    lab = lambda v: f"{cap}+" if v == cap and (hi >= cap).any() else str(v)
    rows = [{"r": lab(int(r.lo)), "c": lab(int(r.hi)), "v": int(r.n), "label": f"{lab(int(r.hi))}-{lab(int(r.lo))}: {int(r.n)} matches"} for r in c.itertuples() if r.hi >= r.lo]
    order = [lab(i) for i in range(cap + 1)]
    return payload("t_score_heatmap", "heatmap", {"rows": rows, "rowOrder": order[::-1], "colOrder": order, "scale": "seq", "vLabel": "Matches", "format": "int", "cell": "number", "xTitle": "Winner's score (or higher score in a draw)", "yTitle": "Loser's score"},
                   axes={"x": "Higher score", "y": "Lower score"}, ctx=ctx, table=table_from([{"higher score": r["c"], "lower score": r["r"], "matches": r["v"]} for r in rows]),
                   interpretation=f"{sport}: {len(m):,} matches. Cells give the number of matches ending with that scoreline, written as higher score vs lower score so the pitch/court side (home or away, which is arbitrary at a neutral-venue tournament) does not matter. "
                                  "The diagonal holds draws (score equal).")


@chart("t_team_progression", S, "team-sports", "Team performance progression", "xy", "Olympedia matches", "olympedia_matches",
       "Track one nation's results across successive Games", ("sport", "noc"), ("bar",))
def team_progression(ctx: Ctx):
    sport = _sport(ctx)
    m = scored(sport, None, None, ctx)
    need_rows(m, "scored matches")
    t = team_rows(m)
    noc = ctx.noc or t.groupby("noc").games_id.nunique().sort_values(ascending=False).index[0]
    x = t[t.noc == noc]
    need_rows(x, f"matches of {noc}")
    g = x.groupby("year").agg(P=("res", "size"), W=("res", lambda s: int((s == "Win").sum())), D=("res", lambda s: int((s == "Draw").sum())), gf=("gf", "sum"), ga=("ga", "sum")).reset_index()
    g["Win rate"] = (g.W / g.P).round(3)
    g["Goal difference per match"] = ((g.gf - g.ga) / g.P).round(2)
    rows = g[["year", "Win rate", "Goal difference per match"]].to_dict("records")
    return payload("t_team_progression", "xy", {"x": "year", "xType": "number", "rows": rows, "series": [{"key": "Win rate", "color": "#009F3D", "axis": "left"}, {"key": "Goal difference per match", "color": "#0085C7", "axis": "right"}],
                   "variant": "line", "dot": True, "xLabel": "Games year", "yLabel": "Win rate (0-1)", "yLabelRight": "Goal/point difference per match"}, axes={"x": "Games year", "y": "Win rate / difference"}, ctx=ctx,
                   interpretation=f"{sport}, {noc}: win rate (left axis, 0-1) and scoring margin per match (right axis, the sport's own units) at each Games the nation played. Two axes are used because the measures have different units; "
                                  "men's and women's teams are pooled. Choose the nation with the noc filter.")


@chart("t_journey", S, "team-sports", "Tournament journey of one team", "xy", "Olympedia matches", "olympedia_matches",
       "Follow one team's match-by-match margin and cumulative goal difference in a tournament", ("sport", "games_id", "event", "noc"), ("line",))
def journey(ctx: Ctx):
    sport, gid, ev = _scope(ctx)
    m = scored(sport, gid, ev)
    need_rows(m, "scored matches")
    t = team_rows(m).sort_values(["date", "id"])
    fin = m[m.stage.fillna("").str.contains("Match 1/2")]
    noc = ctx.noc or (fin.sort_values("date").iloc[-1].pipe(lambda r: r.home_noc if r.hs > r.a_s else r.away_noc) if len(fin) else t.noc.iloc[0])
    x = t[t.noc == noc].reset_index(drop=True)
    need_rows(x, f"matches of {noc}")
    x["margin"] = x.gf - x.ga
    x["Cumulative difference"] = x.margin.cumsum()
    rows = [{"match": f"{i + 1}. v {r.opp} {int(r.gf)}-{int(r.ga)} ({r.res[0]})", "Margin in the match": int(r.margin), "Cumulative difference": int(r["Cumulative difference"])} for i, r in x.iterrows()]
    return payload("t_journey", "xy", {"x": "match", "xType": "category", "rows": rows, "series": [{"key": "Margin in the match", "color": "#9AA3AF", "type": "bar"}, {"key": "Cumulative difference", "color": "#DF0024", "type": "line"}],
                   "variant": "composed", "xLabel": "Match in tournament order", "yLabel": "Goal / point difference", "refs": [{"y": 0, "label": ""}]}, axes={"x": "Match", "y": "Difference"}, ctx=ctx, table=table_from(rows),
                   interpretation=f"{noc} in {ev}, {gid.replace('_', ' ')}: bars are each match's margin (positive = win), the line the running total. Default team = the gold-medal match winner; pick another with the noc filter. W/D/L letters in the labels are from the team's own view.")
