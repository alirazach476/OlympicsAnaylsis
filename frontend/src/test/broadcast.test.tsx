import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import App from "../App";
import { ThemeProvider } from "../lib/theme";
import { AssetProvider } from "../lib/assets";
import { EditionRegistryProvider, Pictogram } from "../themes/olympicThemeEngine";
import { EditionBrandProvider, matchPictogram } from "../themes/editionBrand";
import { BroadcastScoreboard, family } from "../components/broadcast/MatchBoards";
import { MedalTable, ResultsTable } from "../components/tables/BroadcastTables";
import { SportPictogram } from "../components/broadcast/design";

// the app loads /assets/editions.json over HTTP; in jsdom serve the real file
const REGISTRY = readFileSync(join(__dirname, "../../public/assets/editions.json"), "utf-8");
const realFetch = globalThis.fetch;
globalThis.fetch = ((url: any, init?: any) => String(url).endsWith("/assets/editions.json") ? Promise.resolve(new Response(REGISTRY, { headers: { "Content-Type": "application/json" } })) : realFetch(url, init)) as any;

afterEach(() => cleanup());
let up = false;
beforeAll(async () => { try { up = (await realFetch("http://127.0.0.1:8000/api/overview")).ok; } catch { up = false; } }, 60000);

const providers = (ui: any, path = "/") => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } })}>
    <ThemeProvider><AssetProvider><EditionRegistryProvider><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></EditionRegistryProvider></AssetProvider></ThemeProvider>
  </QueryClientProvider>);
const mountApp = (path: string) => render(providers(<App />, path));
const branded = (ui: any, path = "/?games=2024_summer") => render(providers(<EditionBrandProvider>{ui}</EditionBrandProvider>, path));

const P = (sport: string, disc: string | null = null): Pictogram => ({ src: `/p/${sport}${disc ?? ""}.png`, label: sport, sport, sportId: 1, discipline: disc, sportLinked: true, linkedBy: "file name", duplicateOf: null, file_format: "png" });

describe("pictogram matching (verified file-name links only)", () => {
  const list = [P("Gymnastics"), P("Cycling", "track"), P("Cycling", "road"), P("Cycling"), P("Swimming"), { ...P("Mystery"), sportLinked: false, sport: null } as Pictogram];
  it("matches a sport by name, more specific names to the base sport, and prefers the named discipline", () => {
    expect(matchPictogram(list, "Swimming")?.sport).toBe("Swimming");
    expect(matchPictogram(list, "Artistic Gymnastics")?.sport).toBe("Gymnastics");
    expect(matchPictogram(list, "Cycling Track")?.discipline).toBe("track");
    expect(matchPictogram(list, "Cycling BMX Racing")?.discipline).toBeNull();
  });
  it("never invents a pictogram: unknown sport, unlinked image and empty list give nothing", () => {
    expect(matchPictogram(list, "Curling")).toBeUndefined();
    expect(matchPictogram(list, "Mystery")).toBeUndefined();
    expect(matchPictogram([], "Swimming")).toBeUndefined();
    expect(matchPictogram(undefined, "Swimming")).toBeUndefined();
  });
});

describe("design-system components read the selected edition", () => {
  it("SportPictogram shows the edition's own file, and labels an unavailable one", async () => {
    branded(<><SportPictogram sport="Athletics" gamesId="2024_summer" /><SportPictogram sport="Athletics" gamesId="2020_summer" /><SportPictogram sport="Curling" gamesId="2024_summer" /></>);
    const all = await screen.findAllByTestId("sport-pictogram");
    await waitFor(() => expect(screen.getAllByTestId("sport-pictogram").filter((e) => e.getAttribute("data-state") === "verified")).toHaveLength(2), { timeout: 10000 });
    const [paris, tokyo, curling] = screen.getAllByTestId("sport-pictogram");
    expect(paris.querySelector("img")!.getAttribute("src")).toContain("/2024_summer/");
    expect(tokyo.querySelector("img")!.getAttribute("src")).toContain("/2020_summer/");
    expect(curling.getAttribute("data-state")).toBe("unavailable");
    expect(all.length).toBe(3);
  });
  it("ResultsTable shows a record badge only for a verified record (athlete, event AND value)", () => {
    const rows = [{ position: "1", medal: "Gold", competitor: "Noah Lyles", noc: "USA", result_text: "9.784", event_name: "100 metres, Men" }, { position: "2", competitor: "Kishane Thompson", noc: "JAM", result_text: "9.789", event_name: "100 metres, Men" }];
    branded(<ResultsTable rows={rows} records={[{ level: "olympic", type: "Best performance", value: "9.784", event: "100 metres, Men", athlete: "Noah Lyles" }]} title="100 metres, Men" />);
    expect(screen.getAllByTestId("record-badge")).toHaveLength(1);
    expect(screen.getByTestId("record-badge").textContent).toBe("OR");
  });
  it("MedalTable shows medal discs with counts and flags, and the edition heading", () => {
    branded(<MedalTable rows={[{ rank_by_gold_silver_bronze: 1, noc_code: "USA", country_name: "United States", gold: 40, silver: 44, bronze: 42, total: 126 }]} title="Paris 2024 medal table" />);
    expect(screen.getByLabelText("40 gold")).toBeTruthy();
    expect(screen.getByLabelText("44 silver")).toBeTruthy();
    expect(screen.getByLabelText("42 bronze")).toBeTruthy();
    expect(screen.getByText("Paris 2024 medal table")).toBeTruthy();
    expect(screen.getAllByAltText(/United States flag/).length).toBe(1);
  });
});

