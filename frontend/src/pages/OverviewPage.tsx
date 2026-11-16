import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useApi } from "../lib/api";
import { Async, ChartCard, Counter, Flag } from "../components/ui";
import { Bars, LineSeries, TreemapChart } from "../charts/charts";
import { fmtInt, fmtPct, gamesLabel, MEDAL_COLORS } from "../lib/fmt";
import { OlympicRings } from "../components/OlympicRings";
import { EditionGallery, useEditionList } from "../components/editions/EditionGallery";
import { MedalStrip } from "../components/profile/ProfileHero";

const RING = ["#0085C7", "#1a1a1a", "#DF0024", "#F4C300", "#009F3D"];
const LEADERS = ["USA", "URS", "CHN", "GER", "GBR", "NOR"];
const LINE = ["#0085C7", "#DF0024", "#F4C300", "#009F3D", "#8E6BBF", "#FF8A3D"];

function Section({ title, action, children, id }: { title: string; action?: { to: string; label: string }; children: React.ReactNode; id?: string }) {
  return (
    <section className="mt-12" id={id} aria-labelledby={id ? `${id}-h` : undefined}>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2 border-b border-line pb-2">
        <h2 id={id ? `${id}-h` : undefined} className="h-display text-3xl leading-none sm:text-4xl">{title}</h2>
        {action && <Link to={action.to} className="inline-flex items-center gap-1 text-sm text-muted hover:text-accent">{action.label} <ArrowRight className="h-4 w-4" /></Link>}
      </div>
      {children}
    </section>
  );
}

