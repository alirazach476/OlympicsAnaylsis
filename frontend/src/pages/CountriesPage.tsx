import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useApi, csvUrl } from "../lib/api";
import { Async, ChartCard, Flag, Kpi, Note, PageHeader, SeasonToggle, Select, Tabs } from "../components/ui";
import { useParamState } from "../components/navigation/Crumbs";
import { MedalChip, SportPictogram } from "../components/broadcast/design";
import { useEditionList } from "../components/editions/EditionGallery";
import { OlympicRings } from "../components/OlympicRings";
import { TableFrame } from "../components/tables/TableFrame";
import { useTheme } from "../lib/theme";
import { useEditionTheme } from "../themes/olympicThemeEngine";
import { CsvButton } from "../components/CsvButton";
import { Cell, MEDAL_HEX } from "../components/tables/OlympediaTables";
import { CountryRankingTable } from "../components/tables/BroadcastTables";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries, RadarCompare, StackedArea, TreemapChart } from "../charts/charts";
import WorldMap from "../charts/WorldMap";
import { fmtInt, fmtPct, gamesLabel, MEDAL_COLORS, PALETTE } from "../lib/fmt";

import { EditionStrip, ProfileHero } from "../components/profile/ProfileHero";
import { SavedTables } from "../components/broadcast/SavedTables";
import { VizSection } from "../viz/VizGallery";
export function CountriesPage() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [continent, setContinent] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const list = useApi<any>("/countries", { q, continent, page_size: 300, sort: "total_medals" });
  const all = useApi<any>("/countries", { page_size: 300 });
  const compare = useApi<any>("/countries/compare", { nocs: picked.join(",") }, picked.length >= 2);
  const toggle = (n: string) => setPicked((p) => (p.includes(n) ? p.filter((x) => x !== n) : p.length < 4 ? [...p, n] : p));
  return (
    <div>
      <PageHeader title="Country analytics" subtitle="Every historical NOC. USSR, East/West Germany, Czechoslovakia, Yugoslavia, Unified Team and ROC stay separate from their successors." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input className="input w-64" placeholder="Search country or NOC…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search countries" />
        <Select label="Continent" value={continent} onChange={setContinent} options={["Africa", "Americas", "Asia", "Europe", "Oceania"].map((c) => ({ value: c, label: c }))} />
        <a className="btn" href={csvUrl("/countries", { q, continent })} download>Export CSV</a>
        <span className="text-xs text-muted">Tick up to 4 countries to compare →</span>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <ChartCard title="Countries" height={520}>
          <Async q={list} isEmpty={(d) => !d.rows.length}>{(d) => (
            <CountryRankingTable rows={d.rows} height={520} title="Countries" subtitle="all-time medals from the official tables" exportName="countries" onRowClick={(r) => nav(`/countries/${r.noc_code}`)} />)}</Async>
        </ChartCard>
        <ChartCard title="Total medals, world map" subtitle="Official medal tables, 35 Games (click a country)" height={380}>
          <Async q={all}>{(d) => <WorldMap rows={d.rows} valueKey="total_medals" label="medals" onPick={(r) => nav(`/countries/${r.noc_code}`)} />}</Async>
        </ChartCard>
      </div>
      {picked.length >= 2 && <div className="mt-4"><Link className="btn btn-accent" to={`/compare/countries?nocs=${picked.slice(0, 4).join(",")}`}>Open the full country comparison</Link></div>}
      {picked.length >= 2 && (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <ChartCard title="Medal totals by edition" subtitle={picked.join(" vs ")}>
            <Async q={compare}>{(d) => {
              const years: Record<string, any> = {};
              Object.entries(d).forEach(([noc, rows]: any) => rows.forEach((r: any) => { const k = r.games_id; years[k] = { ...(years[k] || { games_id: k, label: gamesLabel(k), year: r.year + (r.season === "winter" ? 0.5 : 0) }), [noc]: r.total }; }));
              const data = Object.values(years).sort((a: any, b: any) => a.year - b.year);
              return <LineSeries data={data as any[]} x="label" series={picked.map((n, i) => ({ key: n, color: PALETTE[i], dot: true }))} yLabel="Total medals" />;
            }}</Async>
          </ChartCard>
          <ChartCard title="Profile radar" subtitle="Each axis scaled 0–100 to the maximum among the selected countries">
            <Async q={compare}>{(d) => {
              const agg = Object.entries(d).map(([noc, rows]: any) => ({ noc, gold: rows.reduce((a: number, r: any) => a + r.gold, 0), total: rows.reduce((a: number, r: any) => a + r.total, 0), athletes: Math.max(...rows.map((r: any) => r.athletes)), sports: Math.max(...rows.map((r: any) => r.sports)), editions: rows.length, goldRatio: rows.reduce((a: number, r: any) => a + r.gold, 0) / Math.max(1, rows.reduce((a: number, r: any) => a + r.total, 0)) }));
              const mx = (k: string) => Math.max(...agg.map((a: any) => a[k]), 1e-9);
              const axes = [["Total medals", "total"], ["Gold medals", "gold"], ["Peak delegation", "athletes"], ["Peak sports", "sports"], ["Editions", "editions"], ["Gold ratio", "goldRatio"]];
              return <RadarCompare data={axes.map(([label, k]) => ({ axis: label, ...Object.fromEntries(agg.map((a: any) => [a.noc, (100 * a[k]) / mx(k)])) }))} series={picked.map((n, i) => ({ key: n, color: PALETTE[i] }))} />;
            }}</Async>
          </ChartCard>
        </div>)}
      <VizSection page="countries" />
    </div>
  );
}

