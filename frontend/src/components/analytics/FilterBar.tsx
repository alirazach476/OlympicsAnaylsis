import { Filter, X } from "lucide-react";

/** The active cross-filters as removable chips. Shown only while something is selected; the hint explains how to set one. */
export function FilterBar({ filters, onClear, onRemove, hint = "Click a bar, row or legend entry to filter everything on this page." }: { filters: { key: string; label: string; value: string }[]; onClear: () => void; onRemove: (key: string) => void; hint?: string }) {
  if (!filters.length) return <div className="mb-3 flex items-center gap-2 text-xs text-muted" data-testid="filter-hint"><Filter className="h-3.5 w-3.5" />{hint}</div>;
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2" role="status" aria-live="polite" data-testid="filter-bar">
      <span className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-muted"><Filter className="h-3.5 w-3.5" />Filtering</span>
      {filters.map((f) => <button key={f.key} className="chip border-accent/50 text-accent hover:bg-accent/10" onClick={() => onRemove(f.key)} aria-label={`Remove filter ${f.label}: ${f.value}`}>{f.label}: <b className="ml-1 text-ink">{f.value}</b><X className="ml-1 h-3 w-3" /></button>)}
      <button className="btn !py-0.5 text-xs" onClick={onClear}>Clear all</button>
    </div>
  );
}