/** Global overview: the Olympic rings on a clean background, global numbers, every Summer and Winter edition with its emblem, then the historical charts shown directly. */
export default function OverviewPage() {
  const q = useApi<any>("/overview");
  const progress = useApi<any>("/countries/compare", { nocs: LEADERS.join(",") });
  const topAthletes = useApi<any>("/athletes", { sort: "medals", page_size: 8 });
  const records = useApi<any>("/records", { page_size: 6, level: "olympic" });
  const summer = useEditionList("summer"), winter = useEditionList("winter");
  const games = useApi<any[]>("/games");
  const list = games.data ?? [];
  const highlights = useMemo(() => {
    if (!list.length) return [];
    const by = (k: string) => [...list].sort((a, b) => b[k] - a[k])[0];
    const s = list.filter((g) => g.season === "summer").sort((a, b) => a.year - b.year);
    const big = by("athletes"), nocs = by("nocs"), events = by("events"), first = s[0], last = s[s.length - 1];
    return [
      { k: "Largest Games", v: `${big.host_city} ${big.year}`, d: `${fmtInt(big.athletes)} athletes`, to: `/edition/${big.games_id}` },
      { k: "Most nations", v: `${nocs.host_city} ${nocs.year}`, d: `${fmtInt(nocs.nocs)} NOCs`, to: `/edition/${nocs.games_id}` },
      { k: "Biggest programme", v: `${events.host_city} ${events.year}`, d: `${fmtInt(events.events)} events`, to: `/edition/${events.games_id}` },
      { k: "Women, Summer Games", v: `${fmtPct(first.female_share, 0)} → ${fmtPct(last.female_share, 0)}`, d: `${first.host_city} ${first.year} → ${last.host_city} ${last.year}`, to: "/visualizations?section=4" },
    ];
  }, [list]);
  const progression = (season: string, c: any) => {
    const years: Record<string, any> = {};
    Object.entries(c).forEach(([noc, rows]: any) => rows.filter((r: any) => r.season === season).forEach((r: any) => { years[r.games_id] = { ...(years[r.games_id] || { label: String(r.year), year: r.year }), [noc]: r.total }; }));
    return Object.values(years).sort((a: any, b: any) => a.year - b.year) as any[];
  };
  return (
    <div data-testid="overview">
      {/* ---- identity: the Olympic rings, large, on a plain professional background (no photograph) ---- */}
      <section className="relative overflow-hidden rounded-3xl border border-line bg-surface shadow-2xl" data-testid="home-hero"
        style={{ backgroundImage: "radial-gradient(ellipse 52% 62% at 50% 42%, rgb(var(--surface) / 0.94) 0%, rgb(var(--surface) / 0.80) 45%, rgb(var(--surface) / 0.18) 78%, transparent 100%), url(/assets/backgrounds/overview-hero.png)", backgroundSize: "cover, cover", backgroundPosition: "center, center" }}>
        <div className="absolute inset-x-0 bottom-0 flex h-1.5">{RING.map((c) => <i key={c} className="flex-1" style={{ background: c }} />)}</div>
        <div className="relative flex flex-col items-center gap-5 px-6 py-10 text-center sm:py-14">
          <OlympicRings size={340} className="max-w-full" />
          <div className="rounded-2xl bg-surface/85 px-6 py-3 shadow-xl ring-1 ring-white/10 backdrop-blur-md">
            <h1 className="h-display text-5xl leading-none sm:text-7xl">Olympic Games</h1>
            <div className="mt-2 text-xs font-semibold uppercase tracking-[0.35em] text-ink/80">Summer 1960 – 2024 · Winter 1960 – 2026</div>
          </div>
        </div>
      </section>

      <Async q={q}>{(d) => {
        const k = d.kpis;
        const byYear: Record<number, any> = {};
        d.participation_growth.forEach((r: any) => { byYear[r.year] = { ...(byYear[r.year] || { year: r.year }), [`${r.season}_athletes`]: r.athletes, [`${r.season}_events`]: r.events }; });
        const growthRows = Object.values(byYear).sort((a: any, b: any) => a.year - b.year) as any[];
        const gender = d.gender_progression.map((r: any) => ({ year: r.year, [r.season]: r.female_share }));
        return (<>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 2xl:grid-cols-8" data-testid="global-stats">
            {[["Editions", k.editions, RING[0]], ["Athletes", k.unique_athletes, RING[4]], ["NOCs", k.nocs, RING[2]], ["Sports", k.sports, RING[3]], ["Disciplines", k.disciplines, "#8E6BBF"], ["Events", k.events, "#FF8A3D"], ["Medals", k.medal_awards, MEDAL_COLORS.gold], ["Matches", k.team_matches, "#2BB3B1"]].map(([l, v, c]) => (
              <div key={l as string} className="relative overflow-hidden rounded-xl border border-line bg-surface p-4" data-testid="kpi">
                <div className="absolute inset-x-0 top-0 h-1" style={{ background: c as string }} />
                <div className="font-display text-3xl font-bold leading-none sm:text-4xl"><Counter value={v as number} /></div>
                <div className="mt-1 text-[11px] font-semibold uppercase tracking-widest text-muted">{l}</div>
              </div>))}
          </div>

          <Section title="Summer Olympic Games" action={{ to: "/summer", label: "Summer Olympics" }} id="summer-editions"><EditionGallery items={summer.items} size="sm" testid="summer-gallery" /></Section>
          <Section title="Winter Olympic Games" action={{ to: "/winter", label: "Winter Olympics" }} id="winter-editions"><EditionGallery items={winter.items} size="sm" testid="winter-gallery" /></Section>


          <Section title="Medal statistics" action={{ to: "/countries", label: "Countries & Medal Statistics" }} id="medals">
            <div className="grid gap-4 xl:grid-cols-[1fr_1.4fr]">
              <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1" data-testid="top-countries">
                {d.top_countries.slice(0, 3).map((c: any, i: number) => (
                  <Link key={c.noc_code} to={`/countries/${c.noc_code}`} className="card flex items-center gap-4 p-4 transition hover:border-accent">
                    <div className="font-display text-5xl font-bold leading-none" style={{ color: [MEDAL_COLORS.gold, MEDAL_COLORS.silver, MEDAL_COLORS.bronze][i] }}>{i + 1}</div><Flag noc={c.noc_code} size={32} />
                    <div className="min-w-0 flex-1"><div className="truncate font-display text-2xl leading-none">{c.historical_name}</div><div className="mt-1 text-xs text-muted">{fmtInt(c.total_medals)} medals</div></div>
                    <div className="hidden sm:block"><MedalStrip gold={c.gold} silver={c.silver} bronze={c.bronze} /></div>
                  </Link>))}
              </div>
              <ChartCard title="Top 12 NOCs by medals" height={360}>
                <Bars horizontal data={d.top_countries.map((c: any) => ({ name: c.noc_code, gold: c.gold, silver: c.silver, bronze: c.bronze }))} x="name" stacked series={[{ key: "gold", name: "Gold", color: MEDAL_COLORS.gold }, { key: "silver", name: "Silver", color: MEDAL_COLORS.silver }, { key: "bronze", name: "Bronze", color: MEDAL_COLORS.bronze }]} />
              </ChartCard>
            </div>
            <Async q={progress}>{(c) => (
              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <ChartCard title="Medal progression · Summer" height={320}><LineSeries data={progression("summer", c)} x="label" yLabel="Medals" series={Object.keys(c).map((n, i) => ({ key: n, color: LINE[i], dot: false }))} /></ChartCard>
                <ChartCard title="Medal progression · Winter" height={320}><LineSeries data={progression("winter", c)} x="label" yLabel="Medals" series={Object.keys(c).map((n, i) => ({ key: n, color: LINE[i], dot: false }))} /></ChartCard>
              </div>)}</Async>
          </Section>

          <Section title="Athlete participation" id="participation">
            <div className="grid gap-4 xl:grid-cols-2">
              <ChartCard title="Athletes per edition"><LineSeries data={growthRows} x="year" xLabel="Year" yLabel="Athletes" series={[{ key: "summer_athletes", name: "Summer", color: "#F4C300", dot: true }, { key: "winter_athletes", name: "Winter", color: "#60C8FF", dot: true }]} /></ChartCard>
              <ChartCard title="Female share of athletes"><LineSeries data={gender} x="year" xLabel="Year" yLabel="Female share" yFormat={(v) => fmtPct(v, 0)} series={[{ key: "summer", name: "Summer", color: "#F4C300" }, { key: "winter", name: "Winter", color: "#60C8FF" }]} /></ChartCard>
            </div>
            <Async q={topAthletes}>{(a) => (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="top-athletes">
                {a.rows.map((r: any, i: number) => (
                  <Link key={r.athlete_id} to={`/athletes/${r.athlete_id}`} className="card flex items-center gap-3 p-4 transition hover:border-accent">
                    <div className="font-display text-4xl font-bold leading-none text-muted/40">{i + 1}</div>
                    <div className="min-w-0 flex-1"><div className="line-clamp-2 font-semibold leading-tight">{r.full_name}</div><div className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">{String(r.nocs ?? "").split(",")[0] && <Flag noc={String(r.nocs).split(",")[0]} size={11} />}{r.sports} · {r.first_year}–{r.last_year}</div></div>
                    <div className="text-right"><div className="font-display text-3xl leading-none" style={{ color: MEDAL_COLORS.gold }}>{r.medals}</div><div className="text-[10px] uppercase tracking-wider text-muted">{r.gold}G {r.silver}S {r.bronze}B</div></div>
                  </Link>))}
              </div>)}</Async>
          </Section>

          <Section title="Sport evolution" id="sports">
            <div className="grid gap-4 xl:grid-cols-2">
              <ChartCard title="Events per edition"><LineSeries data={growthRows} x="year" xLabel="Year" yLabel="Events" series={[{ key: "summer_events", name: "Summer", color: "#F4C300", dot: true }, { key: "winter_events", name: "Winter", color: "#60C8FF", dot: true }]} /></ChartCard>
              <ChartCard title="Largest sports by participations" height={320}><TreemapChart data={d.top_sports.map((s: any) => ({ name: s.sport_name, size: s.athletes }))} /></ChartCard>
            </div>
          </Section>

          <Section title="Historical highlights" id="highlights">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="highlights">
              {highlights.map((h) => <Link key={h.k} to={h.to} className="card p-4 transition hover:border-accent"><div className="text-[11px] font-semibold uppercase tracking-widest text-accent">{h.k}</div><div className="mt-1 font-display text-3xl leading-tight">{h.v}</div><div className="mt-1 text-xs text-muted">{h.d}</div></Link>)}
            </div>
            <Async q={records}>{(rc) => (
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="olympic-records">
                {rc.records.rows.map((r: any) => { const [event, , who] = String(r.description).split(" | "); return (
                  <Link key={r.record_id} to={`/edition/${r.games_id}?tab=records`} className="card p-4 transition hover:border-accent"><div className="flex items-center justify-between"><span className="chip capitalize">{r.record_level} record</span><span className="text-[11px] text-muted">{r.record_date}</span></div>
                    <div className="mt-2 font-display text-3xl leading-none text-accent">{r.record_value}</div><div className="mt-1 text-sm">{event}</div><div className="mt-1 flex items-center gap-1.5 text-xs text-muted"><Flag noc={r.noc_code} size={11} />{who} · {gamesLabel(r.games_id)}</div></Link>); })}
              </div>)}</Async>
          </Section>
        </>);
      }}</Async>
      {q.error && <>
        <Section title="Summer Olympic Games" action={{ to: "/summer", label: "Summer Olympics" }} id="summer-editions"><EditionGallery items={summer.items} size="sm" testid="summer-gallery" /></Section>
        <Section title="Winter Olympic Games" action={{ to: "/winter", label: "Winter Olympics" }} id="winter-editions"><EditionGallery items={winter.items} size="sm" testid="winter-gallery" /></Section>
      </>}
    </div>
  );
}
