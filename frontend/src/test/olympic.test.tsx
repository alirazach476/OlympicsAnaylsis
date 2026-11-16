import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OlympicRings } from "../components/OlympicRings";
import { Crumbs } from "../components/navigation/Crumbs";
import { SavedTables } from "../components/broadcast/SavedTables";

describe("Olympic rings logo", () => {
  it("draws five rings in the official colours, interlaced", () => {
    const { container } = render(<OlympicRings />);
    const strokes = [...container.querySelectorAll("circle")].map((c) => c.getAttribute("stroke"));
    expect(strokes).toEqual(["#0081C8", "currentColor", "#EE334E", "#FCB131", "#00A651"]);
    expect(container.querySelectorAll("path").length).toBe(4);           // one over-crossing per overlapping pair
    expect(screen.getByRole("img", { name: "Olympic rings" })).toBeTruthy();
  });
});

describe("Olympedia-style navigation", () => {
  it("breadcrumbs link every level except the current page", () => {
    render(<MemoryRouter><Crumbs items={[{ label: "Olympic Games", to: "/olympics" }, { label: "Tokyo 2020", to: "/games/2020_summer" }, { label: "Match #1" }]} /></MemoryRouter>);
    expect(screen.getByText("Tokyo 2020").closest("a")?.getAttribute("href")).toBe("/games/2020_summer");
    expect(screen.getByText("Match #1").closest("a")).toBeNull();
  });
  it("a Match # cell with a route becomes an in-app link; a cell without one stays text", () => {
    const t = { index: 4, section: "Round-Robin", headers: ["Match", "Team"], rows: [["Match #1", "Latvia"], ["Match #9", "Poland"]],
      links: [[[{ results: "18000011", text: "Match #1", route: "/games/2020_summer/events/18000000/matches/18000011" }], []], [[{ results: "1", text: "Match #9" }], []]] };
    render(<MemoryRouter><SavedTables tables={[t]} /></MemoryRouter>);
    expect(screen.getByText("Match #1").closest("a")?.getAttribute("href")).toBe("/games/2020_summer/events/18000000/matches/18000011");
    expect(screen.getByText("Match #9").closest("a")).toBeNull();      // never a dead link
  });
});

import { BroadcastBoutBoard, BroadcastHeatTable, MarkerBadges, tableKind } from "../components/tables/OlympediaTables";
import * as Named from "../components/tables/broadcast";

describe("broadcast boards and tables", () => {
  it("exports the full named table set", () => {
    for (const n of ["BroadcastResultsTable", "BroadcastMedalTable", "BroadcastMatchTable", "BroadcastBoutTable", "BroadcastHeatTable", "BroadcastCountryTable", "BroadcastAthleteTable", "BroadcastRankingTable", "BroadcastBoutBoard"])
      expect(typeof (Named as any)[n]).toBe("function");
  });
  it("turns trailing markers into qualification, record, medal and status badges; unknown text stays text", () => {
    const { container, rerender } = render(<MarkerBadges v="Q OR" />);
    expect(container.querySelector("[data-testid=qual-badge]")?.textContent).toBe("Q");
    expect(container.querySelector("[data-testid=record-badge]")?.getAttribute("title")).toBe("Olympic record");
    rerender(<MarkerBadges v="non-scoring" />);
    expect(container.textContent).toBe("non-scoring");
    rerender(<MarkerBadges v="3:45 tie" />);
    expect(container.querySelector("[data-testid=qual-badge]")).toBeNull();
  });
  it("classifies saved tables", () => {
    const t = (section: string, headers: string[] | null, rows: string[][] = [["1"]]) => ({ index: 1, section, headers, rows, links: [] });
    expect(tableKind(t("Heat #1", ["Pos", "Lane", "Competitor", "NOC", "Time", ""]))).toBe("heat");
    expect(tableKind(t("", ["Pos", "Competitor", "NOC", "Time"]))).toBe("results");
    expect(tableKind(t("Round One", ["Match", "Date/Time", "Competitor", "NOC", "Result", "Competitor", "NOC", ""]))).toBe("matches");
    expect(tableKind(t("", ["Color", "Competitor", "NOC", "Judges Favoring"], [["Red", "A", "GHA", "5"], ["Blue", "B", "ECU", "0"]]))).toBe("bout");
    expect(tableKind(t("", null, [["Match Result", "Decision"]]))).toBe("kv");
  });
  it("heat table: lane chips, Q badge and a qualified-row marker; every saved column kept", () => {
    const t = { index: 2, section: "Heat #1", headers: ["Pos", "Lane", "Competitor", "NOC", "Time", ""], rows: [["1", "4", "Ato Boldon", "TTO", "10.04", "Q"], ["5", "2", "X Y", "CAN", "10.50", ""]], links: [] };
    const { container } = render(<MemoryRouter><BroadcastHeatTable t={t} /></MemoryRouter>);
    expect(container.querySelectorAll("[data-testid=lane-chip]").length).toBe(2);
    expect(container.querySelectorAll("[data-testid=qual-badge]").length).toBe(1);
    expect(container.querySelectorAll("tr[data-qualified]").length).toBe(1);
    expect(container.querySelectorAll("thead th").length).toBe(6);
  });
  it("bout board: main score, winner only when scores differ, judges as periods, result line", () => {
    const tables = [
      { index: 1, section: "", headers: ["Color", "Competitor", "NOC", "Judges Favoring", "Judge #1 Score", "Judge #2 Score", ""], rows: [["Red", "Samuel Takyi", "GHA", "5", "29", "30", ""], ["Blue", "Jean Carlos Caicedo", "ECU", "0", "28", "27", ""]], links: [] },
      { index: 2, section: "", headers: null, rows: [["Match Result", "Decision"]], links: [] },
    ];
    const { container } = render(<MemoryRouter><BroadcastBoutBoard tables={tables} sport="Boxing" label="Match #3" /></MemoryRouter>);
    expect(container.querySelector("[data-testid=bout-score]")?.textContent).toBe("5:0");
    expect(container.querySelector("[data-testid=bout-result]")?.textContent).toBe("Decision");
    expect(container.querySelectorAll("[data-testid=bout-periods] thead th").length).toBe(3);   // blank + 2 judges
    expect(screen.getAllByText("Winner").length).toBe(1);
  });
  it("bout board for a bye shows one competitor and no invented score", () => {
    const tables = [{ index: 1, section: "", headers: ["Competitor", "NOC", ""], rows: [["Yang Yung-Wei", "TPE", "bye"]], links: [] }];
    const { container } = render(<MemoryRouter><BroadcastBoutBoard tables={tables} /></MemoryRouter>);
    expect(container.textContent).toContain("Bye");
    expect(container.querySelector("[data-testid=bout-score]")).toBeNull();
  });
});