function GamesResults({ noc, editions }: { noc: string; editions: any[] }) {
  const [gid, setGid] = useState("");
  const q = useApi<any>(gid ? `/countries/${noc}/at/${gid}` : null);
  return (
    <div className="card mb-5 p-4" data-testid="country-at-games">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><h2 className="h-display text-2xl">Results at a Games</h2><p className="text-xs text-muted">This country's own results page for one Games, as it appears on Olympedia: every sport, event, athlete, place and medal.</p></div>
        <select className="input" value={gid} onChange={(e) => setGid(e.target.value)} aria-label="Choose a Games"><option value="">Choose a Games…</option>{[...editions].sort((a, b) => b.year - a.year).map((e) => <option key={e.games_id} value={e.games_id}>{gamesLabel(e.games_id)}</option>)}</select></div>
      {gid && <Link className="btn mb-3" to={`/countries/${noc}/editions/${gid}`} data-testid="country-edition-link">Open the full {gamesLabel(gid)} page (filters, every result) →</Link>}
      {gid && <Async q={q}>{(d) => <div className="max-h-[560px] overflow-y-auto"><div className="mb-2 text-sm font-semibold">{d.title}</div><SavedTables tables={d.tables.map((t: any) => ({ ...t, rows: t.rows.map((r: string[]) => (r.length === 1 && r[0].startsWith("#") ? [r[0].slice(1)] : r)) }))} /></div>}</Async>}
    </div>
  );
}

const lab = (m: any) => `${m.year}${m.season === "winter" ? "W" : "S"}`;
const STATUS_TONE: Record<string, string> = { DNF: "text-amber-500", DNS: "text-muted", DQ: "text-red-500", DSQ: "text-red-500", AC: "text-amber-500" };

