import { useEffect, useMemo, useRef } from "react";
import { Link, useNavigate, useNavigationType, useParams } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useApi, csvUrl } from "../lib/api";
import { Async, ChartCard, Empty, Kpi, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { MedalTable, RecordsTable, SportStatisticsTable } from "../components/tables/BroadcastTables";
import { Bars, LineSeries } from "../charts/charts";
import { fmtInt, fmtNum, fmtPct, MEDAL_COLORS } from "../lib/fmt";
import { useTheme } from "../lib/theme";
import { useEditionTheme } from "../themes/olympicThemeEngine";
import { EditionHero } from "../components/editions/EditionHero";
import { ComingSoon } from "../components/editions/EditionGallery";
import { SportGrid, SportEventList, GenderChip } from "../components/editions/SportGrid";
import { BroadcastCountryFlag, MedalChip } from "../components/broadcast/design";
import { useParamState } from "../components/navigation/Crumbs";

const SECTIONS = [
  { id: "medals", label: "Medal Standings" }, { id: "results", label: "Event Results" }, { id: "participants", label: "Participants" }, { id: "sports", label: "Sports & Disciplines" },
  { id: "records", label: "Records" }, { id: "venues", label: "Venues" }, { id: "gender", label: "Gender Statistics" },
];
const GENDER = { M: "Men", F: "Women" } as Record<string, string>;
const sportSlug = (s: string) => encodeURIComponent(s);

/** One Olympic edition, fully in its own identity: hero (emblem, background, mascot on the right), then seven sections, each showing its complete table. The open section is in ?tab= (Back / Forward restore it). */
export default function EditionPage() {
  const { gamesId = "" } = useParams();
  const [tab, setTab] = useParamState("tab", "medals");
  const q = useApi<any>(`/games/${gamesId}`);
  const { theme: mode } = useTheme();
  const { edition, style } = useEditionTheme(gamesId, mode);
  if (q.error && edition) {   // an upcoming Games: its own themed page from the asset registry, and nothing invented
    const e = { host_city: edition.hostCity, host_country: edition.hostCountry, year: edition.year, season: edition.season };
    return (
      <div data-season={edition.season} style={style} data-edition={gamesId} data-testid="edition-upcoming">
        <EditionHero edition={edition} e={e} />
        <div className="card flex flex-col items-center gap-3 p-10 text-center" data-testid="coming-soon-panel">
          <ComingSoon className="text-sm" />
          <h2 className="h-display text-4xl">{edition.name}</h2>
          <p className="text-sm text-muted">Results, medal standings and participants will appear here after the Games.</p>
          <Link to={edition.season === "summer" ? "/summer" : "/winter"} className="btn">All {edition.season} Games <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </div>
    );
  }
  return (
    <div data-season={gamesId.split("_")[1]} style={style} data-edition={gamesId} data-testid="edition-page">
      <Async q={q}>
        {(d) => {
          const e = d.edition;
          return (
            <>
              <EditionHero edition={edition} e={e} />
              <div className="mb-5 grid grid-cols-3 gap-3 md:grid-cols-6">
                <Kpi label="Athletes" value={e.athletes} /><Kpi label="NOCs" value={e.nocs} accent="#0085C7" /><Kpi label="Sports" value={e.sports} accent="#DF0024" />
                <Kpi label="Events" value={e.events} accent="#F4C300" /><Kpi label="Women" value={fmtPct(e.female_share, 1)} accent="#E86AA6" /><Kpi label="Mean age" value={fmtNum(e.mean_age, 1)} accent="#009F3D" />
              </div>
              <Tabs value={tab} onChange={(t) => setTab(t)} tabs={SECTIONS} />
              <div data-testid={`section-${tab}`}>
                {tab === "medals" && <MedalsSection d={d} gamesId={gamesId} />}
                {tab === "participants" && <ParticipantsSection gamesId={gamesId} nocs={d.participating_nocs} />}
                {tab === "sports" && <SportsSection d={d} gamesId={gamesId} />}
                {tab === "results" && <ResultsSection gamesId={gamesId} />}
                {tab === "records" && <RecordsTable rows={d.records} gamesId={gamesId} title={`${e.host_city} ${e.year} · Records`} exportName={`${gamesId}_records`} height={Math.min(640, 90 + d.records.length * 46)} />}
                {tab === "venues" && <VenuesSection venues={d.venues} title={`${e.host_city} ${e.year} · Venues`} gamesId={gamesId} />}
                {tab === "gender" && <GenderSection gamesId={gamesId} title={`${e.host_city} ${e.year}`} />}
              </div>
            </>
          );
        }}
      </Async>
    </div>
  );
}

function MedalsSection({ d, gamesId }: { d: any; gamesId: string }) {
  const nav = useNavigate();
  const rows = d.medal_table;
  const e = d.edition;
  return (
    <div className="grid gap-4 2xl:grid-cols-[1.2fr_1fr]">
      <MedalTable rows={rows} gamesId={gamesId} title={`${e.host_city} ${e.year} · Medal Standings`} subtitle={`${rows.length} NOCs won medals`} exportName={`${gamesId}_medals`}
        height={Math.min(760, 90 + rows.length * 46)} onRowClick={(r) => nav(`/countries/${r.noc_code}/editions/${gamesId}`)} />
      <ChartCard title="Top 15 NOCs by medals" height={460}>
        <Bars horizontal onSelect={(n) => nav(`/countries/${n}/editions/${gamesId}`)} data={rows.slice().sort((a: any, b: any) => b.total - a.total).slice(0, 15).map((r: any) => ({ name: r.noc_code, gold: r.gold, silver: r.silver, bronze: r.bronze }))} x="name" stacked series={[{ key: "gold", name: "Gold", color: MEDAL_COLORS.gold }, { key: "silver", name: "Silver", color: MEDAL_COLORS.silver }, { key: "bronze", name: "Bronze", color: MEDAL_COLORS.bronze }]} />
      </ChartCard>
    </div>
  );
}

function ParticipantsSection({ gamesId, nocs }: { gamesId: string; nocs: any[] }) {
  const q = useApi<any>(`/games/${gamesId}/participants`);
  const [noc, setNoc] = useParamState("noc");
  const [gender, setGender] = useParamState("gender");
  const [sport, setSport] = useParamState("sport");
  const sports = useMemo(() => [...new Set<string>((q.data?.rows ?? []).map((r: any) => r.sport))].sort(), [q.data]);
  const rows = useMemo(() => (q.data?.rows ?? []).filter((r: any) => (!noc || r.noc === noc) && (!gender || r.gender === gender) && (!sport || r.sport === sport)), [q.data, noc, gender, sport]);
  const athletes = useMemo(() => new Set(rows.map((r: any) => r.athlete_id)).size, [rows]);
  return (
    <div>
      <div className="card mb-3 flex flex-wrap items-center gap-3 p-3" data-testid="participant-filters">
        <label className="flex items-center gap-2 text-xs text-muted">NOC<select className="input" aria-label="NOC" value={noc} onChange={(e) => setNoc(e.target.value)}><option value="">All NOCs ({nocs.length})</option>{nocs.map((n: any) => <option key={n.noc_code} value={n.noc_code}>{n.noc_code} · {n.athletes}</option>)}</select></label>
        <label className="flex items-center gap-2 text-xs text-muted">Sport<select className="input" aria-label="Sport" value={sport} onChange={(e) => setSport(e.target.value)}><option value="">All sports</option>{sports.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label className="flex items-center gap-2 text-xs text-muted">Gender<select className="input" aria-label="Gender" value={gender} onChange={(e) => setGender(e.target.value)}><option value="">All</option><option value="M">Men</option><option value="F">Women</option></select></label>
        {(noc || gender || sport) && <button type="button" className="btn" onClick={() => { setNoc(""); setGender("", false); setSport("", false); }} data-testid="clear-filters">Clear</button>}
        {q.data && <span className="ml-auto text-xs text-muted" data-testid="participant-count">{fmtInt(athletes)} athletes · {fmtInt(rows.length)} entries</span>}
      </div>
      <Async q={q}>{() => (
        <DataTable variant="results" rowMedal={(r) => r.medal} title="Participants" subtitle="every athlete entry, medal winners or not" rows={rows} height={640} exportName={`${gamesId}_participants`} csvHref={csvUrl(`/games/${gamesId}/participants`)}
          rowKey={(r, i) => `${r.athlete_id}-${r.event}-${i}`}
          columns={[
            { key: "athlete", header: "Athlete", width: 230, render: (r) => <Link className="font-semibold hover:text-accent hover:underline" to={`/athletes/${r.athlete_id}`}>{r.athlete}</Link> },
            { key: "noc", header: "NOC", width: 110, render: (r) => <Link to={`/countries/${r.noc}/editions/${gamesId}`} className="hover:underline"><BroadcastCountryFlag noc={r.noc} size={15} showCode /></Link> },
            { key: "sport", header: "Sport", width: 160, render: (r) => <Link className="hover:text-[var(--ed-accent)] hover:underline" to={`/games/${gamesId}/sports/${encodeURIComponent(r.sport)}`}>{r.sport}</Link> },
            { key: "event", header: "Event", width: 330, render: (r) => (r.event_route ? <Link className="hover:text-[var(--ed-accent)] hover:underline" to={r.event_route}>{r.event}</Link> : r.event) },            { key: "gender", header: "Gender", width: 80, render: (r) => GENDER[r.gender] ?? r.gender },
            { key: "age", header: "Age", width: 60, align: "right" },
            { key: "medal", header: "Result", width: 110, render: (r) => (r.medal ? <MedalChip medal={r.medal} /> : <span className="text-muted">–</span>) },
          ]} />)}</Async>
    </div>
  );
}

function SportsSection({ d, gamesId }: { d: any; gamesId: string }) {
  const ev = useApi<any>(`/games/${gamesId}/events`);
  const genders = useMemo(() => Object.fromEntries((ev.data?.sports ?? []).map((s: any) => [s.sport, [...new Set(s.events.map((x: any) => x.gender))].join(", ")])), [ev.data]);
  const disc = useMemo(() => Object.fromEntries((ev.data?.sports ?? []).map((s: any) => [s.sport, s.events.length])), [ev.data]);
  const rows = d.sports.map((x: any) => ({ ...x, games_id: gamesId, genders: genders[x.sport_name] ?? "", saved_events: disc[x.sport_name] }));
  return (
    <SportStatisticsTable rows={rows} gamesId={gamesId} title={`${d.edition.host_city} ${d.edition.year} · Sports & Disciplines`} exportName={`${gamesId}_sports`} height={Math.min(760, 90 + rows.length * 46)}
      numeric={[{ key: "events", header: "Events", align: "right" }, { key: "genders", header: "Categories", width: 170 }, { key: "athletes", header: "Athletes", align: "right", render: (r: any) => fmtInt(r.athletes) },
        { key: "female_athletes", header: "Women", align: "right" }, { key: "male_athletes", header: "Men", align: "right" }, { key: "nocs", header: "NOCs", align: "right" }, { key: "medal_awards", header: "Medals", align: "right" }]}
      extra={[{ key: "open", header: "", width: 90, sortable: false, render: (r: any) => (genders[r.sport_name] !== undefined ? <Link className="text-xs text-accent hover:underline" to={`/games/${gamesId}/sports/${sportSlug(r.sport_name)}`}>Results →</Link> : null) }]} />
  );
}

function ResultsSection({ gamesId }: { gamesId: string }) {
  const ev = useApi<any>(`/games/${gamesId}/events`);
  const [open] = useParamState("sport");
  const panel = useRef<HTMLDivElement>(null);
  const navType = useNavigationType();
  // a pictogram click brings its events into view (beside the pictograms on wide screens, scrolled to on narrow ones)
  useEffect(() => {
    if (!open || navType === "POP" || !panel.current) return;
    const bring = () => { const el = panel.current; if (!el) return; const r = el.getBoundingClientRect(); if (r.top < 0 || r.top > window.innerHeight * 0.6) el.scrollIntoView({ behavior: "auto", block: "start" }); };
    bring();
    const t = setTimeout(bring, 400);   // again once lazy pictograms above have settled the layout
    return () => clearTimeout(t);
  }, [open, ev.data]);  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Async q={ev}>{(d) => {
      const sel = d.sports.find((s: any) => s.sport === open);
      if (!d.sports.length) return <Empty message="No saved results for this edition." />;
      return (
        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_440px]" data-testid="results-layout">
          <SportGrid compact sports={d.sports} gamesId={gamesId} selected={open} href={(s) => `?tab=results${s === open ? "" : `&sport=${encodeURIComponent(s)}`}`} />
          <div ref={panel} className={`scroll-mt-16 xl:sticky xl:top-16 ${open ? "min-h-[75vh] xl:min-h-0" : ""}`} data-testid="events-panel">
            {sel ? <div className="xl:max-h-[calc(100vh-5rem)] xl:overflow-y-auto scroll-thin rounded-xl"><SportEventList compact sport={sel.sport} events={sel.events} gamesId={gamesId} /></div>
              : <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-line bg-surface/70 p-8 text-center" data-testid="events-placeholder">
                  <span className="grid h-14 w-14 place-items-center rounded-full" style={{ background: "var(--ed-tint)", color: "var(--ed-accent)" }}>&#9654;</span>
                  <span className="font-display text-xl font-semibold uppercase tracking-wide">Choose a sport</span>
                  <span className="text-sm text-muted">{d.all_sports.length} sports · {d.total} events</span>
                </div>}
          </div>
        </div>);
    }}</Async>
  );
}

