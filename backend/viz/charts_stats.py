"""Section 5 - statistical visualization library (stored analytics + fresh computation on the silver layer)."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
from scipy import stats as sps

from .core import MEDAL_COLORS, Ctx, Unavailable, age_rows, analytics, box_stats, chart, df, kde, need_rows, payload, series_defs, table_from
from .core import engine, text

S = 5
VARS = {"athlete_age": ("Athlete age (years)", "Athlete participations"), "country_edition_total_medals": ("Medals won per NOC per Games", "NOC-Games observations"),
        "country_edition_athletes": ("Athletes per NOC per Games", "NOC-Games observations")}
SEASON_COLORS = {"Summer": "#F4A300", "Winter": "#0085C7"}
GENDER_COLORS = {"Men": "#0085C7", "Women": "#DF0024"}


def _var(ctx: Ctx):
    key = ctx.metric if ctx.metric in VARS else "athlete_age"
    return key, VARS[key], analytics("stats", "distributions")[key]


def _noc_games(ctx: Ctx) -> pd.DataFrame:
    w, par = ctx.where("g")
    return need_rows(df(f"SELECT g.games_id, g.year, g.season, g.noc_code, g.country_name, g.athletes, g.sports, g.total, g.gold, g.is_host FROM gold_country_medals g WHERE g.athletes>0 {w}", **par), "NOC-Games rows")


@chart("st_hist", S, "statistics", "Histogram", "xy", "Stored distribution analysis", "analytics_results(stats/distributions)",
       "Show the frequency distribution of a variable", ("metric",), ("area",))
def hist(ctx: Ctx):
    key, (xl, unit), d = _var(ctx)
    h = d["histogram"]
    e = np.asarray(h["edges"], float)
    rows = [{"bin": round(float((e[i] + e[i + 1]) / 2), 3), "count": int(c), "from": round(float(e[i]), 3), "to": round(float(e[i + 1]), 3)} for i, c in enumerate(h["counts"])]
    nm = d["normality"]
    return payload("st_hist", "xy", {"x": "bin", "xType": "number", "rows": rows, "series": [{"key": "count", "name": unit, "color": "#0085C7"}], "variant": "bar", "barGap": 0, "xLabel": xl, "yLabel": unit},
                   axes={"x": xl, "y": unit}, ctx=ctx, interpretation=f"Skewness {nm['skewness']:.2f}: {'right-skewed (a long tail of large values)' if nm['skewness'] > 0.5 else 'roughly symmetric'}. {nm['note']}",
                   notes=["Choose the variable with the metric filter: athlete_age, country_edition_total_medals, country_edition_athletes."])


@chart("st_kde", S, "statistics", "Kernel density estimate", "xy", "Stored distribution analysis", "analytics_results(stats/distributions)",
       "Show a smooth estimate of the distribution", ("metric",), ("line",))
def kde_chart(ctx: Ctx):
    key, (xl, unit), d = _var(ctx)
    k = d["kde"]
    rows = [{"x": round(float(x), 3), "density": round(float(y), 6)} for x, y in zip(k["x"], k["density"])]
    return payload("st_kde", "xy", {"x": "x", "xType": "number", "rows": rows, "series": [{"key": "density", "color": "#009F3D"}], "variant": "area", "xLabel": xl, "yLabel": "Density"}, axes={"x": xl, "y": "Density"}, ctx=ctx,
                   interpretation="Gaussian kernel density with Silverman bandwidth; the area under the curve is 1. Peaks show the most typical values; a long right tail means a few very large values.")


@chart("st_ecdf", S, "statistics", "Empirical cumulative distribution (ECDF)", "xy", "Stored distribution analysis", "analytics_results(stats/distributions)",
       "Read percentiles and compare distributions without binning", ("metric",), ("line",))
def ecdf(ctx: Ctx):
    key, (xl, unit), d = _var(ctx)
    e = d["ecdf"]
    rows = [{"x": round(float(x), 3), "cumulative share": round(float(p), 4)} for x, p in zip(e["x"], e["p"])]
    med = next((r["x"] for r in rows if r["cumulative share"] >= 0.5), None)
    return payload("st_ecdf", "xy", {"x": "x", "xType": "number", "rows": rows, "series": [{"key": "cumulative share", "color": "#8E6BBF"}], "variant": "step", "xLabel": xl, "yLabel": "Cumulative share of observations",
                   "yDomain": [0, 1], "refs": [{"y": 0.5, "label": "median"}]}, axes={"x": xl, "y": "Cumulative share"}, ctx=ctx,
                   interpretation=f"The curve gives the share of observations at or below each value; it crosses 0.5 at the median ({med}). Steeper sections hold more observations.")


@chart("st_qq", S, "statistics", "Q-Q plot against the normal distribution", "scatter", "Stored distribution analysis", "analytics_results(stats/distributions)",
       "Check how far a variable departs from normality", ("metric",), ("table",))
def qq(ctx: Ctx):
    key, (xl, unit), d = _var(ctx)
    q = d["qq_normal"]
    th, sm = np.asarray(q["theoretical"], float), np.asarray(q["sample"], float)
    q1, q3 = np.percentile(sm, [25, 75]); t1, t3 = np.percentile(th, [25, 75])
    slope = (q3 - q1) / (t3 - t1); icpt = q1 - slope * t1
    rows = [{"x": float(a), "y": float(b)} for a, b in zip(th, sm)]
    line = [{"x": float(th.min()), "y": float(icpt + slope * th.min())}, {"x": float(th.max()), "y": float(icpt + slope * th.max())}]
    return payload("st_qq", "scatter", {"rows": rows, "xLabel": "Theoretical normal quantiles (standard deviations)", "yLabel": f"Sample quantiles: {xl}", "line": line, "lineLabel": "line through the quartiles"}, axes={"x": "Normal quantiles", "y": xl},
                   ctx=ctx, interpretation=f"Points on the line mean normality. Curvature away from it (here skewness {d['normality']['skewness']:.2f}) means the variable is not normal, so rank-based tests are preferred for it.")


@chart("st_box", S, "statistics", "Box plots of age: season and medal status", "box", "Silver participations", "silver_participations",
       "Compare age distributions across groups with robust summaries", ("year_range",), ("violin",))
def box(ctx: Ctx):
    w, par = ctx.where("p")
    d = age_rows(w, par)
    need_rows(d, "ages")
    groups = []
    for season in ("summer", "winter"):
        for med, nm in ((0, "others"), (1, "medalists")):
            v = d[(d.season == season) & (d.is_medalist == med)].age.values
            if len(v) >= 20:
                groups.append({"name": f"{season.capitalize()} {nm}", **box_stats(v)})
    return payload("st_box", "box", {"groups": groups, "yLabel": "Age (years)", "orientation": "v"}, axes={"x": "Group", "y": "Age (years)"}, ctx=ctx, table=table_from([{k: v for k, v in g.items() if k != "outliers"} for g in groups]),
                   interpretation="Box = interquartile range with the median line; whiskers extend to the furthest value within 1.5 x IQR; dots are a sample of outliers (counts in the table). Winter athletes and medalists are slightly older.")


@chart("st_violin", S, "statistics", "Violin plots of age by season and medal status", "violin", "Stored distribution analysis", "analytics_results(stats/distributions)",
       "Show the full distribution shape per group", (), ("box",))
def violin(ctx: Ctx):
    v = analytics("stats", "distributions")["violin_age"]
    groups = []
    for k, g in v.items():
        ys = np.asarray(g["density"], float)
        groups.append({"name": k.replace("_", " ").replace("non medalist", "others").capitalize(), "x": g["x"], "density": (ys / ys.max()).round(4).tolist(), "median": g["median"], "n": g["n"]})
    return payload("st_violin", "violin", {"groups": groups, "yLabel": "Age (years)", "note": "Width scaled to each group's own peak"}, axes={"x": "Group", "y": "Age (years)"}, ctx=ctx,
                   table=table_from([{"group": g["name"], "n": g["n"], "median_age": g["median"]} for g in groups]), interpretation="Each violin is a mirrored density; widths are scaled per group, so compare shapes, and read sizes from the table.")


@chart("st_strip", S, "statistics", "Strip plot: age by sport (sample)", "scatter", "Silver participations", "silver_participations",
       "Show individual observations behind the summaries", ("year_range",), ("table",))
def strip(ctx: Ctx):
    w, par = ctx.where("p")
    d = age_rows(w, par)
    need_rows(d, "ages")
    top = d.sport_name.value_counts().head(8).index.tolist()
    rng = np.random.default_rng(5)
    rows = []
    for i, sp in enumerate(top):
        g = d[d.sport_name == sp].age.sample(min(250, (d.sport_name == sp).sum()), random_state=1)
        rows += [{"x": i + float(rng.uniform(-.32, .32)), "y": float(a), "group": sp, "name": sp} for a in g]
    return payload("st_strip", "scatter", {"rows": rows, "xLabel": "Sport", "yLabel": "Age (years)", "xCategories": top, "groupLabel": "Sport", "noSize": True}, axes={"x": "Sport", "y": "Age (years)"}, ctx=ctx,
                   interpretation="Random sample of 250 participations per sport (the 8 largest sports) with horizontal jitter only; the vertical position is the true age (integer years).")


def _swarm(vals, width=0.4, step=0.6):
    v = np.sort(vals); xs = np.zeros(len(v)); placed = []
    for i, y in enumerate(v):
        off = 0.0; k = 0
        while any(abs(off - px) < width * 0.12 and abs(y - py) < step for px, py in placed[-60:]):
            k += 1; off = ((k + 1) // 2) * width * 0.12 * (1 if k % 2 else -1)
            if abs(off) > width:
                break
        placed.append((off, y)); xs[i] = off
    return v, xs


@chart("st_swarm", S, "statistics", "Swarm plot: medalist age by season", "scatter", "Silver participations", "silver_participations",
       "Show every observation without overlap", ("year_range",), ("table",))
def swarm(ctx: Ctx):
    w, par = ctx.where("p")
    d = age_rows(w, par)
    d = d[d.is_medalist == 1]
    need_rows(d, "medalist ages")
    rows, cats = [], ["Summer", "Winter"]
    for i, s in enumerate(("summer", "winter")):
        g = d[d.season == s].age.sample(min(220, (d.season == s).sum()), random_state=2).values
        v, xs = _swarm(g.astype(float))
        rows += [{"x": i + float(x), "y": float(y), "group": s.capitalize(), "name": s.capitalize()} for x, y in zip(xs, v)]
    return payload("st_swarm", "scatter", {"rows": rows, "xLabel": "Season", "yLabel": "Age (years)", "xCategories": cats, "groupLabel": "Season", "noSize": True, "colors": SEASON_COLORS}, axes={"x": "Season", "y": "Age (years)"}, ctx=ctx,
                   interpretation="A beeswarm of 220 randomly sampled medal-winning participations per season: points at the same age are spread sideways so none overlap, and the horizontal width shows how many share an age.")


@chart("st_scatter", S, "statistics", "Scatter: delegation size vs medals", "scatter", "Gold country medals", "gold_country_medals",
       "Examine the relationship between two variables observation by observation", ("season", "year_range"), ("table",))
def scatter(ctx: Ctx):
    d = _noc_games(ctx)
    d = d[d.total > 0]
    rows = [{"x": int(r.athletes), "y": int(r.total), "name": f"{r.noc_code} {r.games_id.replace('_', ' ')}", "group": r.season.capitalize(), "noc": r.noc_code} for r in d.itertuples()]
    r_s = sps.spearmanr(d.athletes, d.total)
    return payload("st_scatter", "scatter", {"rows": rows, "xLabel": "Athletes sent (per NOC per Games)", "yLabel": "Medals won", "logX": True, "logY": True, "groupLabel": "Season", "noSize": True, "colors": SEASON_COLORS},
                   axes={"x": "Athletes (log)", "y": "Medals (log)"}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   interpretation=f"{len(d):,} NOC-Games observations with at least one medal. Spearman rho = {r_s.statistic:.2f}: larger delegations win more, but the spread at any size is wide. Log axes; NOCs with no medal are excluded (cannot be shown on a log axis).")


@chart("st_regression", S, "statistics", "Regression plot: log medals on log athletes", "scatter", "Gold country medals", "gold_country_medals",
       "Fit and display a simple regression with its uncertainty", ("season", "year_range"), ("table",))
def regression(ctx: Ctx):
    d = _noc_games(ctx)
    d = d[d.total > 0]
    x, y = np.log10(d.athletes.values.astype(float)), np.log10(d.total.values.astype(float))
    res = sps.linregress(x, y)
    xs = np.linspace(x.min(), x.max(), 40)
    n = len(x); se = np.sqrt(np.sum((y - (res.intercept + res.slope * x)) ** 2) / (n - 2))
    sxx = np.sum((x - x.mean()) ** 2)
    t = sps.t.ppf(0.975, n - 2)
    half = t * se * np.sqrt(1 / n + (xs - x.mean()) ** 2 / sxx)
    line = [{"x": float(a), "y": float(res.intercept + res.slope * a), "lo": float(res.intercept + res.slope * a - h), "hi": float(res.intercept + res.slope * a + h)} for a, h in zip(xs, half)]
    sample = d.sample(min(900, len(d)), random_state=4)
    rows = [{"x": float(np.log10(r.athletes)), "y": float(np.log10(r.total)), "name": f"{r.noc_code} {r.games_id.replace('_', ' ')}", "group": r.season.capitalize()} for r in sample.itertuples()]
    return payload("st_regression", "scatter", {"rows": rows, "xLabel": "log10(athletes sent)", "yLabel": "log10(medals won)", "line": line, "lineLabel": "OLS fit with 95% CI of the mean", "groupLabel": "Season", "noSize": True, "colors": SEASON_COLORS},
                   axes={"x": "log10 athletes", "y": "log10 medals"}, ctx=ctx,
                   table=table_from([{"n": n, "slope": res.slope, "intercept": res.intercept, "r_squared": res.rvalue ** 2, "slope_stderr": res.stderr, "p_value": res.pvalue}]),
                   interpretation=f"Elasticity {res.slope:.2f}: a 10% larger delegation is associated with about {100 * (1.1 ** res.slope - 1):.1f}% more medals (R2 = {res.rvalue ** 2:.2f}, n = {n:,}). "
                                  f"Association, not causation; strong nations send both more athletes and better ones. Only a random sample of {len(sample)} points is drawn; the fit uses all {n:,}.")


@chart("st_residual", S, "statistics", "Residuals vs fitted values", "scatter", "Stored regression diagnostics", "analytics_results(stats/regression)",
       "Check model assumptions: linearity and constant variance", (), ("table",))
def residual(ctx: Ctx):
    r = analytics("stats", "regression")["ols_log_medals"]
    pts = r["residual_vs_fitted"]
    rows = [{"x": float(p["fitted"]), "y": float(p["resid"])} for p in pts]
    dg = r["diagnostics"]
    return payload("st_residual", "scatter", {"rows": rows, "xLabel": "Fitted log medals", "yLabel": "Residual", "refY": 0, "noSize": True, "groupLabel": None}, axes={"x": "Fitted", "y": "Residual"}, ctx=ctx,
                   interpretation=f"OLS on log medals (R2 = {r['r2']:.2f}, n = {r['n']:,}); {len(rows)} stored residuals. Breusch-Pagan p = {dg['breusch_pagan_p']:.2g}: {'a funnel shape means variance grows with the fitted value (heteroscedasticity), so HC3 robust errors are used.' if dg['breusch_pagan_p'] < 0.05 else 'no strong evidence of unequal variance.'}")


@chart("st_corr_heatmap", S, "statistics", "Correlation heatmap", "heatmap", "Stored correlation analysis", "analytics_results(stats/correlations)",
       "Show pairwise associations between NOC-Games variables", ("metric",), ("table",))
def corr(ctx: Ctx):
    d = analytics("stats", "correlations")
    m = ctx.metric if ctx.metric in ("pearson", "spearman", "kendall") else "spearman"
    blk = d[m]
    vars_ = blk["variables"]
    rows, tab = [], []
    for i, rv in enumerate(vars_):
        for j, cv in enumerate(vars_):
            row = blk["matrix"][i]
            val = row[cv] if isinstance(row, dict) and cv in row else (row[j] if isinstance(row, list) else None)
            pv = blk["p_values"][i][cv] if isinstance(blk["p_values"][i], dict) else blk["p_values"][i][j]
            rows.append({"r": rv, "c": cv, "v": round(float(val), 3), "label": f"{rv} vs {cv}: {m} {float(val):.2f} (p={pv:.2g})"})
            tab.append({"x": rv, "y": cv, m: round(float(val), 4), "p_value": pv})
    return payload("st_corr_heatmap", "heatmap", {"rows": rows, "rowOrder": vars_, "colOrder": vars_, "scale": "div", "vLabel": f"{m.capitalize()} correlation", "domain": [-1, 1], "format": "dec2", "cell": "number"},
                   axes={"x": "Variable", "y": "Variable"}, ctx=ctx, table=table_from(tab),
                   interpretation=f"{m.capitalize()} correlation (n = {blk['n']:,}). {d.get('warning', 'Correlation does not establish causation.')} Switch method with the metric filter: pearson, spearman or kendall.")


@chart("st_pairplot", S, "statistics", "Pair plot of NOC-Games variables", "pairs", "Gold country medals", "gold_country_medals",
       "Inspect every pairwise relationship at once", ("season", "year_range"), ())
def pairplot(ctx: Ctx):
    d = _noc_games(ctx)
    d = d[d.total > 0].copy()
    d["gold_share"] = d.gold / d.total
    d = d.sample(min(450, len(d)), random_state=6)
    cols = {"athletes": "Athletes", "sports": "Sports entered", "total": "Medals", "gold_share": "Gold share"}
    rows = [{**{lab: float(getattr(r, k)) for k, lab in cols.items()}, "group": r.season.capitalize(), "name": f"{r.noc_code} {r.games_id.replace('_', ' ')}"} for r in d.itertuples()]
    return payload("st_pairplot", "pairs", {"vars": list(cols.values()), "rows": rows, "colors": SEASON_COLORS}, axes={}, ctx=ctx,
                   interpretation=f"Random sample of {len(rows)} NOC-Games observations that won at least one medal. Diagonal cells show each variable's distribution (histogram); off-diagonal cells are scatter plots coloured by season.")


@chart("st_ci_plot", S, "statistics", "Confidence interval plot of the confirmatory tests", "forest", "Stored hypothesis tests", "analytics_hypothesis_tests",
       "Show each test's estimate and 95% interval on its own meaningful scale", (), ("table",))
def ci_plot(ctx: Ctx):
    t = {r.test_id: r for r in df("SELECT * FROM analytics_hypothesis_tests").itertuples()}
    rows = []

    def add(tid, label, unit, est):
        r = t.get(tid)
        if r is not None and r.ci_low is not None and not pd.isna(r.ci_low):
            rows.append({"panel": f"{label} [{unit}]", "name": label, "est": float(est), "lo": float(r.ci_low), "hi": float(r.ci_high), "p": float(r.p_value), "unit": unit})
    a1 = json.loads(t["H1_host_vs_non_host"].assumptions_json) if "H1_host_vs_non_host" in t else {}
    a2 = json.loads(t["H2_age_medalists_vs_others"].assumptions_json) if "H2_age_medalists_vs_others" in t else {}
    if a1:
        add("H1_host_vs_non_host", "Host minus own non-host medals", "medals", a1["mean_difference"])
    if a2:
        add("H2_age_medalists_vs_others", "Medalist minus other athletes' age", "years", a2["mean_medalists"] - a2["mean_others"])
    for sid, nm in (("H3_female_trend_summer", "Summer female-share trend"), ("H3_female_trend_winter", "Winter female-share trend")):
        if sid in t:
            add(sid, nm, "share points per 4 years", t[sid].effect_size)
    need_rows(rows, "tests with confidence intervals")
    return payload("st_ci_plot", "forest", {"rows": rows, "xLabel": "Estimate with 95% confidence interval (each test on its own scale)", "ref": 0, "panels": True}, axes={}, ctx=ctx, table=table_from(rows),
                   interpretation="Each test is drawn on its own axis because the estimates have different units (medals, years, share points), so intervals must not be compared across rows. An interval that excludes 0 corresponds to a significant difference at alpha = 0.05.")


@chart("st_errorbar", S, "statistics", "Error bars: mean age with 95% CI", "errorbar", "Silver participations", "silver_participations",
       "Compare group means with their uncertainty", ("year_range",), ("table",))
def errorbar(ctx: Ctx):
    w, par = ctx.where("p")
    d = age_rows(w, par)
    d = d[d.gender.isin(["M", "F"])]
    need_rows(d, "ages")
    rows = []
    for season in ("summer", "winter"):
        for g, gn in (("M", "Men"), ("F", "Women")):
            for med, mn in ((0, "others"), (1, "medalists")):
                v = d[(d.season == season) & (d.gender == g) & (d.is_medalist == med)].age.values
                if len(v) < 30:
                    continue
                se = v.std(ddof=1) / math.sqrt(len(v)); m = v.mean()
                rows.append({"name": f"{season.capitalize()} {gn} {mn}", "value": round(float(m), 3), "lo": round(float(m - 1.96 * se), 3), "hi": round(float(m + 1.96 * se), 3), "n": int(len(v)), "color": GENDER_COLORS[gn]})
    return payload("st_errorbar", "errorbar", {"rows": rows, "yLabel": "Mean age (years) with 95% CI", "yAuto": True}, axes={"x": "Group", "y": "Mean age (years)"}, ctx=ctx,
                   interpretation="Bars show the group mean and the whiskers the 95% confidence interval of that mean (normal approximation). With tens of thousands of observations the intervals are narrow, so even small differences are statistically detectable; "
                                  "judge importance by the size of the difference, not by non-overlap alone.")


@chart("st_forest", S, "statistics", "Forest plot: Poisson regression rate ratios", "forest", "Stored regression models", "analytics_results(stats/regression)",
       "Show the multiplicative effect of each predictor on medal counts", (), ("table",))
def forest(ctx: Ctx):
    r = analytics("stats", "regression")["medal_counts"]
    rows = []
    for c in r["poisson_cluster_robust"]["coefs"]:
        if c["term"] == "Intercept":
            continue
        rows.append({"name": c["term"].replace("C(season)[T.winter]", "Winter (vs Summer)").replace("is_host", "Host nation").replace("log_athletes", "log(athletes)").replace("sports", "Sports entered"),
                     "est": math.exp(c["coef"]), "lo": math.exp(c["ci_low"]), "hi": math.exp(c["ci_high"]), "p": c["p"], "unit": "rate ratio"})
    need_rows(rows, "coefficients")
    return payload("st_forest", "forest", {"rows": rows, "xLabel": "Rate ratio (multiplicative effect on expected medals), log scale", "ref": 1, "log": True}, axes={}, ctx=ctx, table=table_from(rows),
                   interpretation=f"Poisson regression of medals per NOC-Games ({r['n']:,} observations) with cluster-robust errors. A ratio of 1.3 means 30% more expected medals per unit increase in the predictor (all else equal). "
                                  f"{r['poisson_cluster_robust']['note']}")


@chart("st_pvalue", S, "statistics", "P-value comparison across tests", "xy", "Stored hypothesis tests", "analytics_hypothesis_tests",
       "Compare the strength of evidence across hypothesis tests on one scale", (), ("table",))
def pvalue(ctx: Ctx):
    d = df("SELECT test_id, p_value, p_adjusted_holm FROM analytics_hypothesis_tests ORDER BY p_value")
    need_rows(d, "tests")
    rows = []
    for r in d.itertuples():
        raw = max(float(r.p_value), 1e-300)
        adj = r.p_adjusted_holm
        rows.append({"name": r.test_id.split("_")[0] + " " + " ".join(r.test_id.split("_")[1:3]), "-log10(p)": round(-math.log10(raw), 2), "-log10(Holm-adjusted p)": None if adj is None or pd.isna(adj) else round(-math.log10(max(float(adj), 1e-300)), 2),
                     "p": float(r.p_value)})
    return payload("st_pvalue", "xy", {"x": "name", "xType": "category", "rows": rows, "series": [{"key": "-log10(p)", "color": "#9AA3AF"}, {"key": "-log10(Holm-adjusted p)", "color": "#DF0024"}], "variant": "grouped", "horizontal": True,
                   "yLabel": "-log10(p): longer bar = stronger evidence", "refs": [{"y": round(-math.log10(0.05), 2), "label": "alpha = 0.05"}], "pickKey": None}, axes={"x": "-log10(p)", "y": "Test"}, ctx=ctx,
                   interpretation="Both bars are on a -log10 scale so tiny p-values stay readable (p = 1e-96 is 96). Bars beyond the dashed alpha = 0.05 line are significant. Holm adjustment controls the family-wise error rate across the confirmatory tests; "
                                  "the S1 exploratory test has no adjusted value. A tiny p-value says the effect is detectable, not that it is large; see the effect-size plot.")


@chart("st_effect", S, "statistics", "Effect sizes of the tests", "forest", "Stored hypothesis tests", "analytics_hypothesis_tests",
       "Separate statistical significance from practical importance", (), ("table",))
def effect(ctx: Ctx):
    d = df("SELECT test_id, effect_size_name, effect_size, p_value FROM analytics_hypothesis_tests WHERE effect_size IS NOT NULL")
    need_rows(d, "effect sizes")
    rows = [{"panel": r.effect_size_name.split(" (")[0], "name": r.test_id.replace("_", " "), "est": float(r.effect_size), "p": float(r.p_value), "unit": r.effect_size_name} for r in d.itertuples()]
    return payload("st_effect", "forest", {"rows": rows, "xLabel": "Effect size (each metric on its own axis)", "ref": 0, "panels": True, "noInterval": True}, axes={}, ctx=ctx, table=table_from(rows),
                   interpretation="Different tests report different effect-size measures (Cohen's d, rank-biserial, Cramer's V, slope, epsilon-squared), which are not comparable, so each metric has its own panel. "
                                  "Conventional magnitudes for Cohen's d are 0.2 small, 0.5 medium, 0.8 large; for Cramer's V roughly 0.1 small, 0.3 medium.")


@chart("st_dist_compare", S, "statistics", "Distribution comparison: Summer vs Winter athlete age", "xy", "Silver participations", "silver_participations",
       "Test visually and numerically whether two groups have the same distribution", ("year_range",), ("line",))
def dist_compare(ctx: Ctx):
    w, par = ctx.where("p")
    d = age_rows(w, par)
    need_rows(d, "ages")
    a, b = d[d.season == "summer"].age.values, d[d.season == "winter"].age.values
    if len(a) < 30 or len(b) < 30:
        raise Unavailable("not enough athletes in one of the seasons")
    xs = np.linspace(12, 60, 100)
    _, da = kde(a, 100, 12, 60); _, db = kde(b, 100, 12, 60)
    ks = sps.ks_2samp(a, b)
    rows = [{"age": round(float(x), 2), "Summer": round(float(y1), 5), "Winter": round(float(y2), 5)} for x, y1, y2 in zip(xs, da, db)]
    return payload("st_dist_compare", "xy", {"x": "age", "xType": "number", "rows": rows, "series": series_defs(["Summer", "Winter"], colors=SEASON_COLORS), "variant": "area", "xLabel": "Age (years)", "yLabel": "Density"},
                   axes={"x": "Age (years)", "y": "Density"}, ctx=ctx,
                   interpretation=f"Two-sample Kolmogorov-Smirnov: D = {ks.statistic:.3f}, p = {ks.pvalue:.2g} (n = {len(a):,} Summer, {len(b):,} Winter). Median age {np.median(a):.0f} (Summer) vs {np.median(b):.0f} (Winter). "
                                  "With samples this large, a small D is still significant, so look at the overlap of the curves.")


@chart("st_outliers", S, "statistics", "Outlier analysis: medals per NOC per Games", "scatter", "Gold country medals", "gold_country_medals",
       "Identify exceptional NOC-Games results with the 1.5 x IQR rule", ("year_range",), ("table",))
def outliers(ctx: Ctx):
    d = _noc_games(Ctx({k: v for k, v in ctx.p.items() if k != "season"}))
    rng = np.random.default_rng(7)
    rows, tab = [], []
    for i, season in enumerate(("summer", "winter")):
        g = d[d.season == season]
        if len(g) < 20:
            continue
        q1, q3 = g.total.quantile([.25, .75]); hi = q3 + 1.5 * (q3 - q1)
        for r in g.itertuples():
            out = r.total > hi
            rows.append({"x": i + float(rng.uniform(-.3, .3)), "y": int(r.total), "name": f"{r.country_name} {r.games_id.replace('_', ' ')}", "group": "Outlier (> Q3 + 1.5 IQR)" if out else "Within fences", "noc": r.noc_code})
            if out:
                tab.append({"season": season, "nation": r.country_name, "games": r.games_id, "medals": int(r.total), "upper_fence": float(hi)})
    top = sorted(tab, key=lambda r: -r["medals"])
    return payload("st_outliers", "scatter", {"rows": rows, "xLabel": "Season", "yLabel": "Medals won", "xCategories": ["Summer", "Winter"], "groupLabel": "Status", "noSize": True,
                   "colors": {"Outlier (> Q3 + 1.5 IQR)": "#DF0024", "Within fences": "#9AA3AF"}, "logY": True}, axes={"x": "Season", "y": "Medals (log)"}, ctx=ctx, drill={"type": "country", "key": "noc"},
                   table=table_from(top), interpretation=f"{len(tab)} NOC-Games results exceed the upper Tukey fence (Q3 + 1.5 x IQR) within their season; the biggest are in the table. Medal counts are heavily right-skewed, "
                                                         "so the fence flags many genuine powerhouses (not data errors); they are real values and are kept.")
