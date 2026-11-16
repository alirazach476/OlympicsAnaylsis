"""PHASE 4 - statistical analysis (descriptive, distributions, correlation, hypothesis tests, regression, time series).

Conventions: every test states H0/H1, why that test, assumption checks, statistic, p, CI, effect size and plain-language interpretation.
p-values of the confirmatory family are Holm-adjusted. Correlation is never presented as causation.
"""
from __future__ import annotations

import datetime as dt
import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.stattools import durbin_watson

from .store import save

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(20260101)
ALPHA = 0.05


# ------------------------------------------------------------------ helpers
def describe(x: pd.Series) -> dict:
    x = pd.Series(x).dropna().astype(float)
    mode = stats.mode(x.round(6), keepdims=False).mode if len(x) else np.nan
    return {
        "n": int(len(x)), "mean": x.mean(), "median": x.median(), "mode": mode, "min": x.min(), "max": x.max(), "range": x.max() - x.min(),
        "variance": x.var(ddof=1), "std": x.std(ddof=1), "q1": x.quantile(.25), "q3": x.quantile(.75), "iqr": x.quantile(.75) - x.quantile(.25),
        "p5": x.quantile(.05), "p10": x.quantile(.10), "p90": x.quantile(.90), "p95": x.quantile(.95), "p99": x.quantile(.99),
        "skewness": stats.skew(x, bias=False), "excess_kurtosis": stats.kurtosis(x, bias=False), "cv": (x.std(ddof=1) / x.mean()) if x.mean() else np.nan,
    }


def cohens_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return (a.mean() - b.mean()) / sp