function VenuesSection({ venues, title, gamesId }: { venues: any[]; title: string; gamesId: string }) {
  // a venue appears once per sport in the source: one row per venue, with every sport it hosted
  const rows = useMemo(() => {
    const by: Record<string, any> = {};
    venues.forEach((v) => { const k = v.venue_name; by[k] = by[k] ? { ...by[k], sports: [...new Set([...by[k].sports, v.sport].filter(Boolean))], capacity: by[k].capacity ?? v.capacity } : { ...v, sports: [v.sport].filter(Boolean) }; });
    return Object.values(by).map((v: any) => ({ ...v, sport: v.sports.join(", "), n: v.sports.length }));
  }, [venues]);
  return (
    <DataTable variant="venues" title={title} subtitle={`${rows.length} venues`} rows={rows} exportName={`${gamesId}_venues`} height={Math.min(720, 90 + rows.length * 46)} empty="No venue rows for this edition."
      columns={[{ key: "venue_name", header: "Venue", width: 280, render: (v) => <span className="font-semibold">{v.venue_name}</span> }, { key: "city", header: "City", width: 150 }, { key: "sport", header: "Sports", width: 360 },
        { key: "n", header: "Sports hosted", align: "right", width: 110 }, { key: "capacity", header: "Capacity", align: "right", width: 100, render: (v) => (v.capacity ? fmtInt(v.capacity) : "–") }]} />
  );
}

