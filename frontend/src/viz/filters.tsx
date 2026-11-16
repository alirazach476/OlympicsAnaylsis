import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import { getJSON, Params, useApi } from "../lib/api";
import { SeasonToggle } from "../components/ui";
import type { ChartMeta } from "./types";

export type FilterState = { season: string; yearFrom: string; yearTo: string; nocs: string[]; sport: string; gamesId: string; athletes: { id: number; name: string }[] };
const EMPTY: FilterState = { season: "", yearFrom: "", yearTo: "", nocs: [], sport: "", gamesId: "", athletes: [] };

type Ctx = { f: FilterState; set: (p: Partial<FilterState>) => void; clear: () => void; params: (m: ChartMeta) => Params; active: number };
const FilterCtx = createContext<Ctx>({ f: EMPTY, set: () => undefined, clear: () => undefined, params: () => ({}), active: 0 });
export const useVizFilters = () => useContext(FilterCtx);

export function VizFilterProvider({ children, initial }: { children: ReactNode; initial?: Partial<FilterState> }) {
  const [f, setF] = useState<FilterState>({ ...EMPTY, ...initial });
  const set = useCallback((p: Partial<FilterState>) => setF((s) => ({ ...s, ...p })), []);
  const clear = useCallback(() => setF(EMPTY), []);
  const params = useCallback((m: ChartMeta): Params => {
    const has = (k: string) => m.filters.includes(k);
    const out: Params = {};
    if (has("season") && f.season) out.season = f.season;
    if (has("year_range")) { if (f.yearFrom) out.year_from = f.yearFrom; if (f.yearTo) out.year_to = f.yearTo; }
    if (has("noc") && f.nocs.length) out.noc = f.nocs[0];
    if (has("nocs") && f.nocs.length) out.nocs = f.nocs.join(",");
    if (has("sport") && f.sport) out.sport = f.sport;
    if (has("games_id") && f.gamesId) out.games_id = f.gamesId;
    if (has("athlete_ids") && f.athletes.length) out.athlete_ids = f.athletes.map((a) => a.id).join(",");
    return out;
  }, [f]);
  const active = (f.season ? 1 : 0) + (f.yearFrom || f.yearTo ? 1 : 0) + f.nocs.length + (f.sport ? 1 : 0) + (f.gamesId ? 1 : 0) + f.athletes.length;
  const value = useMemo(() => ({ f, set, clear, params, active }), [f, set, clear, params, active]);
  return <FilterCtx.Provider value={value}>{children}</FilterCtx.Provider>;
}

export function useVizOptions() {
  return useApi<any>("/viz/options");
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="chip" data-testid="filter-chip">
      {label}
      <button aria-label={`Remove ${label}`} onClick={onRemove} className="ml-0.5 rounded hover:text-ink"><X className="h-3 w-3" /></button>
    </span>
  );
}

function AthletePicker() {
  const { f, set } = useVizFilters();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const run = async (v: string) => {
    setQ(v);
    if (v.trim().length < 2) return setHits([]);
    try { setHits(await getJSON("/viz/search/athletes", { q: v, limit: 8 })); } catch { setHits([]); }
  };
  return (
    <div className="relative">
      <label className="flex items-center gap-2 text-xs text-muted">
        Athletes
        <span className="relative">
          <Search className="pointer-events-none absolute left-2 top-2 h-3.5 w-3.5 text-muted" />
          <input aria-label="Filter charts by athlete" className="input w-44 pl-7" placeholder="search name…" value={q} onChange={(e) => run(e.target.value)} />
        </span>
      </label>
      {hits.length > 0 && (
        <ul className="absolute z-30 mt-1 max-h-60 w-72 overflow-auto rounded-lg border border-line bg-surface p-1 text-sm shadow-card">
          {hits.map((h) => (
            <li key={h.athlete_id}>
              <button className="flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-surface2"
                onClick={() => { if (!f.athletes.some((a) => a.id === h.athlete_id)) set({ athletes: [...f.athletes, { id: h.athlete_id, name: h.full_name }].slice(-6) }); setQ(""); setHits([]); }}>
                <span>{h.full_name}</span><span className="text-xs text-muted">{h.medals} medals</span>
              </button>
            </li>))}
        </ul>)}
    </div>
  );
}