def boot_ci(fn, *arrs, n=2000, level=.95):
    arrs = [np.asarray(a, float) for a in arrs]
    out = []
    for _ in range(n):
        out.append(fn(*[a[RNG.integers(0, len(a), len(a))] for a in arrs]))
    lo, hi = np.percentile(out, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def shapiro_p(x, cap=4000):
    x = np.asarray(x, float)
    if len(x) < 3:
        return None
    if len(x) > cap:
        x = RNG.choice(x, cap, replace=False)
    return float(stats.shapiro(x).pvalue)


def interp(p, what, effect_name, eff, small, large):
    mag = "negligible" if abs(eff) < small else ("small-to-moderate" if abs(eff) < large else "large")
    sig = "statistically significant" if p < ALPHA else "not statistically significant"
    return f"{what}: {sig} at alpha={ALPHA} (p={p:.3g}); effect size {effect_name}={eff:.3f} ({mag})."


# ------------------------------------------------------------------ data
def frames(con):
    q = lambda s: pd.read_sql(s, con)
    part = q("SELECT athlete_id, games_id, year, season, noc_code, gender, age, is_medalist, is_host_noc, sport_name FROM silver_participations")
    cm = q("SELECT c.*, e.nocs AS edition_nocs, e.events AS edition_events FROM gold_country_medals c JOIN gold_edition_performance e USING(games_id)")
    ed = q("SELECT * FROM gold_edition_performance ORDER BY year, season")
    # country-edition panel INCLUDING participants with zero medals
    pan = part.groupby(["games_id", "year", "season", "noc_code"]).agg(athletes=("athlete_id", "nunique"), sports=("sport_name", "nunique")).reset_index()
    pan = pan.merge(cm[["games_id", "noc_code", "gold", "silver", "bronze", "total"]], on=["games_id", "noc_code"], how="left").fillna({"gold": 0, "silver": 0, "bronze": 0, "total": 0})
    hostmap = q("SELECT games_id, host_noc FROM ref_host_noc")
    pan = pan.merge(hostmap, on="games_id", how="left")
    pan["is_host"] = (pan.noc_code == pan.host_noc).astype(int)
    pan = pan.sort_values(["season", "noc_code", "year"])
    pan["prev_total"] = pan.groupby(["season", "noc_code"]).total.shift(1)
    pan["prev_gold"] = pan.groupby(["season", "noc_code"]).gold.shift(1)
    pan["prev_athletes"] = pan.groupby(["season", "noc_code"]).athletes.shift(1)
    pan["appearance_no"] = pan.groupby(["season", "noc_code"]).cumcount() + 1
    return part, cm, ed, pan


# ------------------------------------------------------------------ 1-2 descriptive + distribution
def descriptive_and_distribution(con, part, pan, ed):
    age = part.dropna(subset=["age"])
    specs = {
        "athlete_age_all": age.age, "athlete_age_summer": age[age.season == "summer"].age, "athlete_age_winter": age[age.season == "winter"].age,
        "athlete_age_medalists": age[age.is_medalist == 1].age, "athlete_age_non_medalists": age[age.is_medalist == 0].age,
        "country_edition_total_medals": pan.total, "country_edition_athletes": pan.athletes,
        "sport_participation_per_edition": pd.read_sql("SELECT athletes FROM gold_sport_performance", con).athletes,
        "edition_athletes": ed.athletes,
    }
    d = {k: describe(v) for k, v in specs.items()}
    save(con, "stats", "descriptive", "Descriptive statistics", d, "What do the central tendency, spread and shape of key variables look like?")

    dist = {}
    for name, s in {"athlete_age": age.age, "country_edition_total_medals": pan.total[pan.total > 0], "country_edition_athletes": pan.athletes}.items():
        x = np.sort(s.dropna().astype(float).values)
        hist, edges = np.histogram(x, bins=min(40, max(10, int(np.sqrt(len(x))))))
        qs = np.linspace(0.01, 0.99, 50)
        kde_x = np.linspace(x.min(), np.percentile(x, 99.5), 120)
        dens = stats.gaussian_kde(x if len(x) < 20000 else RNG.choice(x, 20000, replace=False))(kde_x)
        dist[name] = {
            "histogram": {"counts": hist, "edges": edges}, "kde": {"x": kde_x, "density": dens},
            "ecdf": {"x": np.quantile(x, np.linspace(0, 1, 101)), "p": np.linspace(0, 1, 101)},
            "qq_normal": {"theoretical": stats.norm.ppf(qs), "sample": np.quantile(x, qs)},
            "boxplot": {"q1": np.percentile(x, 25), "median": np.median(x), "q3": np.percentile(x, 75), "whisker_low": x[x >= np.percentile(x, 25) - 1.5 * stats.iqr(x)].min(),
                        "whisker_high": x[x <= np.percentile(x, 75) + 1.5 * stats.iqr(x)].max(), "outliers": int(((x < np.percentile(x, 25) - 1.5 * stats.iqr(x)) | (x > np.percentile(x, 75) + 1.5 * stats.iqr(x))).sum())},
            "normality": {"shapiro_p_on_sample": shapiro_p(x), "skewness": stats.skew(x), "note": "large samples reject normality for trivial deviations; use Q-Q plot + skewness"},
        }
    # violin data (age by season x medalist)
    viol = {}
    for (s, m), g in age.groupby(["season", "is_medalist"]):
        x = g.age.values
        xs = np.linspace(14, 60, 80)
        viol[f"{s}_{'medalist' if m else 'non_medalist'}"] = {"x": xs, "density": stats.gaussian_kde(x if len(x) < 15000 else RNG.choice(x, 15000, replace=False))(xs), "n": int(len(x)), "median": float(np.median(x))}
    # Pareto: cumulative share of medals by NOC
    tot = pan.groupby("noc_code").total.sum().sort_values(ascending=False)
    par = pd.DataFrame({"noc_code": tot.index, "medals": tot.values, "cum_share": (tot.cumsum() / tot.sum()).values})
    gini = float((np.abs(tot.values[:, None] - tot.values[None, :]).sum()) / (2 * len(tot) ** 2 * tot.mean()))
    dist["violin_age"] = viol
    dist["pareto_medals_by_noc"] = {"rows": par.head(40), "noc_for_50pct": int((par.cum_share < .5).sum() + 1), "noc_for_80pct": int((par.cum_share < .8).sum() + 1), "gini": gini}
    save(con, "stats", "distributions", "Distribution analysis", dist, "How are age, medals, participation and results distributed?")


# ------------------------------------------------------------------ 3 correlation
def correlations(con, part, pan, ed):
    out = {}
    p = pan.dropna(subset=["prev_total"]).copy()
    p["log_athletes"] = np.log1p(p.athletes)
    cols = ["athletes", "sports", "is_host", "prev_total", "appearance_no", "total"]
    for method in ("pearson", "spearman", "kendall"):
        sub = p[cols] if method != "kendall" else p[cols].sample(min(len(p), 4000), random_state=1)
        c = sub.corr(method=method)
        pv = pd.DataFrame(index=cols, columns=cols, dtype=float)
        for a in cols:
            for b in cols:
                f = {"pearson": stats.pearsonr, "spearman": stats.spearmanr, "kendall": stats.kendalltau}[method]
                pv.loc[a, b] = 0.0 if a == b else f(sub[a], sub[b])[1]
        out[method] = {"variables": cols, "matrix": c, "p_values": pv, "n": int(len(sub))}
    pairs = []
    ps = part.dropna(subset=["age"])
    for name, x, y in [
        ("athlete age vs medal (point-biserial)", ps.age, ps.is_medalist),
        ("country athletes vs medals", p.athletes, p.total), ("country sports entered vs medals", p.sports, p.total),
        ("host flag vs medals", p.is_host, p.total), ("previous-edition medals vs medals", p.prev_total, p.total),
    ]:
        r, pr = stats.pearsonr(x, y)
        rho, ps_ = stats.spearmanr(x, y)
        # Fisher CI for pearson
        z = np.arctanh(r); se = 1 / np.sqrt(len(x) - 3)
        pairs.append({"pair": name, "n": int(len(x)), "pearson_r": r, "pearson_ci": [float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se))], "pearson_p": pr, "spearman_rho": rho, "spearman_p": ps_})
    # athlete experience vs medal
    careers = pd.read_sql("SELECT athlete_id, games_count, medals FROM gold_athlete_career", con)
    rho, pr = stats.spearmanr(careers.games_count, careers.medals)
    pairs.append({"pair": "athlete editions competed vs career medals", "n": int(len(careers)), "spearman_rho": rho, "spearman_p": pr, "pearson_r": float(careers.games_count.corr(careers.medals))})
    # gender participation vs time
    for s in ("summer", "winter"):
        d = ed[ed.season == s]
        rho, pr = stats.spearmanr(d.year, d.female_share)
        pairs.append({"pair": f"female share vs year ({s})", "n": int(len(d)), "spearman_rho": rho, "spearman_p": pr})
    out["pairs"] = pairs
    out["warning"] = "Correlation does not establish causation. Country-edition rows are not independent (the same NOC repeats), so p-values are optimistic; see regression with clustered errors."
    save(con, "stats", "correlations", "Correlation analysis", out, "Which variables move together?")


