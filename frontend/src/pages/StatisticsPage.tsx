import { useState } from "react";
import { useApi } from "../lib/api";
import { Async, ChartCard, Note, PageHeader, Select, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { Bars, BoxStrip, Heat, LineSeries, Pareto, Scatter2, Violin } from "../charts/charts";
import { fmtNum, fmtP, PALETTE } from "../lib/fmt";

import { StatisticsFindings } from "../components/analytics/KeyFindings";
import { VizSection } from "../viz/VizGallery";
const DESC_ROWS = ["n", "mean", "median", "mode", "min", "max", "range", "variance", "std", "q1", "q3", "iqr", "p5", "p10", "p90", "p95", "p99", "skewness", "excess_kurtosis", "cv"];

export default function StatisticsPage() {
  const [tab, setTab] = useState("explore");
  return (
    <div>
      <PageHeader title="Statistical analysis" subtitle="Reproducible, assumption-checked statistics on the Gold marts. Every test reports its hypotheses, sample size, statistic, p-value, confidence interval, effect size and a plain-language reading. Correlation is never presented as causation." />
      <StatisticsFindings />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "explore", label: "Interactive explorer" }, { id: "descriptive", label: "Descriptive" }, { id: "distributions", label: "Distributions" }, { id: "correlation", label: "Correlation" }, { id: "hypothesis", label: "Hypothesis tests" }, { id: "regression", label: "Regression" }, { id: "timeseries", label: "Time series" }, { id: "outliers", label: "Outliers" }]} />
      {tab === "explore" && <Explore />}
      {tab === "descriptive" && <Descriptive />}
      {tab === "distributions" && <Distributions />}
      {tab === "correlation" && <Correlation />}
      {tab === "hypothesis" && <Hypothesis />}
      {tab === "regression" && <Regression />}
      {tab === "timeseries" && <TimeSeries />}
      {tab === "outliers" && <Outliers />}
      <VizSection page="statistics" />
    </div>
  );
}

function Explore() {
  const [f, setF] = useState({ season: "", gender: "", sport: "", noc: "", games_id: "" });
  const set = (k: string) => (v: string) => setF((p) => ({ ...p, [k]: v }));
  const sports = useApi<any[]>("/sports");
  const games = useApi<any[]>("/games");
  const q = useApi<any>("/statistics/explore", f);
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select label="Season" value={f.season} onChange={set("season")} options={[{ value: "summer", label: "Summer" }, { value: "winter", label: "Winter" }]} />
        <Select label="Gender" value={f.gender} onChange={set("gender")} options={[{ value: "M", label: "Men" }, { value: "F", label: "Women" }]} />
        <Select label="Sport" value={f.sport} onChange={set("sport")} options={(sports.data ?? []).map((s: any) => ({ value: s.sport_name, label: s.sport_name }))} />
        <Select label="Edition" value={f.games_id} onChange={set("games_id")} options={(games.data ?? []).map((g: any) => ({ value: g.games_id, label: `${g.year} ${g.season}` }))} />
        <input className="input w-20 uppercase" placeholder="NOC" maxLength={3} value={f.noc} onChange={(e) => set("noc")(e.target.value.toUpperCase())} aria-label="NOC" />
      </div>
      <Async q={q}>{(d) => d.message ? <Note tone="warn">{d.message}</Note> : (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Athlete age distribution" subtitle={`n = ${d.n.toLocaleString()} participations with a recorded age`}>
            <Bars data={d.histogram} x="age" xLabel="Age (2-year bins)" yLabel="Participations" series={[{ key: "count", color: "#0085C7" }]} maxBars={60} />
          </ChartCard>
          <ChartCard title="Descriptive statistics of age">
            <DataTable rows={DESC_ROWS.filter((k) => d.descriptive[k] !== undefined).map((k) => ({ statistic: k, value: fmtNum(d.descriptive[k], 3) }))} columns={[{ key: "statistic", width: 140 }, { key: "value", align: "right" }]} height={330} />
          </ChartCard>
          {d.medalist_vs_others ? (
            <div className="xl:col-span-2"><ChartCard title="Medalists vs other participants (this slice)" height={120}>
              <div className="grid gap-3 text-sm md:grid-cols-4">
                {[["Medalists / others", `${d.medalist_vs_others.n_medalists.toLocaleString()} / ${d.medalist_vs_others.n_others.toLocaleString()}`], ["Mean age", `${fmtNum(d.medalist_vs_others.mean_medalists, 2)} vs ${fmtNum(d.medalist_vs_others.mean_others, 2)}`],
                  ["Difference (95% CI)", `${fmtNum(d.medalist_vs_others.mean_difference, 2)} (${fmtNum(d.medalist_vs_others.ci95_mean_difference[0], 2)} to ${fmtNum(d.medalist_vs_others.ci95_mean_difference[1], 2)})`], ["Mann-Whitney p", fmtP(d.medalist_vs_others.p_value)],
                  ["Cohen's d", fmtNum(d.medalist_vs_others.cohens_d, 3)], ["Rank-biserial r", fmtNum(d.medalist_vs_others.rank_biserial, 3)], ["Welch t (p)", `${fmtNum(d.medalist_vs_others.welch_t, 2)} (${fmtP(d.medalist_vs_others.welch_p)})`], ["Medal rate", `${fmtNum(100 * d.medal_rate, 1)}%`]].map(([k, v]) => <div key={k} className="rounded-lg bg-surface2 p-3"><div className="text-[11px] uppercase tracking-wider text-muted">{k}</div><div className="tabnum font-medium">{v}</div></div>)}
              </div>
              <p className="mt-2 text-xs text-muted">{d.medalist_vs_others.note}</p>
            </ChartCard></div>) : <Note>Fewer than 5 medalists or non-medalists in this slice - no comparison test is shown.</Note>}
        </div>)}</Async>
    </div>
  );
}

