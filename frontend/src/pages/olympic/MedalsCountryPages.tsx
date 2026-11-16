import { useMemo } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import WorldMap from "../../charts/WorldMap";
import { VizSection } from "../../viz/VizGallery";
import { Download, Search } from "lucide-react";
import { csvUrl, useApi } from "../../lib/api";
import { Async, Empty, Note } from "../../components/ui";
import { BroadcastCountryFlag, BroadcastPageHeader, BroadcastStatPanel, MedalChip, MedalCount, SportPictogram } from "../../components/broadcast/design";
import { BroadcastCountryTable, BroadcastMedalTable } from "../../components/tables/broadcast";
import { CsvButton } from "../../components/CsvButton";
import { Crumbs, useParamState } from "../../components/navigation/Crumbs";
import { useRegistry } from "../../themes/olympicThemeEngine";
import { OlympicRings } from "../../components/OlympicRings";


// ------------------------------------------------------------------ Countries & Medal Statistics: Medal table | Visuals
/** The two pages of Countries & Medal Statistics, as a switch under the header. */
export function CountriesSwitch({ active }: { active: "table" | "visuals" }) {
  const tab = (to: string, id: string, label: string) => <Link to={to} aria-current={active === id ? "page" : undefined} data-testid={`countries-switch-${id}`}
    className={`rounded-xl px-5 py-2.5 font-display text-lg font-semibold uppercase tracking-wide transition ${active === id ? "bg-[var(--ed-accent)] text-black shadow-lg" : "text-muted hover:bg-surface2 hover:text-ink"}`}>{label}</Link>;
  return <nav aria-label="Countries & Medal Statistics" className="card mb-4 inline-flex gap-1 p-1">{tab("/countries", "table", "Medal table")}{tab("/countries/visuals", "visuals", "Visuals")}</nav>;
}

/** /countries/visuals - every medal and country visualization on its own page, shown directly: the world map, the country comparison entry and all charts. */
export function CountriesVisualsPage() {
  const nav = useNavigate();
  const all = useApi<any>("/countries", { page_size: 300 });
  return (
    <div data-testid="countries-visuals">
      <Crumbs items={[{ label: "Countries & Medal Statistics", to: "/countries" }, { label: "Visuals" }]} />
      <BroadcastPageHeader title="Countries & Medal Statistics" kicker="Visuals" icon={<OlympicRings size={36} />} />
      <CountriesSwitch active="visuals" />
      <section className="grid gap-4 xl:grid-cols-[1.6fr_1fr]" data-testid="country-map-section">
        <div className="card p-4"><h2 className="h-display mb-2 text-2xl">All-time medals · world map</h2>
          <Async q={all}>{(d) => <WorldMap rows={d.rows} valueKey="total_medals" label="medals" onPick={(r: any) => nav(`/countries/${r.noc_code}`)} />}</Async></div>
        <div className="card flex flex-col justify-center gap-3 p-5"><h2 className="h-display text-2xl">Compare countries</h2>
          <Link className="btn btn-accent self-start" to="/compare/countries?nocs=USA,CHN">Open the country comparison →</Link></div>
      </section>
      <VizSection page="countries" title="Country visuals" lazyOnly={false} />
      <VizSection page="medals" title="Medal visuals" lazyOnly={false} />
    </div>
  );
}

