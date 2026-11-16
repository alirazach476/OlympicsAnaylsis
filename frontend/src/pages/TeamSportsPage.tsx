import { useMemo, useState } from "react";
import { useApi, csvUrl } from "../lib/api";
import { Async, ChartCard, Flag, Note, PageHeader, Select, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries } from "../charts/charts";
import { fmtNum } from "../lib/fmt";
import { BoutScoreboard } from "../components/broadcast/Scoreboards";
import { BroadcastScoreboard } from "../components/broadcast/MatchBoards";
import { MatchDrawer } from "../components/broadcast/MatchDrawer";
import { EditionBranding, SportPictogram } from "../components/broadcast/design";
import { MatchResultsTable } from "../components/tables/BroadcastTables";
import { useEditionBrand } from "../themes/editionBrand";
import { PageDrawer } from "../components/broadcast/SavedTables";

import { VizSection } from "../viz/VizGallery";
const SPORTS = ["Football", "Basketball", "Ice Hockey", "Handball", "Volleyball", "Water Polo", "Hockey", "Beach Volleyball", "Baseball", "Softball", "Rugby Sevens", "Curling"];
const INDIVIDUAL = ["Fencing", "Judo", "Wrestling", "Boxing", "Taekwondo", "Table Tennis", "Badminton", "Tennis", "Modern Pentathlon"];
const STAGE_ORDER = ["Final", "Bronze", "Semi", "Quarter", "Group", "Round", "Pool", "Match"];

