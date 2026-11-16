import { useState } from "react";
import { useApi, csvUrl } from "../lib/api";
import { Async, ChartCard, Flag, Note, PageHeader, Select, SeasonToggle, Tabs } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries, Pareto, SankeyChart, Scatter2, TreemapChart } from "../charts/charts";
import { fmtNum, MEDAL_COLORS, PALETTE } from "../lib/fmt";

import { MedalFindings } from "../components/analytics/KeyFindings";
import { VizSection } from "../viz/VizGallery";
export default function MedalsPage() {
  const [season, setSeason] = useState("");
  const [tab, setTab] = useState("leaderboard");
  const [gid, setGid] = useState("2024_summer");
  const all = useApi<any>("/medals", { view: "alltime", season, limit: 300 });
  const ed = useApi<any>("/medals", { view: "edition", games_id: gid, limit: 300 }, tab === "edition");
  const games = useApi<any[]>("/games");
  const eda = useApi<any>("/eda/F_host", undefined, tab === "host");
  const sports = useApi<any[]>("/sports");
  const [sportId, setSportId] = useState("2");
  const bySport = useApi<any>("/medals", { view: "sport", sport_id: sportId, limit: 20 }, tab === "sport");
  const ctry = useApi<any>("/countries", { page_size: 300 }, tab === "flow");
  return (
    <div>
      <PageHeader title="Medal analytics" subtitle="Country totals count distinct Olympedia podium results (they reproduce the official totals). Ranks are tie-aware (identical gold-silver-bronze share a rank). Team medals count once per event." right={<SeasonToggle value={season} onChange={setSeason} />} />
      <MedalFindings />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "leaderboard", label: "All-time leaderboard" }, { id: "edition", label: "By edition" }, { id: "sport", label: "By sport" }, { id: "host", label: "Host effect" }, { id: "concentration", label: "Concentration" }, { id: "flow", label: "Flow (Sankey)" }]} />
      {tab === "leaderboard" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Historical leaderboard" height={520}>
            <Async q={all}>{(d) => <DataTable rows={d.rows} height={500} csvHref={csvUrl("/medals", { view: "alltime", season })} exportName="medal_leaderboard" columns={[
              { key: "rank", width: 56 }, { key: "noc_code", header: "NOC", width: 160, render: (r) => <span className="inline-flex items-center gap-2"><Flag noc={r.noc_code} size={13} />{r.historical_name ?? r.noc_code}</span> },
              { key: "gold", header: "G", align: "right", width: 56 }, { key: "silver", header: "S", align: "right", width: 56 }, { key: "bronze", header: "B", align: "right", width: 56 }, { key: "total", align: "right", width: 64 }, { key: "appearances", header: "Games", align: "right", width: 64 }]} />}</Async>
          </ChartCard>
          <ChartCard title="Medal progression, top 8 NOCs" height={520}>
            <Async q={all}>{(d) => {
              const m: Record<string, any> = {}; const top = [...new Set<string>(d.progression_top8.map((r: any) => r.noc_code))];
              d.progression_top8.forEach((r: any) => { const k = `${r.year}${r.season === "winter" ? "W" : "S"}`; m[k] = { ...(m[k] || { label: k, sort: r.year + (r.season === "winter" ? 0.5 : 0) }), [r.noc_code]: r.total }; });
              return <LineSeries height={480} data={Object.values(m).sort((a: any, b: any) => a.sort - b.sort) as any[]} x="label" series={top.map((n, i) => ({ key: n, color: PALETTE[i % PALETTE.length], dot: false }))} yLabel="Total medals" />;
            }}</Async>
          </ChartCard>
        </div>)}
      {tab === "edition" && (<>
        <div className="mb-3"><Select label="Edition" allLabel="–" value={gid} onChange={(v) => setGid(v || "2024_summer")} options={(games.data ?? []).map((g: any) => ({ value: g.games_id, label: `${g.year} ${g.season}` }))} /></div>
        <ChartCard title={`Medal table - ${gid}`} subtitle="Rank = by gold, then silver, then bronze (ties share a rank). " height={520}>
          <Async q={ed}>{(d) => <DataTable rows={d.rows} height={500} csvHref={csvUrl("/medals", { view: "edition", games_id: gid })} columns={[{ key: "rank", width: 56 }, { key: "noc_code", header: "NOC", width: 150, render: (r) => <span className="inline-flex items-center gap-2"><Flag noc={r.noc_code} size={13} />{r.country_name ?? r.noc_code}{r.is_host ? <span className="chip">host</span> : null}</span> }, { key: "gold", header: "G", align: "right", width: 50 }, { key: "silver", header: "S", align: "right", width: 50 }, { key: "bronze", header: "B", align: "right", width: 50 }, { key: "total", align: "right", width: 60 }, { key: "medal_share", header: "Share", align: "right", width: 70, render: (r) => `${fmtNum(100 * r.medal_share, 1)}%` }]} />}</Async>
        </ChartCard></>)}
      {tab === "sport" && (<>
        <div className="mb-3"><Select label="Sport" allLabel="–" value={sportId} onChange={(v) => setSportId(v || "2")} options={(sports.data ?? []).map((s: any) => ({ value: String(s.sport_id), label: s.sport_name }))} /></div>
        <ChartCard title="Medals in this sport, all editions"><Async q={bySport}>{(d) => <Bars horizontal stacked data={d.rows.map((r: any) => ({ name: r.noc_code, gold: r.gold, silver: r.silver, bronze: r.bronze }))} x="name" series={[{ key: "gold", color: MEDAL_COLORS.gold }, { key: "silver", color: MEDAL_COLORS.silver }, { key: "bronze", color: MEDAL_COLORS.bronze }]} />}</Async></ChartCard></>)}
      {tab === "host" && (
        <Async q={eda}>{({ data }) => (
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Host medals vs the NOC's own non-host mean" subtitle={`${data.hosts_that_beat_their_non_host_mean} of ${data.n_hosts} hosts exceeded their non-host mean`}>
              <Scatter2 data={data.rows.filter((r: any) => r.mean_non_host_medals != null)} x="mean_non_host_medals" y="host_medals" z="host_gold" name="games_id" colorKey="season" xLabel="Mean medals at other editions" yLabel="Medals when hosting" />
            </ChartCard>
            <ChartCard title="Uplift by host edition" subtitle="Medals as host minus previous edition of the same season"><Bars data={data.rows.map((r: any) => ({ name: `${r.host_noc} ${r.year}`, uplift: r.uplift_vs_prev }))} x="name" series={[{ key: "uplift", color: "#009F3D" }]} maxBars={40} /></ChartCard>
            <div className="xl:col-span-2"><Note>{data.note} Median uplift vs previous edition: {fmtNum(data.median_uplift_vs_prev, 1)} medals. See Statistical Analysis (H1) for the formal paired test.</Note></div>
          </div>)}</Async>)}
      {tab === "concentration" && (
        <Async q={all}>{(d) => d.concentration ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Pareto: medal concentration across NOCs" subtitle={`${d.concentration.noc_for_50pct} NOCs hold 50% of medals, ${d.concentration.noc_for_80pct} hold 80%; Gini ${fmtNum(d.concentration.gini, 3)}`}>
              <Pareto data={d.concentration.rows} label="noc_code" value="medals" cum="cum_share" />
            </ChartCard>
            <ChartCard title="Medal awards by NOC (treemap)"><TreemapChart data={d.concentration.rows.slice(0, 30).map((r: any) => ({ name: r.noc_code, size: r.medals }))} /></ChartCard>
          </div>) : null}</Async>)}
      {tab === "flow" && (
        <ChartCard title="Where the medals go" subtitle="Continent → medal colour (medal totals of all 35 Games)">
          <Async q={ctry}>{(c) => {
            const cont: Record<string, any> = {};
            c.rows.forEach((r: any) => { const k = r.continent || "Neutral / unified"; cont[k] = cont[k] || { gold: 0, silver: 0, bronze: 0 }; });
            const names = ["Africa", "Americas", "Asia", "Europe", "Oceania", "Neutral / unified", "Gold", "Silver", "Bronze"];
            const links: any[] = [];
            c.rows.forEach((r: any) => { const ci = names.indexOf(r.continent || "Neutral / unified"); if (ci < 0) return;
              [["Gold", r.gold], ["Silver", r.silver], ["Bronze", r.bronze]].forEach(([m, v]: any) => v > 0 && links.push({ source: ci, target: names.indexOf(m), value: v })); });
            const agg: Record<string, any> = {}; links.forEach((l) => { const k = `${l.source}-${l.target}`; agg[k] = { ...l, value: (agg[k]?.value || 0) + l.value }; });
            return <SankeyChart nodes={names.map((n) => ({ name: n }))} links={Object.values(agg)} />;
          }}</Async>
        </ChartCard>)}
      <VizSection page="medals" />
    </div>
  );
}