// ------------------------------------------------------------------ /countries (and /medals/editions/:gamesId)
/** Medal table by NOC with every filter in the URL (season, years, edition, NOC, sport, gender, medal), sortable columns, paging and CSV export. The counting convention is shown. */
export function MedalsByCountryPage() {
  const { gamesId: routeGames } = useParams();
  const nav = useNavigate();
  const loc = useLocation();
  const reg = useRegistry();
  const [season, setSeason] = useParamState("season");
  const [yf, setYf] = useParamState("year_from");
  const [yt, setYt] = useParamState("year_to");
  const [gq, setGames] = useParamState("games_id");
  const [noc, setNoc] = useParamState("noc");
  const [text, setText] = useParamState("q");
  const [sport, setSport] = useParamState("sport");
  const [gender, setGender] = useParamState("gender");
  const [medal, setMedal] = useParamState("medal");
  const [sort, setSort] = useParamState("sort", "rank");
  const [order, setOrder] = useParamState("order", "asc");
  const games = routeGames ?? gq;
  const params = { season: season || undefined, year_from: yf || undefined, year_to: yt || undefined, games_id: games || undefined, noc: noc || undefined, sport: sport || undefined,
    gender: gender || undefined, medal: medal || undefined, include_all: routeGames ? undefined : 1, sort: sort === "rank" ? "gold" : sort, order: sort === "rank" ? (order === "asc" ? "desc" : "asc") : order, page: 1, page_size: 500 };   // the complete table (there are fewer than 250 NOCs), no paging
  const q = useApi<any>("/medals/countries", params, true, { keepPrevious: true });
  const sportsQ = useApi<any>("/medals/countries", { games_id: games || undefined, season: season || undefined, page_size: 1 });
  const editions = useMemo(() => Object.values(reg.editions).filter((e: any) => e.year <= 2026 && (!season || e.season === season)).sort((a: any, b: any) => b.year - a.year), [reg, season]);
  const years = useMemo(() => [...new Set(Object.values(reg.editions).filter((e: any) => e.year <= 2026).map((e: any) => e.year))].sort(), [reg]);
  const ed = games ? reg.editions[games] : undefined;
  const clickSort = (k: string) => { if (sort === k) setOrder(order === "asc" ? "desc" : "asc"); else { setSort(k); setOrder(["noc", "rank"].includes(k) ? "asc" : "desc", false); } };
  return (
    <div data-testid="medals-by-country">
      <Crumbs items={routeGames ? [{ label: "Countries & Medal Statistics", to: "/countries" }, { label: ed?.name ?? routeGames }] : [{ label: "Countries & Medal Statistics" }]} />
      <BroadcastPageHeader title={ed ? `Medal table · ${ed.name}` : "Countries & Medal Statistics"} kicker="Olympedia podiums" icon={<OlympicRings size={36} />}
 />
      {!routeGames && <CountriesSwitch active="table" />}
      <div className="card mb-4 flex flex-wrap items-center gap-2 p-3" data-testid="medal-filters">
        <select className="input" aria-label="Season" value={season} onChange={(e) => setSeason(e.target.value)}><option value="">Summer + Winter</option><option value="summer">Summer</option><option value="winter">Winter</option></select>
        {!routeGames && <>
          <select className="input" aria-label="From year" value={yf} onChange={(e) => setYf(e.target.value)}><option value="">From 1960</option>{years.map((y) => <option key={y} value={y}>From {y}</option>)}</select>
          <select className="input" aria-label="To year" value={yt} onChange={(e) => setYt(e.target.value)}><option value="">To 2026</option>{years.map((y) => <option key={y} value={y}>To {y}</option>)}</select>
        </>}
        <select className="input" aria-label="Edition" value={games} onChange={(e) => routeGames ? nav(e.target.value ? `/medals/editions/${e.target.value}${loc.search}` : `/countries${loc.search}`) : setGames(e.target.value)}>
          <option value="">All editions</option>{editions.map((e: any) => <option key={e.editionId} value={e.editionId}>{e.name}</option>)}
        </select>
        <select className="input" aria-label="Sport" value={sport} onChange={(e) => setSport(e.target.value)}><option value="">All sports</option>{(sportsQ.data?.sports ?? []).map((s: string) => <option key={s}>{s}</option>)}</select>
        <select className="input" aria-label="Gender" value={gender} onChange={(e) => setGender(e.target.value)}><option value="">All genders</option>{["Men", "Women", "Mixed", "Open"].map((g) => <option key={g}>{g}</option>)}</select>
        <select className="input" aria-label="Medal" value={medal} onChange={(e) => setMedal(e.target.value)}><option value="">All medals</option>{["Gold", "Silver", "Bronze"].map((g) => <option key={g}>{g}</option>)}</select>
        <label className="relative"><Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted" /><input className="input w-48 pl-8" placeholder="Search country or NOC…" value={text} onChange={(e) => setText(e.target.value, false)} aria-label="Search country" /></label>
        {(season || yf || yt || gq || noc || text || sport || gender || medal || routeGames) && <button type="button" className="btn" data-testid="clear-filters" onClick={() => nav("/countries")}>Clear filters</button>}
        <a className="btn ml-auto" href={csvUrl("/medals/countries", { ...params, page: undefined, page_size: 500 })} download><Download className="h-4 w-4" />Export CSV</a>
      </div>
      <Async q={q}>{(d) => (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-4">
            <BroadcastStatPanel label={routeGames || sport || gender || medal ? "NOCs with a medal" : "NOCs"} value={d.total} />
            <BroadcastStatPanel label="Gold" value={d.totals.gold} accent="#D4AF37" /><BroadcastStatPanel label="Silver" value={d.totals.silver} accent="#C0C7D1" /><BroadcastStatPanel label="Bronze" value={d.totals.bronze} accent="#CD7F32" />
          </div>
          {(() => { const t = text.trim().toLowerCase(); const shown = t ? d.rows.filter((r: any) => r.noc.toLowerCase().includes(t) || String(r.country).toLowerCase().includes(t)) : d.rows; return shown.length ? (
            <BroadcastMedalTable rows={shown} total={shown.length} page={d.page} pageSize={d.page_size} sort={sort} order={order} onSort={clickSort} linkFor={(n: string) => routeGames ? `/countries/${n}/editions/${routeGames}` : `/countries/${n}`} />) : <Empty message="No country matches these filters." />; })()}
          <Note><b>Counting convention.</b> {d.convention} NOCs that took part without a medal follow the medal winners, numbered by number of appearances. Appearances = editions entered within the filters.</Note>
        </>)}
      </Async>

    </div>
  );
}

