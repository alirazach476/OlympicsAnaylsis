import { useMemo } from "react";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, ExternalLink, Search, Snowflake, Sun } from "lucide-react";
import { useApi } from "../../lib/api";
import { Async, Empty, Note } from "../../components/ui";
import { BroadcastCountryFlag, BroadcastPageHeader, EditionLogo, MedalChip, SportPictogram } from "../../components/broadcast/design";
import { SavedTables, SavedTable } from "../../components/broadcast/SavedTables";
import { TableScope } from "../../components/tables/TableHead";
import { MatchBroadcastView } from "../../components/broadcast/MatchBoards";
import { BroadcastBoutBoard, tableKind } from "../../components/tables/OlympediaTables";
import { ResultLeaderboard } from "../../components/broadcast/SportScoreboards";
import { Crumbs, useParamState } from "../../components/navigation/Crumbs";
import { OlympicRings } from "../../components/OlympicRings";
import { SportGrid, SportEventList } from "../../components/editions/SportGrid";
import { EditionGallery, useEditionList } from "../../components/editions/EditionGallery";
import { ResultLegend } from "../../components/tables/ResultLegend";

const sportSlug = (s: string) => encodeURIComponent(s);

function editionCrumbs(ed: any) {
  return [{ label: "Olympic Games", to: `/olympics/${ed.season}` }, { label: ed.name, to: `/games/${ed.games_id}` }];
}

// ------------------------------------------------------------------ /olympics, /olympics/summer, /olympics/winter
/** Hub of every edition: each links to its event index. Future Games are listed but marked (no results yet). */
export function OlympicsHub() {
  const { season } = useParams();
  const { items } = useEditionList(season);
  const list = [...items].sort((a, b) => b.year - a.year || a.season.localeCompare(b.season));
  return (
    <div>
      <Crumbs items={season ? [{ label: "Games & Results", to: "/olympics" }, { label: season === "summer" ? "Summer" : "Winter" }] : [{ label: "Games & Results" }]} />
      <BroadcastPageHeader title="Games & Results" kicker={season ? `${season} Olympic Games` : "Summer and Winter Olympic Games"} icon={<OlympicRings size={36} />} />
      <div className="mb-4 flex gap-2" role="group" aria-label="Season">
        {[["", "All"], ["summer", "Summer"], ["winter", "Winter"]].map(([s, l]) => <Link key={l} to={s ? `/olympics/${s}` : "/olympics"} aria-current={(season ?? "") === s ? "page" : undefined} className={`btn ${((season ?? "") === s) ? "bg-accent/15 text-accent" : ""}`}>{s === "summer" ? <Sun className="h-4 w-4" /> : s === "winter" ? <Snowflake className="h-4 w-4" /> : null}{l}</Link>)}
      </div>
      <div data-testid="edition-list"><EditionGallery items={list} to={(i) => `/games/${i.id}/results`} /></div>
    </div>
  );
}