export default function TeamSportsPage() {
  const [sportChoice, setSport] = useState("Football");
  const brand = useEditionBrand();
  const gid = brand.gamesId;   // the selected edition of the whole app (sidebar switcher)
  const [view, setView] = useState("scoreboards");
  const [tab, setTab] = useState("matches");
  const [open, setOpen] = useState<string | null>(null);
  const [event, setEvent] = useState("");
  const [pg, setPg] = useState(1);
  const editionSports = useApi<any>(`/games/${gid}`);
  // only sports that exist at the selected edition (a winter edition offers Ice Hockey and Curling, not Football)
  const offered = [...SPORTS, ...INDIVIDUAL].filter((x) => !editionSports.data || editionSports.data.sports?.some((e: any) => e.sport_name === x));
  const sport = offered.includes(sportChoice) || !offered.length ? sportChoice : offered[0];
  const isBout = INDIVIDUAL.includes(sport);
  const bouts = useApi<any>(isBout ? "/bouts" : null, { games_id: gid, sport, event: event || undefined, page: pg, page_size: 60 });
  const games = useApi<any[]>("/games");
  const standings = useApi<any[]>(INDIVIDUAL.includes(sport) ? null : "/team-sports", { sport, games_id: gid });
  const matches = useApi<any>(INDIVIDUAL.includes(sport) ? null : "/match-board", { sport, games_id: gid, page_size: 300 });
  const an = useApi<any>(INDIVIDUAL.includes(sport) ? null : `/sports-analytics/team_${sport.toLowerCase().replace(/ /g, "_")}`);
  const stats = useApi<any>(INDIVIDUAL.includes(sport) ? null : "/matches", { sport, games_id: gid, page_size: 1 });
  const bracket = useMemo(() => {
    const rows: any[] = matches.data?.rows ?? [];
    const ko = rows.filter((m) => /final|semi|quarter|bronze/i.test(m.stage || ""));
    const order = (s: string) => STAGE_ORDER.findIndex((k) => new RegExp(k, "i").test(s));
    return ko.sort((a, b) => order(a.stage) - order(b.stage));
  }, [matches.data]);
  const gameOpts = (games.data ?? []).map((g: any) => ({ value: g.games_id, label: `${g.year} ${g.season}` }));
  return (
    <div>
      <PageHeader title="Team sports & matches" subtitle="Real fixtures and scores from Olympedia. Lineups, period scores and player statistics are shown only where the source has them - nothing is filled in." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Sport" data-testid="sport-pills">{offered.map((x) => <button key={x} role="tab" aria-label={x} aria-selected={sport === x} onClick={() => { setSport(x); setEvent(""); setPg(1); }} className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs transition ${sport === x ? "border-[var(--ed-accent)] bg-[var(--ed-tint)] font-semibold" : "border-line text-muted hover:text-ink"}`}><SportPictogram sport={x} size={20} />{x}</button>)}</div>
      </div>
      {isBout ? (
        <div data-testid="bouts-view">
          <div className="mb-3 flex flex-wrap items-center gap-3"><Select label="Event" value={event} onChange={(v) => { setEvent(v); setPg(1); }} options={(bouts.data?.events ?? []).map((e: string) => ({ value: e, label: e }))} />
            <span className="text-xs text-muted">{bouts.data?.total ?? 0} bouts · {sport} · {gid} - open a bout for every table of its page (touches, bad points, match result, winning techniques ...)</span></div>
          <Async q={bouts} isEmpty={(d) => !d.rows.length}>{(d) => (<>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{d.rows.map((b: any) => <BoutScoreboard key={b.result_id} b={b} onOpen={setOpen} />)}</div>
            <div className="mt-4 flex items-center justify-center gap-3 text-sm"><button className="btn" disabled={pg <= 1} onClick={() => setPg(pg - 1)}>Previous</button><span className="tabnum text-muted">page {pg} of {Math.max(1, Math.ceil(d.total / 60))}</span><button className="btn" disabled={pg * 60 >= d.total} onClick={() => setPg(pg + 1)}>Next</button></div></>)}</Async>
        </div>
      ) : (<>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "matches", label: "Match results" }, { id: "standings", label: "Standings" }, { id: "bracket", label: "Knockout bracket" }, { id: "history", label: "Historical performance" }]} />
      {tab === "matches" && (
        <Async q={matches} isEmpty={(d) => !d.rows.length}>{(d) => (
          <div>
            <div className="mb-3 flex items-center justify-between text-xs text-muted"><span className="flex items-center gap-3"><span>{d.total} matches · {sport} · {gid}</span><span className="inline-flex overflow-hidden rounded-lg border border-line" role="group" aria-label="View"><button className={`px-3 py-1 ${view === "scoreboards" ? "bg-[var(--ed-tint)] font-semibold text-ink" : ""}`} onClick={() => setView("scoreboards")} aria-pressed={view === "scoreboards"}>Scoreboards</button><button className={`px-3 py-1 ${view === "table" ? "bg-[var(--ed-tint)] font-semibold text-ink" : ""}`} onClick={() => setView("table")} aria-pressed={view === "table"}>Table</button></span></span><a className="btn" href={csvUrl("/matches", { sport, games_id: gid })} download>CSV</a></div>
            {view === "table" ? <MatchResultsTable rows={d.rows} title={`${sport} results`} subtitle={`${d.total} matches`} exportName={`${sport}_${gid}_results`} onRowClick={(r) => setOpen(String(r.result_id))} height={560} /> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="scoreboard-grid">{d.rows.slice(0, 120).map((m: any, i: number) => <BroadcastScoreboard key={m.result_id ?? i} m={m} onOpen={setOpen} />)}</div>}
          </div>)}</Async>)}
      {tab === "standings" && (
        <ChartCard title="Team records at this edition" subtitle="Computed from match scores: W/D/L, goals for/against, goal difference, points per game (3-1-0 convention shown for comparison only)" height={420}>
          <Async q={standings} isEmpty={(d) => !d.length}>{(rows) => <DataTable rows={rows} height={420} exportName={`${sport}_${gid}`} columns={[{ key: "team", width: 190, render: (r) => <span className="inline-flex items-center gap-2"><Flag noc={r.noc} size={13} />{r.team}</span> }, { key: "played", header: "P", align: "right", width: 52 }, { key: "won", header: "W", align: "right", width: 52 }, { key: "drawn", header: "D", align: "right", width: 52 }, { key: "lost", header: "L", align: "right", width: 52 }, { key: "goals_for", header: "GF", align: "right", width: 56 }, { key: "goals_against", header: "GA", align: "right", width: 56 }, { key: "goal_diff", header: "GD", align: "right", width: 56 }, { key: "points_per_game", header: "Pts/G", align: "right", width: 72 }]} />}</Async>
        </ChartCard>)}
      {tab === "bracket" && (
        <ChartCard title="Knockout rounds" subtitle="Quarter-finals → semi-finals → bronze/final as labelled in the source" height={300}>
          {bracket.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{bracket.map((m, i) => <BroadcastScoreboard key={m.result_id ?? i} m={m} onOpen={setOpen} />)}</div> : <Note>No knockout-stage matches are labelled for this sport/edition (round-robin, or stages not recorded).</Note>}
        </ChartCard>)}
      {tab === "history" && (
        <Async q={an}>{({ data }) => data.status ? <Note>{data.status}</Note> : (
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Scoring trend by edition" subtitle={data.scoring_trend_slope_per_year ? `Goals/points per match: slope ${fmtNum(data.scoring_trend_slope_per_year.slope, 4)} per year (R² ${fmtNum(data.scoring_trend_slope_per_year.r2, 2)}, p ${fmtNum(data.scoring_trend_slope_per_year.p, 4)})` : ""}>
              <LineSeries data={data.scoring_trend_by_edition} x="year" series={[{ key: "goals_per_match", name: "per match (both teams)", color: "#F4C300", dot: true }, { key: "mean_margin", name: "mean margin", color: "#0085C7", dot: true }]} />
            </ChartCard>
            <ChartCard title="All-time team records" subtitle="Minimum 10 matches"><DataTable height={320} rows={data.team_records} columns={[{ key: "team", width: 170 }, { key: "played", header: "P", align: "right", width: 50 }, { key: "win_pct", header: "Win %", align: "right", width: 70, render: (r) => `${fmtNum(100 * r.win_pct, 0)}%` }, { key: "gd", header: "GD", align: "right", width: 60 }, { key: "editions", align: "right", width: 70 }]} /></ChartCard>
            <ChartCard title="Knockout wins" height={280}><Bars horizontal data={data.knockout_performance.map((k: any) => ({ name: k.noc ?? k.team, wins: k.knockout_wins, matches: k.knockout_matches }))} x="name" series={[{ key: "wins", color: "#009F3D" }, { key: "matches", color: "#B0B7C3" }]} /></ChartCard>
            {data.period_scoring && <ChartCard title="Scoring by period" subtitle="Mean combined points per period, by edition"><LineSeries data={Object.values(data.period_scoring.reduce((a: any, r: any) => { a[r.year] = { ...(a[r.year] || { year: r.year }), [`P${r.period}`]: r.total_points }; return a; }, {}))} x="year" series={["P1", "P2", "P3", "P4"].map((k, i) => ({ key: k }))} /></ChartCard>}
            <div className="xl:col-span-2"><Note>{data.note}</Note></div>
          </div>)}</Async>)}
      </>)}
      {isBout ? <PageDrawer resultId={open} onClose={() => setOpen(null)} /> : <MatchDrawer resultId={open} onClose={() => setOpen(null)} />}
      <VizSection page="team-sports" />
    </div>
  );
}
