import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { BoutScoreboard, TeamScoreboard } from "../components/broadcast/Scoreboards";
import { SavedTables } from "../components/broadcast/SavedTables";
import { flagUrl } from "../lib/fmt";

const wrap = (ui: any) => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);

describe("team scoreboard", () => {
  const m = { stage: "Final", match_date: "9 August 2024", location: "Parc des Princes, Paris", home_team: "Spain", home_noc: "ESP", home_score: 5, away_team: "France", away_noc: "FRA", away_score: 3, period_scores: "2-1; 3-2", result_id: "1" };
  it("shows both teams, the score, the winner, the venue and period scores", () => {
    wrap(<TeamScoreboard m={m} />);
    const card = screen.getByTestId("scorecard");
    expect(within(card).getByText("Spain")).toBeTruthy();
    expect(within(card).getByLabelText("5 to 3")).toBeTruthy();
    expect(within(card).getAllByText("Winner")).toHaveLength(1);
    expect(within(card).getByText("Parc des Princes, Paris")).toBeTruthy();
    expect(within(card).getByText("2-1")).toBeTruthy();
  });
  it("never invents a score: no score recorded shows dashes and no winner", () => {
    wrap(<TeamScoreboard m={{ ...m, home_score: null, away_score: null }} />);
    expect(screen.getByLabelText("no score recorded")).toBeTruthy();
    expect(screen.queryByText("Winner")).toBeNull();
  });
});

describe("bout scoreboard", () => {
  const two = (a: string, b: string, key = "touches delivered") => ({ stage: "Bout #1", match_date: "1 August 1984", location: "Long Beach", result_id: "9", participants: [{ competitor: "A. Fencer", noc: "FRA", extra: { athlete_id: "1", bib: "66", [key]: a } }, { competitor: "B. Fencer", noc: "ITA", extra: { athlete_id: "2", bib: "115", [key]: b } }] });
  it("shows the sport's own statistic and highlights the higher touches as the winner", () => {
    wrap(<BoutScoreboard b={two("5", "4")} />);
    expect(screen.getAllByText("touches delivered")).toHaveLength(2);
    expect(screen.getByText("A. Fencer").className).toMatch(/font-bold/);
    expect(screen.getByText("B. Fencer").className).not.toMatch(/font-bold/);
  });
  it("does not infer a winner from bad points (wrestling): lower is not 'more'", () => {
    wrap(<BoutScoreboard b={two("0", "4", "bad points")} />);
    expect(screen.getByText("A. Fencer").className).not.toMatch(/font-bold/);
    expect(screen.getByText("B. Fencer").className).not.toMatch(/font-bold/);
  });
});

describe("saved tables render a page as it appears", () => {
  it("renders a key/value strip for 'Match Result | Ippon' and a normal table with flags and medals", () => {
    wrap(<SavedTables tables={[
      { index: 0, section: "", headers: ["Competitor", "NOC", ""], rows: [["Peter Jupke", "FRG", ""], ["Djibril Sall", "SEN", ""]], links: [] },
      { index: 1, section: "", headers: null, rows: [["Match Result", "Ippon"]], links: [] },
      { index: 2, section: "Winning Techniques", headers: ["Time", "Athlete(s)", "Result"], rows: [["4:14", "Peter Jupke", "Kansetsu-juji-gatame"]], links: [] },
      { index: 3, section: "Final", headers: ["Pos", "Competitor", "NOC", "Medal"], rows: [["1", "Maurice Greene", "USA", "Gold"]], links: [] },
    ]} />);
    expect(screen.getByText("Match Result")).toBeTruthy();
    expect(screen.getByText("Ippon")).toBeTruthy();
    expect(screen.getByText("Winning Techniques")).toBeTruthy();
    expect(screen.getByText("Kansetsu-juji-gatame")).toBeTruthy();
    expect(screen.getByText("Gold")).toBeTruthy();
    expect(screen.getAllByAltText("FRG flag").length).toBe(1);
  });
});

describe("local flag collection", () => {
  const PUBLIC = join(__dirname, "../../public/assets/flags");
  const flags = JSON.parse(readFileSync(join(PUBLIC, "flags.json"), "utf-8"));
  it("serves flags from the app itself, not an external CDN", () => {
    expect(flagUrl("GER")).toBe("/assets/flags/GER.svg");
  });
  it("has a flag file for (almost) every NOC code of the data, each a real SVG", () => {
    expect(Object.keys(flags).length).toBeGreaterThanOrEqual(231);
    for (const [noc, v] of Object.entries<any>(flags)) {
      const f = join(PUBLIC, `${noc}.svg`);
      expect(existsSync(f)).toBe(true);
      expect(readFileSync(f, "utf-8").slice(0, 600)).toContain("<svg");
      expect(v.license.length).toBeGreaterThan(3);
    }
  });
  it("labels historical and neutral teams honestly", () => {
    expect(flags.URS.kind).toBe("historical flag");
    expect(flags.EUN.kind).toMatch(/olympic flag/);
    expect(flags.GER.kind).toBe("national flag");
  });
});