// ------------------------------------------------------------------ /games/:gamesId/results and /games/:gamesId/sports/:sport
/** Edition results index: every sport as an edition pictogram card; a sport opens its events. Search, gender and sort are kept in the URL; with a search every matching event is listed. */
export function EditionEventsPage() {
  const { gamesId = "", sport: sportParam } = useParams();
  const nav = useNavigate();
  const loc = useLocation();
  const [q, setQ] = useParamState("q");
  const [gender, setGender] = useParamState("gender");
  const [sort, setSort] = useParamState("sort", "sport");
  const res = useApi<any>(`/games/${gamesId}/events`);
  const sport = sportParam ? decodeURIComponent(sportParam) : "";
  const groups = useMemo(() => {
    const d = res.data;
    if (!d) return [];
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const keep = (e: any) => (!sport || e.sport === sport) && (!gender || e.gender === gender) && words.every((w) => `${e.title} ${e.sport}`.toLowerCase().includes(w));
    const order = (a: any, b: any) => sort === "date" ? String(a.date ?? "").localeCompare(String(b.date ?? "")) : sort === "participants" ? parseInt(b.participants ?? "0") - parseInt(a.participants ?? "0") : a.title.localeCompare(b.title);
    return d.sports.map((s: any) => ({ sport: s.sport, events: s.events.filter(keep).sort(order) })).filter((s: any) => s.events.length);
  }, [res.data, q, gender, sort, sport]);
  const n = groups.reduce((a: number, s: any) => a + s.events.length, 0);
  const filtered = !!(q || gender);
  return (
    <Async q={res}>{(d) => (
      <div data-testid="edition-events">
        <Crumbs items={[...editionCrumbs(d.edition), ...(sport ? [{ label: "Results", to: `/games/${gamesId}/results` }, { label: sport }] : [{ label: "Results" }])]} />
        <BroadcastPageHeader title={sport ? sport : d.edition.name} kicker={sport ? `${d.edition.name} · ${n} events` : `${d.edition.official_edition_name ?? ""} · ${d.all_sports.length} sports · ${d.total} events`}
          icon={sport ? <SportPictogram sport={sport} gamesId={gamesId} size={40} /> : <EditionLogo gamesId={gamesId} size={56} />} />
        <div className="card mb-4 flex flex-wrap items-center gap-3 p-3" data-testid="event-filters">
          <label className="relative"><Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted" /><input className="input pl-8" placeholder="Search events…" value={q} onChange={(e) => setQ(e.target.value, false)} aria-label="Search events" /></label>
          <select className="input" aria-label="Sport" value={sport} onChange={(e) => nav(e.target.value ? `/games/${gamesId}/sports/${sportSlug(e.target.value)}${loc.search}` : `/games/${gamesId}/results${loc.search}`)}>
            <option value="">All sports ({d.all_sports.length})</option>{d.all_sports.map((s: string) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="input" aria-label="Gender" value={gender} onChange={(e) => setGender(e.target.value)}><option value="">All genders</option>{d.genders.map((g: string) => <option key={g}>{g}</option>)}</select>
          <select className="input" aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}><option value="sport">Sort: name</option><option value="date">Sort: date</option><option value="participants">Sort: participants</option></select>
          {(filtered || sport) && <button type="button" className="btn" onClick={() => nav(`/games/${gamesId}/results`)} data-testid="clear-filters">Clear</button>}
          <span className="ml-auto text-xs text-muted" data-testid="event-count">{n} events</span>
        </div>
        {!sport && !filtered && <SportGrid sports={d.sports} gamesId={gamesId} href={(s) => `/games/${gamesId}/sports/${sportSlug(s)}`} />}
        {sport && (
          <nav aria-label="Sports at this edition" className="scroll-thin mb-4 flex gap-1.5 overflow-x-auto rounded-xl border border-line bg-surface p-2" data-testid="sport-strip">
            {d.sports.map((s: any) => { const on = s.sport === sport; return (
              <Link key={s.sport} to={`/games/${gamesId}/sports/${sportSlug(s.sport)}${loc.search}`} aria-current={on ? "page" : undefined} title={`${s.sport} · ${s.events.length} events`} data-testid="strip-sport" data-sport={s.sport}
                ref={on ? (el) => { const p = el?.parentElement; if (el && p) p.scrollLeft = el.offsetLeft - p.clientWidth / 2 + el.clientWidth / 2; } : undefined}
                className={`flex shrink-0 flex-col items-center gap-1 rounded-lg px-2 py-1.5 text-center transition ${on ? "bg-[var(--ed-tint)] ring-2 ring-[var(--ed-accent)]" : "opacity-70 hover:opacity-100"}`}>
                <SportPictogram sport={s.sport} gamesId={gamesId} size={36} /><span className="max-w-[5.5rem] truncate text-[10px] font-semibold">{s.sport}</span>
              </Link>); })}
          </nav>)}
        {(sport || filtered) && (<>
          {!groups.length && <Empty message="No event matches these filters." />}
          <div className="space-y-5">{groups.map((s: any) => <SportEventList key={s.sport} sport={s.sport} events={s.events} gamesId={gamesId} />)}</div>
        </>)}
      </div>)}
    </Async>
  );
}

// ------------------------------------------------------------------ shared bits
function MetaGrid({ meta }: { meta: Record<string, string> }) {
  const entries = Object.entries(meta).filter(([, v]) => v);
  if (!entries.length) return null;
  return <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]" data-testid="event-meta">{entries.map(([k, v]) => <div key={k} className="contents"><dt className="font-semibold text-muted">{k}</dt><dd>{v}</dd></div>)}</dl>;
}