function Descriptive() {
  const q = useApi<any>("/statistics", { section: "descriptive" });
  return (
    <Async q={q}>{({ data }) => {
      const vars = Object.keys(data);
      return (
        <ChartCard title="Descriptive statistics" subtitle="Mean, median, mode, range, variance, SD, quartiles, IQR, percentiles, skewness, excess kurtosis, coefficient of variation" height={500}>
          <DataTable height={520} rows={DESC_ROWS.map((s) => ({ statistic: s, ...Object.fromEntries(vars.map((v) => [v, fmtNum(data[v][s], 3)])) }))}
            columns={[{ key: "statistic", width: 130 }, ...vars.map((v) => ({ key: v, header: v.replace(/_/g, " "), align: "right" as const, width: 150 }))]} />
        </ChartCard>);
    }}</Async>
  );
}

function Distributions() {
  const q = useApi<any>("/statistics", { section: "distributions" });
  const [v, setV] = useState("athlete_age");
  return (
    <Async q={q}>{({ data }) => {
      const d = data[v];
      const hist = d.histogram.counts.map((c: number, i: number) => ({ x: Math.round((d.histogram.edges[i] + d.histogram.edges[i + 1]) / 2 * 10) / 10, count: c }));
      const vv = data.violin_age;
      return (
        <div>
          <div className="mb-3"><Select label="Variable" allLabel="–" value={v} onChange={(x) => setV(x || "athlete_age")} options={["athlete_age", "country_edition_total_medals", "country_edition_athletes"].map((k) => ({ value: k, label: k.replace(/_/g, " ") }))} /></div>
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Histogram" subtitle={`skewness ${fmtNum(d.normality.skewness, 2)}; Shapiro-Wilk p (sample) ${fmtP(d.normality.shapiro_p_on_sample)}`}><Bars data={hist} x="x" series={[{ key: "count", color: "#0085C7" }]} maxBars={60} /></ChartCard>
            <ChartCard title="Density (Gaussian KDE)"><LineSeries data={d.kde.x.map((x: number, i: number) => ({ x: Math.round(x * 10) / 10, density: d.kde.density[i] }))} x="x" series={[{ key: "density", color: "#F4C300" }]} /></ChartCard>
            <ChartCard title="ECDF" subtitle="Empirical cumulative distribution"><LineSeries data={d.ecdf.x.map((x: number, i: number) => ({ x, p: d.ecdf.p[i] }))} x="x" series={[{ key: "p", name: "P(X ≤ x)", color: "#009F3D" }]} /></ChartCard>
            <ChartCard title="Normal Q-Q plot" subtitle="Points on the diagonal would indicate normality"><Scatter2 data={d.qq_normal.theoretical.map((t: number, i: number) => ({ theoretical: t, sample: d.qq_normal.sample[i] }))} x="theoretical" y="sample" xLabel="Theoretical normal quantile" yLabel="Sample quantile" /></ChartCard>
            <ChartCard title="Box plot" height={140}><BoxStrip items={[{ label: v.replace(/_/g, " "), q1: d.boxplot.q1, median: d.boxplot.median, q3: d.boxplot.q3, low: d.boxplot.whisker_low, high: d.boxplot.whisker_high, outliers: d.boxplot.outliers }]} /></ChartCard>
            <ChartCard title="Violin: age by season and outcome" height={300}><Violin xLabel="Age" items={Object.entries<any>(vv).map(([k, x], i) => ({ label: `${k.replace("_", " ")} (n=${x.n.toLocaleString()})`, x: x.x, density: x.density, median: x.median, color: PALETTE[i] }))} /></ChartCard>
            <div className="xl:col-span-2"><ChartCard title="Pareto: medal concentration across NOCs" subtitle={`${data.pareto_medals_by_noc.noc_for_50pct} NOCs account for 50% and ${data.pareto_medals_by_noc.noc_for_80pct} for 80% of country-edition medals; Gini ${fmtNum(data.pareto_medals_by_noc.gini, 3)}`}><Pareto data={data.pareto_medals_by_noc.rows} label="noc_code" value="medals" cum="cum_share" /></ChartCard></div>
          </div>
        </div>);
    }}</Async>
  );
}

