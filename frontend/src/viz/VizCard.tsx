import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Download, FileImage, FileText, Info, Maximize2, Minimize2, RefreshCw, Table2 } from "lucide-react";
import { API_BASE, Params, qs, useApi } from "../lib/api";
import { Empty, Loading } from "../components/ui";
import { downloadCsv, exportPng, exportSvg } from "./export";
import { useVizFilters, useVizOptions } from "./filters";
import DrillModal from "./DrillModal";
import { availableViews, renderView, SUPPORTED_KINDS, VIEW_LABEL } from "./renderers";
import type { ChartMeta, Payload } from "./types";

const STAT_VARS = [["athlete_age", "Athlete age"], ["country_edition_total_medals", "Medals per NOC per Games"], ["country_edition_athletes", "Athletes per NOC per Games"]];
const SHAP_FEATURES = ["age", "age_sq", "is_female", "is_winter", "prior_games", "prior_medals", "noc_prior_rate", "noc_prior_n", "sport_prior_rate", "is_host_noc"].map((f) => [f, f]);
const METRIC_OPTIONS: Record<string, string[][]> = {
  st_hist: STAT_VARS, st_kde: STAT_VARS, st_ecdf: STAT_VARS, st_qq: STAT_VARS,
  st_corr_heatmap: [["spearman", "Spearman"], ["pearson", "Pearson"], ["kendall", "Kendall"]],
  ml_confusion: [["", "Best model"], ["logistic_regression", "Logistic regression"], ["random_forest", "Random forest"], ["xgboost", "XGBoost"]],
  ml_shap_dependence: [["", "Most important"], ...SHAP_FEATURES],
  ml_cv_compare: [["pr_auc", "PR-AUC"], ["roc_auc", "ROC-AUC"]],
};
const WIDE: string[] = ["heatmap", "calendar", "timeline", "flow", "map", "sankey", "pairs", "bracket", "tree", "dendrogram", "scorecard", "table", "beeswarm", "forest", "pca3d", "slope"];

/** true once the card is near the viewport. Without IntersectionObserver (old browsers, test DOM) a card loads at once - unless `lazyOnly`
 *  (charts embedded below a page's main content), which then wait: a page never fires dozens of chart requests together. */
