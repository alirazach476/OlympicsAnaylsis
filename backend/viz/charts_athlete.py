"""Section 3 - athlete charts (silver_participations + gold_athlete_career)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .core import MEDAL_COLORS, Ctx, Unavailable, age_rows, box_stats, chart, df, kde, need_rows, payload, series_defs, table_from, wide

S = 3
GENDER_COLORS = {"Men": "#0085C7", "Women": "#DF0024"}


def part_where(ctx: Ctx, alias: str = "p") -> tuple[str, dict]:
    w, par = ctx.where(alias)
    if ctx.noc:
        w += f" AND {alias}.noc_code=:_noc"; par["_noc"] = ctx.noc
    if ctx.sport:
        w += f" AND {alias}.sport_name=:_sport"; par["_sport"] = ctx.sport
    return w, par


def _scope(ctx: Ctx) -> str:
    bits = [ctx.season.capitalize() if ctx.season else "Summer + Winter", f"{ctx.year_from or 1960}-{ctx.year_to or 2026}"]
    if ctx.sport:
        bits.append(ctx.sport)
    if ctx.noc:
        bits.append(ctx.noc)
    return ", ".join(bits)


def ages(ctx: Ctx, extra_cols: str = "") -> pd.DataFrame:
    w, par = part_where(ctx)
    return need_rows(age_rows(w, par), "athletes with a recorded age")


@chart("a_age_hist", S, "athletes", "Athlete age histogram", "xy", "Silver participations", "silver_participations",
       "Show the age distribution of Olympic participants", ("season", "year_range", "sport", "noc"), ("area",))
def age_hist(ctx: Ctx):
    d = ages(ctx)
    d = d[d.gender.isin(["M", "F"])]
    pv = d.groupby(["age", "gender"]).size().unstack(fill_value=0).reindex(range(int(d.age.min()), int(d.age.max()) + 1), fill_value=0)
    rows = [{"age": int(a), "Men": int(r.get("M", 0)), "Women": int(r.get("F", 0))} for a, r in pv.iterrows()]
    return payload("a_age_hist", "xy", {"x": "age", "xType": "number", "rows": rows, "series": series_defs(["Men", "Women"], colors=GENDER_COLORS), "variant": "stacked", "barGap": 0,
                   "xLabel": "Age at competition (years)", "yLabel": "Participations"}, axes={"x": "Age (years)", "y": "Participations"}, ctx=ctx,
                   interpretation=f"{len(d):,} participations with a recorded age ({_scope(ctx)}). Median age {d.age.median():.0f}; 90% of participations are aged {d.age.quantile(.05):.0f}-{d.age.quantile(.95):.0f}. "
                                  "One bar per year of age, men and women stacked; an athlete competing at several Games counts once per Games.")


@chart("a_age_density", S, "athletes", "Age density: medalists vs other athletes", "xy", "Silver participations", "silver_participations",
       "Compare the age profile of medalists and non-medalists on a common density scale", ("season", "year_range", "sport", "noc"), ("area",))
def age_density(ctx: Ctx):
    d = ages(ctx)
    cols, series = {}, []
    for flag, name, color in ((0, "Did not medal", "#9AA3AF"), (1, "Medalists", "#D4AF37")):
        v = d[d.is_medalist == flag].age.values
        if len(v) < 30:
            continue
        xs, ys = kde(v, n=100, lo=12, hi=60)
        cols[name] = ys
        series.append({"key": name, "color": color, "med": float(np.median(v)), "n": int(len(v))})
    if len(series) < 2:
        raise Unavailable("not enough medalists or non-medalists for the selected filters")
    xs = np.linspace(12, 60, 100)
    rows = [{"age": round(float(x), 2), **{k: round(float(c[i]), 5) for k, c in cols.items()}} for i, x in enumerate(xs)]
    m = {s["key"]: s["med"] for s in series}
    return payload("a_age_density", "xy", {"x": "age", "xType": "number", "rows": rows, "series": series, "variant": "area", "xLabel": "Age at competition (years)", "yLabel": "Density (share of group per year of age)"},
                   axes={"x": "Age (years)", "y": "Density"}, ctx=ctx,
                   interpretation=f"Each curve integrates to 1, so groups of very different size can be compared. Median age: medalists {m['Medalists']:.0f}, others {m['Did not medal']:.0f} "
                                  f"({_scope(ctx)}). Kernel density estimate with Silverman bandwidth.")


@chart("a_box_age", S, "athletes", "Age by sport (box plots)", "box", "Silver participations", "silver_participations",
       "Compare age spread across sports", ("season", "year_range", "noc"), ("violin",))
def box_age(ctx: Ctx):
    d = ages(ctx)
    top = d.groupby("sport_name").size().sort_values(ascending=False).head(14).index
    groups = []
    for sp in top:
        st = box_stats(d[d.sport_name == sp].age.values)
        groups.append({"name": sp, **st})
    groups.sort(key=lambda g: g["median"])
    return payload("a_box_age", "box", {"groups": groups, "yLabel": "Age at competition (years)", "orientation": "h"}, axes={"x": "Sport", "y": "Age (years)"}, ctx=ctx,
                   table=table_from([{k: v for k, v in g.items() if k != "outliers"} for g in groups]), drill={"type": "sport", "key": "name"},
                   interpretation="Box = middle 50% of ages, line = median, whiskers reach the furthest point within 1.5 x IQR, dots are outliers (at most 60 drawn per sport). "
                                  f"Shown: the 14 sports with the most participations ({_scope(ctx)}), ordered by median age.")


@chart("a_violin_age", S, "athletes", "Age distribution by season and gender (violin)", "violin", "Silver participations", "silver_participations",
       "Show the full shape of age distributions, not just quartiles", ("year_range", "sport", "noc"), ("box",))
def violin_age(ctx: Ctx):
    d = ages(ctx)
    d = d[d.gender.isin(["M", "F"])]
    groups = []
    for season in ("summer", "winter"):
        for g, gn in (("M", "Men"), ("F", "Women")):
            v = d[(d.season == season) & (d.gender == g)].age.values
            if len(v) < 40:
                continue
            xs, ys = kde(v, n=80, lo=12, hi=60)
            groups.append({"name": f"{season.capitalize()} {gn}", "x": np.round(xs, 2).tolist(), "density": np.round(ys / ys.max(), 4).tolist(), "median": float(np.median(v)), "n": int(len(v)),
                           "color": GENDER_COLORS[gn]})
    need_rows(groups, "groups with enough athletes")
    return payload("a_violin_age", "violin", {"groups": groups, "yLabel": "Age at competition (years)", "note": "Width scaled to each group's own peak"}, axes={"x": "Group", "y": "Age (years)"}, ctx=ctx,
                   table=table_from([{"group": g["name"], "n": g["n"], "median_age": g["median"]} for g in groups]),
                   interpretation="Violin width is the kernel density (each group scaled to its own maximum, so widths show shape, not group size). Group sizes and medians are in the data table.")


@chart("a_career_timeline", S, "athletes", "Athlete career timelines", "timeline", "Silver participations", "silver_participations",
       "Show when selected athletes competed and what they won", ("athlete_ids",), ("table",))
def career_timeline(ctx: Ctx):
    ids = ctx.athlete_ids
    if not ids:
        ids = df("SELECT athlete_id FROM gold_athlete_career ORDER BY medals DESC, gold DESC, games_count DESC LIMIT 12").athlete_id.tolist()
    ph = ",".join(f":a{i}" for i in range(len(ids)))
    par = {f"a{i}": a for i, a in enumerate(ids)}
    d = df(f"""SELECT p.athlete_id, a.full_name, p.year, p.season, p.games_id, MAX(CASE p.medal WHEN 'Gold' THEN 3 WHEN 'Silver' THEN 2 WHEN 'Bronze' THEN 1 ELSE 0 END) best,
                      COUNT(*) entries, GROUP_CONCAT(DISTINCT p.sport_name) sports
               FROM silver_participations p JOIN athletes a USING(athlete_id) WHERE p.athlete_id IN ({ph}) GROUP BY p.athlete_id, p.games_id ORDER BY p.year""", **par)
    need_rows(d, "participations")
    cmap = {3: ("Gold", MEDAL_COLORS["Gold"]), 2: ("Silver", MEDAL_COLORS["Silver"]), 1: ("Bronze", MEDAL_COLORS["Bronze"]), 0: ("No medal", "#5B6B86")}
    rows = [{"lane": r.full_name, "start": int(r.year), "end": int(r.year) + 1, "label": f"{r.games_id.replace('_', ' ')}: {r.sports} - {cmap[r.best][0]}", "color": cmap[r.best][1], "group": cmap[r.best][0],
             "athlete_id": int(r.athlete_id)} for r in d.itertuples()]
    order = d.groupby("full_name").year.min().sort_values().index.tolist()
    return payload("a_career_timeline", "timeline", {"rows": rows, "laneOrder": order, "xLabel": "Year", "legend": [{"name": v[0], "color": v[1]} for v in cmap.values()], "unit": "year"}, axes={"x": "Year", "y": "Athlete"}, ctx=ctx,
                   drill={"type": "athlete", "key": "athlete_id"}, table=table_from(rows, ["lane", "start", "label", "group"]),
                   interpretation="One block per Games attended, coloured by the best medal won there. Default selection: the 12 most decorated athletes in the dataset; pick other athletes with the filter. "
                                  "Athletes whose results could not be linked to a medal appear as 'No medal'.")


@chart("a_medal_progression", S, "athletes", "Athlete cumulative medal progression", "xy", "Gold athlete career x silver participations", "silver_participations",
       "Show how selected athletes accumulated medals Games by Games", ("athlete_ids",), ("step", "bar"))
def medal_progression(ctx: Ctx):
    ids = ctx.athlete_ids or df("SELECT athlete_id FROM gold_athlete_career ORDER BY medals DESC, gold DESC LIMIT 6").athlete_id.tolist()
    ph = ",".join(f":a{i}" for i in range(len(ids)))
    par = {f"a{i}": a for i, a in enumerate(ids)}
    d = df(f"SELECT p.athlete_id, a.full_name, p.year, SUM(p.is_medalist) m FROM silver_participations p JOIN athletes a USING(athlete_id) WHERE p.athlete_id IN ({ph}) GROUP BY 1,2,3", **par)
    need_rows(d, "participations")
    d = d.sort_values(["athlete_id", "year"])
    d["cum"] = d.groupby("athlete_id").m.cumsum()
    rows, keys = wide(d, "year", "full_name", "cum")
    # forward-fill cumulative values so each athlete's line stays flat between their Games
    df_rows = pd.DataFrame(rows).sort_values("year")
    for k in keys:
        first = d[d.full_name == k].year.min()
        df_rows.loc[df_rows.year < first, k] = np.nan
        df_rows[k] = df_rows[k].ffill()
    return payload("a_medal_progression", "xy", {"x": "year", "xType": "number", "rows": df_rows.to_dict("records"), "series": series_defs(keys), "variant": "step", "dot": True, "xLabel": "Games year",
                   "yLabel": "Cumulative medals"}, axes={"x": "Games year", "y": "Cumulative medals"}, ctx=ctx, interpretation="Steps mark Games where a medal was added. Counts are medal awards recorded for the athlete, so each team-event medal counts for every team member.")


RADAR = [("games_count", "Games attended"), ("medals", "Medals"), ("gold", "Gold medals"), ("sports_count", "Sports"), ("events_count", "Events entered"), ("career_span_years", "Career span (years)")]


@chart("a_radar", S, "athletes", "Athlete comparison radar", "radar", "Gold athlete career", "gold_athlete_career",
       "Compare selected athletes' careers on normalised axes", ("athlete_ids",), ("table",))
def athlete_radar(ctx: Ctx):
    ids = ctx.athlete_ids or df("SELECT athlete_id FROM gold_athlete_career ORDER BY medals DESC, gold DESC LIMIT 4").athlete_id.tolist()
    ph = ",".join(f":a{i}" for i in range(len(ids)))
    d = df(f"SELECT athlete_id, full_name, games_count, medals, gold, sports_count, events_count, career_span_years FROM gold_athlete_career WHERE athlete_id IN ({ph})", **{f"a{i}": a for i, a in enumerate(ids)})
    need_rows(d, "athletes")
    series, table = [], []
    for r in d.itertuples():
        series.append({"name": r.full_name, "athlete_id": int(r.athlete_id), "values": {lab: (float(getattr(r, k)) / float(d[k].max()) * 100 if d[k].max() else 0) for k, lab in RADAR}})
        table.append({"athlete": r.full_name, **{lab: float(getattr(r, k)) for k, lab in RADAR}})
    return payload("a_radar", "radar", {"axes": [lab for _, lab in RADAR], "series": series, "max": 100}, table=table_from(table), ctx=ctx,
                   interpretation="Axes have different units, so each is scaled to 100 for the largest value among the athletes compared; raw values are in the table.")


@chart("a_scatter_careers", S, "athletes", "Career length vs medals (most decorated athletes)", "scatter", "Gold athlete career", "gold_athlete_career",
       "Relate longevity to success", ("season",), ("table",))
def scatter_careers(ctx: Ctx):
    d = df("SELECT athlete_id, full_name, gender, games_count, medals, gold, career_span_years, sports FROM gold_athlete_career WHERE medals>=2 ORDER BY medals DESC, gold DESC LIMIT 3000")
    need_rows(d, "athletes")
    d = d[d.gender.isin(["M", "F"])]
    rng = np.random.default_rng(3)
    rows = [{"name": r.full_name, "athlete_id": int(r.athlete_id), "x": int(r.games_count) + float(rng.uniform(-.18, .18)), "y": int(r.medals) + float(rng.uniform(-.18, .18)), "z": int(r.gold) + 1, "group": "Men" if r.gender == "M" else "Women",
             "games": int(r.games_count), "medals": int(r.medals), "sports": r.sports} for r in d.itertuples()]
    return payload("a_scatter_careers", "scatter", {"rows": rows, "xLabel": "Games attended (jittered +/-0.18 to reduce overplotting)", "yLabel": "Career medals (jittered)", "sizeLabel": "Gold medals + 1", "groupLabel": "Gender",
                   "extra": ["games", "medals", "sports"], "colors": GENDER_COLORS}, axes={"x": "Games attended", "y": "Medals"}, ctx=ctx, drill={"type": "athlete", "key": "athlete_id"},
                   table=table_from([{k: v for k, v in r.items() if k not in ("x", "y")} for r in rows]),
                   interpretation="The 3,000 most decorated athletes with at least 2 medals (jitter only separates integer-valued points). Team-event medals inflate counts for team sports such as swimming relays or team games.")


@chart("a_heat_participation", S, "athletes", "Participation by age band and Games", "heatmap", "Silver participations", "silver_participations",
       "Show how the age mix of the Games has shifted", ("season", "year_range", "sport", "noc"), ())
def heat_participation(ctx: Ctx):
    c = Ctx({**ctx.p, **({"season": "summer"} if not ctx.season else {})})
    d = ages(c)
    bands = pd.cut(d.age, [0, 17, 20, 23, 26, 29, 32, 35, 40, 80], labels=["<18", "18-20", "21-23", "24-26", "27-29", "30-32", "33-35", "36-40", "41+"])
    d["band"] = bands.astype(str)
    g = d.groupby(["year", "band"]).size().reset_index(name="n")
    g["share"] = g.n / g.groupby("year").n.transform("sum")
    rows = [{"r": r.band, "c": str(int(r.year)), "v": round(float(r.share) * 100, 2), "label": f"{r.band} in {int(r.year)}: {r.share * 100:.1f}% ({int(r.n):,} participations)"} for r in g.itertuples()]
    return payload("a_heat_participation", "heatmap", {"rows": rows, "rowOrder": ["<18", "18-20", "21-23", "24-26", "27-29", "30-32", "33-35", "36-40", "41+"][::-1], "colOrder": [str(y) for y in sorted(d.year.unique())],
                   "scale": "seq", "vLabel": "Share of the Games' participations (%)", "format": "pct1"}, axes={"x": "Games year", "y": "Age band"}, ctx=ctx,
                   interpretation=f"Each column sums to 100%: the age mix of that Games ({(c.season or 'summer').capitalize()}). Brighter = larger share. Participations with no recorded age are excluded.")


@chart("a_medal_distribution", S, "athletes", "How many medals do athletes win?", "xy", "Gold athlete career", "gold_athlete_career",
       "Show the heavy-tailed distribution of career medal counts", (), ("table",))
def medal_distribution(ctx: Ctx):
    d = df("SELECT medals, COUNT(*) athletes FROM gold_athlete_career WHERE medals>=1 GROUP BY medals ORDER BY medals")
    need_rows(d, "medalists")
    cap = 8
    head = d[d.medals < cap]
    tail = d[d.medals >= cap]
    rows = [{"medals": str(int(r.medals)), "Athletes": int(r.athletes)} for r in head.itertuples()]
    if len(tail):
        rows.append({"medals": f"{cap}+", "Athletes": int(tail.athletes.sum())})
    tot = int(d.athletes.sum())
    return payload("a_medal_distribution", "xy", {"x": "medals", "xType": "category", "rows": rows, "series": [{"key": "Athletes", "color": "#D4AF37"}], "variant": "bar", "xLabel": "Career medals", "yLabel": "Athletes (log scale)",
                   "logY": True}, axes={"x": "Career medals", "y": "Athletes (log)"}, ctx=ctx,
                   interpretation=f"{tot:,} athletes have won at least one medal; {100 * d[d.medals == 1].athletes.sum() / tot:.0f}% won exactly one. Log scale keeps the rare multi-medalists visible. "
                                  "Team-event medals count for every team member.")


@chart("a_sankey_sports", S, "athletes", "Career transitions between sports (Sankey)", "sankey", "Silver participations", "silver_participations",
       "Show which sports athletes move between across consecutive Games", ("year_range",), ("table",))
def sankey_sports(ctx: Ctx):
    w, par = Ctx({k: v for k, v in ctx.p.items() if k != "season"}).where("p")
    d = df(f"SELECT p.athlete_id, p.year, p.sport_name FROM silver_participations p WHERE p.sport_name IS NOT NULL {w}", **par)
    need_rows(d, "participations")
    main = d.groupby(["athlete_id", "year", "sport_name"]).size().reset_index(name="n").sort_values(["athlete_id", "year", "n"], ascending=[True, True, False]).drop_duplicates(["athlete_id", "year"])
    main = main.sort_values(["athlete_id", "year"])
    main["next_sport"] = main.groupby("athlete_id").sport_name.shift(-1)
    sw = main[main.next_sport.notna() & (main.next_sport != main.sport_name)]
    flows = sw.groupby(["sport_name", "next_sport"]).size().reset_index(name="athletes").sort_values("athletes", ascending=False)
    flows = flows[flows.athletes >= 8].head(30)
    need_rows(flows, "sport changes with at least 8 athletes")
    left = sorted(set(flows.sport_name)); right = sorted(set(flows.next_sport))
    nodes = [{"name": f"{s} (from)"} for s in left] + [{"name": f"{s} (to)"} for s in right]
    li = {s: i for i, s in enumerate(left)}; ri = {s: len(left) + i for i, s in enumerate(right)}
    links = [{"source": li[r.sport_name], "target": ri[r.next_sport], "value": int(r.athletes)} for r in flows.itertuples()]
    total_sw = len(sw)
    return payload("a_sankey_sports", "sankey", {"nodes": nodes, "links": links, "valueLabel": "athletes"}, ctx=ctx,
                   table=table_from([{"from_sport": r.sport_name, "to_sport": r.next_sport, "athletes": int(r.athletes)} for r in flows.itertuples()]),
                   interpretation=f"Each link counts athletes whose main sport changed between two consecutive Games they attended: {total_sw:,} changes out of {len(main) - main.athlete_id.nunique():,} consecutive attendances ({100 * total_sw / max(1, len(main) - main.athlete_id.nunique()):.1f}%), so switching sport is rare. "
                                  "Only flows of at least 8 athletes are drawn (30 at most). Athletes who stayed in their sport are excluded. Both seasons are included, so Summer-to-Winter moves such as Athletics to Bobsleigh appear.")