/** Olympedia's written account of the event, paragraph by paragraph as published (nothing is added or summarised). */
function Description({ paras, source }: { paras: string[]; source: string }) {
  if (!paras?.length) return null;
  return (
    <section className="card mb-4 p-4 sm:p-5" data-testid="event-description" style={{ borderLeft: "3px solid var(--ed-accent)" }}>
      <h2 className="h-display mb-2 text-xl">About this event</h2>
      <div className="max-w-4xl space-y-3 text-sm leading-relaxed">{paras.map((p, i) => <p key={i}>{p}</p>)}</div>
      <p className="mt-3 text-[11px] text-muted">Text: <a className="underline hover:text-[var(--ed-accent)]" href={source} target="_blank" rel="noreferrer">Olympedia</a></p>
    </section>
  );
}

function PartsPicker({ parts, current }: { parts: any[]; current?: string }) {
  const nav = useNavigate();
  if (!parts?.length) return null;
  const groups = parts.reduce((m: Record<string, any[]>, p) => { const g = p.group && !String(p.group).startsWith("sub_select") ? p.group : "Parts"; (m[g] ??= []).push(p); return m; }, {});
  return (
    <div className="flex flex-wrap gap-3" data-testid="parts-picker">
      {(Object.entries(groups) as [string, any[]][]).map(([g, ps]) => (
        <label key={g} className="flex items-center gap-2 text-xs text-muted">{g}
          <select className="input" value={current ?? ""} aria-label={g} onChange={(e) => { const p = ps.find((x: any) => x.result_id === e.target.value); if (p?.route) nav(p.route); }}>
            <option value="">Choose… ({ps.length})</option>{ps.map((p: any) => <option key={p.result_id} value={p.result_id} disabled={!p.route}>{p.label}</option>)}
          </select>
        </label>))}
    </div>
  );
}

function PrevNext({ prev, next, middle }: { prev?: any; next?: any; middle?: string }) {
  return (
    <nav className="mt-6 grid grid-cols-2 items-center gap-3 sm:grid-cols-[1fr_auto_1fr]" aria-label="Previous and next" data-testid="prev-next">
      {prev ? <Link to={prev.route} className="btn min-w-0 max-w-full justify-self-start" rel="prev"><ArrowLeft className="h-4 w-4 shrink-0" /><span className="truncate">{prev.label ?? prev.title}</span></Link> : <span />}
      {middle ? <span className="hidden text-center text-xs text-muted sm:block">{middle}</span> : <span className="hidden sm:block" />}
      {next ? <Link to={next.route} className="btn min-w-0 max-w-full justify-self-end" rel="next"><span className="truncate">{next.label ?? next.title}</span><ArrowRight className="h-4 w-4 shrink-0" /></Link> : <span />}
    </nav>
  );
}

