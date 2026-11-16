import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import App from "../App";
import { DataTable } from "../components/DataTable";
import { SavedTables } from "../components/broadcast/SavedTables";
import { FilterBar } from "../components/analytics/FilterBar";
import { useCrossFilter } from "../lib/crossFilter";
import { ThemeProvider } from "../lib/theme";
import { AssetProvider } from "../lib/assets";
import { EditionRegistryProvider } from "../themes/olympicThemeEngine";

afterEach(() => cleanup());

const qc = () => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
const wrap = (ui: any, path = "/") => render(<QueryClientProvider client={qc()}><ThemeProvider><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></ThemeProvider></QueryClientProvider>);
const mount = (path: string) => render(<QueryClientProvider client={qc()}><ThemeProvider><AssetProvider><EditionRegistryProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></EditionRegistryProvider></AssetProvider></ThemeProvider></QueryClientProvider>);

/** Capture what a CSV download would contain. */
function captureCsv() {
  let body = "", name = "";
  const blobs: Blob[] = [];
  (URL as any).createObjectURL = (b: Blob) => { blobs.push(b); return "blob:x"; };
  (URL as any).revokeObjectURL = () => undefined;
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { name = this.download; });
  return { read: async () => { body = await blobs[blobs.length - 1].text(); return { body, name }; }, restore: () => click.mockRestore() };
}

