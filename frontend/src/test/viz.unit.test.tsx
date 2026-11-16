/** Every chart kind renders from a minimal payload of its documented shape (no API needed) and exports data. */
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "../lib/theme";
import { availableViews, renderView, RENDERERS, SUPPORTED_KINDS } from "../viz/renderers";
import { tableToCsv } from "../viz/export";
import { fmtCell, niceTicks, ramp, VIRIDIS } from "../viz/util";
import type { Payload } from "../viz/types";

const base = (kind: string, data: any, extra: Partial<Payload> = {}): Payload => ({ id: `t_${kind}`, title: kind, kind: kind as any, status: "ok", alternatives: [], axes: {}, data, table: { columns: [], rows: [] }, interpretation: "", notes: [], drill: null, filters_applied: {}, source: "", generated_at: "", ...extra });
const years = [1960, 1964, 1968, 1972];
const xyRows = years.map((y, i) => ({ year: y, A: 10 + i, B: 5 + 2 * i }));
const FIXTURES: Record<string, Payload> = {
  xy: base("xy", { x: "year", xType: "number", rows: xyRows, series: [{ key: "A" }, { key: "B" }], variant: "line", xLabel: "Year", yLabel: "Count" }, { alternatives: ["area", "bar", "stacked"] }),
  slope: base("slope", { left: "1960", right: "2024", rows: [{ name: "USA", noc: "USA", from: 10, to: 20 }, { name: "CHN", noc: "CHN", from: 0, to: 15 }], yLabel: "Medals" }),
  donut: base("donut", { rows: [{ name: "USA", noc: "USA", value: 10 }, { name: "Other", noc: null, value: 5 }], valueLabel: "medals", total: 15 }),
  treemap: base("treemap", { rows: [{ name: "USA", noc: "USA", group: "Americas", size: 10 }, { name: "FRA", noc: "FRA", group: "Europe", size: 7 }], sizeLabel: "medals" }),
  radar: base("radar", { axes: ["a", "b", "c"], series: [{ name: "X", values: { a: 10, b: 50, c: 90 } }, { name: "Y", values: { a: 40, b: 60, c: 20 } }], max: 100 }),
  scatter: base("scatter", { rows: [{ x: 1, y: 2, z: 3, name: "p", group: "g1" }, { x: 2, y: 4, z: 5, name: "q", group: "g2" }], xLabel: "x", yLabel: "y", groupLabel: "Group", sizeLabel: "size" }),
  heatmap: base("heatmap", { rows: [{ r: "a", c: "1", v: 1, label: "a1" }, { r: "a", c: "2", v: 5, label: "a2" }, { r: "b", c: "1", v: 3, label: "b1" }], rowOrder: ["a", "b"], colOrder: ["1", "2"], scale: "seq", vLabel: "v" }),
  calendar: base("calendar", { rows: [{ r: "2024 Summer", c: 0, v: 3, label: "x" }], rowOrder: ["2024 Summer"], colOrder: [0, 1], scale: "seq", vLabel: "m" }),
  box: base("box", { groups: [{ name: "g", n: 10, q1: 1, median: 2, q3: 3, min: 0, max: 4, outliers: [6] }, { name: "h", n: 9, q1: 2, median: 3, q3: 4, min: 1, max: 5, outliers: [] }], yLabel: "v", orientation: "v" }),
  violin: base("violin", { groups: [{ name: "g", x: [1, 2, 3], density: [0.2, 1, 0.3], median: 2, n: 10 }], yLabel: "v" }),
  timeline: base("timeline", { rows: [{ lane: "a", start: 1960, end: 1961, label: "x", color: "#0072B2" }, { lane: "b", start: 1964, end: 1965, label: "y", color: "#D55E00" }], laneOrder: ["a", "b"], xLabel: "Year", unit: "year", legend: [] }),
  sankey: base("sankey", { nodes: [{ name: "A (from)" }, { name: "B (to)" }], links: [{ source: 0, target: 1, value: 5 }], valueLabel: "athletes" }),
  forest: base("forest", { rows: [{ name: "x", est: 1.2, lo: 1.0, hi: 1.5, p: 0.01, unit: "rate ratio" }], xLabel: "Rate ratio", ref: 1, log: true }),
  errorbar: base("errorbar", { rows: [{ name: "g", value: 25, lo: 24, hi: 26, n: 100 }], yLabel: "Mean" }),
  interval: base("interval", { rows: [{ name: "USA", pred: 50, lo: 40, hi: 60, actual: 55, inside: true }], xLabel: "Medals", predLabel: "Predicted", intervalLabel: "80%", actualLabel: "Actual" }),
  beeswarm: base("beeswarm", { features: ["f1", "f2"], points: [{ lane: 0, shap: 0.5, v: 0.3, raw: 1, jit: 0.1 }, { lane: 1, shap: -0.2, v: 0.9, raw: 2, jit: -0.1 }], xLabel: "SHAP" }),
  tree: base("tree", { root: { name: "A 2-1 B", meta: "2024-08-09", winner: "A", children: [{ name: "A 1-0 C", meta: "2024-08-05", winner: "A", children: [] }] } }),
  bracket: base("bracket", { rounds: [{ name: "Semi-finals", matches: [{ a: "A", b: "B", sa: 1, sb: 0, winner: "A" }, { a: "C", b: "D", sa: 2, sb: 1, winner: "C" }] }, { name: "Final", matches: [{ label: "Gold", a: "A", b: "C", sa: 3, sb: 2, winner: "A" }] }, { name: "Bronze-medal match", matches: [{ label: "Bronze", a: "B", b: "D", sa: 1, sb: 0, winner: "B" }] }], title: "t" }),
  dendrogram: base("dendrogram", { icoord: [[5, 5, 15, 15]], dcoord: [[0, 1, 1, 0]], leaves: ["AAA", "BBB"], yLabel: "d" }),
  pca3d: base("pca3d", { rows: [{ x: 1, y: 2, z: 3, name: "n", noc: "N", group: "Cluster 1", size: 1 }, { x: -1, y: 0, z: 1, name: "m", noc: "M", group: "Cluster 2", size: 2 }], axes: ["PC1", "PC2", "PC3"] }),
  pairs: base("pairs", { vars: ["a", "b"], rows: [{ a: 1, b: 2, group: "g", name: "x" }, { a: 2, b: 3, group: "g", name: "y" }] }),
  flow: base("flow", { nodes: [{ id: "a", label: "A", sub: "1 row", col: 0, row: 0, kind: "source" }, { id: "b", label: "B", sub: "2 rows", col: 1, row: 0, kind: "gold" }], edges: [{ from: "a", to: "b" }], cols: 2, rows: 1 }),
  map: base("map", { frames: [{ label: "x", rows: [{ noc: "USA", iso3: "USA", name: "United States", v: 10 }] }, { label: "y", rows: [{ noc: "USA", iso3: "USA", name: "United States", v: 20 }] }], vLabel: "Medals", animate: true }),
  lorenz: base("lorenz", { rows: [{ share_of_nations: 0, share_of_medals: 0 }, { share_of_nations: 0.5, share_of_medals: 0.1 }, { share_of_nations: 1, share_of_medals: 1 }], x: "share_of_nations", y: "share_of_medals", gini: 0.8, xLabel: "x", yLabel: "y" }),
  pareto: base("pareto", { rows: [{ name: "A", medals: 10, cumulative_share: 0.6 }, { name: "B", medals: 5, cumulative_share: 1 }], x: "name", bar: "medals", line: "cumulative_share", barLabel: "Medals", lineLabel: "Cum." }),
  table: base("table", { columns: [{ key: "a", label: "A" }], rows: [{ a: 1 }, { a: 2 }] }),
  scorecard: base("scorecard", { tiles: [{ label: "L", value: "9", hint: "h", status: "ok" }], tables: [{ title: "T", columns: ["a"], rows: [{ a: 1 }] }] }),
};