/** Country profile: header (flag, NOC, key numbers), then exactly two sections in ?tab=: Visuals (charts only) and Results (the complete results table only). */
export function CountryPage() {
  const { noc = "" } = useParams();
  const q = useApi<any>(`/countries/${noc}`);
  const [tab, setTab] = useParamState("tab", "visuals");
  return (
    <Async q={q}>
      {(d) => {
        const p = d.profile;
        return (
          <div data-testid="country-profile">
            <ProfileHero back={{ to: "/countries", label: "Countries & Medal Statistics" }} kicker={`${p.noc_code}${p.continent ? " · " + p.continent : ""}`} title={p.historical_name} flagNoc={noc} medals={{ gold: p.gold, silver: p.silver, bronze: p.bronze }}
              facts={<><span className="inline-flex items-center gap-2"><Flag noc={noc} size={18} /> {p.noc_code}</span><span>{p.first_year ? `${p.first_year} – ${p.last_year ?? ""}` : ""}</span><span>{p.summer_appearances} Summer · {p.winter_appearances} Winter appearances</span><span>{fmtInt(p.athletes)} athletes</span><span>{fmtInt(p.total_medals)} medals</span>{d.noc_info?.notes && <span className="max-w-md truncate" title={d.noc_info.notes}>{d.noc_info.notes}</span>}</>} />
            <Tabs value={tab} onChange={(t) => setTab(t)} tabs={[{ id: "visuals", label: "Visuals" }, { id: "results", label: "Results" }]} />
            {tab === "results" ? <CountryResults noc={noc} /> : <CountryVisuals d={d} noc={noc} />}
          </div>);
      }}
    </Async>
  );
}

function CountryVisuals({ d, noc }: { d: any; noc: string }) {
  const [season, setSeason] = useParamState("season");
  const res = useApi<any>(`/countries/${noc}/results`);
  const keep = (m: any) => !season || m.season === season;
  const med = d.medals_by_edition.filter(keep);
  const part = d.participation_by_edition.filter(keep);
  const tot = med.reduce((a: any, m: any) => ({ gold: a.gold + m.gold, silver: a.silver + m.silver, bronze: a.bronze + m.bronze }), { gold: 0, silver: 0, bronze: 0 });
  const best = [...med].sort((a: any, b: any) => b.gold - a.gold || b.total - a.total).slice(0, 8);
  const gender = useMemo(() => {
    const by: Record<string, any> = {};
    (res.data?.rows ?? []).filter((r: any) => !season || r.season === season).forEach((r: any) => {
      const e = (by[r.games_id] ??= { label: lab(r), year: r.year, season: r.season, Men: 0, Women: 0, Mixed: 0, Open: 0 });
      e[r.gender] = (e[r.gender] ?? 0) + 1;
    });
    return Object.values(by).sort((a: any, b: any) => a.year - b.year || (a.season > b.season ? 1 : -1));
  }, [res.data, season]);
  const M = [{ key: "Gold", color: MEDAL_COLORS.gold }, { key: "Silver", color: MEDAL_COLORS.silver }, { key: "Bronze", color: MEDAL_COLORS.bronze }];
  return (
    <div data-testid="country-visuals">
      <div className="card mb-4 flex flex-wrap items-center gap-3 p-3">
        <SeasonToggle value={season} onChange={(v) => setSeason(v)} />
        <span className="text-xs text-muted">{med.length} medal-winning editions · {part.length} editions entered</span>
      </div>
      {!d.medals_by_edition.length && <Note>This NOC has appeared at the Games but is absent from every official medal table.</Note>}
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Medal distribution"><Bars data={[{ name: "Gold", v: tot.gold }, { name: "Silver", v: tot.silver }, { name: "Bronze", v: tot.bronze }]} x="name" colorByIndex series={[{ key: "v", name: "Medals", color: MEDAL_COLORS.gold }]} /></ChartCard>
        <ChartCard title="Medal progression"><StackedArea data={med.map((m: any) => ({ label: lab(m), Gold: m.gold, Silver: m.silver, Bronze: m.bronze }))} x="label" series={M} /></ChartCard>
        <ChartCard title="Summer vs Winter"><Bars data={d.summer_vs_winter.map((s: any) => ({ season: s.season, Gold: s.gold, Silver: s.silver, Bronze: s.bronze }))} x="season" stacked series={M} /></ChartCard>
        <ChartCard title="Medals by sport · all editions" height={360}><Bars horizontal stacked data={d.medals_by_sport.slice(0, 15).map((s: any) => ({ name: s.sport_name, Gold: s.gold, Silver: s.silver, Bronze: s.bronze }))} x="name" series={M} /></ChartCard>
        <ChartCard title="Top sports · all editions" height={320}><TreemapChart data={d.medals_by_sport.map((s: any) => ({ name: s.sport_name, size: s.total }))} /></ChartCard>
        <ChartCard title="Best Games (gold, then total)" height={320}><Bars horizontal stacked data={best.map((m: any) => ({ name: gamesLabel(m.games_id), Gold: m.gold, Silver: m.silver, Bronze: m.bronze }))} x="name" series={M} /></ChartCard>
        <ChartCard title="Athlete participation"><LineSeries data={part.map((m: any) => ({ label: lab(m), athletes: m.athletes, sports: m.sports }))} x="label" series={[{ key: "athletes", name: "Athletes", color: "#0085C7", dot: true }, { key: "sports", name: "Sports", color: "#F4C300", dot: true }]} /></ChartCard>
        <ChartCard title="Medal-table rank by edition (lower is better)"><LineSeries data={med.map((m: any) => ({ label: lab(m), rank: m.official_rank }))} x="label" series={[{ key: "rank", name: "Rank", color: "#DF0024", dot: true }]} /></ChartCard>
        <ChartCard title="Entries by gender category"><Async q={res}>{() => <Bars stacked data={gender as any[]} x="label" series={[{ key: "Men", color: "#0085C7" }, { key: "Women", color: "#E86AA6" }, { key: "Mixed", color: "#8E6BBF" }, { key: "Open", color: "#64748b" }]} />}</Async></ChartCard>
        <ChartCard title="Medal composition by edition (share)"><StackedArea percent data={med.map((m: any) => ({ label: lab(m), Gold: m.gold, Silver: m.silver, Bronze: m.bronze }))} x="label" series={M} /></ChartCard>
      </div>
    </div>
  );
}