function useInView(lazyOnly = false): [React.RefObject<HTMLDivElement>, boolean] {
  const ref = useRef<HTMLDivElement>(null);
  const [seen, setSeen] = useState(typeof IntersectionObserver === "undefined" && !lazyOnly);
  useEffect(() => {
    if (seen || !ref.current || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((e) => e.some((x) => x.isIntersecting) && (setSeen(true), io.disconnect()), { rootMargin: "400px" });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [seen]);
  return [ref, seen];
}

function LocalControls({ meta, local, setLocal }: { meta: ChartMeta; local: Record<string, string>; setLocal: (p: Record<string, string>) => void }) {
  const o = useVizOptions().data;
  const has = (k: string) => meta.filters.includes(k);
  const set = (k: string, v: string) => setLocal({ ...local, [k]: v });
  const eventOptions: string[] = useMemo(() => {
    if (!o) return [];
    if (meta.id.startsWith("s_record") || meta.id === "s_or_vs_wr") return o.record_events;
    return [];
  }, [o, meta.id]);
  const teamEvents: string[] = useMemo(() => (o && meta.id.startsWith("t_") ? Array.from(new Set<string>(o.team_events.map((e: any) => e.event_name))) : []), [o, meta.id]);
  const mo = METRIC_OPTIONS[meta.id];
  const bits: any[] = [];
  if (has("top")) bits.push(<label key="top" className="flex items-center gap-1.5 text-xs text-muted">Show top<select aria-label="Top N" className="input py-0.5" value={local.top ?? ""} onChange={(e) => set("top", e.target.value)}><option value="">default</option>{[5, 8, 10, 15, 20, 30, 40].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>);
  if (has("metric") && mo) bits.push(<label key="metric" className="flex items-center gap-1.5 text-xs text-muted">Variable<select aria-label="Variable" className="input py-0.5" value={local.metric ?? ""} onChange={(e) => set("metric", e.target.value)}>{!mo.some((m) => m[0] === "") && <option value="">default</option>}{mo.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>);
  if (has("event") && (eventOptions.length || teamEvents.length || meta.id.startsWith("s_result"))) {
    const opts = eventOptions.length ? eventOptions : teamEvents;
    bits.push(<label key="event" className="flex items-center gap-1.5 text-xs text-muted">Event<input aria-label="Event" list={`ev-${meta.id}`} className="input w-52 py-0.5" placeholder="default" value={local.event ?? ""} onChange={(e) => set("event", e.target.value)} /><datalist id={`ev-${meta.id}`}>{opts.map((e) => <option key={e} value={e} />)}</datalist></label>);
  }
  if (has("a") && o) for (const k of ["a", "b"]) bits.push(<label key={k} className="flex items-center gap-1.5 text-xs text-muted">Nation {k.toUpperCase()}<select aria-label={`Nation ${k}`} className="input py-0.5" value={local[k] ?? ""} onChange={(e) => set(k, e.target.value)}><option value="">auto</option>{o.nocs.map((n: any) => <option key={n.code} value={n.code}>{n.code}</option>)}</select></label>);
  if (has("noc") && !has("nocs") && o && meta.id.startsWith("t_")) bits.push(<label key="noc" className="flex items-center gap-1.5 text-xs text-muted">Nation<select aria-label="Nation" className="input py-0.5" value={local.noc ?? ""} onChange={(e) => set("noc", e.target.value)}><option value="">auto</option>{o.nocs.map((n: any) => <option key={n.code} value={n.code}>{n.code}</option>)}</select></label>);
  return bits.length ? <div className="mb-2 flex flex-wrap gap-3">{bits}</div> : null;
}

export default function VizCard({ meta, height = 340, forceWide, lazyOnly }: { meta: ChartMeta; height?: number; forceWide?: boolean; lazyOnly?: boolean }) {
  const { params, f } = useVizFilters();
  const [local, setLocal] = useState<Record<string, string>>({});
  const [view, setView] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);
  const [info, setInfo] = useState(false);
  const [full, setFull] = useState(false);
  const [drill, setDrill] = useState<{ type: string; key: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [wrapRef, inView] = useInView(lazyOnly);
  const bodyRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLElement>(null);
  const q: Params = useMemo(() => ({ ...params(meta), ...Object.fromEntries(Object.entries(local).filter(([, v]) => v !== "")) }), [params, meta, local]);
  const res = useApi<Payload>(`/viz/chart/${meta.id}`, q, inView);
  const p = res.data;
  const views = useMemo(() => (p && p.status === "ok" ? availableViews(p) : []), [p]);
  const cur = view && views.includes(view) ? view : views[0];
  useEffect(() => { setView(null); }, [meta.id]);
  useEffect(() => {
    if (!full) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && setFull(false);
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", h); document.body.style.overflow = ""; };
  }, [full]);
  const toggleFull = useCallback(() => {
    const next = !full;
    setFull(next);
    try { if (next) cardRef.current?.requestFullscreen?.().catch(() => undefined); else if (document.fullscreenElement) document.exitFullscreen?.(); } catch { /* overlay mode still works */ }
  }, [full]);
  useEffect(() => { const h = () => { if (!document.fullscreenElement) setFull(false); }; document.addEventListener("fullscreenchange", h); return () => document.removeEventListener("fullscreenchange", h); }, []);

  const h = full ? Math.max(380, (typeof window !== "undefined" ? window.innerHeight : 800) - 250) : height;
  const wide = forceWide || WIDE.includes(meta.kind);
  const csvName = meta.id;
  const doCsv = () => p && downloadCsv(csvName, p.table.columns, p.table.rows);
  const doSvg = () => bodyRef.current && (exportSvg(bodyRef.current, csvName) || setBusy("No SVG to export for this view"));
  const doPng = async () => bodyRef.current && ((await exportPng(bodyRef.current, csvName)) || setBusy("No image to export for this view"));
  useEffect(() => { if (busy) { const t = setTimeout(() => setBusy(null), 2500); return () => clearTimeout(t); } }, [busy]);

  const applied = p?.filters_applied ?? {};
  const chips = Object.entries(applied).filter(([k]) => !["top", "metric"].includes(k)).map(([k, v]) => `${k.replace("_", " ")}: ${v}`);
  const noData = p && p.status === "ok" && ((Array.isArray(p.data?.rows) && p.data.rows.length === 0) || (p.data?.frames && p.data.frames.every((fr: any) => !fr.rows.length)));

  return (
    <div ref={wrapRef} className={wide && !full ? "lg:col-span-2" : ""}>
      <section ref={cardRef} aria-label={meta.name} data-testid={`viz-${meta.id}`} className={`card p-4 ${full ? "fixed inset-0 z-50 overflow-auto rounded-none bg-bg p-6" : ""}`}>
        <header className="mb-2 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="h-display text-lg leading-tight">{meta.name}</h3>
            <p className="mt-0.5 text-xs text-muted">{meta.purpose}</p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5" role="toolbar" aria-label={`${meta.name} tools`}>
            {views.length > 2 && (
              <label className="flex items-center gap-1 text-xs text-muted">View
                <select aria-label="Chart view" className="input py-0.5" value={cur} onChange={(e) => { setView(e.target.value); setShowTable(false); }}>
                  {views.map((v) => <option key={v} value={v}>{VIEW_LABEL[v] ?? v}</option>)}</select></label>)}
            <button className={`btn px-2 ${showTable ? "btn-accent" : ""}`} onClick={() => setShowTable((s) => !s)} aria-pressed={showTable} aria-label="Toggle data table" title="Underlying data table"><Table2 className="h-4 w-4" /></button>
            <button className="btn px-2" onClick={doCsv} disabled={!p || p.status !== "ok"} aria-label="Download CSV" title="Download chart data as CSV"><FileText className="h-4 w-4" /></button>
            <button className="btn px-2" onClick={doPng} disabled={!p || p.status !== "ok" || cur === "table"} aria-label="Export PNG" title="Export PNG"><FileImage className="h-4 w-4" /></button>
            <button className="btn px-2" onClick={doSvg} disabled={!p || p.status !== "ok" || cur === "table"} aria-label="Export SVG" title="Export SVG"><Download className="h-4 w-4" /></button>
            <button className={`btn px-2 ${info ? "btn-accent" : ""}`} onClick={() => setInfo((s) => !s)} aria-pressed={info} aria-label="About this chart" title="Dataset and source"><Info className="h-4 w-4" /></button>
            <button className="btn px-2" onClick={toggleFull} aria-label={full ? "Exit full screen" : "Full screen"} title={full ? "Exit full screen (Esc)" : "Full screen"}>{full ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}</button>
          </div>
        </header>
        {busy && <div role="status" className="mb-2 rounded border border-line bg-surface2 px-2 py-1 text-xs text-muted">{busy}</div>}
        {info && <div className="mb-2 rounded-lg border border-line bg-surface2 p-2 text-xs text-muted"><b>Chart ID</b> {meta.id} · <b>Type</b> {meta.kind} · <b>Dataset</b> {meta.dataset} · <b>Source</b> {meta.source_table} · <b>Endpoint</b> {meta.endpoint}{meta.filters.length ? <> · <b>Filters</b> {meta.filters.join(", ")}</> : null}</div>}
        <LocalControls meta={meta} local={local} setLocal={setLocal} />
        <div ref={bodyRef} style={{ minHeight: full ? 400 : Math.min(height, 260) }}>
          {!inView ? <div className="grid h-full min-h-[200px] place-items-center text-xs text-muted" data-testid="viz-waiting">Chart loads as you scroll</div>
            : res.isLoading ? <Loading label="Loading chart…" /> :
            res.error ? (
              <div role="alert" className="flex items-start gap-2 rounded-lg border border-red/40 bg-red/10 p-3 text-sm"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red" />
                <div className="flex-1"><div className="font-semibold">This chart could not be loaded</div><div className="text-muted">{String((res.error as any)?.message ?? res.error)}</div></div>
                <button className="btn" onClick={() => res.refetch()}><RefreshCw className="h-4 w-4" /> Retry</button></div>) :
            !p ? <Empty /> :
            p.status === "unavailable" ? (
              <div data-testid="unavailable" className="flex flex-col items-center gap-1 rounded-lg border border-dashed border-line p-8 text-center text-sm text-muted"><Info className="h-5 w-5" aria-hidden /><div className="font-semibold text-ink">Not available for this selection</div><div>{p.reason}</div></div>) :
            noData ? <Empty message="No data for this filter selection." /> :
            !SUPPORTED_KINDS.includes(p.kind) ? <Empty message={`Unsupported chart type: ${p.kind}`} /> :
            showTable ? renderView(p, "table", h, () => undefined) : renderView(p, cur, h, (type, key) => setDrill({ type, key }))}
        </div>
        {p && p.status === "ok" && !noData && (<>
          {(chips.length > 0 || f.athletes.length > 0) && <div className="mt-2 flex flex-wrap gap-1" aria-label="Filters applied to this chart">{chips.map((c) => <span key={c} className="chip">{c}</span>)}</div>}
          {p.interpretation && <p className="mt-3 text-sm leading-relaxed" data-testid="interpretation"><span className="font-semibold">How to read it. </span><span className="text-muted">{p.interpretation}</span></p>}
          {p.notes?.map((n, i) => <p key={i} className="mt-1 text-xs text-muted">{n}</p>)}
        </>)}
        {drill && <DrillModal target={drill} onClose={() => setDrill(null)} />}
      </section>
    </div>
  );
}