# ------------------------------------------------------------------ 4 hypothesis tests
def hypothesis_tests(con, part, pan, ed):
    tests = []
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    def add(**k):
        k.setdefault("ci_level", .95)
        tests.append(k)

    # ---- H1 host effect (paired within NOC & season)
    pr = pd.read_sql("SELECT * FROM gold_host_performance WHERE mean_non_host_medals IS NOT NULL", con)
    d = (pr.host_medals - pr.mean_non_host_medals).values
    sw = shapiro_p(d)
    t = stats.ttest_rel(pr.host_medals, pr.mean_non_host_medals)
    w = stats.wilcoxon(d)
    tcrit = stats.t.ppf(.975, len(d) - 1)
    ci = (d.mean() - tcrit * d.std(ddof=1) / np.sqrt(len(d)), d.mean() + tcrit * d.std(ddof=1) / np.sqrt(len(d)))
    dz = d.mean() / d.std(ddof=1)
    use_w = sw is not None and sw < ALPHA
    add(test_id="H1_host_vs_non_host", family="confirmatory", research_question="Do host countries win a different number of medals when hosting than in their other editions?",
        null_hypothesis="Mean (host medals - same NOC's mean non-host medals) = 0", alternative_hypothesis="The mean difference is not 0",
        method="Wilcoxon signed-rank (primary); paired t-test reported" if use_w else "Paired t-test (primary); Wilcoxon reported",
        why_this_test="Each host is compared with its OWN other editions of the same season (matched pairs). Shapiro-Wilk on the differences decides between the rank test and the t-test.",
        assumptions={"n_pairs": len(d), "shapiro_p_differences": sw, "paired_t": {"t": t.statistic, "p": t.pvalue}, "wilcoxon": {"W": w.statistic, "p": w.pvalue}, "mean_difference": d.mean(), "median_difference": float(np.median(d))},
        n=len(d), statistic=float(w.statistic if use_w else t.statistic), p_value=float(w.pvalue if use_w else t.pvalue), ci_low=float(ci[0]), ci_high=float(ci[1]),
        effect_size_name="Cohen's d_z (paired)", effect_size=float(dz),
        interpretation=interp(w.pvalue if use_w else t.pvalue, f"On average hosts won {d.mean():.1f} more medals when hosting", "d_z", dz, .2, .8),
        caveats="Only 35 host-editions; hosts are not randomly chosen (they are often strong NOCs) and some NOCs host once, so the comparison mean uses few non-host editions. Not causal.")

    # ---- H2 age: medalists vs non-medalists
    ps = part.dropna(subset=["age"])
    a, b = ps[ps.is_medalist == 1].age.values, ps[ps.is_medalist == 0].age.values
    mw = stats.mannwhitneyu(a, b, alternative="two-sided")
    wt = stats.ttest_ind(a, b, equal_var=False)
    lev = stats.levene(a, b)
    diff = a.mean() - b.mean()
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    rbc = 1 - 2 * mw.statistic / (len(a) * len(b))  # rank-biserial (sign: positive => medalists older)
    add(test_id="H2_age_medalists_vs_others", family="confirmatory", research_question="Is the age of medal-winning athletes different from athletes who did not medal?",
        null_hypothesis="Age distributions of medalists and non-medalists are identical (no stochastic dominance)", alternative_hypothesis="One group tends to be older",
        method="Mann-Whitney U (primary); Welch t-test and bootstrap CI reported",
        why_this_test="Ages are right-skewed with many ties, so a rank test avoids the normality assumption; Welch handles unequal variances; n is huge so the effect size matters more than p.",
        assumptions={"n_medalists": len(a), "n_others": len(b), "mean_medalists": a.mean(), "mean_others": b.mean(), "levene_p": lev.pvalue, "welch_t": wt.statistic, "welch_p": wt.pvalue,
                     "skew_medalists": stats.skew(a), "skew_others": stats.skew(b)},
        n=len(a) + len(b), statistic=float(mw.statistic), p_value=float(mw.pvalue), ci_low=float(diff - 1.96 * se), ci_high=float(diff + 1.96 * se),
        effect_size_name="Cohen's d (and rank-biserial in assumptions)", effect_size=float(cohens_d(a, b)),
        interpretation=interp(mw.pvalue, f"Medalists are {diff:+.2f} years older on average", "d", cohens_d(a, b), .2, .5) + f" Rank-biserial r={rbc:.3f}.",
        caveats="Age is missing for ~0.4% of participations. A participation, not a person, is the unit (one athlete can appear many times), so observations are not independent.")
    tests[-1]["assumptions"]["rank_biserial"] = rbc
    tests[-1]["assumptions"]["bootstrap_ci_mean_diff"] = boot_ci(lambda x, y: x.mean() - y.mean(), RNG.choice(a, 20000), RNG.choice(b, 20000), n=500)

    # ---- H3 female participation trend
    h3 = []
    for s in ("summer", "winter"):
        dd = ed[ed.season == s].sort_values("year")
        X = sm.add_constant((dd.year - dd.year.min()) / 4.0)  # per 4-year cycle
        m = sm.OLS(dd.female_share, X).fit()
        rho = stats.spearmanr(dd.year, dd.female_share)
        ci = m.conf_int().iloc[1]
        h3.append((s, len(dd), m.params.iloc[1], m.pvalues.iloc[1], ci[0], ci[1], rho.statistic, rho.pvalue, m.rsquared, durbin_watson(m.resid)))
    for s, n, slope, p_, lo, hi, rho, rp, r2, dw in h3:
        add(test_id=f"H3_female_trend_{s}", family="confirmatory", research_question=f"Has the female share of {s} Olympic athletes changed across editions?",
            null_hypothesis="Slope of female share on edition index = 0", alternative_hypothesis="Slope != 0 (share changes over time)",
            method="OLS linear trend on edition index (per 4 years) with Spearman rank correlation as a check",
            why_this_test="One observation per edition, ordered in time; a trend test is appropriate. Edition index (not calendar year) is the observation index because editions are discrete, irregular events.",
            assumptions={"spearman_rho": rho, "spearman_p": rp, "r_squared": r2, "durbin_watson": dw, "note": "Durbin-Watson well below 2 would suggest positive autocorrelation"},
            n=n, statistic=float(slope / ((hi - lo) / (2 * stats.t.ppf(.975, n - 2)))), p_value=float(p_), ci_low=float(lo), ci_high=float(hi), effect_size_name="slope (share points per 4 yrs)", effect_size=float(slope),
            interpretation=f"Female share changes by {slope * 100:+.2f} percentage points per edition (95% CI {lo * 100:+.2f} to {hi * 100:+.2f}); " + ("statistically significant." if p_ < ALPHA else "not statistically significant."),
            caveats="Time-series regression with autocorrelated residuals understates uncertainty; n is small (17-18 editions).")

    # ---- H4 summer vs winter (normalised)
    pe = pan.merge(ed[["games_id", "events", "medal_events"]], on="games_id")
    pe["medals_per_medal_event"] = pe.total / pe.medal_events
    wins = pe[pe.total > 0]
    x, y = wins[wins.season == "summer"].medals_per_medal_event.values, wins[wins.season == "winter"].medals_per_medal_event.values
    mw = stats.mannwhitneyu(x, y)
    ks = stats.ks_2samp(x, y)
    rbc = 1 - 2 * mw.statistic / (len(x) * len(y))
    # chi-square: share of participating NOC-editions that win >=1 medal, by season
    tab = pd.crosstab(pe.season, pe.total > 0)
    chi = stats.chi2_contingency(tab)
    v = np.sqrt(chi.statistic / (tab.values.sum() * (min(tab.shape) - 1)))
    add(test_id="H4a_medal_distribution_summer_vs_winter", family="confirmatory", research_question="Do medal-winning NOCs take a different share of the medal programme in Summer vs Winter?",
        null_hypothesis="The distribution of (medals / medal events) per medal-winning NOC-edition is the same in Summer and Winter", alternative_hypothesis="The distributions differ",
        method="Mann-Whitney U (KS test as a shape check)", why_this_test="Normalising medals by the number of medal events removes the size difference of the two programmes; the variable is heavily right-skewed so a rank test is used.",
        assumptions={"ks_D": ks.statistic, "ks_p": ks.pvalue, "median_summer": float(np.median(x)), "median_winter": float(np.median(y)), "n_summer": len(x), "n_winter": len(y)},
        n=len(x) + len(y), statistic=float(mw.statistic), p_value=float(mw.pvalue), ci_low=None, ci_high=None, effect_size_name="rank-biserial", effect_size=float(rbc),
        interpretation=interp(mw.pvalue, "Medal shares per medal event differ between seasons", "rank-biserial", rbc, .1, .3), caveats="NOC-edition rows are not independent. Only NOCs with >=1 medal are included.")
    add(test_id="H4b_medal_winning_rate_summer_vs_winter", family="confirmatory", research_question="Is the probability that a participating NOC wins at least one medal different in Summer vs Winter?",
        null_hypothesis="Season and 'wins >=1 medal' are independent", alternative_hypothesis="They are associated", method="Chi-square test of independence (Cramer's V effect size)",
        why_this_test="Two categorical variables with large expected counts in every cell.", assumptions={"contingency": tab.to_dict(), "min_expected": float(chi.expected_freq.min())},
        n=int(tab.values.sum()), statistic=float(chi.statistic), p_value=float(chi.pvalue), ci_low=None, ci_high=None, effect_size_name="Cramer's V", effect_size=float(v),
        interpretation=interp(chi.pvalue, "Share of participating NOCs that medal differs by season", "V", v, .1, .3), caveats="Repeated NOCs across editions violate independence.")

    # ---- H5 results across editions (speed skating / alpine events with numeric times)
    res = pd.read_sql("""SELECT g.year, e.sport_name, e.event_name, e.medal, e.result_value, e.result_unit FROM gold_event_results e JOIN games g USING(games_id)
                         WHERE e.result_unit='s' AND e.result_value IS NOT NULL AND e.medal IS NOT NULL AND e.sport_name='Speed Skating' AND e.event_name='500 metres, Men'""", con)
    if res.empty:
        res = pd.read_sql("SELECT g.year, e.sport_name, e.event_name, e.medal, e.result_value FROM gold_event_results e JOIN games g USING(games_id) WHERE e.result_unit='s' AND e.result_value IS NOT NULL AND e.medal IS NOT NULL", con)
    ev = res.groupby(["sport_name", "event_name"]).year.nunique().sort_values(ascending=False)
    sport, event = ev.index[0]
    res = pd.read_sql("SELECT g.year, e.result_value FROM gold_event_results e JOIN games g USING(games_id) WHERE e.result_unit='s' AND e.sport_name=? AND e.event_name=? AND e.result_value IS NOT NULL AND e.medal IS NOT NULL", con, params=(sport, event))
    res["decade"] = (res.year // 10 * 10).astype(str) + "s"
    groups = [g.result_value.values for _, g in res.groupby("decade") if len(g) >= 3]
    names = [k for k, g in res.groupby("decade") if len(g) >= 3]
    f = stats.f_oneway(*groups)
    kw = stats.kruskal(*groups)
    k, N = len(groups), sum(len(g) for g in groups)
    eps2 = (kw.statistic - k + 1) / (N - k)
    tuk = pairwise_tukeyhsd(res[res.decade.isin(names)].result_value, res[res.decade.isin(names)].decade)
    lev = stats.levene(*groups)
    ss_b = sum(len(g) * (g.mean() - np.concatenate(groups).mean()) ** 2 for g in groups); ss_t = ((np.concatenate(groups) - np.concatenate(groups).mean()) ** 2).sum()
    add(test_id="H5_results_across_decades", family="confirmatory", research_question=f"Do medal-winning times in '{sport}: {event}' differ across decades?",
        null_hypothesis="Mean (and distribution of) medal-winning times are equal in every decade", alternative_hypothesis="At least one decade differs",
        method="Kruskal-Wallis (primary), one-way ANOVA and Tukey HSD post-hoc reported", why_this_test="Podium times are few per decade and are not normally distributed across a strong time trend; Kruskal-Wallis needs no normality, ANOVA/Tukey identify which decades differ.",
        assumptions={"event": f"{sport}: {event}", "decades": names, "levene_p": lev.pvalue, "anova_F": f.statistic, "anova_p": f.pvalue, "tukey_significant_pairs": int(tuk.reject.sum()), "tukey_pairs": int(len(tuk.reject))},
        n=int(N), statistic=float(kw.statistic), p_value=float(kw.pvalue), ci_low=None, ci_high=None, effect_size_name="epsilon-squared (Kruskal-Wallis); eta-squared in assumptions", effect_size=float(eps2),
        interpretation=interp(kw.pvalue, "Podium times differ across decades", "epsilon^2", eps2, .06, .14), caveats="Chosen event = the one with the most editions of numeric podium times; one event only. Times fall with technology/ice and rule changes (not just athlete ability).")
    tests[-1]["assumptions"]["eta_squared"] = ss_b / ss_t

    # ---- supplementary (not in the corrected family): gender x medal
    gm = pd.crosstab(part[part.gender.isin(["M", "F"])].gender, part[part.gender.isin(["M", "F"])].is_medalist)
    chi = stats.chi2_contingency(gm)
    add(test_id="S1_gender_vs_medal_rate", family="supplementary", research_question="Is the share of participations that end in a medal different for men and women?",
        null_hypothesis="Gender and medal outcome are independent", alternative_hypothesis="They are associated", method="Chi-square test of independence (Cramer's V)", why_this_test="Two categorical variables, huge counts.",
        assumptions={"contingency": gm.to_dict()}, n=int(gm.values.sum()), statistic=float(chi.statistic), p_value=float(chi.pvalue), ci_low=None, ci_high=None, effect_size_name="Cramer's V",
        effect_size=float(np.sqrt(chi.statistic / gm.values.sum())), interpretation=interp(chi.pvalue, "Medal rate differs by gender", "V", np.sqrt(chi.statistic / gm.values.sum()), .1, .3),
        caveats="Team events count each team member; the number of medal opportunities per gender differs by era.")

    # Holm correction across the confirmatory family
    conf = [t for t in tests if t["family"] == "confirmatory"]
    adj = multipletests([t["p_value"] for t in conf], method="holm")[1]
    for t, p in zip(conf, adj):
        t["p_adjusted_holm"] = float(p)
        t["interpretation"] += f" Holm-adjusted p={p:.3g} across {len(conf)} confirmatory tests."
    con.execute("DELETE FROM analytics_hypothesis_tests")
    for t in tests:
        con.execute("INSERT INTO analytics_hypothesis_tests VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            t["test_id"], t["family"], t["research_question"], t["null_hypothesis"], t["alternative_hypothesis"], t["method"], t["why_this_test"], json.dumps(t["assumptions"], default=float),
            t["n"], t["statistic"], t["p_value"], t.get("p_adjusted_holm"), t.get("ci_low"), t.get("ci_high"), t["ci_level"], t["effect_size_name"], t["effect_size"], t["interpretation"], t["caveats"], dt.datetime.now(dt.timezone.utc).isoformat()))
    con.commit()
    save(con, "stats", "hypothesis_tests", "Hypothesis tests", tests, "Formal tests with assumptions, effect sizes and multiple-testing correction")
    return tests


