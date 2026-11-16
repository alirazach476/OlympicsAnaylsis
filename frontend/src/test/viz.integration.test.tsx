/**
 * Integration: the visualization library against the REAL running API (no mocks except one failure injection).
 * Start the API first:  uvicorn backend.api.main:app --port 8000   (tests are skipped if it is not reachable)
 */
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ThemeProvider } from "../lib/theme";
import { AssetProvider } from "../lib/assets";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

let up = false;
let registry: any = null;
const API = (window as any).__API_BASE__ as string;
beforeAll(async () => {
  try {
    const r = await fetch(`${API}/viz/registry`);
    up = r.ok;
    if (up) {
      registry = await r.json();
      // warm the API's query cache (heavy charts compute on first request) so the tests measure rendering, not a cold start
      const ids: string[] = registry.charts.map((c: any) => c.id);
      for (let i = 0; i < ids.length; i += 4) await Promise.all(ids.slice(i, i + 4).map((id) => fetch(`${API}/viz/chart/${id}`).catch(() => undefined)));
    }
  } catch { up = false; }
}, 600000);

function mount(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(<QueryClientProvider client={qc}><ThemeProvider><AssetProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></AssetProvider></ThemeProvider></QueryClientProvider>);
}
const settled = (n: number) => waitFor(() => {
  expect(screen.getAllByTestId(/^viz-/).length).toBeGreaterThanOrEqual(n);
  expect(screen.queryAllByText("Loading chart…")).toHaveLength(0);
}, { timeout: 60000, interval: 400 });

describe("visualization library (live API)", () => {
  it("registry documents every chart with the required fields", async () => {
    if (!up) return;
    expect(registry.total).toBeGreaterThanOrEqual(106);
    for (const c of registry.charts) {
      for (const k of ["id", "page", "name", "kind", "dataset", "source_table", "purpose", "filters", "endpoint", "status"]) expect(c[k], `${c.id}.${k}`).toBeDefined();
      expect(c.endpoint).toBe(`/api/viz/chart/${c.id}`);
    }
    expect(new Set(registry.charts.map((c: any) => c.id)).size).toBe(registry.total);
  });

  for (const section of [1, 2, 3, 4, 5, 6, 7, 8]) {
    it(`section ${section}: every chart loads real data without an error state`, async () => {
      if (!up) return;
      const expected = registry.charts.filter((c: any) => c.section === section).length;
      const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
      mount(`/visualizations?section=${section}`);
      await settled(expected);
      expect(screen.getAllByTestId(/^viz-/)).toHaveLength(expected);
      expect(screen.queryAllByRole("alert")).toHaveLength(0);
      expect(screen.queryAllByTestId("unavailable")).toHaveLength(0);
      expect(screen.getAllByTestId("interpretation").length).toBeGreaterThanOrEqual(expected - 1);
      const reactErrors = spy.mock.calls.map((c) => c.join(" ")).filter((m) => /Element type is invalid|Cannot read|is not a function|Invariant failed|Rendered (more|fewer) hooks/.test(m));
      spy.mockRestore();
      expect(reactErrors).toEqual([]);
    }, 90000);
  }
});