describe("a scoreboard per sport, from recorded data only", () => {
  const base = { stage: "Final", match_date: "9 Aug 2024", location: "Arena", home_team: "A", home_noc: "FRA", away_team: "B", away_noc: "ESP", home_score: 3, away_score: 2, games_id: "2024_summer" };
  it("reads each sport's period columns correctly", () => {
    expect(family("Football")).toMatchObject({ kind: "football", cumulative: true });
    expect(family("Volleyball").heading).toBe("Set by set");
    expect(family("Basketball").heading).toBe("By half");
    expect(family("Ice Hockey").heading).toBe("By period");
  });
  it.each([["Football", "Score after each half"], ["Volleyball", "Set by set"], ["Basketball", "By half"], ["Ice Hockey", "By period"]])("%s scoreboard", (sport, heading) => {
    branded(<BroadcastScoreboard m={{ ...base, sport_name: sport, periods: [{ label: "Period #1", scores: [1, 0] }, { label: "Period #2", scores: [2, 2] }] }} />);
    expect(screen.getByTestId("period-strip").textContent).toContain(heading);
    expect(screen.getByLabelText("3 to 2")).toBeTruthy();
    expect(screen.getAllByText("Winner")).toHaveLength(1);
  });
  it("never invents a clock, a winner or a score", () => {
    branded(<BroadcastScoreboard m={{ ...base, sport_name: "Football", home_score: null, away_score: null, periods: [] }} />);
    expect(screen.getByLabelText("no score recorded")).toBeTruthy();
    expect(screen.queryByText("Winner")).toBeNull();
    expect(screen.queryByTestId("period-strip")).toBeNull();
  });
});

describe("selected edition persistence", () => {
  it("a future edition is shown on its own page but never becomes the app-wide selection", async () => {
    localStorage.clear();
    const { unmount } = branded(<span data-testid="x" />, "/edition/2028_summer");
    await waitFor(() => expect(screen.getByTestId("x")).toBeTruthy());
    expect(localStorage.getItem("selectedEdition")).toBeNull();
    unmount();
    branded(<span data-testid="y" />, "/team-sports?games=2028_summer");
    await waitFor(() => expect(screen.getByTestId("y")).toBeTruthy());
    expect(localStorage.getItem("selectedEdition")).toBe("2024_summer");
  });
  it("a past edition is remembered between visits", async () => {
    localStorage.clear();
    branded(<span data-testid="z" />, "/results?games=1964_summer");
    await waitFor(() => expect(localStorage.getItem("selectedEdition")).toBe("1964_summer"));
  });
});

