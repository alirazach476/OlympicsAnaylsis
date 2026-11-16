import { render, screen, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { fmtInt, fmtNum, fmtP, fmtPct, gamesLabel } from "../lib/fmt";
import { qs, csvUrl } from "../lib/api";
import { DataTable } from "../components/DataTable";
import { Async, Empty, ErrorBox, Kpi, Loading, SeasonToggle } from "../components/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Shell, { NAV } from "../components/Shell";
import { ThemeProvider } from "../lib/theme";
import { LineSeries, Bars, Heat } from "../charts/charts";

describe("formatting", () => {
  it("formats numbers without inventing values", () => {
    expect(fmtInt(12345)).toBe("12,345");
    expect(fmtInt(null)).toBe("–");
    expect(fmtNum(1.23456, 2)).toBe("1.23");
    expect(fmtNum("abc")).toBe("–");
    expect(fmtPct(0.4806)).toBe("48.1%");
  });
  it("never prints a p-value of exactly 0", () => {
    expect(fmtP(0)).toBe("< 1e-16");
    expect(fmtP(0.0421)).toBe("0.0421");
    expect(fmtP(0.00001234)).toMatch(/e-5$/);
    expect(fmtP(null)).toBe("–");
  });
  it("labels games", () => expect(gamesLabel("2024_summer")).toBe("2024 Summer"));
  it("builds query strings and skips empty params", () => {
    expect(qs({ a: 1, b: "", c: undefined, d: "x y" })).toBe("?a=1&d=x+y");
    expect(csvUrl("/results", { sport: "Swimming" })).toContain("format=csv");
  });
});

describe("DataTable", () => {
  const rows = [{ name: "B", n: 2 }, { name: "A", n: 10 }, { name: "C", n: 5 }];
  it("shows an empty state for no rows", () => {
    render(<DataTable rows={[]} columns={[{ key: "name" }]} empty="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
  it("renders rows and sorts when a header is clicked", async () => {
    render(<DataTable rows={rows} columns={[{ key: "name" }, { key: "n", align: "right" }]} />);
    expect(screen.getByText("10")).toBeInTheDocument();
    const header = screen.getByRole("columnheader", { name: "n" });
    await userEvent.click(header);
    const body = screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);
    expect(body).toEqual(["A", "C", "B"]);        // numeric columns sort largest-first on first click: 10, 5, 2
    await userEvent.click(header);
    const desc = screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);
    expect(desc).toEqual(["B", "C", "A"]);         // second click reverses to ascending
  });
  it("offers CSV export of the loaded view", () => {
    render(<DataTable rows={rows} columns={[{ key: "name" }]} exportName="x" csvHref="/api/x?format=csv" />);
    expect(screen.getByText(/CSV \(all matching\)/)).toHaveAttribute("href", "/api/x?format=csv");
    expect(screen.getByText(/CSV \(this view\)/)).toBeInTheDocument();
  });
});

describe("async states", () => {
  it("shows loading, error and empty states", () => {
    const { rerender } = render(<Async q={{ isLoading: true, error: null }}>{() => <div>data</div>}</Async>);
    expect(screen.getByRole("status")).toBeInTheDocument();
    rerender(<Async q={{ isLoading: false, error: new Error("500 boom") }}>{() => <div>data</div>}</Async>);
    expect(screen.getByRole("alert")).toHaveTextContent("500 boom");
    rerender(<Async q={{ isLoading: false, error: null, data: undefined }}>{() => <div>data</div>}</Async>);
    expect(screen.getByTestId("empty")).toBeInTheDocument();
    rerender(<Async q={{ isLoading: false, error: null, data: [1] as any }}>{(d) => <div>got {d.length}</div>}</Async>);
    expect(screen.getByText("got 1")).toBeInTheDocument();
  });
  it("toggles season filter", async () => {
    let v = "";
    const { rerender } = render(<SeasonToggle value={v} onChange={(x) => (v = x)} />);
    await userEvent.click(screen.getByRole("button", { name: "Winter" }));
    expect(v).toBe("winter");
    rerender(<SeasonToggle value="winter" onChange={() => undefined} />);
    expect(screen.getByRole("button", { name: "Winter" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("navigation shell", () => {
  it("exposes the 9 main sections (Countries & Medal Statistics combined, no admin pages) and toggles theme", async () => {
    render(<QueryClientProvider client={new QueryClient()}><ThemeProvider><MemoryRouter><Shell /></MemoryRouter></ThemeProvider></QueryClientProvider>);
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getAllByRole("link")).toHaveLength(NAV.length);
    expect(NAV.length).toBe(9);
    expect(NAV.filter((n) => /Countries|Medal/.test(n.label)).map((n) => n.label)).toEqual(["Countries & Medal Statistics"]);
    expect(NAV.some((n) => n.to === "/assets" || n.to === "/crawler")).toBe(false);
    expect(NAV.some((n) => n.to === "/visualizations")).toBe(true);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    await userEvent.click(screen.getAllByRole("button", { name: /theme/i })[0]);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
  it("opens the mobile menu", async () => {
    render(<QueryClientProvider client={new QueryClient()}><ThemeProvider><MemoryRouter><Shell /></MemoryRouter></ThemeProvider></QueryClientProvider>);
    const btn = screen.getByRole("button", { name: "Menu" });
    expect(btn).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(btn);
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });
});

describe("charts", () => {
  it("show an empty state instead of a blank chart", () => {
    render(<ThemeProvider><LineSeries data={[]} x="x" series={[{ key: "y" }]} /></ThemeProvider>);
    expect(screen.getByTestId("empty")).toBeInTheDocument();
    render(<ThemeProvider><Bars data={[]} x="x" series={[{ key: "y" }]} /></ThemeProvider>);
    expect(screen.getAllByTestId("empty").length).toBe(2);
  });
  it("renders a heat-map with accessible cell titles", () => {
    render(<Heat rowsLabels={["a", "b"]} colLabels={["a", "b"]} values={[[1, 0.5], [0.5, 1]]} />);
    expect(screen.getAllByTitle(/a × b: 0.5/).length).toBeGreaterThan(0);
  });
  it("KPI renders label", () => {
    render(<Kpi label="Athletes" value="1,000" />);
    expect(screen.getByText("Athletes")).toBeInTheDocument();
  });
});