/** Results: a sidebar of EVERY Olympic Games (Summer and Winter, with their emblems) - the ones this NOC entered open its full Olympedia table for that edition,
 *  the others are shown greyed ("did not take part"). "All editions" lists every entry of every Games. Only tables here - no charts or statistic cards. */
function CountryResults({ noc }: { noc: string }) {
  const eds = useApi<any[]>(`/countries/${noc}/olympedia-editions`);
  const { items } = useEditionList();
  const [ed] = useParamState("r_edition");
  const loc = useLocation();
  const href = (id: string) => { const n = new URLSearchParams(loc.search); n.set("tab", "results"); if (id) n.set("r_edition", id); else n.delete("r_edition"); return `?${n.toString()}`; };
  const entered = new Set((eds.data ?? []).map((e) => e.games_id));
  const held = items.filter((i) => !i.upcoming).sort((a, b) => b.year - a.year);
  const cur = held.find((i) => i.id === ed);
  const row = (i: (typeof held)[number]) => {
    const on = ed === i.id, can = entered.has(i.id);
    const body = (<>
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-white p-1 shadow">{i.logo ? <img src={i.logo} alt={`${i.name} emblem`} loading="lazy" className={`max-h-full max-w-full object-contain ${can ? "" : "grayscale"}`} /> : null}</span>
      <span className="min-w-0 flex-1 leading-tight"><span className="block truncate text-sm font-semibold">{i.city}</span><span className="text-[11px] text-muted">{i.year}</span>{!can && <span className="mt-0.5 block w-fit rounded-full border border-amber-500/50 px-1.5 text-[9px] font-bold uppercase tracking-wider text-amber-400" data-testid="not-entered">did not take part</span>}</span>
      {on && <span className="h-6 w-1 rounded-full" style={{ background: "var(--ed-accent)" }} />}
    </>);
    return can
      ? <Link key={i.id} to={href(i.id)} aria-current={on ? "true" : undefined} data-testid="side-edition" data-edition={i.id}
          className={`flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition ${on ? "bg-[var(--ed-tint)] ring-1 ring-[var(--ed-accent)]" : "hover:bg-surface2"}`} style={{ borderLeft: `3px solid ${i.primary ?? "#888"}` }}>{body}</Link>
      : <div key={i.id} data-testid="side-edition" data-edition={i.id} data-disabled="true" aria-disabled="true" title={`${noc} did not take part in ${i.name}`} className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-2 py-1.5 opacity-75" style={{ borderLeft: "3px solid transparent" }}>{body}</div>;
  };
  return (
    <div data-testid="country-results" className="grid items-start gap-4 lg:grid-cols-[270px_minmax(0,1fr)]">
      <aside className="card overflow-hidden lg:sticky lg:top-16" data-testid="edition-sidebar" aria-label="Olympic editions">
        <div className="relative px-3 py-2.5" style={{ background: "linear-gradient(90deg, color-mix(in srgb, var(--ed-deep, var(--ed-primary)) 70%, #070a12), color-mix(in srgb, var(--ed-deep, var(--ed-primary)) 38%, #070a12))" }}>
          <h2 className="h-display text-lg text-white">Olympic editions</h2>
          <div className="text-[11px] text-white/75">{eds.data ? `${entered.size} of ${held.length} Games entered` : ""}</div>
          <div className="ed-stripe absolute inset-x-0 bottom-0 h-0.5" />
        </div>
        <nav className="scroll-thin flex max-h-[40vh] flex-col gap-1 overflow-y-auto p-2 lg:max-h-[calc(100vh-10rem)]">
          <Link to={href("")} aria-current={!ed ? "true" : undefined} data-testid="side-edition" data-edition="all"
            className={`flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition ${!ed ? "bg-[var(--ed-tint)] ring-1 ring-[var(--ed-accent)]" : "hover:bg-surface2"}`}>
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-white p-1 shadow"><OlympicRings size={36} /></span>
            <span className="leading-tight"><span className="block text-sm font-semibold">All editions</span><span className="text-[11px] text-muted">every entry</span></span>
          </Link>
          {(["summer", "winter"] as const).map((sn) => (
            <div key={sn} className="mt-2">
              <div className="mb-1 px-2 text-[10px] font-bold uppercase tracking-[0.2em] text-muted">{sn} Olympics</div>
              <div className="flex flex-col gap-1">{held.filter((i) => i.season === sn).map(row)}</div>
            </div>))}
        </nav>
      </aside>
      <div className="min-w-0">
        {ed && cur && <div className="mb-3 flex justify-end"><Link className="btn" to={`/countries/${noc}/editions/${ed}`}>{cur.name} by sport →</Link></div>}
        {ed ? <OlympediaCountryEdition noc={noc} gamesId={ed} /> : <AllCountryResults noc={noc} />}
      </div>
    </div>
  );
}