function Correlation() {
  const q = useApi<any>("/statistics", { section: "correlations" });
  const [m, setM] = useState("spearman");
  return (
    <Async q={q}>{({ data }) => {
      const mat = data[m];
      return (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Correlation matrix" subtitle={`n = ${mat.n.toLocaleString()} country-edition rows`} right={<select aria-label="Method" className="input" value={m} onChange={(e) => setM(e.target.value)}><option value="pearson">Pearson</option><option value="spearman">Spearman</option><option value="kendall">Kendall (sampled)</option></select>}>
            <Heat rowsLabels={mat.variables} colLabels={mat.variables} values={mat.variables.map((_: string, i: number) => mat.variables.map((b: string) => mat.matrix[i][b]))} />
          </ChartCard>
          <ChartCard title="Selected relationships" height={300}>
            <DataTable height={330} rows={data.pairs.map((p: any) => ({ pair: p.pair, n: p.n, pearson: fmtNum(p.pearson_r, 3), ci: p.pearson_ci ? `${fmtNum(p.pearson_ci[0], 3)} … ${fmtNum(p.pearson_ci[1], 3)}` : "–", spearman: fmtNum(p.spearman_rho, 3), p: fmtP(p.spearman_p) }))}
              columns={[{ key: "pair", width: 260 }, { key: "n", align: "right", width: 80 }, { key: "pearson", header: "Pearson r", align: "right", width: 90 }, { key: "ci", header: "95% CI", width: 150 }, { key: "spearman", header: "Spearman ρ", align: "right", width: 100 }, { key: "p", header: "p (ρ)", align: "right", width: 90 }]} />
          </ChartCard>
          <div className="xl:col-span-2"><Note tone="warn">{data.warning}</Note></div>
        </div>);
    }}</Async>
  );
}

