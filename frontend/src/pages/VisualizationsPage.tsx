import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { Async, Kpi, Note, PageHeader, Tabs } from "../components/ui";
import { useApi } from "../lib/api";
import { downloadCsv } from "../viz/export";
import { FilterBar, VizFilterProvider } from "../viz/filters";
import { VizGallery } from "../viz/VizGallery";
import { SimpleTable } from "../viz/renderers/misc";

const SECTIONS = [
  { id: "1", label: "1 · Time series" }, { id: "2", label: "2 · Countries & medals" }, { id: "3", label: "3 · Athletes" }, { id: "4", label: "4 · Sports & events" },
  { id: "5", label: "5 · Statistics" }, { id: "6", label: "6 · Machine learning" }, { id: "7", label: "7 · Team sports" }, { id: "8", label: "8 · Data engineering" }, { id: "cov", label: "Registry & coverage" },
];
const BLURB: Record<string, string> = {
  "1": "How participation, programme size, rankings and activity changed across Games.", "2": "Who wins medals, how concentrated they are and where.", "3": "Ages, careers, medals and movement between sports.",
  "4": "Sports, events, results, records and gender balance.", "5": "Distributions, relationships, intervals and tests, each with its data table.", "6": "Validated models: predictions, errors, explanations and clusters.",
  "7": "Fixtures, standings, scores and tournament paths for team sports (only statistics the collected fixtures support).", "8": "Provenance, completeness, quality and pipeline health, measured live.",
};

function Coverage() {
  const cov = useApi<any>("/viz/coverage");
  const reg = useApi<any>("/viz/registry");
  const [q, setQ] = useState("");
  return (
    <div className="space-y-6">
      <Async q={cov}>{(c: any) => (<>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="Planned items" value={c.summary.planned_items} hint={`${c.summary.registered_charts} chart builders registered`} />
          <Kpi label="Implemented" value={c.summary.implemented} accent="#009F3D" hint="data returned and renderer available" />
          <Kpi label="Unavailable (missing data)" value={c.summary.unavailable} accent="#F4C300" />
          <Kpi label="Pending" value={c.summary.pending} accent="#DF0024" hint="not built yet or failing" />
        </div>
        <p className="text-xs text-muted">Generated {c.generated_at} by scripts/build_viz_coverage.py - every chart is executed against the live warehouse with default filters.</p>
        <div>
          <div className="mb-2 flex items-center justify-between"><h3 className="h-display text-xl">Coverage by planned item</h3>
            <button className="btn" onClick={() => downloadCsv("visualization_coverage", ["section", "item", "charts", "status", "reason"], c.items)}>Download CSV</button></div>
          <SimpleTable columns={["section", "item", "charts", "status", "reason"].map((k) => ({ key: k, label: k }))} rows={c.items} max={200} />
        </div></>)}</Async>
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h3 className="h-display text-xl">Visualization registry</h3>
          <div className="flex gap-2"><span className="relative"><Search className="pointer-events-none absolute left-2 top-2 h-3.5 w-3.5 text-muted" /><input className="input pl-7" placeholder="filter registry…" aria-label="Filter registry" value={q} onChange={(e) => setQ(e.target.value)} /></span>
            {reg.data && <button className="btn" onClick={() => downloadCsv("visualization_registry", ["id", "page", "name", "kind", "dataset", "source_table", "purpose", "filters", "endpoint", "status"], reg.data.charts.map((c: any) => ({ ...c, filters: c.filters.join(" ") })))}>Download CSV</button>}</div></div>
        <Async q={reg}>{(r: any) => (
          <SimpleTable columns={[["id", "Chart ID"], ["page", "Dashboard page"], ["name", "Visualization"], ["kind", "Chart type"], ["dataset", "Dataset"], ["source_table", "Source table"], ["purpose", "Analytical purpose"], ["filters", "Filters"], ["endpoint", "Backend endpoint"], ["status", "Status"]].map(([key, label]) => ({ key, label }))}
            rows={r.charts.filter((c: any) => !q || JSON.stringify(c).toLowerCase().includes(q.toLowerCase())).map((c: any) => ({ ...c, filters: c.filters.join(", ") }))} max={200} />)}</Async>
      </div>
    </div>
  );
}

export default function VisualizationsPage() {
  const [sp, setSp] = useSearchParams();
  const tab = SECTIONS.some((s) => s.id === sp.get("section")) ? sp.get("section")! : "1";
  const setTab = (id: string) => setSp((p) => { const n = new URLSearchParams(p); n.set("section", id); return n; });
  const [q, setQ] = useState(sp.get("q") ?? "");
  const reg = useApi<any>("/viz/registry");
  const count = useMemo(() => reg.data?.charts?.length ?? 0, [reg.data]);
  return (
    <div>
      <PageHeader title="Analytics" subtitle={`${count || ""} charts from the warehouse`} />
      <VizFilterProvider>
        {tab !== "cov" && <FilterBar />}
        <Tabs tabs={SECTIONS} value={tab} onChange={setTab} />
        {tab === "cov" ? <Coverage /> : (
          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-muted">{BLURB[tab]}</p>
              <span className="relative"><Search className="pointer-events-none absolute left-2 top-2 h-3.5 w-3.5 text-muted" /><input className="input pl-7" placeholder="search charts…" aria-label="Search charts" value={q} onChange={(e) => setQ(e.target.value)} /></span>
            </div>
            <VizGallery section={Number(tab)} query={q} />
          </div>)}
      </VizFilterProvider>
      <div className="mt-6"><Note>Standards: medal colours are fixed (gold, silver, bronze); categorical colours are colour-blind safe; axes carry labels and units; charts mixing units use indexing or separate axes; pie-style charts show at most 11 slices; log scales are labelled.</Note></div>
    </div>
  );
}
