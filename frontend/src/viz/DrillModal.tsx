import { useEffect } from "react";
import { Download, Filter, X } from "lucide-react";
import { API_BASE, qs, useApi } from "../lib/api";
import { Async } from "../components/ui";
import { downloadCsv } from "./export";
import { useVizFilters } from "./filters";
import { SimpleTable } from "./renderers/misc";

/** Drill-down: the records behind a clicked chart element, with CSV export and an 'apply as filter' action (cross-filtering). */
export default function DrillModal({ target, onClose }: { target: { type: string; key: string }; onClose: () => void }) {
  const { f, set } = useVizFilters();
  const params = { type: target.type, key: target.key, season: f.season, year_from: f.yearFrom, year_to: f.yearTo };
  const q = useApi<any>("/viz/drilldown", params);
  useEffect(() => { const h = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h); }, [onClose]);
  const apply = () => {
    if (target.type === "country") set({ nocs: Array.from(new Set([...f.nocs, target.key.toUpperCase()])).slice(-6) });
    else if (target.type === "sport") set({ sport: target.key });
    else if (target.type === "games") set({ gamesId: target.key });
    onClose();
  };
  const canFilter = ["country", "sport", "games"].includes(target.type);
  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="Records" onClick={onClose}>
      <div className="card max-h-[88vh] w-full max-w-4xl overflow-hidden p-4" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="h-display text-xl">{q.data?.title ?? "Records"}</h3>
          <div className="flex gap-2">
            {canFilter && <button className="btn btn-accent" onClick={apply}><Filter className="h-4 w-4" /> Filter all charts by this</button>}
            {q.data && <button className="btn" onClick={() => downloadCsv(`${target.type}_${target.key}`, q.data.columns, q.data.rows)}><Download className="h-4 w-4" /> CSV</button>}
            <button className="btn" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
          </div>
        </div>
        <Async q={q}>{(d: any) => (<>
          <SimpleTable columns={d.columns.map((c: string) => ({ key: c, label: c }))} rows={d.rows} max={500} />
          <p className="mt-2 text-xs text-muted">{d.total.toLocaleString()} records{d.total > d.rows.length ? ` (first ${d.rows.length} shown; the CSV link on the chart's data table has the complete selection)` : ""}.</p></>)}</Async>
      </div>
    </div>
  );
}