describe("every table exports CSV", () => {
  it("DataTable always offers CSV, in the current sort order and with the visible column titles", async () => {
    const cap = captureCsv();
    const user = userEvent.setup();
    wrap(<DataTable rows={[{ noc_code: "USA", gold: 40 }, { noc_code: "CHN", gold: 40 }, { noc_code: "GBR", gold: 14 }]} columns={[{ key: "noc_code", header: "NOC" }, { key: "gold", header: "Gold" }]} />);
    await user.click(screen.getByRole("columnheader", { name: /Gold/ }));   // numbers sort descending first
    await user.click(screen.getByRole("columnheader", { name: /Gold/ }));   // then ascending
    await user.click(screen.getByRole("button", { name: /CSV \(this view\)/ }));
    const { body, name } = await cap.read();
    expect(name).toBe("noc_code.csv");
    const lines = body.split("\n");
    expect(lines[0].replace(/"/g, "")).toBe("NOC,Gold");
    expect(lines[1]).toContain("GBR");   // 14 first when sorted ascending
    cap.restore();
  });

  it("saved page tables each get their own CSV button", () => {
    wrap(<SavedTables tables={[{ index: 0, section: "Round One", headers: ["Pos", "Competitor"], rows: [["1", "A"]], links: [] }, { index: 1, section: "Heat 1", headers: ["Pos", "Competitor"], rows: [["1", "B"]], links: [] }]} />);
    expect(screen.getAllByRole("button", { name: /as CSV/ })).toHaveLength(2);
  });
});

describe("cross-filter state", () => {
  function Probe() {
    const xf = useCrossFilter(["noc", "sport"]);
    const loc = useLocation();
    return (
      <div>
        <button onClick={() => xf.set("noc", "USA")}>pick USA</button><button onClick={() => xf.set("sport", "7")}>pick sport</button><button onClick={xf.clear}>clear</button>
        <span data-testid="url">{loc.search}</span><span data-testid="active">{xf.active.join(",")}</span>
        <FilterBar onClear={xf.clear} onRemove={(k) => xf.set(k, "", false)} filters={xf.active.map((k) => ({ key: k, label: k, value: xf.values[k] }))} />
      </div>
    );
  }
  it("puts the selection in the URL, toggles it off when clicked again, and clears everything", async () => {
    const user = userEvent.setup();
    wrap(<Probe />);
    await user.click(screen.getByText("pick USA"));
    expect(screen.getByTestId("url").textContent).toBe("?noc=USA");
    expect(screen.getByTestId("filter-bar")).toBeTruthy();
    await user.click(screen.getByText("pick sport"));
    expect(screen.getByTestId("active").textContent).toBe("noc,sport");
    await user.click(screen.getByText("pick USA"));          // same item again: toggles off
    expect(screen.getByTestId("active").textContent).toBe("sport");
    await user.click(screen.getByText("clear"));
    expect(screen.getByTestId("url").textContent).toBe("");
    expect(screen.getByTestId("filter-hint")).toBeTruthy();
  });
  it("restores a shared filtered view from the URL", () => {
    wrap(<Probe />, "/x?noc=GER&sport=3");
    expect(screen.getByTestId("active").textContent).toBe("noc,sport");
    expect(screen.getByRole("button", { name: /Remove filter noc: GER/ })).toBeTruthy();
  });
  it("a clicked table row can select a country (keyboard and mouse)", async () => {
    const user = userEvent.setup();
    const picked: string[] = [];
    wrap(<DataTable rows={[{ noc_code: "USA" }, { noc_code: "CHN" }]} columns={[{ key: "noc_code", header: "NOC" }]} onRowClick={(r) => picked.push(r.noc_code)} selectedKey={(r) => r.noc_code === "CHN"} />);
    const rows = screen.getAllByRole("row").filter((r) => r.getAttribute("tabindex") === "0");
    await user.click(rows[0]);
    rows[1].focus();
    await user.keyboard("{Enter}");
    expect(picked).toEqual(["USA", "CHN"]);
    expect(rows[1].getAttribute("aria-selected")).toBe("true");
  });
});

let up = false;
beforeAll(async () => {
  try { up = (await fetch("http://127.0.0.1:8000/api/overview")).ok; } catch { up = false; }
}, 60000);

describe("edition page sections (live API)", () => {
  it("clicking a country in the medal standings opens that country at this edition, and the open section is kept in the URL", async () => {
    if (!up) return;
    const user = userEvent.setup();
    mount("/edition/2024_summer?tab=medals");
    const table = await screen.findByTestId("broadcast-table", {}, { timeout: 30000 });
    await waitFor(() => expect(within(table).getAllByText(/France/).length).toBeGreaterThan(0), { timeout: 20000 });
    await user.click(screen.getByRole("tab", { name: "Participants" }));
    await waitFor(() => expect(screen.getByTestId("participant-count").textContent).toMatch(/athletes/), { timeout: 30000 });
    expect(screen.getByRole("tab", { name: "Participants" }).getAttribute("aria-selected")).toBe("true");
  }, 90000);
});

describe("country comparison page (live API)", () => {
  it("shows the chosen countries, the side-by-side table with CSV, and lets you add and remove a country", async () => {
    if (!up) return;
    const user = userEvent.setup();
    mount("/compare/countries?nocs=USA,CHN");
    const cards = await screen.findByTestId("country-cards", {}, { timeout: 30000 });
    await waitFor(() => expect(within(cards).getAllByRole("button")).toHaveLength(2), { timeout: 20000 });
    await waitFor(() => expect(screen.getByText("Total medals")).toBeTruthy(), { timeout: 30000 });
    expect(screen.getAllByRole("button", { name: /CSV \(this view\)/ }).length).toBeGreaterThan(0);
    // focus a country by clicking its card
    await user.click(within(cards).getAllByRole("button")[0]);
    expect((await screen.findByTestId("filter-bar")).textContent).toMatch(/Country:\s*USA/);
    // add a third country
    await waitFor(() => expect(screen.getByLabelText("Add a country").querySelectorAll("option").length).toBeGreaterThan(10), { timeout: 20000 });
    await user.selectOptions(screen.getByLabelText("Add a country"), "GBR");
    await waitFor(() => expect(within(screen.getByTestId("country-cards")).getAllByRole("button")).toHaveLength(3), { timeout: 20000 });
    // at least two countries must remain
    const picker = screen.getByTestId("country-picker");
    await user.click(within(picker).getByRole("button", { name: /Remove Great Britain|Remove GBR/ }));
    await waitFor(() => expect(within(screen.getByTestId("country-cards")).getAllByRole("button")).toHaveLength(2), { timeout: 20000 });
    expect((within(picker).getAllByRole("button") as HTMLButtonElement[]).every((b) => !b.getAttribute("aria-label")?.startsWith("Remove") || b.disabled)).toBe(true);
  }, 120000);
});

describe("CSV audit: every table on every main page has a CSV button (live API)", () => {
  const ROUTES = ["/", "/medals", "/records", "/sports", "/athletes", "/countries", "/countries/GER", "/results", "/team-sports", "/edition/2024_summer", "/compare/countries", "/assets", "/engineering", "/athletes/72064", "/sports/1"];
  it.each(ROUTES)("%s", async (route) => {
    if (!up) return;
    mount(route);
    await waitFor(() => expect(document.querySelector("h1")).toBeTruthy(), { timeout: 40000 });
    // wait for tables to appear (some pages are mostly charts); when a page really has none there is nothing to export
    await waitFor(() => expect(document.querySelectorAll("table").length).toBeGreaterThan(0), { timeout: 8000 }).catch(() => undefined);
    await new Promise((r) => setTimeout(r, 1500));
    const missing = [...document.querySelectorAll("table")].filter((t) => !t.closest("[data-csv-scope]")?.querySelector("[data-csv]"));
    expect(missing.length, `${missing.length} table(s) without a CSV button on ${route}`).toBe(0);
  }, 120000);
});