# ------------------------------------------------------------------ 5 regression
def regression(con, part, pan, ed):
    out = {}
    p = pan.dropna(subset=["prev_total"]).copy()
    p["log_athletes"] = np.log1p(p.athletes)
    p["log_prev"] = np.log1p(p.prev_total)

    def tab(m):
        ci = m.conf_int()
        return [{"term": k, "coef": float(m.params[k]), "se": float(m.bse[k]), "p": float(m.pvalues[k]), "ci_low": float(ci.loc[k, 0]), "ci_high": float(ci.loc[k, 1])} for k in m.params.index]

    # ---- medal counts: Poisson vs negative binomial (counts, non-negative, overdispersed)
    form = "total ~ log_athletes + sports + is_host + log_prev + C(season)"
    pois = smf.glm(form, p, family=sm.families.Poisson()).fit(cov_type="cluster", cov_kwds={"groups": p.noc_code.astype("category").cat.codes})
    disp = float(pois.pearson_chi2 / pois.df_resid)
    nb = smf.glm(form, p, family=sm.families.NegativeBinomial(alpha=max(disp / 4, .1))).fit()
    # estimate alpha by ML via discrete NB for honesty
    try:
        nbd = smf.negativebinomial(form, p).fit(disp=False, maxiter=200)
        nbm = {"alpha": float(nbd.params["alpha"]), "aic": float(nbd.aic), "coefs": [{"term": k, "coef": float(nbd.params[k]), "se": float(nbd.bse[k]), "p": float(nbd.pvalues[k]), "rate_ratio": float(np.exp(nbd.params[k]))} for k in nbd.params.index if k != "alpha"]}
    except Exception as e:  # noqa: BLE001
        nbm = {"error": str(e)}
    out["medal_counts"] = {"formula": form, "n": int(len(p)), "poisson_cluster_robust": {"coefs": tab(pois), "aic": float(pois.aic), "pearson_dispersion": disp,
                           "overdispersed": disp > 1.5, "note": "dispersion >> 1 means variance exceeds mean: plain Poisson SEs are too small; use cluster-robust SEs or negative binomial"},
                           "negative_binomial_ml": nbm, "mcfadden_pseudo_r2_poisson": float(1 - pois.deviance / pois.null_deviance),
                           "interpretation": "Rate ratios = exp(coef): multiplicative change in expected medals for a one-unit change, holding other terms fixed. Association, not causation."}

    # ---- OLS: log(1+medals) with diagnostics
    ols = smf.ols("np.log1p(total) ~ log_athletes + sports + is_host + log_prev + C(season)", p).fit(cov_type="HC3")
    ols_plain = smf.ols("np.log1p(total) ~ log_athletes + sports + is_host + log_prev + C(season)", p).fit()
    resid = ols_plain.resid
    from statsmodels.stats.diagnostic import het_breuschpagan
    bp = het_breuschpagan(resid, ols_plain.model.exog)
    out["ols_log_medals"] = {"n": int(len(p)), "coefs_hc3": tab(ols), "r2": float(ols_plain.rsquared), "adj_r2": float(ols_plain.rsquared_adj), "diagnostics": {
        "breusch_pagan_p": float(bp[1]), "durbin_watson": float(durbin_watson(resid)), "residual_skew": float(stats.skew(resid)), "residual_shapiro_p_sample": shapiro_p(resid),
        "note": "heteroscedasticity expected -> HC3 robust errors reported"}, "residual_vs_fitted": pd.DataFrame({"fitted": ols_plain.fittedvalues, "resid": resid}).sample(min(500, len(p)), random_state=1)}

    # ---- multiple regression: host effect (athletes held constant)
    # ---- logistic: medal ~ age + experience (athlete-level, chronological features only)
    ps = part.dropna(subset=["age"]).sort_values(["athlete_id", "year"]).copy()
    ps["prior_games"] = ps.groupby("athlete_id").games_id.transform(lambda s: pd.factorize(s)[0])  # number of earlier distinct Games for that athlete
    ps["age_c"] = ps.age - 26
    ps = ps[ps.gender.isin(["M", "F"])].sample(min(len(ps), 120000), random_state=3)
    lg = smf.logit("is_medalist ~ age_c + I(age_c**2) + prior_games + C(gender) + C(season) + is_host_noc", ps).fit(disp=False)
    from sklearn.metrics import roc_auc_score
    ci = lg.conf_int()
    out["logistic_medal"] = {"n": int(len(ps)), "coefs": [{"term": k, "coef": float(lg.params[k]), "se": float(lg.bse[k]), "p": float(lg.pvalues[k]), "odds_ratio": float(np.exp(lg.params[k])),
                             "or_ci": [float(np.exp(ci.loc[k, 0])), float(np.exp(ci.loc[k, 1]))]} for k in lg.params.index], "pseudo_r2": float(lg.prsquared),
                             "auc_in_sample": float(roc_auc_score(ps.is_medalist, lg.predict(ps))), "note": "In-sample association model (not a forecast); see ML section for chronological validation. Observations repeat athletes."}

    # ---- growth of female participation (OLS per season)
    gr = {}
    for s in ("summer", "winter"):
        d = ed[ed.season == s].sort_values("year").reset_index(drop=True)
        d["idx"] = np.arange(len(d))
        m = smf.ols("female_share ~ idx", d).fit()
        gr[s] = {"coefs": tab(m), "r2": float(m.rsquared), "adj_r2": float(m.rsquared_adj), "n": int(len(d)), "durbin_watson": float(durbin_watson(m.resid)),
                 "fitted": pd.DataFrame({"year": d.year, "actual": d.female_share, "fitted": m.fittedvalues})}
    out["female_share_growth"] = gr
    # ---- host effect with country fixed effects (within-NOC)
    big = p[p.noc_code.isin(p.groupby("noc_code").size()[lambda s: s >= 6].index)]
    fe = smf.ols("np.log1p(total) ~ is_host + log_athletes + C(noc_code) + C(season)", big).fit(cov_type="cluster", cov_kwds={"groups": big.noc_code.astype("category").cat.codes})
    out["host_effect_fixed_effects"] = {"n": int(len(big)), "host_coef_log1p_medals": float(fe.params["is_host"]), "se": float(fe.bse["is_host"]), "p": float(fe.pvalues["is_host"]),
                                         "ci": [float(x) for x in fe.conf_int().loc["is_host"]], "reading": "approx. % change in (1+medals) in the hosting edition vs the same NOC's other editions, given athletes entered",
                                         "note": "NOC fixed effects + cluster-robust SEs; hosting is non-random."}
    save(con, "stats", "regression", "Regression models", out, "How are medals, age and participation related, controlling for other factors?")


