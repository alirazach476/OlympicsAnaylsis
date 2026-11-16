import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { getJSON, useApi } from "../lib/api";
import { Async, ChartCard, Flag, Note, PageHeader } from "../components/ui";
import { DataTable } from "../components/DataTable";
import { Bars, LineSeries, RadarCompare } from "../charts/charts";
import { fmtInt, PALETTE } from "../lib/fmt";
import { MedalStrip } from "../components/profile/ProfileHero";
import { FilterBar } from "../components/analytics/FilterBar";
import { useCrossFilter } from "../lib/crossFilter";
import { flagUrl } from "../lib/fmt";

const DEFAULT = ["USA", "CHN", "GBR"];
const MAX = 4;

export function CompareTabs({ active }: { active: "editions" | "countries" }) {
  return (
    <div role="tablist" className="mb-4 flex gap-1 border-b border-line" aria-label="Comparison type">
      {[["editions", "/compare", "Editions"], ["countries", "/compare/countries", "Countries"]].map(([id, to, label]) => (
        <Link key={id} to={to} role="tab" aria-selected={active === id} className={`px-4 py-2 text-sm font-medium ${active === id ? "border-b-2 border-accent text-accent" : "text-muted hover:text-ink"}`}>{label}</Link>))}
    </div>
  );
}

