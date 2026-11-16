import { useState } from "react";
import { useApi, csvUrl } from "../lib/api";
import { Async, ChartCard, Flag, Note, PageHeader, Select, Tabs } from "../components/ui";
import { SavedTables } from "../components/broadcast/SavedTables";
import { BroadcastSectionHeader, EditionBranding, MedalChip, SportPictogram } from "../components/broadcast/design";
import { IndividualResultCard } from "../components/broadcast/MatchBoards";
import { ResultsTable } from "../components/tables/BroadcastTables";
import { useEditionBrand } from "../themes/editionBrand";
import { DataTable } from "../components/DataTable";

function ResultsExplorer() {
  const [f, setF] = useState({ games_id: "", sport: "", event: "", athlete: "", noc: "", medal: "", position: "" });
  const [pageNo, setPageNo] = useState(1);
  const set = (k: string) => (v: string) => { setF((p) => ({ ...p, [k]: v })); setPageNo(1); };
  const games = useApi<any[]>("/games");
  const sports = useApi<any[]>("/sports");
  const [rounds, setRounds] = useState(false);
  const q = useApi<any>(rounds ? "/results/phases" : "/results", { ...f, medal: rounds ? undefined : f.medal, position: rounds ? undefined : f.position, page: pageNo, page_size: 100, ...(rounds ? {} : { sort: "year", order: "desc" }) });
  const last = q.data ? Math.max(1, Math.ceil(q.data.total / 100)) : 1;
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select label="Edition" value={f.games_id} onChange={set("games_id")} options={(games.data ?? []).map((g: any) => ({ value: g.games_id, label: `${g.year} ${g.season}` }))} />
        <Select label="Sport" value={f.sport} onChange={set("sport")} options={(sports.data ?? []).map((s: any) => ({ value: s.sport_name, label: s.sport_name }))} />
        <input className="input w-56" placeholder="Event contains…" value={f.event} onChange={(e) => set("event")(e.target.value)} aria-label="Event" />
        <input className="input w-48" placeholder="Athlete / team…" value={f.athlete} onChange={(e) => set("athlete")(e.target.value)} aria-label="Athlete" />
        <input className="input w-20 uppercase" placeholder="NOC" maxLength={3} value={f.noc} onChange={(e) => set("noc")(e.target.value.toUpperCase())} aria-label="NOC" />
        <Select label="Medal" value={f.medal} onChange={set("medal")} options={["Gold", "Silver", "Bronze"].map((m) => ({ value: m, label: m }))} />
        <input className="input w-24" placeholder="Position" value={f.position} onChange={(e) => set("position")(e.target.value)} aria-label="Position" />
        <label className="flex items-center gap-2 text-xs text-muted"><input type="checkbox" checked={rounds} onChange={(e) => { setRounds(e.target.checked); setPageNo(1); }} /> Earlier rounds (heats, semi-finals…)</label>
        <button className="btn" onClick={() => { setF({ games_id: "", sport: "", event: "", athlete: "", noc: "", medal: "", position: "" }); setPageNo(1); }}>Reset</button>
      </div>
      <ChartCard title="Results" subtitle="Click a column header to sort the loaded page" height={560}>
        <Async q={q} isEmpty={(d) => !d.rows.length}>{(d) => (
          <>
            <DataTable rows={d.rows} height={520} csvHref={csvUrl(rounds ? "/results/phases" : "/results", f)} exportName="results_page" columns={[
              { key: "year", width: 60 }, { key: "season", width: 70 }, { key: "sport_name", header: "Sport", width: 150 }, { key: "event_name", header: "Event", width: 260 },
              { key: rounds ? "phase" : "medal", header: rounds ? "Round" : "Medal", width: rounds ? 160 : 80 }, { key: "competitor", width: 220 }, { key: "noc", width: 70, render: (r) => <span className="inline-flex items-center gap-1"><Flag noc={r.noc} size={12} />{r.noc}</span> }, { key: "result_text", header: "Result", width: 110 }, { key: "position", header: "Pos", width: 56 }]} />
            <div className="mt-3 flex items-center gap-3 text-sm"><button className="btn" disabled={pageNo <= 1} onClick={() => setPageNo(pageNo - 1)}>Prev</button><span>Page {pageNo} / {last.toLocaleString()} · {d.total.toLocaleString()} results</span><button className="btn" disabled={pageNo >= last} onClick={() => setPageNo(pageNo + 1)}>Next</button></div>
          </>)}</Async>
      </ChartCard>
      <div className="mt-3"><Note>Coverage: all finishers of the final standings and the earlier rounds of every event for the 35 Games, as printed on the Olympedia result pages. Results keep the source's format (seconds, metres, points); events without a numeric result show the position only.</Note></div>
    </div>
  );
}


const posNum = (p: any) => { const n = parseInt(String(p ?? "").replace(/[^0-9]/g, ""), 10); return Number.isFinite(n) ? n : 9999; };

