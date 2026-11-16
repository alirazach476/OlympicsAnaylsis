import { ReactNode } from "react";
import { useApi } from "../../lib/api";
import { fmtInt, fmtNum, fmtP, MEDAL_COLORS } from "../../lib/fmt";
import { Flag } from "../ui";

export function FindingsStrip({ items, label = "Key findings" }: { items: { k: string; v: ReactNode; d?: string; color?: string }[]; label?: string }) {
  if (!items.length) return null;
  return (
    <section aria-label={label} className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="key-findings">
      {items.map((i) => (
        <div key={i.k} className="relative overflow-hidden rounded-xl border border-line bg-surface p-4">
          <div className="absolute inset-y-0 left-0 w-1" style={{ background: i.color ?? "rgb(var(--accent))" }} />
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted">{i.k}</div>
          <div className="mt-1 font-display text-3xl leading-none">{i.v}</div>
          {i.d && <div className="mt-1 text-xs text-muted">{i.d}</div>}
        </div>))}
    </section>
  );
}

/** Statistics: how many pre-registered tests were run and how many reach p < 0.05 (Holm-adjusted p shown for the strongest). */
export function StatisticsFindings() {
  const q = useApi<any[]>("/statistics/hypothesis-tests");
  const t = q.data ?? [];
  if (!t.length) return null;
  const sig = t.filter((x) => (x.p_adjusted_holm ?? x.p_value) < 0.05);
  const best = [...t].sort((a, b) => a.p_value - b.p_value)[0];
  return <FindingsStrip label="Statistical findings" items={[
    { k: "Hypothesis tests", v: t.length, d: "each with hypotheses, assumptions, CI and effect size", color: "#0085C7" },
    { k: "Significant after Holm", v: `${sig.length} of ${t.length}`, d: "family-wise adjusted p < 0.05", color: "#009F3D" },
    { k: "Strongest evidence", v: fmtP(best.p_value), d: String(best.research_question).slice(0, 70), color: "#DF0024" },
    { k: "Largest sample", v: fmtInt(Math.max(...t.map((x) => x.n || 0))), d: "observations in one test", color: "#F4C300" },
  ]} />;
}

/** Machine learning: the best backtested model against the naive baseline. */
export function MlFindings() {
  const q = useApi<any>("/machine-learning/predictions", { kind: "medal_prediction" });
  const d = q.data?.data;
  if (!d) return null;
  const m = d.metrics_all_participating_nocs;
  const best = d.best_model_by_rmse;
  const naive = m?.naive_previous_total?.rmse, b = m?.[best]?.rmse;
  return <FindingsStrip label="Machine learning findings" items={[
    { k: "Best model (RMSE)", v: String(best).replace(/_/g, " "), d: `RMSE ${fmtNum(b, 2)} medals`, color: "#8E6BBF" },
    { k: "vs naive baseline", v: naive && b ? `${fmtNum(100 * (1 - b / naive), 1)}%` : "–", d: naive && b && b > naive ? "worse than repeating the last total" : "lower error than repeating the last total", color: "#009F3D" },
    { k: "Backtest size", v: fmtInt(d.design.n_predictions), d: `${d.design.test_editions.length} chronological test editions`, color: "#0085C7" },
    { k: "Interval coverage", v: d.prediction_interval_80?.empirical_coverage != null ? `${fmtNum(100 * d.prediction_interval_80.empirical_coverage, 1)}%` : "–", d: "nominal 80% prediction interval", color: "#F4C300" },
  ]} />;
}

/** Medals: the leader, the totals and the split. */
export function MedalFindings() {
  const q = useApi<any>("/medals", { view: "alltime", limit: 3 });
  const r = q.data?.rows ?? [];
  if (!r.length) return null;
  return <FindingsStrip label="Medal findings" items={[
    { k: "All-time leader", v: <span className="inline-flex items-center gap-2"><Flag noc={r[0].noc_code} size={20} />{r[0].noc_code}</span>, d: `${fmtInt(r[0].total)} medals · ${fmtInt(r[0].gold)} gold`, color: MEDAL_COLORS.gold },
    { k: "Runner-up", v: <span className="inline-flex items-center gap-2"><Flag noc={r[1].noc_code} size={20} />{r[1].noc_code}</span>, d: `${fmtInt(r[1].total)} medals`, color: MEDAL_COLORS.silver },
    { k: "Third", v: <span className="inline-flex items-center gap-2"><Flag noc={r[2].noc_code} size={20} />{r[2].noc_code}</span>, d: `${fmtInt(r[2].total)} medals`, color: MEDAL_COLORS.bronze },
    { k: "Gold share of leader", v: `${fmtNum((100 * r[0].gold) / r[0].total, 1)}%`, d: `${r[0].historical_name ?? r[0].noc_code}`, color: "#0085C7" },
  ]} />;
}

/** Records: how many records the book holds. */
export function RecordFindings() {
  const o = useApi<any>("/records", { level: "olympic", page_size: 1 });
  const w = useApi<any>("/records", { level: "world", page_size: 1 });
  const top = useApi<any>("/records", { page_size: 1 });
  const a = o.data?.records?.total, b = w.data?.records?.total;
  if (a == null && b == null) return null;
  const mostDec = top.data?.most_decorated?.[0];
  return <FindingsStrip label="Record findings" items={[
    { k: "Olympic records", v: fmtInt(a ?? 0), d: "as listed by Olympedia", color: "#DF0024" },
    { k: "World records", v: fmtInt(b ?? 0), d: "set at an Olympic Games", color: "#F4C300" },
    { k: "Most decorated", v: mostDec ? String(mostDec.full_name).split(",")[0].split(" ").slice(-1)[0] : "–", d: mostDec ? `${mostDec.medals} medals (${mostDec.gold} gold)` : "", color: MEDAL_COLORS.gold },
    { k: "Longest career", v: top.data?.longest_careers?.[0] ? `${top.data.longest_careers[0].career_span_years} years` : "–", d: top.data?.longest_careers?.[0]?.full_name, color: "#009F3D" },
  ]} />;
}