function Hypothesis() {
  const q = useApi<any[]>("/statistics/hypothesis-tests");
  return (
    <Async q={q}>{(tests) => (
      <div className="grid gap-4 xl:grid-cols-2">
        {tests.map((t) => (
          <article key={t.test_id} className="card p-4" data-testid="hypothesis">
            <div className="mb-1 flex items-center justify-between"><span className="chip">{t.test_id}</span><span className="chip">{t.family}</span></div>
            <h3 className="mb-2 text-base font-semibold">{t.research_question}</h3>
            <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted">H0</dt><dd>{t.null_hypothesis}</dd><dt className="text-muted">H1</dt><dd>{t.alternative_hypothesis}</dd>
              <dt className="text-muted">Method</dt><dd>{t.method}</dd><dt className="text-muted">Why</dt><dd className="text-xs text-muted">{t.why_this_test}</dd>
              <dt className="text-muted">Sample size</dt><dd className="tabnum">{t.n?.toLocaleString()}</dd><dt className="text-muted">Statistic</dt><dd className="tabnum">{fmtNum(t.statistic, 3)}</dd>
              <dt className="text-muted">p-value</dt><dd className="tabnum">{fmtP(t.p_value)}{t.p_adjusted_holm != null && <span className="text-muted"> (Holm-adjusted {fmtP(t.p_adjusted_holm)})</span>}</dd>
              <dt className="text-muted">{Math.round((t.ci_level ?? 0.95) * 100)}% CI</dt><dd className="tabnum">{t.ci_low != null ? `${fmtNum(t.ci_low, 3)} to ${fmtNum(t.ci_high, 3)}` : "not applicable for this test"}</dd>
              <dt className="text-muted">Effect size</dt><dd className="tabnum">{t.effect_size_name}: {fmtNum(t.effect_size, 3)}</dd>
            </dl>
            <p className="mt-3 rounded-lg bg-surface2 p-3 text-sm">{t.interpretation}</p>
            <details className="mt-2 text-xs text-muted"><summary className="cursor-pointer">Assumption checks &amp; caveats</summary><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap">{JSON.stringify(t.assumptions, null, 1)}</pre><p className="mt-2">{t.caveats}</p></details>
          </article>))}
      </div>)}</Async>
  );
}