/** One edition (the app-wide selection), one sport, one event: podium cards, the official results table with verified record badges, every medal winner of the sport, and the event's rounds and heats exactly as saved. */
function EditionResults() {
  const brand = useEditionBrand();
  const gid = brand.gamesId;
  const [sport, setSport] = useState("Athletics");
  const [event, setEvent] = useState("");
  const [view, setView] = useState("final");
  const base = useApi<any>(`/games/${gid}`);
  const sportList: string[] = (base.data?.sports ?? []).map((x: any) => x.sport_name);
  const active = sportList.includes(sport) ? sport : sportList[0] ?? sport;
  const events = useApi<any[]>("/event-pages", { games_id: gid, sport: active });
  const eventNames = Array.from(new Set((events.data ?? []).map((e) => e.event_name)));
  const ev = eventNames.includes(event) ? event : eventNames.find((n) => /100 metres, men/i.test(n)) ?? eventNames[0] ?? "";
  const evPage = (events.data ?? []).find((e) => e.event_name === ev);
  const results = useApi<any>(ev ? "/results" : null, { games_id: gid, sport: active, event: ev, page_size: 300, sort: "event_name", order: "asc" });
  const records = useApi<any[]>("/records/for-games", { games_id: gid });
  const gold = useApi<any>(view === "medals" ? "/results" : null, { games_id: gid, sport: active, medal: "Gold", page_size: 500 });
  const silver = useApi<any>(view === "medals" ? "/results" : null, { games_id: gid, sport: active, medal: "Silver", page_size: 500 });
  const bronze = useApi<any>(view === "medals" ? "/results" : null, { games_id: gid, sport: active, medal: "Bronze", page_size: 500 });
  const page = useApi<any>(view === "pages" && evPage ? `/pages/${evPage.result_id}` : null);
  const rows = ((results.data?.rows ?? []) as any[]).filter((r) => r.event_name === ev).sort((a, b) => posNum(a.position) - posNum(b.position));
  const recs = records.data ?? [];
  const recordLevel = (r: any) => recs.find((x) => x.event.toLowerCase() === String(r.event_name).toLowerCase() && x.athlete.toLowerCase().includes(String(r.competitor).toLowerCase()) && String(x.value).trim() === String(r.result_text ?? "").trim())?.level;
  const medalRows = ["gold", "silver", "bronze"].flatMap((m, i) => ((([gold, silver, bronze][i].data?.rows ?? []) as any[]).map((r) => ({ ...r, medal: r.medal ?? m[0].toUpperCase() + m.slice(1) }))));
  const byEvent: Record<string, any[]> = {};
  medalRows.forEach((r) => { (byEvent[r.event_name] ||= []).push(r); });
  const order = { Gold: 0, Silver: 1, Bronze: 2 } as Record<string, number>;
  return (
    <div data-testid="edition-results" data-edition={gid}>
      <p className="mb-3 text-xs text-muted">The edition is the app-wide selection: change it in the sidebar and every graphic follows.</p>
      <div className="mb-3 flex flex-wrap gap-1.5" role="tablist" aria-label="Sport" data-testid="sport-pills">
        {sportList.map((x) => <button key={x} role="tab" aria-label={x} aria-selected={active === x} onClick={() => { setSport(x); setEvent(""); }} className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-xs transition ${active === x ? "border-[var(--ed-accent)] bg-[var(--ed-tint)] font-semibold" : "border-line text-muted hover:text-ink"}`}><SportPictogram sport={x} size={22} />{x}</button>)}
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-muted">Event<select className="input min-w-[16rem]" value={ev} onChange={(e) => setEvent(e.target.value)} aria-label="Event">{eventNames.map((n) => <option key={n}>{n}</option>)}</select></label>
        <Tabs value={view} onChange={setView} tabs={[{ id: "final", label: "Final results" }, { id: "medals", label: "Medal winners" }, { id: "pages", label: "Rounds & heats" }]} />
      </div>
      {view === "final" && (
        <Async q={results} isEmpty={() => !rows.length}>{() => (
          <>
            <BroadcastSectionHeader kicker={`${gid.replace("_", " ")} · ${active}`} title={ev} />
            <div className="mb-4 grid gap-3 md:grid-cols-3" data-testid="podium">{rows.filter((r) => r.medal).slice(0, 3).map((r) => <IndividualResultCard key={r.competitor + r.position} r={{ ...r, record_level: recordLevel(r) }} big />)}</div>
            <ResultsTable rows={rows} records={recs} gamesId={gid} title={ev} subtitle={`${rows.length} competitors`} exportName={`${gid}_${ev}`} height={560} />
          </>)}</Async>)}
      {view === "medals" && (
        <div className="grid gap-3 md:grid-cols-2" data-testid="medal-winners">{Object.entries(byEvent).sort(([a], [b]) => a.localeCompare(b)).map(([name, rs]) => (
          <section key={name} className="card overflow-hidden"><div className="flex items-center gap-2 border-b border-line bg-surface2/70 px-3 py-2"><SportPictogram sport={active} size={24} /><b className="truncate font-display text-lg">{name}</b></div>
            <ul>{rs.sort((a, b) => order[a.medal] - order[b.medal]).map((r, i) => <li key={i} className="flex items-center gap-3 border-b border-line/60 px-3 py-2 text-sm last:border-0"><MedalChip medal={r.medal} /><span className="min-w-0 flex-1 truncate font-medium">{r.competitor}</span><span className="inline-flex items-center gap-1.5 text-xs text-muted"><Flag noc={r.noc} size={12} />{r.noc}</span><b className="font-display tabular-nums">{r.result_text ?? ""}</b></li>)}</ul></section>))}
          {!medalRows.length && <Async q={gold}>{() => null}</Async>}
        </div>)}
      {view === "pages" && <Async q={page}>{(d) => (<><BroadcastSectionHeader kicker="As saved from Olympedia" title={d.title} /><SavedTables tables={d.tables} /></>)}</Async>}
    </div>
  );
}

export default function ResultsPage() {
  const [tab, setTab] = useState("edition");
  return (
    <div>
      <PageHeader title="Event results explorer" subtitle="Official results of every event: the final standings, every medal winner and every round and heat as saved from the Olympedia result pages, with the original result strings. Record badges appear only for records the record book lists for that athlete, event and value." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "edition", label: "Edition results" }, { id: "search", label: "Search all results" }]} />
      {tab === "edition" ? <EditionResults /> : <ResultsExplorer />}
    </div>
  );
}
