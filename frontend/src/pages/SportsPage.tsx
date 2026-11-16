import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApi } from "../lib/api";
import { Async, ChartCard, Kpi, Note, PageHeader, SeasonToggle, Tabs, Select } from "../components/ui";
import { SportStatisticsTable } from "../components/tables/BroadcastTables";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries, StackedArea } from "../charts/charts";
import { fmtNum, MEDAL_COLORS, PALETTE } from "../lib/fmt";
import { useAssets } from "../lib/assets";

import { ProfileHero } from "../components/profile/ProfileHero";
import { useRegistry } from "../themes/olympicThemeEngine";
import { useParamState } from "../components/navigation/Crumbs";
/** Newest pictogram the asset collection links to a sport (by file name), with its edition; none means no verified artwork. */
function usePictogramOf() {
  const reg = useRegistry();
  return useMemo(() => {
    const out: Record<string, { src: string; edition: string }> = {};
    Object.values(reg.editions).sort((a, b) => a.year - b.year).forEach((e) => e.assets.pictograms.forEach((p) => { if (p.sportLinked && p.sport) out[p.sport.toLowerCase()] = { src: p.src, edition: e.name }; }));
    return (sport: string) => out[sport.toLowerCase()];
  }, [reg]);
}

function SportCard({ s, pic }: { s: any; pic?: { src: string; edition: string } }) {
  return (
    <Link to={`/sports/${s.sport_id}`} data-testid="sport-card" className="group flex flex-col items-center gap-2 rounded-xl border border-line bg-surface p-3 text-center transition hover:-translate-y-0.5 hover:border-[var(--ed-accent)]" style={{ borderTop: `3px solid ${s.season === "winter" ? "#60C8FF" : "#F4C300"}` }}>
      <span className="grid h-16 w-16 place-items-center rounded-lg bg-white p-1">{pic ? <img src={pic.src} alt={`${s.sport_name} pictogram, ${pic.edition}`} loading="lazy" className="max-h-full max-w-full object-contain" /> : <span className="text-[9px] text-neutral-500">no pictogram</span>}</span>
      <span className="font-display text-base font-semibold leading-tight">{s.sport_name}</span>
      <span className="text-[11px] text-muted">{s.first_appearance}–{s.last_appearance} · {s.editions} editions</span>
      <span className="text-[10px] uppercase tracking-wider text-muted">{[s.mens_events && "Men", s.womens_events && "Women", s.mixed_events && "Mixed"].filter(Boolean).join(" · ")}{s.is_discontinued ? " · not in latest" : ""}</span>
    </Link>
  );
}

/** Sports: every sport of the 1960-2026 Games as a pictogram card (Summer and Winter), then the full catalogue table and the results-progression modules. */
export function SportsPage() {
  const nav = useNavigate();
  const [season, setSeason] = useParamState("season");
  const q = useApi<any[]>("/sports", { season });
  const idx = useApi<any[]>("/sports-analytics");
  const pic = usePictogramOf();
  return (
    <div>
      <PageHeader title="Sports" right={<SeasonToggle value={season} onChange={(v: string) => setSeason(v)} />} />
      <Async q={q}>{(all) => {
        const rows = all.filter((s) => (s.last_appearance ?? 0) >= 1960);
        return (<>
          {(["summer", "winter"] as const).filter((x) => !season || season === x).map((x) => {
            const list = rows.filter((s) => s.season === x).sort((a, b) => Number(a.is_discontinued) - Number(b.is_discontinued) || a.sport_name.localeCompare(b.sport_name));
            return list.length ? (
              <section key={x} className="mb-8" aria-labelledby={`sports-${x}`}>
                <h2 id={`sports-${x}`} className="h-display mb-3 border-b border-line pb-2 text-3xl capitalize">{x} sports <span className="text-base text-muted">({list.length})</span></h2>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6" data-testid={`sport-cards-${x}`}>{list.map((s) => <SportCard key={s.sport_id} s={s} pic={pic(s.sport_name)} />)}</div>
              </section>) : null;
          })}
          <h2 className="h-display mb-3 border-b border-line pb-2 text-3xl">Sport catalogue</h2>
          <SportStatisticsTable rows={rows} height={Math.min(760, 90 + rows.length * 46)} title="Sports" exportName="sports" onRowClick={(r) => nav(`/sports/${r.sport_id}`)}
            numeric={[{ key: "season", width: 80 }, { key: "first_appearance", header: "First", align: "right", width: 70 }, { key: "last_appearance", header: "Last", align: "right", width: 70 }, { key: "editions", align: "right", width: 80 }, { key: "number_of_events", header: "Events (latest)", align: "right", width: 110 },
              { key: "mens_events", header: "Men", align: "right", width: 64 }, { key: "womens_events", header: "Women", align: "right", width: 72 }, { key: "mixed_events", header: "Mixed", align: "right", width: 64 }, { key: "athlete_participations", header: "Athletes", align: "right", width: 90 }, { key: "medal_winning_nocs", header: "Medal NOCs", align: "right", width: 100 }]} />
        </>);
      }}</Async>
      <h2 className="h-display mb-3 mt-10 border-b border-line pb-2 text-3xl">Results progression</h2>
      <ScienceTab index={idx.data ?? []} />
    </div>
  );
}