// ------------------------------------------------------------------ /games/:gamesId/events/:eventId
/** One event as on Olympedia: header facts, podium, then every table of the page. The Stage dropdown and tabs filter the tables (kept in ?stage=); Parts / Standings dropdowns open the sub-pages. */
export function EventResultsPage() {
  const { gamesId = "", eventId = "" } = useParams();
  const q = useApi<any>(`/events/${eventId}`);
  const loc = useLocation();
  const [stage, setStage] = useParamState("stage");
  return (
    <Async q={q}>{(d) => {
      if (d.kind !== "events") return <Note tone="warn">This id is a {d.kind} page. <Link className="underline" to={`/games/${d.games_id}/events/${d.event.result_id}`}>Open its event</Link>.</Note>;
      // a link with the wrong edition in it goes to the event's own address, so the edition theme always matches the data
      if (gamesId !== d.games_id) return <Navigate replace to={`/games/${d.games_id}/events/${d.result_id}${loc.search}`} />;
      const stages: any[] = d.stages;
      const shown: SavedTable[] = stage ? d.tables.filter((t: any) => stages.find((s) => s.label === stage)?.tables.includes(t.index)) : d.tables;
      return (
        <div data-testid="event-page" data-result-id={d.result_id}>
          <Crumbs items={[...editionCrumbs(d.edition), { label: d.sport ?? "Sport", to: `/games/${d.games_id}/sports/${sportSlug(d.sport ?? "")}` }, { label: d.title }]} />
          <BroadcastPageHeader title={d.title} kicker={`${d.sport ?? ""} · ${d.edition.name}`} icon={<SportPictogram sport={d.sport} gamesId={d.games_id} size={22} />}
            subtitle={<MetaGrid meta={d.meta} />}
            right={<a className="btn" href={d.source_url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />Olympedia</a>} />
          {d.medals.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-3" data-testid="event-podium">
              {d.medals.map((m: any, i: number) => <Link key={i} to={`/countries/${m.noc}/editions/${d.games_id}`} className="card flex items-center gap-2 px-3 py-2 hover:border-[var(--ed-accent)]"><MedalChip medal={m.medal} compact /><BroadcastCountryFlag noc={m.noc} size={16} showCode /></Link>)}
            </div>)}
          {!d.counts?.matches && !stage && (() => { const t = d.tables.find((x: any) => ["results", "ranking"].includes(tableKind(x))) ?? d.tables.find((x: any) => tableKind(x) === "heat");
            return t ? <div className="mb-5"><ResultLeaderboard t={t} sport={d.sport} gamesId={d.games_id} event={d.title} stage={t.section || "Final standings"} date={d.meta?.Date} /></div> : null; })()}
          <div className="card mb-4 flex flex-wrap items-center gap-3 p-3">
            {stages.length > 1 && (
              <label className="flex items-center gap-2 text-xs text-muted">Stage
                <select className="input" value={stage} onChange={(e) => setStage(e.target.value)} aria-label="Stage" data-testid="stage-select">
                  <option value="">All stages ({stages.length})</option>{stages.map((s) => <option key={s.label} value={s.label}>{s.label}</option>)}
                </select>
              </label>)}
            <PartsPicker parts={d.parts} />
            <span className="ml-auto text-xs text-muted">{d.tables.length} tables{d.counts?.matches ? ` · ${d.counts.matches} match pages` : ""}{d.counts?.heats ? ` · ${d.counts.heats} heat pages` : ""}</span>
          </div>
          {stages.length > 1 && (
            <div role="tablist" aria-label="Stages" className="mb-4 flex gap-1 overflow-x-auto pb-1 scroll-thin" data-testid="stage-tabs">
              {[{ label: "" }, ...stages].map((s) => <button key={s.label || "all"} role="tab" aria-selected={stage === s.label} onClick={() => setStage(s.label)} className={`shrink-0 rounded-md border px-3 py-1 text-xs ${stage === s.label ? "border-[var(--ed-accent)] bg-[var(--ed-tint)] font-semibold" : "border-line text-muted hover:text-ink"}`}>{s.label || "All"}</button>)}
            </div>)}
          <ResultLegend tables={shown} context={`${d.sport ?? ""} ${d.title}`} />
          {shown.length ? <TableScope gamesId={d.games_id} sport={d.sport}><SavedTables tables={shown} untitled="Final standings" sectionMeta={d.section_meta} kindHint={d.counts?.matches && !d.team_sport ? "bout" : "match"} /></TableScope> : <Empty message="No table for this stage." />}
          <PrevNext prev={d.siblings.prev} next={d.siblings.next} middle={d.sport ? `${d.sport} events` : undefined} />
        </div>);
    }}</Async>
  );
}