describe("chart interactions (live API)", () => {
  it("data table, CSV download, full screen and view switching work on a card", async () => {
    if (!up) return;
    mount("/visualizations?section=2");
    const card = await screen.findByTestId("viz-c_rank_hbar", {}, { timeout: 40000 });
    await waitFor(() => expect(within(card).queryByText("Loading chart…")).not.toBeInTheDocument(), { timeout: 40000 });
    await userEvent.click(within(card).getByLabelText("Toggle data table"));
    expect(within(card).getByRole("table")).toBeInTheDocument();
    await userEvent.click(within(card).getByLabelText("Toggle data table"));
    const create = vi.fn(() => "blob:x");
    (URL as any).createObjectURL = create; (URL as any).revokeObjectURL = vi.fn();
    await userEvent.click(within(card).getByLabelText("Download CSV"));
    expect(create).toHaveBeenCalled();
    const sel = within(card).getByLabelText("Chart view") as HTMLSelectElement;
    expect([...sel.options].map((o) => o.value)).toEqual(expect.arrayContaining(["bar", "donut", "treemap", "table"]));
    await userEvent.selectOptions(sel, "donut");
    expect(sel.value).toBe("donut");
    expect(within(card).queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.click(within(card).getByLabelText("Full screen"));
    expect(within(card).getByLabelText("Exit full screen")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(within(card).getByLabelText("Full screen")).toBeInTheDocument());
  }, 90000);

  it("a season filter re-queries charts and shows a removable chip", async () => {
    if (!up) return;
    mount("/visualizations?section=2");
    const card = await screen.findByTestId("viz-c_rank_hbar", {}, { timeout: 40000 });
    await waitFor(() => expect(within(card).getByTestId("interpretation")).toHaveTextContent("Summer + Winter"), { timeout: 40000 });
    await userEvent.click(screen.getByRole("button", { name: "Winter" }));
    await waitFor(() => expect(within(card).getByTestId("interpretation")).not.toHaveTextContent("Summer + Winter"), { timeout: 40000 });
    expect(within(card).getByTestId("interpretation")).toHaveTextContent("Winter");
    const chip = screen.getAllByTestId("filter-chip")[0];
    expect(chip).toHaveTextContent("Season: winter");
    await userEvent.click(within(chip).getByRole("button"));
    await waitFor(() => expect(screen.queryAllByTestId("filter-chip")).toHaveLength(0));
  }, 90000);

  it("clicking a heatmap row opens its records and can cross-filter every chart", async () => {
    if (!up) return;
    mount("/visualizations?section=2");
    const card = await screen.findByTestId("viz-c_rank_heatmap", {}, { timeout: 40000 });
    const usa = await within(card).findByText("USA", {}, { timeout: 40000 });
    await userEvent.click(usa);
    const dlg = await screen.findByRole("dialog", {}, { timeout: 20000 });
    expect(await within(dlg).findByText(/Medal-table results for USA/, {}, { timeout: 20000 })).toBeInTheDocument();
    expect(within(dlg).getAllByRole("button", { name: /CSV/ }).length).toBeGreaterThanOrEqual(1);
    await userEvent.click(within(dlg).getByRole("button", { name: /Filter all charts by this/ }));
    await waitFor(() => expect(screen.getAllByTestId("filter-chip")[0]).toHaveTextContent("Nation: USA"));
  }, 90000);

  it("an event with no data shows the 'not available' state with the reason", async () => {
    if (!up) return;
    mount("/visualizations?section=4");
    const card = await screen.findByTestId("viz-s_result_hist", {}, { timeout: 40000 });
    await waitFor(() => expect(within(card).queryByText("Loading chart…")).not.toBeInTheDocument(), { timeout: 40000 });
    await userEvent.type(within(card).getByLabelText("Event"), "Zzz");
    expect(await within(card).findByTestId("unavailable", {}, { timeout: 30000 })).toHaveTextContent(/no results for Athletics \/ Zzz/);
  }, 90000);

  it("a failing chart request shows an error with a retry button, without breaking other charts", async () => {
    if (!up) return;
    const real = globalThis.fetch;
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(((url: any, init: any) => String(url).includes("/viz/chart/c_grouped_gsb") ? Promise.resolve(new Response(JSON.stringify({ detail: "boom" }), { status: 500 })) : real(url, init)) as any);
    mount("/visualizations?section=2");
    const bad = await screen.findByTestId("viz-c_grouped_gsb", {}, { timeout: 40000 });
    expect(await within(bad).findByRole("alert", {}, { timeout: 30000 })).toHaveTextContent(/could not be loaded/i);
    expect(within(bad).getByRole("button", { name: /Retry/ })).toBeInTheDocument();
    const good = await screen.findByTestId("viz-c_rank_hbar");
    await waitFor(() => expect(within(good).getByTestId("interpretation")).toBeInTheDocument(), { timeout: 40000 });
    spy.mockRestore();
  }, 90000);

  it("the coverage tab lists every planned item with a status", async () => {
    if (!up) return;
    mount("/visualizations");
    await userEvent.click(await screen.findByRole("tab", { name: "Registry & coverage" }));
    expect(await screen.findByText("Visualization registry", {}, { timeout: 30000 })).toBeInTheDocument();
    for (const h of ["Chart ID", "Dashboard page", "Chart type", "Source table", "Backend endpoint"]) expect((await screen.findAllByText(h, {}, { timeout: 30000 })).length).toBeGreaterThan(0);
  }, 60000);
});

describe("existing dashboard pages embed the library", () => {
  it("Countries & Medal Statistics has a separate Visuals page that shows every chart directly (nothing to open)", async () => {
    if (!up) return;
    mount("/countries/visuals");
    expect(await screen.findByTestId("countries-visuals", {}, { timeout: 30000 })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Visualization library/ })).toBeNull();
    await waitFor(() => expect(screen.getAllByTestId(/^viz-(?!section)/).length).toBeGreaterThanOrEqual(5), { timeout: 40000 });
  }, 90000);
});
