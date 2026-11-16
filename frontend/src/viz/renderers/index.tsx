import { createElement } from "react";
import type { Payload, RenderProps, VizKind } from "../types";
import { DonutChart, LorenzChart, ParetoChart, RadarViz, ScatterViz, TreemapChart, XYChart } from "./xy";
import { Beeswarm, BoxPlot, ErrorBars, Flow, Forest, Heatmap, IntervalChart, PairPlot, Slope, Timeline, Violin } from "./svg";
import { Bracket, Dendrogram, KnockoutTree, Pca3D } from "./trees";
import { MapViz } from "./map";
import { SankeyViz, Scorecard, SimpleTable, TableViz } from "./misc";

export const RENDERERS: Record<VizKind, (p: RenderProps) => any> = {
  xy: XYChart, slope: Slope, donut: DonutChart, treemap: TreemapChart, radar: RadarViz, scatter: ScatterViz, heatmap: Heatmap, calendar: Heatmap, box: BoxPlot, violin: Violin,
  timeline: Timeline, sankey: SankeyViz, forest: Forest, errorbar: ErrorBars, interval: IntervalChart, beeswarm: Beeswarm, tree: KnockoutTree, bracket: Bracket, dendrogram: Dendrogram,
  pca3d: Pca3D, pairs: PairPlot, flow: Flow, map: MapViz, lorenz: LorenzChart, pareto: ParetoChart, table: TableViz, scorecard: Scorecard,
};
export const SUPPORTED_KINDS = Object.keys(RENDERERS) as VizKind[];

const XY_VARIANTS = ["line", "area", "bar", "stacked", "grouped", "percent", "step", "stream"];
export const VIEW_LABEL: Record<string, string> = {
  line: "Line", area: "Area", bar: "Bars", stacked: "Stacked", grouped: "Grouped", percent: "100% stacked", step: "Step", stream: "Stream", donut: "Donut", treemap: "Treemap", table: "Data table", default: "Default view",
};

/** Views the chart can switch between: only those the same data meaningfully supports and an adapter implements. */
export function availableViews(p: Payload): string[] {
  const base = p.data?.variant ?? "default";
  const out = [p.kind === "xy" ? base : "default"];
  const multi = (p.data?.series ?? []).length >= 2;
  (p.alternatives ?? []).forEach((a) => {
    if (out.includes(a) || a === "table") return;
    if (p.kind === "xy") {
      if (XY_VARIANTS.includes(a)) { if (["stream", "percent", "stacked", "grouped"].includes(a) && !multi) return; out.push(a); }
      else if ((a === "donut" || a === "treemap") && !multi) out.push(a);
    } else if ((p.kind === "donut" || p.kind === "treemap") && ["donut", "treemap", "bar"].includes(a) && a !== p.kind) out.push(a);
  });
  if ((p.kind === "donut" || p.kind === "treemap") && !out.includes("bar")) out.push("bar");
  out.push("table");
  return out;
}

const rowsOf = (p: Payload) => {
  const d = p.data;
  if (p.kind === "xy" && d.series?.length) return d.rows.map((r: any) => ({ name: String(r[d.x]), value: Number(r[d.series[0].key]) || 0, noc: r[d.pickKey] })).filter((r: any) => r.value > 0);
  if (p.kind === "donut") return d.rows.map((r: any) => ({ name: r.name, value: r.value, noc: r.noc }));
  if (p.kind === "treemap") return d.rows.map((r: any) => ({ name: r.name, value: r.size, noc: r.noc, group: r.group }));
  return [];
};

export function renderView(p: Payload, view: string, height: number, onPick: RenderProps["onPick"]) {
  const props = { p, height, onPick, variant: "" } as RenderProps;
  if (view === "table") return <div><SimpleTable columns={p.table.columns.map((c) => ({ key: c, label: c }))} rows={p.table.rows} /></div>;
  if (p.kind === "xy" && (view === "donut" || view === "treemap")) {
    const rows = rowsOf(p).sort((a: any, b: any) => b.value - a.value);
    const head = rows.slice(0, 10), tail = rows.slice(10);
    const dr = [...head, ...(tail.length ? [{ name: `Other (${tail.length})`, value: tail.reduce((s: number, r: any) => s + r.value, 0) }] : [])];
    const np = { ...p, kind: view, data: view === "donut" ? { rows: dr, valueLabel: p.data.series[0].key } : { rows: rows.map((r: any) => ({ name: r.name, size: r.value, group: "All", noc: r.noc })), sizeLabel: p.data.series[0].key } } as Payload;
    return createElement(RENDERERS[view as VizKind], { ...props, p: np, key: `${p.id}-${view}` } as any);
  }
  if ((p.kind === "donut" || p.kind === "treemap") && view !== p.kind && view !== "default") {
    const rows = rowsOf(p).sort((a: any, b: any) => b.value - a.value);
    if (view === "bar") {
      const np = { ...p, kind: "xy", data: { x: "name", xType: "category", rows: rows.map((r: any) => ({ name: r.name, value: r.value, noc: r.noc })), series: [{ key: "value", name: p.data.valueLabel ?? p.data.sizeLabel ?? "value", color: "#0072B2" }], variant: "bar", horizontal: true, pickKey: "noc", yLabel: p.data.valueLabel ?? p.data.sizeLabel } } as Payload;
      return createElement(RENDERERS.xy, { ...props, p: np, variant: "bar", key: `${p.id}-bar` } as any);
    }
    const np = { ...p, kind: view, data: view === "donut" ? { rows: rows.slice(0, 11).map((r: any) => ({ name: r.name, value: r.value, noc: r.noc })), valueLabel: p.data.sizeLabel } : { rows: rows.map((r: any) => ({ name: r.name, size: r.value, group: r.group ?? "All", noc: r.noc })), sizeLabel: p.data.valueLabel } } as Payload;
    return createElement(RENDERERS[view as VizKind], { ...props, p: np, key: `${p.id}-${view}` } as any);
  }
  const R = RENDERERS[p.kind];
  if (!R) return <div className="p-6 text-sm text-muted">This chart type ({p.kind}) is not supported by the renderer.</div>;
  return createElement(R, { ...props, variant: p.kind === "xy" && XY_VARIANTS.includes(view) ? view : "", key: `${p.id}-${view}` } as any);
}