// ------------------------------------------------------------------ /games/:gamesId/events/:eventId/(matches|bouts|heats)/:subId
/** A match, bout or heat page: the team scoreboard when the sport has one, the duel header for bouts, then every saved table; previous / next follow the order of the event's table or dropdown. */
export function SubResultPage() {
  const { matchId, boutId, heatId } = useParams();
  const { gamesId = "", eventId = "" } = useParams();
  const id = matchId ?? boutId ?? heatId ?? "";
  const q = useApi<any>(`/subpages/${id}`);
  return (
    <Async q={q}>{(d) => {
      const seg = d.type ?? (matchId ? "matches" : boutId ? "bouts" : "heats");
      const want = `/games/${d.games_id}/events/${d.event.result_id}/${seg}/${d.result_id}`;
      if (gamesId !== d.games_id || eventId !== d.event.result_id || !location.pathname.endsWith(`/${seg}/${d.result_id}`)) return <Navigate replace to={want} />;
      const label = d.title.includes(" – ") ? d.title.split(" – ").slice(1).join(" – ") : d.title;
      const evRoute = `/games/${d.games_id}/events/${d.event.result_id}`;
      const parentIsPart = d.nav.parent && d.nav.parent.kind !== "events";
      const m = d.match;
      return (
        <div data-testid="subpage" data-type={d.type} data-result-id={d.result_id}>
          <Crumbs items={[...editionCrumbs(d.edition), { label: d.sport ?? "Sport", to: `/games/${d.games_id}/sports/${sportSlug(d.sport ?? "")}` }, { label: d.event.title, to: evRoute },
            ...(parentIsPart ? [{ label: d.nav.parent.title.split(" – ").slice(1).join(" – ") || d.nav.parent.title, to: d.nav.parent.route }] : []),
            ...(d.nav.section ? [{ label: d.nav.section, to: `${evRoute}?stage=${encodeURIComponent(d.nav.section)}` }] : []), { label }]} />
          <BroadcastPageHeader title={label} kicker={`${d.event.title} · ${d.edition.name}`} icon={<SportPictogram sport={d.sport} gamesId={d.games_id} size={22} />}
            subtitle={<MetaGrid meta={d.meta} />}
            right={<><Link className="btn" to={evRoute}><ArrowLeft className="h-4 w-4" />Event</Link><a className="btn" href={d.source_url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />Olympedia</a></>} />
          {d.has_scoreboard ? <div className="mb-5"><TableScope gamesId={d.games_id} sport={d.sport}><MatchBroadcastView resultId={d.result_id} /></TableScope></div>
            : d.type === "bouts" ? <BroadcastBoutBoard tables={d.tables} sport={d.sport} gamesId={d.games_id} event={d.event.title} label={[d.nav.section, label].filter(Boolean).join(" · ")} date={d.meta?.Date} />
            : (() => { const t = d.tables.find((x: any) => ["heat", "results", "ranking"].includes(tableKind(x))); return t ? <div className="mb-5"><ResultLeaderboard t={t} sport={d.sport} gamesId={d.games_id} event={d.event.title} stage={label} date={d.meta?.Date} limit={12} /></div> : null; })()}
          <div className="mb-4"><PartsPicker parts={d.parts} /></div>
          <ResultLegend tables={d.tables} context={`${d.sport ?? ""} ${d.event.title}`} />
          {d.tables.length ? <TableScope gamesId={d.games_id} sport={d.sport}><SavedTables tables={d.tables} untitled="Result" sectionMeta={d.section_meta} kindHint={d.type === "bouts" ? "bout" : "match"} /></TableScope> : <Empty message="This page has no table on Olympedia." />}
          <PrevNext prev={d.nav.prev} next={d.nav.next} middle={d.nav.index ? `${d.nav.index} of ${d.nav.count}` : undefined} />
        </div>);
    }}</Async>
  );
}