function GenderSection({ gamesId, title }: { gamesId: string; title: string }) {
  const q = useApi<any>(`/games/${gamesId}/gender`);
  const pct = (r: any) => (r.total ? fmtPct(r.women / r.total, 1) : "–");
  const cols = (first: string, link?: (r: any) => string) => [
    { key: "name", header: first, width: 300, render: (r: any) => (first === "NOC" ? <Link to={link!(r)} className="hover:underline"><BroadcastCountryFlag noc={r.name} size={15} showCode /></Link> : <span className="font-semibold">{r.name}</span>) },
    { key: "men", header: "Men", align: "right" as const }, { key: "women", header: "Women", align: "right" as const }, { key: "total", header: "Total", align: "right" as const },
    { key: "share", header: "Women %", align: "right" as const, render: pct, sortable: false },
  ];
  return (
    <Async q={q}>{(g) => (
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <Kpi label="Men" value={g.overall.men} accent="#0085C7" /><Kpi label="Women" value={g.overall.women} accent="#E86AA6" /><Kpi label="Women share" value={fmtPct(g.overall.women / g.overall.total, 1)} hint={g.overall.unrecorded ? `${g.overall.unrecorded} athlete(s) without recorded gender` : undefined} accent="var(--ed-accent)" />
        </div>
        <ChartCard title="Gender progression" height={300}>
          <LineSeries data={g.progression.map((r: any) => ({ ...r, label: String(r.year) }))} x="label" yLabel="Athletes" refLines={[{ x: String(gamesId.split("_")[0]), label: "this edition" }]}
            series={[{ key: "men", name: "Men", color: "#0085C7", dot: true }, { key: "women", name: "Women", color: "#E86AA6", dot: true }]} />
        </ChartCard>
        <div className="grid gap-4 2xl:grid-cols-2">
          <DataTable variant="gender" title={`${title} · By sport`} rows={g.by_sport} columns={cols("Sport")} height={Math.min(640, 90 + g.by_sport.length * 46)} exportName={`${gamesId}_gender_sport`} />
          <DataTable variant="gender" title={`${title} · By NOC`} rows={g.by_noc} columns={cols("NOC", (r) => `/countries/${r.name}/editions/${gamesId}`)} height={640} exportName={`${gamesId}_gender_noc`} />
        </div>
        <DataTable variant="gender" title={`${title} · By event`} rows={g.by_event} columns={cols("Event")} height={640} exportName={`${gamesId}_gender_event`} />
      </div>)}</Async>
  );
}

export { GenderChip };