function Regression() {
  const q = useApi<any>("/statistics/regression");
  return (
    <Async q={q}>{({ data }) => {
      const nb = data.medal_counts.negative_binomial_ml;
      const forest = (coefs: any[], exp = true) => coefs.filter((c) => c.term !== "Intercept").map((c) => ({ term: c.term, rr: exp ? Math.exp(c.coef) : c.coef }));
      return (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Medal counts: negative binomial (rate ratios)" subtitle={`Poisson dispersion ${fmtNum(data.medal_counts.poisson_cluster_robust.pearson_dispersion, 2)} > 1 ⇒ overdispersed; NB α = ${fmtNum(nb.alpha, 3)}`}>
            <DataTable height={300} rows={(nb.coefs ?? []).map((c: any) => ({ term: c.term, rate_ratio: fmtNum(c.rate_ratio, 3), coef: fmtNum(c.coef, 3), se: fmtNum(c.se, 3), p: fmtP(c.p) }))} columns={[{ key: "term", width: 180 }, { key: "rate_ratio", header: "Rate ratio", align: "right" }, { key: "coef", align: "right" }, { key: "se", align: "right" }, { key: "p", align: "right" }]} />
            <p className="mt-2 text-xs text-muted">{data.medal_counts.interpretation}</p>
          </ChartCard>
          <ChartCard title="Poisson (cluster-robust SEs) coefficients" subtitle={`n = ${data.medal_counts.n}; McFadden pseudo-R² ${fmtNum(data.medal_counts.mcfadden_pseudo_r2_poisson, 3)}`}>
            <DataTable height={300} rows={data.medal_counts.poisson_cluster_robust.coefs.map((c: any) => ({ term: c.term, coef: fmtNum(c.coef, 3), ci: `${fmtNum(c.ci_low, 3)} … ${fmtNum(c.ci_high, 3)}`, p: fmtP(c.p) }))} columns={[{ key: "term", width: 180 }, { key: "coef", align: "right" }, { key: "ci", header: "95% CI", width: 150 }, { key: "p", align: "right" }]} />
          </ChartCard>
          <ChartCard title="OLS: log(1 + medals)" subtitle={`R² ${fmtNum(data.ols_log_medals.r2, 3)}, adj R² ${fmtNum(data.ols_log_medals.adj_r2, 3)}; HC3 robust SEs; Breusch-Pagan p ${fmtP(data.ols_log_medals.diagnostics.breusch_pagan_p)}; Durbin-Watson ${fmtNum(data.ols_log_medals.diagnostics.durbin_watson, 2)}`}>
            <DataTable height={260} rows={data.ols_log_medals.coefs_hc3.map((c: any) => ({ term: c.term, coef: fmtNum(c.coef, 3), se: fmtNum(c.se, 3), ci: `${fmtNum(c.ci_low, 3)} … ${fmtNum(c.ci_high, 3)}`, p: fmtP(c.p) }))} columns={[{ key: "term", width: 180 }, { key: "coef", align: "right" }, { key: "se", align: "right" }, { key: "ci", header: "95% CI", width: 150 }, { key: "p", align: "right" }]} />
          </ChartCard>
          <ChartCard title="Residuals vs fitted (diagnostic)" subtitle="A funnel shape = heteroscedasticity (hence robust errors)"><Scatter2 data={data.ols_log_medals.residual_vs_fitted} x="fitted" y="resid" xLabel="Fitted log(1+medals)" yLabel="Residual" /></ChartCard>
          <ChartCard title="Logistic: medal ~ age + experience" subtitle={`odds ratios, n = ${data.logistic_medal.n.toLocaleString()}, in-sample AUC ${fmtNum(data.logistic_medal.auc_in_sample, 3)}, pseudo-R² ${fmtNum(data.logistic_medal.pseudo_r2, 3)}`}>
            <DataTable height={280} rows={data.logistic_medal.coefs.map((c: any) => ({ term: c.term, or: fmtNum(c.odds_ratio, 3), ci: `${fmtNum(c.or_ci[0], 3)} … ${fmtNum(c.or_ci[1], 3)}`, p: fmtP(c.p) }))} columns={[{ key: "term", width: 180 }, { key: "or", header: "Odds ratio", align: "right" }, { key: "ci", header: "95% CI", width: 160 }, { key: "p", align: "right" }]} />
            <p className="mt-2 text-xs text-muted">{data.logistic_medal.note}</p>
          </ChartCard>
          <ChartCard title="Host effect with country fixed effects" subtitle="Within-NOC comparison, cluster-robust SEs">
            <div className="grid gap-2 text-sm"><div>Coefficient on host (log(1+medals)): <b className="tabnum">{fmtNum(data.host_effect_fixed_effects.host_coef_log1p_medals, 3)}</b> (SE {fmtNum(data.host_effect_fixed_effects.se, 3)}, p {fmtP(data.host_effect_fixed_effects.p)}), 95% CI {fmtNum(data.host_effect_fixed_effects.ci[0], 3)} … {fmtNum(data.host_effect_fixed_effects.ci[1], 3)}</div>
              <div>≈ {fmtNum(100 * (Math.exp(data.host_effect_fixed_effects.host_coef_log1p_medals) - 1), 0)}% more (1 + medals) when hosting, holding delegation size constant.</div><div className="text-xs text-muted">{data.host_effect_fixed_effects.note}</div></div>
          </ChartCard>
          <ChartCard title="Female share growth (OLS per season)">
            <LineSeries data={data.female_share_growth.summer.fitted.map((r: any, i: number) => ({ year: r.year, summer: r.actual, summer_fit: r.fitted, winter: data.female_share_growth.winter.fitted.find((w: any) => w.year === r.year)?.actual ?? null }))} x="year" yFormat={(v) => `${Math.round(v * 100)}%`}
              series={[{ key: "summer", color: "#F4C300", dot: true }, { key: "summer_fit", name: "Summer trend", color: "#F4C300", dash: "5 4" }, { key: "winter", color: "#60C8FF", dot: true }]} />
            <p className="mt-2 text-xs text-muted">Summer R² {fmtNum(data.female_share_growth.summer.r2, 3)} · Winter R² {fmtNum(data.female_share_growth.winter.r2, 3)}.</p>
          </ChartCard>
        </div>);
    }}</Async>
  );
}