function ScienceTab({ index }: { index: any[] }) {
  const modules = index.filter((m) => ["athletics", "swimming", "gymnastics", "speed_skating", "rowing"].includes(m.key));
  const [key, setKey] = useState("athletics");
  const q = useApi<any>(`/sports-analytics/${key}`);
  const [ev, setEv] = useState("");
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3"><Select label="Sport" allLabel="–" value={key} onChange={(v) => { setKey(v || "athletics"); setEv(""); }} options={modules.map((m) => ({ value: m.key, label: m.title }))} /></div>
      <Async q={q}>{({ data }) => {
        if (data.status) return <Note>{data.status}</Note>;
        const events = Object.entries<any>(data.event_progression || {});
        const current = events.find(([n]) => n === ev) ?? events[0];
        return (
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Event result progression" subtitle={current ? `${current[0]} - ${current[1].unit}${current[1].lower_is_better ? " (lower is better)" : ""}` : ""}
              right={<select aria-label="Event" className="input max-w-[220px]" value={current?.[0] ?? ""} onChange={(e) => setEv(e.target.value)}>{events.map(([n]) => <option key={n}>{n}</option>)}</select>}>
              {current ? <LineSeries data={current[1].years.map((y: number, i: number) => ({ year: y, Gold: current[1].gold[i], Silver: current[1].silver[i], Bronze: current[1].bronze[i] }))} x="year" xLabel="Games year" series={[{ key: "Gold", color: MEDAL_COLORS.gold, dot: true }, { key: "Silver", color: MEDAL_COLORS.silver }, { key: "Bronze", color: MEDAL_COLORS.bronze }]} /> : <Note>No event has enough editions of numeric results.</Note>}
              {current && <p className="mt-2 text-xs text-muted">Linear trend {fmtNum(current[1].slope_per_year, 4)} per year (R² {fmtNum(current[1].r2, 2)}, p = {fmtNum(current[1].slope_p, 4)}); change first→last winning mark: {fmtNum(current[1].change_pct_first_to_last, 1)}%.</p>}
            </ChartCard>
            <ChartCard title="Medals by country" subtitle={`${data.sport} - team medals counted once`}>
              <Bars horizontal stacked data={(data.country_medals || []).slice(0, 15).map((c: any) => ({ name: c.noc_code, gold: c.Gold, silver: c.Silver, bronze: c.Bronze }))} x="name" series={[{ key: "gold", color: MEDAL_COLORS.gold }, { key: "silver", color: MEDAL_COLORS.silver }, { key: "bronze", color: MEDAL_COLORS.bronze }]} />
            </ChartCard>
            {data.gender_gap_time_ratio && Object.keys(data.gender_gap_time_ratio).length > 0 && (
              <ChartCard title="Women's vs men's winning times" subtitle="Ratio of gold-medal times (women ÷ men) for matching events">
                <LineSeries data={(Object.values<any>(data.gender_gap_time_ratio)[0].years as number[]).map((y, i) => ({ year: y, ...Object.fromEntries(Object.entries<any>(data.gender_gap_time_ratio).slice(0, 5).map(([n, v]) => [n, v.years.includes(y) ? v.women_over_men_time_ratio[v.years.indexOf(y)] : null])) }))} x="year" series={Object.keys(data.gender_gap_time_ratio).slice(0, 5).map((n, i) => ({ key: n, color: PALETTE[i] }))} />
              </ChartCard>)}
            <ChartCard title="Most decorated athletes" height={260}><DataTable rows={data.top_athletes || []} height={300} columns={[{ key: "full_name", header: "Athlete", width: 200 }, { key: "gold", align: "right", width: 50 }, { key: "silver", align: "right", width: 50 }, { key: "bronze", align: "right", width: 50 }, { key: "medals", align: "right", width: 60 }, { key: "nocs", width: 70 }]} /></ChartCard>
            <div className="xl:col-span-2"><Note>{data.coverage_note}</Note></div>
          </div>);
      }}</Async>
    </div>
  );
}