describe("final acceptance: the five editions (live API, real data)", () => {
  it("1. Paris 2024 -> Athletics -> Men's 100 m results", async () => {
    if (!up) return;
    mountApp("/results?games=2024_summer");
    const root = await screen.findByTestId("edition-results", {}, { timeout: 40000 });
    expect(root.getAttribute("data-edition")).toBe("2024_summer");
    expect(screen.getByTestId("edition-background").getAttribute("data-edition")).toBe("2024_summer");
    expect(within(screen.getByTestId("page-header")).getAllByAltText("Paris 2024 emblem").length).toBeGreaterThan(0);
    const pods = await screen.findByTestId("podium", {}, { timeout: 40000 });
    await waitFor(() => expect(within(pods).getAllByTestId("individual-card")).toHaveLength(3), { timeout: 30000 });
    expect(within(pods).getAllByTestId("individual-card")[0].textContent).toMatch(/Noah Lyles/);
    expect(within(pods).getAllByTestId("sport-pictogram")[0].querySelector("img")!.getAttribute("src")).toContain("/2024_summer/");
    expect(screen.getByRole("tab", { name: /Athletics/, selected: true })).toBeTruthy();
    const table = await screen.findByTestId("broadcast-table", {}, { timeout: 30000 });
    expect(table.getAttribute("data-variant")).toBe("results");
    expect(within(table).getAllByTestId("country-flag").length).toBeGreaterThan(3);
  }, 120000);

  it("2. Tokyo 2020 -> Swimming -> medal results", async () => {
    if (!up) return;
    const user = userEvent.setup();
    mountApp("/results?games=2020_summer");
    await screen.findByTestId("edition-results", {}, { timeout: 40000 });
    await user.click(await screen.findByRole("tab", { name: /^Swimming$/ }, { timeout: 30000 }));
    await user.click(screen.getByRole("tab", { name: "Medal winners" }));
    const winners = await screen.findByTestId("medal-winners", {}, { timeout: 40000 });
    await waitFor(() => expect(within(winners).getAllByTestId("medal-chip").length).toBeGreaterThanOrEqual(6), { timeout: 40000 });
    expect(within(screen.getByTestId("page-header")).getAllByAltText("Tokyo 2020 emblem").length).toBeGreaterThan(0);
    expect(within(winners).getAllByTestId("sport-pictogram")[0].querySelector("img")!.getAttribute("src")).toContain("/2020_summer/");
    await waitFor(() => expect(["Gold", "Silver", "Bronze"].every((m) => within(winners).getAllByTestId("medal-chip").some((c) => c.getAttribute("data-medal") === m))).toBe(true), { timeout: 40000 });
  }, 150000);

  it("3. Beijing 2022 -> Ice Hockey -> match scoreboard", async () => {
    if (!up) return;
    const user = userEvent.setup();
    mountApp("/team-sports?games=2022_winter");
    await user.click(await screen.findByRole("tab", { name: /Ice Hockey/ }, { timeout: 30000 }));
    const cards = await screen.findAllByTestId("scorecard", {}, { timeout: 40000 });
    expect(cards[0].getAttribute("data-family")).toBe("icehockey");
    await waitFor(() => expect(within(cards[0]).getByTestId("period-strip").textContent).toMatch(/By period/), { timeout: 20000 });
    expect(within(screen.getByTestId("page-header")).getAllByAltText("Beijing 2022 emblem").length).toBeGreaterThan(0);
    await user.click(cards[0]);
    const view = await screen.findByTestId("match-broadcast", {}, { timeout: 40000 });
    expect(within(view).getByText("Team statistics")).toBeTruthy();
    expect(within(view).getAllByTestId("stat-row").length).toBeGreaterThanOrEqual(3);
  }, 150000);

  it("4. London 2012 -> Basketball -> match results", async () => {
    if (!up) return;
    const user = userEvent.setup();
    mountApp("/team-sports?games=2012_summer");
    await user.click(await screen.findByRole("tab", { name: /^Basketball$/ }, { timeout: 30000 }));
    const cards = await screen.findAllByTestId("scorecard", {}, { timeout: 40000 });
    expect(cards[0].getAttribute("data-family")).toBe("basketball");
    await user.click(screen.getByRole("button", { name: "Table" }));
    const table = await screen.findByTestId("broadcast-table", {}, { timeout: 30000 });
    expect(table.getAttribute("data-variant")).toBe("match");
    expect(within(table).getAllByRole("row").length).toBeGreaterThan(5);
    expect(within(screen.getByTestId("page-header")).getAllByAltText("London 2012 emblem").length).toBeGreaterThan(0);
  }, 150000);

  it("5. Milano Cortina 2026 -> winter sports -> edition page", async () => {
    if (!up) return;
    const user = userEvent.setup();
    mountApp("/edition/2026_winter");
    const hero = await screen.findByTestId("edition-hero", {}, { timeout: 40000 });
    expect(within(hero).getByAltText(/2026 emblem/)).toBeTruthy();
    expect(screen.getByTestId("edition-background").getAttribute("data-edition")).toBe("2026_winter");
    await user.click(screen.getByRole("tab", { name: /Sports & Disciplines/i }));
    const table = await screen.findByTestId("broadcast-table", {}, { timeout: 30000 });
    await waitFor(() => expect(within(table).getAllByTestId("sport-pictogram").filter((e) => e.getAttribute("data-state") === "verified").length).toBeGreaterThan(5), { timeout: 30000 });
    expect(within(table).getAllByTestId("sport-pictogram")[0].querySelector("img")!.getAttribute("src")).toContain("/2026_winter/");
  }, 150000);

  it("switching the selected edition restyles the whole page (background, header, pictograms)", async () => {
    if (!up) return;
    const user = userEvent.setup();
    mountApp("/results?games=2024_summer");
    await screen.findByTestId("podium", {}, { timeout: 40000 });
    const before = screen.getByTestId("edition-background").getAttribute("data-edition");
    await user.selectOptions(screen.getByLabelText("Selected edition"), "2020_summer");
    await waitFor(() => expect(screen.getByTestId("edition-background").getAttribute("data-edition")).toBe("2020_summer"), { timeout: 20000 });
    expect(before).toBe("2024_summer");
    await waitFor(() => expect(within(screen.getByTestId("page-header")).getAllByAltText("Tokyo 2020 emblem").length).toBeGreaterThan(0), { timeout: 20000 });
    await waitFor(() => expect(screen.getAllByTestId("sport-pictogram")[0].querySelector("img")?.getAttribute("src") ?? "").toContain("/2020_summer/"), { timeout: 20000 });
  }, 150000);
});
