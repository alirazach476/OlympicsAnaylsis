import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useApi, csvUrl } from "../lib/api";
import { Async, ChartCard, Flag, Kpi, Note, PageHeader, Select } from "../components/ui";
import { AthleteRankingTable } from "../components/tables/BroadcastTables";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries, Scatter2 } from "../charts/charts";
import { gamesLabel, MEDAL_COLORS, PALETTE } from "../lib/fmt";

import { EditionStrip, ProfileHero } from "../components/profile/ProfileHero";
import { VizSection } from "../viz/VizGallery";
export function AthletesPage() {
  const nav = useNavigate();
  const [f, setF] = useState({ q: "", noc: "", sport: "", gender: "", games_id: "", medal: "" });
  const [picked, setPicked] = useState<number[]>([]);
  const set = (k: string) => (v: string) => setF((p) => ({ ...p, [k]: v }));
  const q = useApi<any>("/athletes", { ...f, page_size: 200, sort: "medals" });
  const sports = useApi<any[]>("/sports");
  const games = useApi<any[]>("/games");
  const cmp = useApi<any[]>("/athletes/compare", { ids: picked.join(",") }, picked.length >= 2);
  const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 4 ? [...p, id] : p));
  return (
    <div>
      <PageHeader title="Athlete explorer" subtitle="Search 125k Olympic athletes. Bio fields (birth, death) are present only where a source states them; no photographs have been collected." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input className="input w-60" placeholder="Search athlete name…" value={f.q} onChange={(e) => set("q")(e.target.value)} aria-label="Search athletes" />
        <input className="input w-24 uppercase" placeholder="NOC" maxLength={3} value={f.noc} onChange={(e) => set("noc")(e.target.value.toUpperCase())} aria-label="Country NOC" />
        <Select label="Sport" value={f.sport} onChange={set("sport")} options={(sports.data ?? []).map((s: any) => ({ value: s.sport_name, label: s.sport_name }))} />
        <Select label="Gender" value={f.gender} onChange={set("gender")} options={[{ value: "M", label: "Men" }, { value: "F", label: "Women" }]} />
        <Select label="Edition" value={f.games_id} onChange={set("games_id")} options={(games.data ?? []).map((g: any) => ({ value: g.games_id, label: `${g.year} ${g.season}` }))} />
        <Select label="Medal" value={f.medal} onChange={set("medal")} allLabel="Any" options={[{ value: "any", label: "Has medal" }, { value: "gold", label: "Gold" }, { value: "silver", label: "Silver" }, { value: "bronze", label: "Bronze" }]} />
      </div>
      <ChartCard title="Athletes" subtitle="Sorted by career medals. Tick up to 4 to compare." height={520}>
        <Async q={q} isEmpty={(d) => !d.rows.length}>{(d) => (
          <>
            <div className="mb-2 text-xs text-muted">{d.total.toLocaleString()} matching athletes (showing the first {d.rows.length})</div>
            <AthleteRankingTable rows={d.rows} height={460} title="Athletes" subtitle="click an athlete for the full profile" csvHref={csvUrl("/athletes", { ...f })} onRowClick={(r) => nav(`/athletes/${r.athlete_id}`)} />
          </>)}</Async>
      </ChartCard>
      {picked.length >= 2 && (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <Async q={cmp}>{(d) => (<>
            <ChartCard title="Career comparison"><Bars data={d.map((a: any) => ({ name: a.career.full_name.split(" ")[0], Gold: a.career.gold, Silver: a.career.silver, Bronze: a.career.bronze }))} x="name" stacked series={[{ key: "Gold", color: MEDAL_COLORS.gold }, { key: "Silver", color: MEDAL_COLORS.silver }, { key: "Bronze", color: MEDAL_COLORS.bronze }]} /></ChartCard>
            <ChartCard title="Age at each Games" subtitle="Career timelines"><Scatter2 data={d.flatMap((a: any) => a.timeline.map((t: any) => ({ year: t.year, age: t.age, who: a.career.full_name })))} x="year" y="age" colorKey="who" xLabel="Games year" yLabel="Age" /></ChartCard>
          </>)}</Async>
        </div>)}
      <VizSection page="athletes" athletes />
    </div>
  );
}