export function SportPage() {
  const { id = "" } = useParams();
  const reg = useRegistry();
  const q = useApi<any>(`/sports/${id}`);
  return (
    <Async q={q}>{(d) => {
      const s = d.sport;
      return (
        <div>
          {(() => {
            // pictograms of THIS sport across editions: only those whose file name named the sport (registry), newest first
            const key = String(s.sport_name).toLowerCase();
            const pics = Object.values(reg.editions).flatMap((e) => e.assets.pictograms.filter((p) => p.sportLinked && p.sport && (p.sport.toLowerCase() === key || key.includes(p.sport.toLowerCase()) || p.sport.toLowerCase().includes(key))).map((p) => ({ ...p, e }))).sort((x, y) => y.e.year - x.e.year);
            const latest = pics[0];
            return (<>
              <ProfileHero back={{ to: "/sports", label: "sports" }} kicker={`${s.season} · ${s.first_appearance ?? "?"} – ${s.last_appearance ?? "?"}`} title={s.sport_name} tile={latest ? <img src={latest.src} alt={`${s.sport_name} pictogram, ${latest.e.name}`} className="max-h-full max-w-full object-contain" /> : undefined}
                facts={<>{latest ? <span>Pictogram: {latest.e.name}</span> : <span>No pictogram linked to this sport yet</span>}{s.is_discontinued ? <span>discontinued</span> : null}</>} />
              {pics.length > 1 && <section className="mb-6" data-testid="pictogram-history"><h2 className="h-display mb-2 text-xl">Pictogram history</h2><div className="scroll-thin flex gap-3 overflow-x-auto pb-2">{pics.map((p) => <Link key={p.src} to={`/edition/${p.e.editionId}`} className="card w-24 shrink-0 p-2 text-center transition hover:border-accent"><span className="grid aspect-square place-items-center rounded bg-white p-1"><img src={p.src} alt={`${s.sport_name}, ${p.e.name}`} loading="lazy" className="max-h-full max-w-full object-contain" /></span><div className="mt-1 text-[11px] font-semibold">{p.e.year}</div><div className="truncate text-[10px] text-muted">{p.discipline ?? p.e.hostCity}</div></Link>)}</div></section>}
            </>);
          })()}
          <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-5"><Kpi label="Events (latest)" value={s.number_of_events} /><Kpi label="Men" value={s.mens_events} accent="#0085C7" /><Kpi label="Women" value={s.womens_events} accent="#E86AA6" /><Kpi label="Mixed" value={s.mixed_events} accent="#8E6BBF" /><Kpi label="Editions" value={d.by_edition.length} accent="#009F3D" /></div>
          <section className="mb-6" data-testid="sport-editions">
            <h2 className="h-display mb-2 text-2xl">Editions</h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6 2xl:grid-cols-8">
              {d.by_edition.slice().sort((a: any, b: any) => b.year - a.year).map((e: any) => { const ed = reg.editions[e.games_id]; return (
                <Link key={e.games_id} to={`/games/${e.games_id}/sports/${encodeURIComponent(s.sport_name)}`} className="card flex items-center gap-2 p-2 transition hover:border-accent" style={{ borderLeft: `3px solid ${ed?.theme.primary ?? "#888"}` }}>
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-white p-0.5">{ed?.assets.logo ? <img src={ed.assets.logo} alt="" loading="lazy" className="max-h-full max-w-full object-contain" /> : null}</span>
                  <span className="min-w-0"><span className="block truncate text-sm font-semibold">{ed?.name ?? e.games_id}</span><span className="text-[11px] text-muted">{e.events} events · {e.athletes} athletes</span></span>
                </Link>); })}
            </div>
          </section>
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Athletes by edition"><StackedArea data={d.by_edition.map((e: any) => ({ year: e.year, Men: e.male_athletes, Women: e.female_athletes }))} x="year" series={[{ key: "Men", color: "#0085C7" }, { key: "Women", color: "#E86AA6" }]} /></ChartCard>
            <ChartCard title="Events and medal awards"><LineSeries data={d.by_edition.map((e: any) => ({ year: e.year, events: e.events, medal_awards: e.medal_awards, nocs: e.nocs }))} x="year" series={[{ key: "events", color: "#F4C300", dot: true }, { key: "medal_awards", color: "#DF0024", dot: true }, { key: "nocs", color: "#0085C7", dot: true }]} /></ChartCard>
            <ChartCard title="Medals by country"><Bars horizontal stacked data={d.medals_by_noc.map((m: any) => ({ name: m.noc_code, gold: m.gold, silver: m.silver, bronze: m.bronze }))} x="name" series={[{ key: "gold", color: MEDAL_COLORS.gold }, { key: "silver", color: MEDAL_COLORS.silver }, { key: "bronze", color: MEDAL_COLORS.bronze }]} /></ChartCard>
            <ChartCard title="Disciplines" height={200}><DataTable rows={d.disciplines} columns={[{ key: "discipline_name", header: "Discipline", width: 240 }, { key: "first_appearance", header: "First" }, { key: "last_appearance", header: "Last" }]} empty="No discipline rows linked to this sport." /></ChartCard>
          </div>
        </div>);
    }}</Async>
  );
}
