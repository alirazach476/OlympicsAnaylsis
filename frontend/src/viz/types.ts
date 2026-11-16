export type VizKind =
  | "xy" | "slope" | "donut" | "treemap" | "radar" | "scatter" | "heatmap" | "calendar" | "box" | "violin" | "timeline" | "sankey" | "forest" | "errorbar" | "interval"
  | "beeswarm" | "tree" | "bracket" | "dendrogram" | "pca3d" | "pairs" | "flow" | "map" | "lorenz" | "pareto" | "table" | "scorecard";

export type ChartMeta = {
  id: string; section: number; section_name: string; page: string; name: string; kind: VizKind; alternatives: string[]; dataset: string; source_table: string;
  purpose: string; filters: string[]; endpoint: string; status: string; status_reason?: string;
};

export type Payload = {
  id: string; title: string; kind: VizKind; status: "ok" | "unavailable"; reason?: string; alternatives: string[]; axes: { x?: string; y?: string };
  data: any; table: { columns: string[]; rows: Record<string, any>[] }; interpretation: string; notes: string[]; drill?: { type: string; key: string } | null;
  filters_applied: Record<string, any>; source: string; generated_at: string;
};

export type Pick = (type: string, value: string) => void;

export type RenderProps = { p: Payload; variant: string; height: number; onPick: Pick };

/** Filters shared by every chart on a page (cross-filtering): a click in one chart updates the others. */
export type VizFilters = {
  season: string; yearFrom: string; yearTo: string; noc: string; sport: string; gamesId: string;
};