function AllCountryResults({ noc }: { noc: string }) {
  const q = useApi<any>(`/countries/${noc}/results`);
  const [season, setSeason] = useParamState("r_season");
  const [year, setYear] = useParamState("r_year");
  const [sport, setSport] = useParamState("r_sport");
  const [event, setEvent] = useParamState("r_event");
  const [athlete, setAthlete] = useParamState("r_athlete");
  const [medal, setMedal] = useParamState("r_medal");
  const [status, setStatus] = useParamState("r_status");
  const nav = useNavigate();
  const loc = useLocation();
  const all: any[] = q.data?.rows ?? [];
  const opts = (f: (r: any) => any, base: any[] = all) => [...new Set(base.map(f).filter(Boolean))].sort() as string[];
  const rows = useMemo(() => {
    const a = athlete.trim().toLowerCase();
    return all.filter((r) => (!season || r.season === season) && (!year || String(r.year) === year) && (!sport || r.sport === sport) && (!event || r.event === event)
      && (!a || String(r.athlete).toLowerCase().includes(a)) && (!medal || (medal === "none" ? !r.medal : r.medal === medal)) && (!status || r.status === status));
  }, [all, season, year, sport, event, athlete, medal, status]);
  const anyFilter = !!(season || year || sport || event || athlete || medal || status);
  const clear = () => { const n = new URLSearchParams(loc.search); [...n.keys()].filter((k) => k.startsWith("r_")).forEach((k) => n.delete(k)); nav({ search: n.toString() }); };
  return (
    <>
      <div className="card mb-3 flex flex-wrap items-center gap-2 p-3" data-testid="results-filters">
        <select className="input" aria-label="Season" value={season} onChange={(e) => setSeason(e.target.value)}><option value="">Summer + Winter</option><option value="summer">Summer</option><option value="winter">Winter</option></select>
        <select className="input" aria-label="Year" value={year} onChange={(e) => setYear(e.target.value)}><option value="">All years</option>{opts((r) => String(r.year)).reverse().map((y) => <option key={y}>{y}</option>)}</select>
        <select className="input" aria-label="Sport" value={sport} onChange={(e) => setSport(e.target.value)}><option value="">All sports</option>{opts((r) => r.sport).map((s) => <option key={s}>{s}</option>)}</select>
        <select className="input max-w-[16rem]" aria-label="Event" value={event} onChange={(e) => setEvent(e.target.value)}><option value="">All events</option>{opts((r) => r.event, sport ? all.filter((r) => r.sport === sport) : all).map((s) => <option key={s}>{s}</option>)}</select>
        <input className="input w-44" placeholder="Athlete / team…" aria-label="Athlete" value={athlete} onChange={(e) => setAthlete(e.target.value, false)} />
        <select className="input" aria-label="Medal" value={medal} onChange={(e) => setMedal(e.target.value)}><option value="">Any result</option><option>Gold</option><option>Silver</option><option>Bronze</option><option value="none">No medal</option></select>
        <select className="input" aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Any status</option>{opts((r) => r.status).map((s) => <option key={s}>{s}</option>)}</select>
        {anyFilter && <button type="button" className="btn" onClick={clear} data-testid="clear-filters">Clear all</button>}
        <span className="ml-auto text-xs text-muted" data-testid="results-count">{q.data ? `${fmtInt(rows.length)} of ${fmtInt(all.length)} entries` : ""}</span>
      </div>
      <Async q={q}>{() => (
        <DataTable variant="results" branding={false} rowMedal={(r) => r.medal} title={`${q.data.country} · Olympic results`} subtitle="every entry, medal or not" rows={rows} height={680} exportName={`${noc}_results`} csvHref={csvUrl(`/countries/${noc}/results`)}
          rowKey={(r, i) => `${r.games_id}-${r.event}-${r.athlete}-${i}`} empty="No entry matches these filters."
          columns={[
            { key: "year", header: "Edition", width: 150, render: (r) => <Link className="hover:text-accent hover:underline" to={`?tab=results&r_edition=${r.games_id}`}>{r.edition}</Link> },
            { key: "sport", header: "Sport", width: 170, render: (r) => <Link className="hover:text-[var(--ed-accent)] hover:underline" to={`/games/${r.games_id}/sports/${encodeURIComponent(r.sport)}`}>{r.sport}</Link> },
            { key: "event", header: "Event", width: 280, render: (r) => (r.event_route ? <Link className="font-semibold hover:text-accent hover:underline" to={r.event_route} data-testid="result-event-link">{r.event}</Link> : r.event) },
            { key: "gender", header: "Category", width: 90 },
            { key: "athlete", header: "Athlete / team", width: 220, render: (r) => (r.athlete_route ? <Link className="hover:text-accent hover:underline" to={r.athlete_route}>{r.athlete}</Link> : r.athlete) },
            { key: "result", header: "Result", width: 150, align: "right", render: (r) => (r.result ? <span className="font-display text-base tabular-nums" title={r.result_type ?? ""}>{r.result}</span> : <span className="text-muted" title="not listed in the saved results table">—</span>) },
            { key: "position", header: "Pos", width: 70, align: "right", render: (r) => <span className="font-display text-base tabular-nums">{r.position ?? "—"}</span> },
            { key: "status", header: "Status", width: 90, render: (r) => <span className={`text-xs ${STATUS_TONE[r.status] ?? ""}`}>{r.status}</span> },
            { key: "medal", header: "Medal", width: 100, render: (r) => (r.medal ? <MedalChip medal={r.medal} /> : null) },
          ]} />)}</Async>
    </>
  );
}