function TimeSeries() {
  const q = useApi<any>("/statistics/time-series");
  const [season, setSeason] = useState("summer");
  const [v, setV] = useState("athletes");
  return (
    <Async q={q}>{({ data }) => {
      const s = data[season][v];
      const rows = s.years.map((y: number, i: number) => ({ year: y, actual: s.values[i], moving_avg_3: s.moving_average_3[i], holt: s.holt_fitted[i] }));
      return (
        <div>
          <div className="mb-3 flex flex-wrap gap-3"><Select label="Season" allLabel="–" value={season} onChange={(x) => setSeason(x || "summer")} options={[{ value: "summer", label: "Summer" }, { value: "winter", label: "Winter" }]} />
            <Select label="Series" allLabel="–" value={v} onChange={(x) => setV(x || "athletes")} options={["athletes", "events", "nocs", "sports", "female_share", "medal_awards"].map((k) => ({ value: k, label: k.replace("_", " ") }))} /></div>
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title={`${season} · ${v.replace("_", " ")} by edition`} subtitle="Observation index = Olympic edition (irregular calendar spacing)">
              <LineSeries data={rows} x="year" xLabel="Games year" refLines={s.change_point?.supported_by_bic ? [{ x: s.change_point.year_after_change, label: "change-point" }] : []}
                series={[{ key: "actual", color: "#F4C300", dot: true }, { key: "moving_avg_3", name: "3-edition moving average", color: "#0085C7" }, { key: "holt", name: "Holt smoothing (fitted)", color: "#009F3D", dash: "5 4" }]} />
            </ChartCard>
            <ChartCard title="Trend, smoothing & change-point" height={200}>
              <ul className="space-y-2 text-sm">
                <li>Linear trend: {fmtNum(s.trend_slope_per_edition, 4)} per edition (R² {fmtNum(s.trend_r2, 2)}, p {fmtP(s.trend_p)}).</li>
                <li>Holt one-edition-ahead point value (a smoothing extrapolation, not a forecast): {fmtNum(s.holt_next_edition_point, 3)} (approx. 95% interval {fmtNum(s.holt_next_edition_interval_approx[0], 2)} – {fmtNum(s.holt_next_edition_interval_approx[1], 2)}).</li>
                <li>Change-point: best single mean shift after {s.change_point.year_after_change}; BIC {fmtNum(s.change_point.bic_one_change, 1)} vs {fmtNum(s.change_point.bic_no_change, 1)} without ⇒ {s.change_point.supported_by_bic ? "supported" : "not supported"}.</li>
              </ul>
            </ChartCard>
            <div className="xl:col-span-2"><Note>{data.method_note}</Note></div>
          </div>
        </div>);
    }}</Async>
  );
}

function Outliers() {
  const q = useApi<any>("/statistics", { section: "distributions" });
  return (
    <Async q={q}>{({ data }) => (
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Tukey outliers (1.5 × IQR)" height={220}>
          <DataTable rows={["athlete_age", "country_edition_total_medals", "country_edition_athletes"].map((k) => ({ variable: k.replace(/_/g, " "), outliers: data[k].boxplot.outliers, q1: fmtNum(data[k].boxplot.q1, 1), median: fmtNum(data[k].boxplot.median, 1), q3: fmtNum(data[k].boxplot.q3, 1), upper_fence_whisker: fmtNum(data[k].boxplot.whisker_high, 1) }))}
            columns={[{ key: "variable", width: 240 }, { key: "outliers", align: "right" }, { key: "q1", align: "right" }, { key: "median", align: "right" }, { key: "q3", align: "right" }, { key: "upper_fence_whisker", header: "Upper whisker", align: "right" }]} />
        </ChartCard>
        <ChartCard title="Box plots" height={220}><BoxStrip items={["athlete_age", "country_edition_total_medals", "country_edition_athletes"].map((k) => ({ label: k.replace(/_/g, " ").slice(0, 22), q1: data[k].boxplot.q1, median: data[k].boxplot.median, q3: data[k].boxplot.q3, low: data[k].boxplot.whisker_low, high: data[k].boxplot.whisker_high, outliers: data[k].boxplot.outliers }))} /></ChartCard>
        <div className="xl:col-span-2"><Note>Medal and delegation-size distributions are extremely right-skewed: "outliers" are the dominant NOCs, a feature of the data, not errors. They are kept in all analyses.</Note></div>
      </div>)}</Async>
  );
}
