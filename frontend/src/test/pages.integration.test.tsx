/**
 * Integration: every route is rendered in jsdom against the REAL running API (no mocks).
 * Start the API first:  uvicorn backend.api.main:app --port 8000   (tests are skipped if it is not reachable)
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ThemeProvider } from "../lib/theme";
import { AssetProvider } from "../lib/assets";

let up = false;
beforeAll(async () => {
  try {
    up = (await fetch("http://127.0.0.1:8000/api/overview")).ok;
    // warm the heavier endpoints once so route tests are not timed against a cold API
    for (const u of ["/api/statistics/explore", "/api/statistics/hypothesis-tests", "/api/statistics/regression", "/api/statistics/time-series", "/api/eda", "/api/machine-learning/models"]) await fetch("http://127.0.0.1:8000" + u).catch(() => undefined);
  } catch {
    up = false;
  }
}, 300000);

function mount(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}><ThemeProvider><AssetProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></AssetProvider></ThemeProvider></QueryClientProvider>
  );
}

const ROUTES: [string, RegExp][] = [
  ["/", /Olympic Games/i],
  ["/summer", /Summer Olympics/i],
  ["/winter", /Winter Olympics/i],
  ["/edition/2024_summer", /Medal Standings/i],
  ["/countries", /Countries & Medal Statistics/i],
  ["/countries/USA", /United States/i],
  ["/athletes", /Athlete explorer/i],
  ["/sports", /Summer sports/i],
  ["/results", /Event results explorer/i],
  ["/medals", /Medal analytics/i],
  ["/statistics", /Statistical analysis/i],
  ["/machine-learning", /Machine learning/i],
  ["/team-sports", /Team sports/i],
  ["/records", /Records & achievements/i],
  ["/engineering", /Data engineering monitor/i],
];

describe.each(ROUTES)("route %s (live API)", (path, heading) => {
  it("renders real data without an error state", async () => {
    if (!up) return;
    const errors: any[] = [];
    const spy = vi.spyOn(console, "error").mockImplementation((...a) => { errors.push(a.join(" ")); });
    mount(path);
    await waitFor(() => expect(screen.getAllByText(heading).length).toBeGreaterThan(0), { timeout: 20000 });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument(), { timeout: 20000 });
    expect(screen.queryByText("Could not load data")).not.toBeInTheDocument();
    const reactErrors = errors.filter((e) => /Error:|Uncaught|Cannot read|is not a function|undefined/.test(e) && !/ResponsiveContainer|width\(0\)|act\(/.test(e));
    expect(reactErrors).toEqual([]);
    spy.mockRestore();
  });
});

describe("behaviour against live data", () => {
  it("overview shows KPI cards with the real edition count", async () => {
    if (!up) return;
    mount("/");
    await waitFor(() => expect(screen.getAllByTestId("kpi").length).toBeGreaterThanOrEqual(6), { timeout: 20000 });
    expect(within(screen.getByTestId("global-stats")).getByText("Editions")).toBeInTheDocument();
  });
  it("summer page lists 17 held editions + 2 coming soon, winter 18 + 2", async () => {
    if (!up) return;
    const a = mount("/summer");
    await waitFor(() => expect(screen.getAllByTestId("edition-tile")).toHaveLength(19), { timeout: 20000 });
    expect(screen.getAllByTestId("coming-soon")).toHaveLength(2);
    a.unmount();
    mount("/winter");
    await waitFor(() => expect(screen.getAllByTestId("edition-tile")).toHaveLength(20), { timeout: 20000 });
    expect(screen.getAllByTestId("coming-soon")).toHaveLength(2);
  });
  it("athlete search filters the table", async () => {
    if (!up) return;
    mount("/athletes");
    const box = await screen.findByLabelText("Search athletes");
    await userEvent.type(box, "Phelps");
    await waitFor(() => expect(screen.getAllByText(/Phelps/).length).toBeGreaterThan(0), { timeout: 20000 });
  });
  it("hypothesis tests page shows every required field", async () => {
    if (!up) return;
    mount("/statistics");
    await userEvent.click(await screen.findByRole("tab", { name: "Hypothesis tests" }));
    const cards = await screen.findAllByTestId("hypothesis", {}, { timeout: 20000 });
    expect(cards.length).toBeGreaterThanOrEqual(7);
    for (const label of ["H0", "H1", "Method", "Sample size", "Statistic", "p-value", "Effect size"]) expect(within(cards[0]).getByText(label)).toBeInTheDocument();
  });
  it("statistics explorer recomputes when a filter changes", async () => {
    if (!up) return;
    mount("/statistics");
    await screen.findByText(/Athlete age distribution/i, {}, { timeout: 20000 });
    await userEvent.selectOptions(screen.getByLabelText("Season"), "winter");
    await waitFor(() => expect(screen.getByText(/participations with a recorded age/)).toBeInTheDocument(), { timeout: 20000 });
  });
  it("machine learning page labels results as a backtest", async () => {
    if (!up) return;
    mount("/machine-learning");
    expect(await screen.findByText(/HISTORICAL BACKTEST/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Model comparison/)).toBeInTheDocument(), { timeout: 20000 });
  });
  it("unknown country shows the error state, not a crash", async () => {
    if (!up) return;
    mount("/countries/ZZZ");
    expect(await screen.findByRole("alert", {}, { timeout: 20000 })).toHaveTextContent(/404/);
  });
});
