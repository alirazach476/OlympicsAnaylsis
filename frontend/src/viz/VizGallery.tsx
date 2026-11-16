import { ReactNode } from "react";
import { useApi } from "../lib/api";
import { Loading } from "../components/ui";
import VizCard from "./VizCard";
import { FilterBar, VizFilterProvider } from "./filters";
import type { ChartMeta } from "./types";

type Registry = { sections: Record<string, string>; charts: ChartMeta[]; total: number };

/** Cards for every chart registered for a dashboard page and/or section. Charts load lazily as they scroll into view. */
export function VizGallery({ page, section, query, lazyOnly }: { page?: string; section?: number; query?: string; lazyOnly?: boolean }) {
  const reg = useApi<Registry>("/viz/registry", { page, section });
  if (reg.isLoading) return <Loading label="Loading chart registry…" />;
  if (reg.error || !reg.data) return null;
  const q = (query ?? "").trim().toLowerCase();
  const charts = reg.data.charts.filter((c) => !q || `${c.name} ${c.kind} ${c.dataset} ${c.purpose}`.toLowerCase().includes(q));
  if (!charts.length) return <div className="p-6 text-center text-sm text-muted">No charts match.</div>;
  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="chart-gallery">
      {charts.map((c) => <VizCard key={c.id} meta={c} lazyOnly={lazyOnly} />)}
    </div>
  );
}

/** The page's visualizations, shown directly (no collapsed section to open): heading, chart count, the shared filter row and every chart (charts load lazily as they scroll into view). */
export function VizSection({ page, title = "Visualizations", athletes = false, lazyOnly = true }: { page: string; title?: string; athletes?: boolean; defaultOpen?: boolean; lazyOnly?: boolean }) {
  const reg = useApi<Registry>("/viz/registry", { page });
  const n = reg.data?.charts.length ?? 0;
  if (reg.data && n === 0) return null;
  return (
    <section className="mt-10" aria-label={title} data-testid="viz-section">
      <div className="mb-4 flex items-end gap-3 border-b border-line pb-2">
        <h2 className="h-display text-3xl leading-none">{title}</h2>
        {n > 0 && <span className="chip">{n} charts</span>}
      </div>
      <VizFilterProvider>
        <FilterBar athletes={athletes} />
        <VizGallery page={page} lazyOnly={lazyOnly} />
      </VizFilterProvider>
    </section>
  );
}

export function Wrap({ children }: { children: ReactNode }) {
  return <VizFilterProvider>{children}</VizFilterProvider>;
}