// ------------------------------------------------------------------ /countries/:noc/editions/:gamesId

/** One NOC at one edition: every entry (medal or not) grouped sport → event → athlete, with the place or status Olympedia lists; filters in the URL; links to athletes and events. */
export function CountryEditionPage() {
  const { noc = "", gamesId = "" } = useParams();
  const nav = useNavigate();
  const loc = useLocation();
  const q = useApi<any>(`/countries/${noc}/editions/${gamesId}`);
  const list = useApi<any>(`/countries/${noc}/editions`);
  const [sport, setSport] = useParamState("sport");
  const [status, setStatus] = useParamState("status");
  const [gender, setGender] = useParamState("gender");
  const [text, setText] = useParamState("q");
  return (
    <Async q={q}>{(d) => {
      const words = text.toLowerCase().split(/\s+/).filter(Boolean);
      const keepEntry = (en: any) => !status || (status === "medal" ? !!en.medal : status === "no-medal" ? !en.medal : en.status === status);
      const sports = d.sports.filter((s: any) => !sport || s.sport === sport).map((s: any) => ({ ...s, events: s.events.filter((e: any) => !gender || e.gender === gender)
        .map((e: any) => ({ ...e, entries: e.entries.filter((en: any) => keepEntry(en) && words.every((w) => `${e.event} ${en.athlete}`.toLowerCase().includes(w))) })).filter((e: any) => e.entries.length) })).filter((s: any) => s.events.length);
      const statuses = [...new Set<string>(d.sports.flatMap((s: any) => s.events.flatMap((e: any) => e.entries.map((en: any) => en.status))))].sort();
      const flat = sports.flatMap((s: any) => s.events.flatMap((e: any) => e.entries.map((en: any) => [s.sport, e.event, en.athlete, en.position, en.status, en.medal ?? ""])));
      return (
        <div data-testid="country-edition">
          <Crumbs items={[{ label: "Countries", to: "/countries" }, { label: d.country, to: `/countries/${d.noc}` }, { label: d.edition.name }]} />
          <BroadcastPageHeader title={`${d.country} at ${d.edition.name}`} kicker={`${d.noc} · ${d.edition.official_edition_name ?? ""}`} icon={<BroadcastCountryFlag noc={d.noc} size={14} />}
            right={(list.data?.editions?.length ?? 0) > 1 ? <select className="input" aria-label="Edition" value={gamesId} onChange={(e) => nav(`/countries/${d.noc}/editions/${e.target.value}${loc.search}`)}>
              {list.data.editions.map((e: any) => <option key={e.games_id} value={e.games_id}>{e.edition.name}</option>)}</select> : undefined} />
          <div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <BroadcastStatPanel label="Entries" value={d.summary.entries} /><BroadcastStatPanel label="Athletes" value={d.summary.athletes} /><BroadcastStatPanel label="Events" value={d.summary.events} />
            <BroadcastStatPanel label="Gold" value={d.summary.gold} accent="#D4AF37" /><BroadcastStatPanel label="Silver" value={d.summary.silver} accent="#C0C7D1" /><BroadcastStatPanel label="Bronze" value={d.summary.bronze} accent="#CD7F32" />
          </div>
          <div className="card mb-4 flex flex-wrap items-center gap-2 p-3" data-testid="country-filters">
            <select className="input" aria-label="Sport" value={sport} onChange={(e) => setSport(e.target.value)}><option value="">All sports ({d.sports.length})</option>{d.sports.map((s: any) => <option key={s.sport}>{s.sport}</option>)}</select>
            <select className="input" aria-label="Result" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All results</option><option value="medal">Medal</option><option value="no-medal">No medal</option>{statuses.map((s) => <option key={s} value={s}>{s}</option>)}</select>
            <select className="input" aria-label="Gender" value={gender} onChange={(e) => setGender(e.target.value)}><option value="">All genders</option>{["Men", "Women", "Mixed", "Open"].map((g) => <option key={g}>{g}</option>)}</select>
            <label className="relative"><Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted" /><input className="input pl-8" placeholder="Athlete or event…" value={text} onChange={(e) => setText(e.target.value, false)} aria-label="Search athlete or event" /></label>
            <span className="ml-auto flex items-center gap-2 text-xs text-muted">{flat.length} entries<CsvButton name={`${d.noc}_${gamesId}`} headers={["sport", "event", "athlete", "position", "status", "medal"]} rows={flat} /></span>
          </div>
          {!sports.length && <Empty message="No entry matches these filters." />}
          <div className="space-y-5">
            {sports.map((s: any) => (
              <BroadcastCountryTable key={s.sport} sport={s.sport} events={s.events} gamesId={gamesId} />))}
          </div>
          <Note>{d.convention}</Note>
        </div>);
    }}</Async>
  );
}