# ------------------------------------------------------------------ 6 time series
def time_series(con, ed):
    out = {}
    for s in ("summer", "winter"):
        d = ed[ed.season == s].sort_values("year").reset_index(drop=True)
        d["edition_index"] = np.arange(len(d))
        res = {}
        for var in ("athletes", "events", "nocs", "female_share", "medal_awards", "sports"):
            y = d[var].astype(float).values
            ma = pd.Series(y).rolling(3, min_periods=1).mean().values
            tr = sm.OLS(y, sm.add_constant(d.edition_index)).fit()
            holt = sm.tsa.Holt(y, initialization_method="estimated").fit()
            fc = holt.forecast(1)
            resid_sd = float(np.std(y - holt.fittedvalues, ddof=2))
            # change-point: best single mean shift (binary segmentation, one split) by SSE reduction; accept if BIC improves
            best = None
            n = len(y)
            for k in range(3, n - 2):
                sse = ((y[:k] - y[:k].mean()) ** 2).sum() + ((y[k:] - y[k:].mean()) ** 2).sum()
                if best is None or sse < best[0]:
                    best = (sse, k)
            sse0 = ((y - y.mean()) ** 2).sum()
            bic0 = n * np.log(sse0 / n + 1e-12) + 1 * np.log(n)
            bic1 = n * np.log(best[0] / n + 1e-12) + 3 * np.log(n)
            res[var] = {"years": d.year.tolist(), "values": y.tolist(), "moving_average_3": ma.tolist(), "trend_slope_per_edition": float(tr.params.iloc[1]), "trend_p": float(tr.pvalues.iloc[1]),
                        "trend_r2": float(tr.rsquared), "holt_fitted": holt.fittedvalues.tolist(),
                        "holt_next_edition_point": float(fc[0]), "holt_next_edition_interval_approx": [float(fc[0] - 1.96 * resid_sd), float(fc[0] + 1.96 * resid_sd)],
                        "change_point": {"index": int(best[1]), "year_after_change": int(d.year.iloc[best[1]]), "bic_no_change": float(bic0), "bic_one_change": float(bic1), "supported_by_bic": bool(bic1 < bic0)}}
        # ARIMA only where justified: log-athletes differenced, n small -> report with a clear caveat
        try:
            from statsmodels.tsa.arima.model import ARIMA
            a = ARIMA(np.log(d.athletes.astype(float)), order=(0, 1, 0), trend="t").fit()
            res["arima_log_athletes_(0,1,0)+drift"] = {"drift_log_per_edition": float(a.params.iloc[0]), "aic": float(a.aic),
                                                       "note": "random walk with drift: the only ARIMA order identifiable from 17-18 points; SARIMA is NOT justified (editions are not a seasonal series)"}
        except Exception as e:  # noqa: BLE001
            res["arima_error"] = str(e)
        out[s] = res
    out["method_note"] = ("Editions, not calendar years, are the observation index (irregular spacing: 1994 Winter, Tokyo 2020 held in 2021). With n=17-18 per season, classical decomposition "
                          "and SARIMA are not justified; trend regression, moving averages, Holt smoothing and a one-change-point mean-shift test are reported instead.")
    save(con, "stats", "time_series", "Time-series analysis", out, "What are the long-run trends in participation, events, medals and gender balance?")


def run(con):
    part, cm, ed, pan = frames(con)
    descriptive_and_distribution(con, part, pan, ed)
    correlations(con, part, pan, ed)
    tests = hypothesis_tests(con, part, pan, ed)
    regression(con, part, pan, ed)
    time_series(con, ed)
    return [t["test_id"] for t in tests]