/** The NOC's Olympedia page for one edition (olympedia.org/countries/{NOC}/editions/{id}), the full table as published: sport headings with the edition's pictogram,
 *  event rows (event -> its results page, athlete / team -> profile, place, medal) and team-member rows. Nothing is dropped or re-ordered. */
function OlympediaCountryEdition({ noc, gamesId }: { noc: string; gamesId: string }) {
  const q = useApi<any>(`/countries/${noc}/olympedia/${gamesId}`);
  const { theme: mode } = useTheme();
  const { style } = useEditionTheme(gamesId, mode);   // the table wears the identity of ITS edition (artwork, emblem, colours), not the menu's selection
  return (
    <Async q={q}>{(d) => {
      const t = d.tables[0];
      if (!t) return <Note>Olympedia lists no entries for this edition.</Note>;
      let sport = "";
      const events = t.rows.filter((r: string[]) => r.length >= 3 && r[0]).length;
      const medals = t.rows.filter((r: string[]) => /^(Gold|Silver|Bronze)$/.test(r[3] ?? "")).length;
      return (
        <div style={style} data-edition-table={gamesId}><TableFrame gamesId={gamesId} title={d.title} subtitle={`${events} entries · ${medals} medals`} variant="results"
          actions={<><CsvButton name={`${noc}_${gamesId}_olympedia`} headers={["sport", "event", "athlete / team", "pos", "medal"]} rows={(() => { let sp = ""; return t.rows.flatMap((r: string[]) => { if (r.length === 1 && r[0].startsWith("#")) { sp = r[0].slice(1); return []; } return [[sp, r[0] ?? "", r[1] ?? "", r[2] ?? "", r[3] ?? ""]]; }); })()} />
            <a className="btn !py-1 text-xs" href={d.source_url} target="_blank" rel="noreferrer">Olympedia</a></>}>
          <table className="w-full text-sm" data-testid="olympedia-country-table">
            <thead><tr><th className="th">Event</th><th className="th">Athlete / team</th><th className="th text-right">Pos</th><th className="th">Medal</th></tr></thead>
            <tbody>{t.rows.map((r: string[], i: number) => {
              const links = t.links[i] ?? [];
              if (r.length === 1 && r[0].startsWith("#")) {
                sport = r[0].slice(1);
                return <tr key={i} data-testid="sport-heading"><td colSpan={4} className="border-t-2 border-[var(--ed-accent)] px-3 pb-1.5 pt-3" style={{ background: "var(--ed-tint)" }}><span className="flex items-center gap-2 font-display text-lg font-bold uppercase tracking-wide"><SportPictogram sport={sport} gamesId={gamesId} size={28} />{sport}</span></td></tr>;
              }
              if (!r[0]) return <tr key={i} className="text-xs text-muted"><td className="td py-1" /><td className="td py-1" colSpan={3}><Cell v={r[1] ?? ""} links={links[1]} /></td></tr>;
              const medal = /^(Gold|Silver|Bronze)$/.test(r[3] ?? "") ? r[3] : null;
              return (
                <tr key={i} data-medal={medal || undefined}>
                  <td className="td font-semibold"><Cell v={r[0]} links={links[0]} /></td>
                  <td className="td"><Cell v={r[1] ?? ""} links={links[1]} /></td>
                  <td className="td text-right font-display text-base tabular-nums">{r[2] || "—"}</td>
                  <td className="td">{medal ? <MedalChip medal={medal} /> : r[3] ? <span className="text-xs text-muted">{r[3]}</span> : null}</td>
                </tr>);
            })}</tbody>
          </table>
        </TableFrame></div>);
    }}</Async>
  );
}