export function AthletePage() {
  const { id = "" } = useParams();
  const q = useApi<any>(`/athletes/${id}`);
  return (
    <Async q={q}>
      {(d) => {
        const a = d.athlete;
        const byYear: Record<string, any> = {};
        d.participations.forEach((p: any) => { byYear[p.games_id] = { ...(byYear[p.games_id] || { label: gamesLabel(p.games_id), year: p.year, age: p.age, events: 0, medals: 0 }), events: (byYear[p.games_id]?.events || 0) + 1, medals: (byYear[p.games_id]?.medals || 0) + (p.medal ? 1 : 0) }; });
        const timeline = Object.values(byYear).sort((x: any, y: any) => x.year - y.year);
        return (
          <div>
            <ProfileHero back={{ to: "/athletes", label: "athletes" }} kicker={String(a.sports ?? "").split(",").filter(Boolean).slice(0, 3).join(" · ")} title={a.full_name} flagNoc={String(a.nocs ?? "").split(",")[0]} medals={{ gold: a.gold, silver: a.silver, bronze: a.bronze }}
              facts={<>{String(a.nocs ?? "").split(",").filter(Boolean).map((n: string) => <span key={n} className="inline-flex items-center gap-1"><Flag noc={n} size={14} />{n}</span>)}<span>{a.first_year ? `${a.first_year}${a.last_year && a.last_year !== a.first_year ? " – " + a.last_year : ""}` : ""}</span><span>{a.date_of_birth ? `Born ${a.date_of_birth}` : ""}{a.date_of_death ? ` · Died ${a.date_of_death}` : ""}</span></>} />
            <EditionStrip items={Object.entries(byYear).map(([gid, t]: any) => ({ gamesId: gid, line1: `${t.events} event${t.events > 1 ? "s" : ""}`, line2: t.age ? `age ${t.age}` : "", medals: t.medals })).sort((x, y) => x.gamesId.localeCompare(y.gamesId))} />
            <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-5">
              <Kpi label="Olympic Games" value={a.games_count} /><Kpi label="Gold" value={a.gold} accent={MEDAL_COLORS.gold} /><Kpi label="Silver" value={a.silver} accent={MEDAL_COLORS.silver} /><Kpi label="Bronze" value={a.bronze} accent={MEDAL_COLORS.bronze} /><Kpi label="Career" value={a.first_year ? `${a.first_year}–${a.last_year}` : "–"} />
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              <ChartCard title="Career timeline" subtitle="Events entered and medals won per Games"><Bars data={timeline as any[]} x="label" series={[{ key: "events", color: "#0085C7" }, { key: "medals", color: MEDAL_COLORS.gold }]} /></ChartCard>
              <ChartCard title="Age progression"><LineSeries data={timeline as any[]} x="label" series={[{ key: "age", color: "#009F3D", dot: true }]} yLabel="Age" /></ChartCard>
            </div>
            <ChartCard title="Event history" height={300}><DataTable rows={d.participations} height={360} exportName={`athlete_${id}`} columns={[{ key: "games_id", header: "Games", width: 110 }, { key: "sport_name", header: "Sport", width: 160 }, { key: "event_name", header: "Event", width: 300 }, { key: "noc_code", header: "NOC", width: 70 }, { key: "age", width: 60 }, { key: "medal", width: 80 }]} /></ChartCard>
            <ChartCard title="Every recorded finish" subtitle="Heats, semi-finals and finals from the Olympedia per-athlete results (position codes as printed, e.g. '7 h6 r1/4' = 7th in heat 6, round 1 of 4)" height={200}>
              <DataTable rows={d.performances ?? []} height={320} exportName={`athlete_${id}_finishes`} empty="No per-athlete Olympedia results are linked to this athlete (the athlete could not be matched to an Olympedia profile)." columns={[{ key: "games_id", header: "Games", width: 110 }, { key: "sport", width: 160 }, { key: "event", width: 280 }, { key: "position", header: "Position", width: 140 }, { key: "medal", width: 80 }, { key: "team", width: 140 }]} />
            </ChartCard>
          </div>);
      }}
    </Async>
  );
}