function show(p: Payload, view = "default") {
  return render(<ThemeProvider>{renderView(p, view, 360, vi.fn())}</ThemeProvider>);
}

describe("visualization renderers", () => {
  it("has a renderer and a fixture for every kind", () => {
    expect(SUPPORTED_KINDS.length).toBeGreaterThanOrEqual(27);
    SUPPORTED_KINDS.forEach((k) => { expect(typeof RENDERERS[k]).toBe("function"); expect(FIXTURES[k], `fixture for ${k}`).toBeDefined(); });
  });
  it.each(Object.keys(FIXTURES))("renders kind %s without throwing", (k) => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const { container } = show(FIXTURES[k]);
    expect(container.innerHTML.length).toBeGreaterThan(50);
    const bad = spy.mock.calls.map((c) => c.join(" ")).filter((m) => /Element type is invalid|Cannot read|is not a function|Invariant failed/.test(m));
    spy.mockRestore();
    expect(bad).toEqual([]);
  });
  it("switches the same data between views", () => {
    const p = FIXTURES.xy;
    const views = availableViews(p);
    expect(views).toContain("line"); expect(views).toContain("area"); expect(views).toContain("table");
    ["line", "area", "bar", "stacked", "table"].forEach((v) => { const { container, unmount } = show(p, v); expect(container.innerHTML.length).toBeGreaterThan(20); unmount(); });
    const d = FIXTURES.donut;
    expect(availableViews(d)).toEqual(expect.arrayContaining(["bar", "table"]));
    ["bar", "treemap", "table"].forEach((v) => { const { container, unmount } = show(d, v); expect(container.innerHTML.length).toBeGreaterThan(20); unmount(); });
  });
  it("renders the table view with the chart's own rows", () => {
    const p = base("xy", FIXTURES.xy.data, { table: { columns: ["year", "A"], rows: [{ year: 1960, A: 10 }] } });
    const { getByText } = show(p, "table");
    expect(getByText("year")).toBeInTheDocument();
  });
});

describe("visualization utilities", () => {
  it("builds valid CSV with quoting", () => {
    expect(tableToCsv(["a", "b"], [{ a: 'x,"y"', b: null }, { a: 2, b: 3 }])).toBe('a,b\n"x,""y""",\n2,3');
  });
  it("formats cells and ticks", () => {
    expect(fmtCell(12.345, "pct1")).toBe("12.3%");
    expect(fmtCell(1234.4, "int")).toBe("1,234");
    expect(niceTicks(0, 100, 5)).toEqual([0, 20, 40, 60, 80, 100]);
  });
  it("interpolates a colour ramp", () => {
    expect(ramp(VIRIDIS, 0)).toBe("rgb(68,1,84)");
    expect(ramp(VIRIDIS, 1)).toBe("rgb(253,231,37)");
  });
});