/** Up to four countries side by side: totals, medal progression, sports, profile radar. Click a country (card or legend) or a sport (bar) to highlight it everywhere; the selection is in the URL. */
export default function CompareCountriesPage() {
  const [params, setParams] = useSearchParams();
  const nocs = useMemo(() => (params.get("nocs") ? params.get("nocs")!.split(",").filter(Boolean).slice(0, MAX) : DEFAULT), [params]);
  const xf = useCrossFilter(["focus", "sport"]);
  const focus = xf.values.focus, sport = xf.values.sport;
  const [season, setSeason] = useState("summer");
  const list = useApi<any>("/countries", { page_size: 300, sort: "total_medals" });
  const setNocs = (next: string[]) => setParams((p) => { const n = new URLSearchParams(p); n.set("nocs", next.join(",")); return n; }, { replace: true });
  const details = useQueries({ queries: nocs.map((n) => ({ queryKey: [`/countries/${n}`, {}], queryFn: () => getJSON<any>(`/countries/${n}`), staleTime: 5 * 60_000 })) });
  const compare = useApi<any>(nocs.length >= 2 ? "/countries/compare" : null, { nocs: nocs.join(",") });
  const ready = details.every((d) => d.data);
  const color = (i: number) => PALETTE[i % PALETTE.length];
  const name = (n: string) => list.data?.rows?.find((r: any) => r.noc_code === n)?.historical_name ?? n;

  const metrics = useMemo(() => {
    if (!ready) return [];
    const P = details.map((d) => d.data.profile);
    const row = (label: string, f: (p: any) => any) => ({ metric: label, ...Object.fromEntries(nocs.map((n, i) => [n, f(P[i]) ?? "–"])) });
    return [row("Gold", (p) => p.gold), row("Silver", (p) => p.silver), row("Bronze", (p) => p.bronze), row("Total medals", (p) => p.total_medals), row("Appearances", (p) => p.appearances),
      row("Summer appearances", (p) => p.summer_appearances), row("Winter appearances", (p) => p.winter_appearances), row("Athletes (all Games)", (p) => p.athletes), row("First year", (p) => p.first_year), row("Last year", (p) => p.last_year)];
  }, [ready, details, nocs]);

  const sportsData = useMemo(() => {
    if (!ready) return [];
    const by: Record<string, any> = {};
    details.forEach((d, i) => d.data.medals_by_sport.forEach((s: any) => { by[s.sport_name] = { ...(by[s.sport_name] || { sport: s.sport_name, _t: 0 }), [nocs[i]]: s.total, _t: (by[s.sport_name]?._t || 0) + s.total }; }));
    return Object.values(by).sort((a: any, b: any) => b._t - a._t).slice(0, 12);
  }, [ready, details, nocs]);

  return (
    <div>
      <PageHeader title="Compare countries" subtitle="Up to four countries side by side from the official medal tables and the participation records. Click a card or a legend entry to highlight a country, a bar to highlight a sport." />
      <CompareTabs active="countries" />
      <div className="mb-4 flex flex-wrap items-center gap-2" data-testid="country-picker">
        {nocs.map((n, i) => <span key={n} className="chip" style={{ borderColor: color(i) }}><Flag noc={n} size={12} />{name(n)}<button aria-label={`Remove ${name(n)}`} className="ml-1 hover:text-accent" onClick={() => setNocs(nocs.filter((x) => x !== n))} disabled={nocs.length <= 2}><X className="h-3 w-3" /></button></span>)}
        {nocs.length < MAX && (
          <label className="inline-flex items-center gap-1 text-xs text-muted"><Plus className="h-3.5 w-3.5" />
            <select className="input" aria-label="Add a country" value="" onChange={(e) => e.target.value && setNocs([...nocs, e.target.value])}>
              <option value="">Add a country…</option>{(list.data?.rows ?? []).filter((r: any) => !nocs.includes(r.noc_code)).map((r: any) => <option key={r.noc_code} value={r.noc_code}>{r.historical_name} ({r.noc_code})</option>)}
            </select></label>)}
      </div>
      <FilterBar onClear={xf.clear} onRemove={(k) => xf.set(k, "", false)} hint="Click a country card or legend entry, or a sport bar, to highlight it in every chart."
        filters={[...(focus ? [{ key: "focus", label: "Country", value: focus }] : []), ...(sport ? [{ key: "sport", label: "Sport", value: sport }] : [])]} />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="country-cards">
        {details.map((d, i) => {
          const n = nocs[i]; const p = d.data?.profile;
          return (
            <button key={n} onClick={() => xf.set("focus", n)} aria-pressed={focus === n} className={`relative overflow-hidden rounded-2xl border bg-surface p-4 text-left transition hover:-translate-y-0.5 ${focus === n ? "border-accent" : "border-line"} ${focus && focus !== n ? "opacity-60" : ""}`} style={{ borderTop: `4px solid ${color(i)}` }}>
              <img src={flagUrl(n)} alt="" aria-hidden className="absolute -right-6 top-0 h-full w-2/3 object-cover opacity-20 [mask-image:linear-gradient(to_left,black,transparent)]" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
              <div className="relative"><div className="flex items-center gap-2"><Flag noc={n} size={20} /><span className="text-xs uppercase tracking-widest text-muted">{n}</span></div>
                <div className="mt-1 h-display text-3xl leading-none">{p?.historical_name ?? name(n)}</div>
                <div className="mt-3">{p ? <MedalStrip gold={p.gold} silver={p.silver} bronze={p.bronze} /> : <span className="text-xs text-muted">loading…</span>}</div>
                {p && <div className="mt-2 text-xs text-muted">{fmtInt(p.total_medals)} medals · {p.appearances} appearances · since {p.first_year}</div>}</div>
            </button>);
        })}
      </div>

      {!ready ? <Async q={{ data: undefined, isLoading: true, error: details.find((d) => d.error)?.error }}>{() => null}</Async> : (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Side by side" subtitle="The highest value in each row is marked; export the table as CSV" height={380}>
            <DataTable rows={metrics} exportName="compare_countries" height={380} columns={[{ key: "metric", header: "Metric", width: 170 }, ...nocs.map((n) => ({ key: n, header: n, align: "right" as const }))]} selectedKey={() => false} />
            <p className="mt-2 text-xs text-muted">Medals are the official medal-table totals; appearances count Games with at least one competitor.</p>
          </ChartCard>
          <ChartCard title={`Medal progression, ${season} Games`} subtitle="Total medals per edition (Summer and Winter are separate: their programmes differ). Click a legend entry to highlight a country."
            right={<select className="input" value={season} onChange={(e) => setSeason(e.target.value)} aria-label="Season"><option value="summer">Summer</option><option value="winter">Winter</option></select>} height={380}>
            <Async q={compare}>{(c) => {
              const years: Record<string, any> = {};
              Object.entries(c).forEach(([n, rows]: any) => rows.filter((r: any) => r.season === season).forEach((r: any) => { years[r.games_id] = { ...(years[r.games_id] || { label: String(r.year), year: r.year }), [n]: r.total }; }));
              return <LineSeries onSelect={(n) => xf.set("focus", n)} selected={focus} data={Object.values(years).sort((a: any, b: any) => a.year - b.year) as any[]} x="label" xLabel="Games year" yLabel="Medals" series={nocs.map((n, i) => ({ key: n, color: color(i), dot: true }))} />;
            }}</Async>
          </ChartCard>
          <ChartCard title="Medals by sport" subtitle="Top 12 sports across the selected countries (team medals counted once). Click a bar to highlight a sport." height={420}>
            <Bars horizontal data={sportsData} x="sport" onSelect={(s) => xf.set("sport", s)} selected={sport} series={nocs.map((n, i) => ({ key: n, color: color(i) }))} />
          </ChartCard>
          <ChartCard title="Profile radar" subtitle="Each axis scaled 0–100 to the maximum among the selected countries" height={420}>
            {(() => {
              const P = details.map((d) => ({ ...d.data.profile, summer_total: (d.data.summer_vs_winter.find((x: any) => x.season === "summer") ?? {}).total ?? 0, winter_total: (d.data.summer_vs_winter.find((x: any) => x.season === "winter") ?? {}).total ?? 0 }));
              const axes: [string, (p: any) => number][] = [["Total medals", (p) => p.total_medals], ["Gold medals", (p) => p.gold], ["Appearances", (p) => p.appearances], ["Athletes", (p) => p.athletes], ["Gold ratio", (p) => (p.total_medals ? p.gold / p.total_medals : 0)], ["Summer medals", (p) => p.summer_total], ["Winter medals", (p) => p.winter_total]];
              const mx = axes.map(([, f]) => Math.max(...P.map((p) => Number(f(p)) || 0), 1e-9));
              return <RadarCompare data={axes.map(([label, f], k) => ({ axis: label, ...Object.fromEntries(nocs.map((n, i) => [n, (100 * (Number(f(P[i])) || 0)) / mx[k]])) }))} series={nocs.map((n, i) => ({ key: n, color: color(i) }))} />;
            })()}
          </ChartCard>
          <ChartCard title="Summer vs Winter" subtitle="Medals by season" height={300}>
            <Bars data={["summer", "winter"].map((s) => ({ season: s, ...Object.fromEntries(nocs.map((n, i) => [n, (details[i].data.summer_vs_winter.find((x: any) => x.season === s) ?? {}).total ?? 0])) }))} x="season" series={nocs.map((n, i) => ({ key: n, color: color(i) }))} />
          </ChartCard>
          <div className="xl:col-span-2"><Note>Figures follow each country's own NOC code: the Soviet Union, East and West Germany and the Unified Team are separate entries, not merged into Russia or Germany.</Note></div>
        </div>)}
    </div>
  );
}
