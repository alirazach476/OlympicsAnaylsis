import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it } from "vitest";
import App from "../App";
import { ThemeProvider } from "../lib/theme";
import { AssetProvider } from "../lib/assets";
import { EditionRegistryProvider } from "../themes/olympicThemeEngine";
import { ChartCard, PageHeader } from "../components/ui";
import { FindingsStrip } from "../components/analytics/KeyFindings";

const wrap = (ui: any, path = "/") => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ThemeProvider><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></ThemeProvider></QueryClientProvider>);

describe("chart card fullscreen", () => {
  it("expands to a fullscreen dialog and closes again with the button and with Esc", async () => {
    const user = userEvent.setup();
    wrap(<ChartCard title="Demo chart" subtitle="what it shows"><div>chart body</div></ChartCard>);
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Fullscreen" }));
    expect(screen.getByRole("dialog", { name: "Demo chart" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Exit fullscreen" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Fullscreen" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("analytics page header", () => {
  it("shows the section label and keeps a long method note behind a disclosure", () => {
    wrap(<PageHeader title="Medal analytics" subtitle={"Country totals count distinct podium results. ".repeat(8)} />, "/medals");
    expect(screen.getByText("Medal analytics", { selector: "div" })).toBeTruthy();
    expect(screen.getByText("Read the full method note")).toBeTruthy();
  });
  it("shows a short subtitle in full and works without any section", () => {
    wrap(<PageHeader title="Anything" subtitle="Short note." />, "/");
    expect(screen.getByText("Short note.")).toBeTruthy();
    expect(screen.queryByText("Read the full method note")).toBeNull();
  });
});

describe("key findings strip", () => {
  it("renders each finding with its label and detail, and nothing when empty", () => {
    const { unmount } = wrap(<FindingsStrip items={[{ k: "Hypothesis tests", v: 8, d: "each with CI" }, { k: "Best model", v: "linear regression" }]} />);
    expect(screen.getByText("Hypothesis tests")).toBeTruthy();
    expect(screen.getByText("linear regression")).toBeTruthy();
    unmount();
    wrap(<FindingsStrip items={[]} />);
    expect(screen.queryByTestId("key-findings")).toBeNull();
  });
});

let up = false;
beforeAll(async () => {
  try { up = (await fetch("http://127.0.0.1:8000/api/overview")).ok; } catch { up = false; }
});
const mount = (path: string) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } })}><ThemeProvider><AssetProvider><EditionRegistryProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></EditionRegistryProvider></AssetProvider></ThemeProvider></QueryClientProvider>);

describe("homepage (live API)", () => {
  it("shows the rings, the eight global statistics, every edition with its emblem and the charts from real data", async () => {
    if (!up) return;
    mount("/");
    expect(await screen.findByTestId("home-hero", {}, { timeout: 30000 })).toBeTruthy();
    expect(screen.getByTestId("home-hero").querySelector("img")).toBeNull();   // no photographic background on the overview
    const stats = await screen.findByTestId("global-stats", {}, { timeout: 30000 });
    for (const l of ["Editions", "Athletes", "NOCs", "Sports", "Disciplines", "Events", "Medals", "Matches"]) expect(within(stats).getByText(l)).toBeTruthy();
    await waitFor(() => expect(within(screen.getByTestId("summer-gallery")).getAllByTestId("edition-tile")).toHaveLength(19), { timeout: 20000 });
    expect(within(screen.getByTestId("winter-gallery")).getAllByTestId("edition-tile")).toHaveLength(20);
    expect(screen.getAllByTestId("coming-soon")).toHaveLength(4);
    await waitFor(() => expect(screen.getByTestId("top-athletes").children.length).toBe(8), { timeout: 20000 });
    expect(screen.getByText("Historical highlights")).toBeTruthy();
  }, 90000);

  it("an edition tile links to its edition page; an upcoming Games links to its Coming soon page", async () => {
    if (!up) return;
    mount("/");
    const g = await screen.findByTestId("summer-gallery", {}, { timeout: 30000 });
    await waitFor(() => expect(within(g).getAllByTestId("edition-tile").length).toBe(19), { timeout: 20000 });
    expect(g.querySelector('[data-edition="2024_summer"]')!.getAttribute("href")).toBe("/edition/2024_summer");
    expect(g.querySelector('[data-edition="2028_summer"]')!.getAttribute("href")).toBe("/edition/2028_summer");
  }, 90000);
});

describe("analytics pages show key findings from the API (live)", () => {
  it.each([["/statistics", /Hypothesis tests/], ["/machine-learning", /Best model/], ["/medals", /All-time leader/], ["/records", /Olympic records/]])("%s", async (path, label) => {
    if (!up) return;
    mount(path as string);
    const strip = await screen.findByTestId("key-findings", {}, { timeout: 40000 });
    expect(within(strip).getByText(label as RegExp)).toBeTruthy();
  }, 90000);
});