export function FilterBar({ athletes = true }: { athletes?: boolean }) {
  const { f, set, clear, active } = useVizFilters();
  const opt = useVizOptions();
  const o = opt.data;
  const years = useMemo(() => (o ? Array.from(new Set<number>(o.games.map((g: any) => g.year))).sort((a, b) => a - b) : []), [o]);
  return (
    <div className="card mb-4 p-3" role="search" aria-label="Chart filters">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <SeasonToggle value={f.season} onChange={(v) => set({ season: v })} label="Chart season" />
        <label className="flex items-center gap-2 text-xs text-muted">From
          <select aria-label="Chart year from" className="input" value={f.yearFrom} onChange={(e) => set({ yearFrom: e.target.value })}><option value="">1960</option>{years.map((y) => <option key={y} value={y}>{y}</option>)}</select></label>
        <label className="flex items-center gap-2 text-xs text-muted">to
          <select aria-label="Chart year to" className="input" value={f.yearTo} onChange={(e) => set({ yearTo: e.target.value })}><option value="">2026</option>{years.map((y) => <option key={y} value={y}>{y}</option>)}</select></label>
        <label className="flex items-center gap-2 text-xs text-muted">Nation
          <select aria-label="Chart nation" className="input max-w-[11rem]" value="" onChange={(e) => e.target.value && !f.nocs.includes(e.target.value) && set({ nocs: [...f.nocs, e.target.value].slice(-6) })}>
            <option value="">add…</option>{(o?.nocs ?? []).map((n: any) => <option key={n.code} value={n.code}>{n.name} ({n.code})</option>)}</select></label>
        <label className="flex items-center gap-2 text-xs text-muted">Sport
          <select aria-label="Chart sport" className="input max-w-[11rem]" value={f.sport} onChange={(e) => set({ sport: e.target.value })}><option value="">All</option>{(o?.sports ?? []).map((s: string) => <option key={s} value={s}>{s}</option>)}</select></label>
        <label className="flex items-center gap-2 text-xs text-muted">Edition
          <select aria-label="Chart edition" className="input max-w-[11rem]" value={f.gamesId} onChange={(e) => set({ gamesId: e.target.value })}><option value="">Default</option>
            {(o?.games ?? []).map((g: any) => <option key={g.games_id} value={g.games_id}>{g.year} {g.season} - {g.host_city}</option>)}</select></label>
        {athletes && <AthletePicker />}
        {active > 0 && <button className="btn" onClick={clear}><X className="h-3.5 w-3.5" /> Clear all</button>}
      </div>
      {active > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Active filters">
          {f.season && <Chip label={`Season: ${f.season}`} onRemove={() => set({ season: "" })} />}
          {(f.yearFrom || f.yearTo) && <Chip label={`Years: ${f.yearFrom || 1960}-${f.yearTo || 2026}`} onRemove={() => set({ yearFrom: "", yearTo: "" })} />}
          {f.nocs.map((n) => <Chip key={n} label={`Nation: ${n}`} onRemove={() => set({ nocs: f.nocs.filter((x) => x !== n) })} />)}
          {f.sport && <Chip label={`Sport: ${f.sport}`} onRemove={() => set({ sport: "" })} />}
          {f.gamesId && <Chip label={`Edition: ${f.gamesId.replace("_", " ")}`} onRemove={() => set({ gamesId: "" })} />}
          {f.athletes.map((a) => <Chip key={a.id} label={`Athlete: ${a.name}`} onRemove={() => set({ athletes: f.athletes.filter((x) => x.id !== a.id) })} />)}
        </div>)}
      <p className="mt-2 text-[11px] text-muted">Filters apply to every chart that supports them (the chip row on each chart shows what it used). Clicking an element in a chart opens its records and can filter the others.</p>
    </div>
  );
}
