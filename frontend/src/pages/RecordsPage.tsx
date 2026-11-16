import { Link } from "react-router-dom";
import { useMemo, useState } from "react";
import { useApi } from "../lib/api";
import { Async, ChartCard, Flag, Note, PageHeader, Select, Tabs } from "../components/ui";
import { RecordsTable } from "../components/tables/BroadcastTables";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries } from "../charts/charts";
import { fmtNum, MEDAL_COLORS } from "../lib/fmt";

import { RecordFindings } from "../components/analytics/KeyFindings";
import { VizSection } from "../viz/VizGallery";
export default function RecordsPage() {
  const [tab, setTab] = useState("records");
  const [level, setLevel] = useState("");
  const q = useApi<any>("/records", { level: level || undefined, page_size: 500 });
  const prog = useApi<any>("/sports-analytics/records_progression");
  const [ev, setEv] = useState("");
  return (
    <div>
      <PageHeader title="Records & achievements" subtitle="Olympic and world records as listed by Olympedia (archery, athletics, canoe sprint, modern pentathlon, rowing, short-track, ski jumping, speed skating) plus career achievements from the athlete marts." />
      <RecordFindings />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "records", label: "Record book" }, { id: "progression", label: "Record progression" }, { id: "legends", label: "Most decorated & careers" }]} />
      {tab === "records" && (<>
        <div className="mb-3"><Select label="Level" value={level} onChange={setLevel} options={[{ value: "world", label: "World records (WR)" }, { value: "olympic", label: "Olympic records" }]} /></div>
        <ChartCard title="Record book" subtitle="Rows are record progressions: each entry was the best mark at the time" height={520}>
          <Async q={q} isEmpty={(d) => !d.records.rows.length}>{(d) => <RecordsTable height={500} rows={d.records.rows} title="Record book" subtitle="Olympic and world records as listed by Olympedia" exportName="records" />}</Async>
        </ChartCard></>)}
      {tab === "progression" && (
        <Async q={prog}>{({ data }) => {
          const names = Object.keys(data.events);
          const cur = ev && data.events[ev] ? ev : names[0];
          const e = data.events[cur];
          return (
            <div className="grid gap-4 xl:grid-cols-2">
              <ChartCard title="Record progression" subtitle={cur} right={<select aria-label="Event" className="input max-w-[260px]" value={cur} onChange={(x) => setEv(x.target.value)}>{names.map((n) => <option key={n}>{n}</option>)}</select>}>
                {e && <LineSeries data={e.years.map((y: number, i: number) => ({ year: y, mark: e.values[i], flag: e.record_types[i], noc: e.noc[i] }))} x="year" xLabel="Games year" series={[{ key: "mark", color: "#DF0024", dot: true }]} />}
              </ChartCard>
              <ChartCard title="Marks" height={300}>{e && <DataTable rows={e.years.map((y: number, i: number) => ({ year: y, mark: e.values[i], flag: e.record_types[i], noc: e.noc[i] }))} columns={[{ key: "year" }, { key: "mark" }, { key: "flag" }, { key: "noc" }]} height={300} />}</ChartCard>
              <div className="xl:col-span-2"><Note>{data.note}</Note></div>
            </div>);
        }}</Async>)}
      {tab === "legends" && (
        <Async q={q}>{(d) => (
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Most decorated athletes"><Bars horizontal stacked data={d.most_decorated.map((a: any) => ({ name: a.full_name.split(" ").slice(-1)[0], gold: a.gold, silver: a.silver, bronze: a.bronze }))} x="name" series={[{ key: "gold", color: MEDAL_COLORS.gold }, { key: "silver", color: MEDAL_COLORS.silver }, { key: "bronze", color: MEDAL_COLORS.bronze }]} /></ChartCard>
            <ChartCard title="Most successful countries (by gold)"><Bars horizontal stacked data={d.most_successful_countries.map((c: any) => ({ name: c.noc_code, gold: c.gold, silver: c.silver, bronze: c.bronze }))} x="name" series={[{ key: "gold", color: MEDAL_COLORS.gold }, { key: "silver", color: MEDAL_COLORS.silver }, { key: "bronze", color: MEDAL_COLORS.bronze }]} /></ChartCard>
            <ChartCard title="Longest Olympic careers (years between first and last Games)"><DataTable height={340} rows={d.longest_careers} columns={[{ key: "full_name", header: "Athlete", width: 220, render: (r: any) => (r.athlete_id ? <Link className="font-semibold hover:text-[var(--ed-accent)] hover:underline" to={`/athletes/${r.athlete_id}`}>{r.full_name}</Link> : r.full_name) }, { key: "career_span_years", header: "Years", align: "right" }, { key: "first_year", header: "From" }, { key: "last_year", header: "To" }]} /></ChartCard>
            <ChartCard title="Most Games attended"><DataTable height={340} rows={d.most_appearances} columns={[{ key: "full_name", header: "Athlete", width: 240, render: (r: any) => (r.athlete_id ? <Link className="font-semibold hover:text-[var(--ed-accent)] hover:underline" to={`/athletes/${r.athlete_id}`}>{r.full_name}</Link> : r.full_name) }, { key: "games_count", header: "Games", align: "right" }]} /></ChartCard>
            <div className="xl:col-span-2"><Note>Consecutive-appearance streaks, youngest/oldest participants and milestone lists are derivable from the athlete marts but are not yet exposed as dedicated charts.</Note></div>
          </div>)}</Async>)}
      <VizSection page="records" />
    </div>
  );
}
