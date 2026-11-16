import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../lib/api";
import { Async, Flag, PageHeader } from "../components/ui";
import { fmtInt, fmtPct } from "../lib/fmt";
import { useTheme } from "../lib/theme";
import { themeVars, useRegistry } from "../themes/olympicThemeEngine";
import { CompareTabs } from "./CompareCountriesPage";

const ROWS: [string, string, (v: any) => string][] = [["Athletes", "athletes", fmtInt], ["NOCs", "nocs", fmtInt], ["Sports", "sports", fmtInt], ["Events", "events", fmtInt], ["Women", "female_share", (v) => fmtPct(v, 1)]];

/** Two editions side by side, each in its own colours, with the same sport's pictogram from both (historical comparison). */
export default function ComparePage() {
  const games = useApi<any[]>("/games");
  const reg = useRegistry();
  const { theme: mode } = useTheme();
  const [a, setA] = useState("2016_summer");
  const [b, setB] = useState("2024_summer");
  const [sport, setSport] = useState("Athletics");
  const list = games.data ?? [];
  const sportsOf = useMemo(() => [...new Set([a, b].flatMap((g) => reg.editions[g]?.assets.pictograms.filter((p) => p.sportLinked).map((p) => p.sport as string) ?? []))].sort(), [a, b, reg]);
  const col = (id: string, other: string) => {
    const g = list.find((x) => x.games_id === id); const ed = reg.editions[id];
    const pic = ed?.assets.pictograms.find((p) => p.sportLinked && p.sport === sport);
    return (
      <section className="card overflow-hidden" style={themeVars(ed?.theme ?? reg.neutralTheme, mode)} data-testid="compare-col">
        <div className="relative h-32 overflow-hidden">{ed?.assets.background && <img src={ed.assets.background} alt="" className="absolute inset-0 h-full w-full object-cover" />}<div className="absolute inset-0" style={{ background: "linear-gradient(135deg, var(--ed-primary), transparent 75%)", opacity: 0.7 }} /><div className="absolute inset-0 bg-gradient-to-t from-surface to-transparent" />
          <div className="absolute bottom-2 left-4 flex items-end gap-3">{ed?.assets.logo && <img src={ed.assets.logo} alt="" className="h-16 w-16 rounded-lg bg-white/95 object-contain p-1" />}<div><div className="font-display text-4xl leading-none text-white">{ed?.year ?? id}</div><div className="text-sm text-white/90">{ed?.hostCity}</div></div></div></div>
        <div className="p-4">
          <dl className="grid grid-cols-5 gap-2 text-center">{ROWS.map(([label, k, f]) => { const v = g?.[k], o = list.find((x) => x.games_id === other)?.[k]; return <div key={k}><dd className="font-display text-2xl leading-none" style={{ color: v != null && o != null && v > o ? "var(--ed-accent)" : undefined }}>{f(v)}</dd><dt className="mt-0.5 text-[10px] uppercase tracking-wider text-muted">{label}</dt></div>; })}</dl>
          <div className="mt-4 text-xs text-muted">Medal table</div>
          <div className="mt-1 text-sm">{(g?.podium_preview || "").split(" ").filter(Boolean).map((p: string) => { const [noc, gsb] = p.split(":"); return <div key={noc} className="flex items-center gap-2"><Flag noc={noc} size={12} />{noc} <span className="tabnum text-muted">{gsb}</span></div>; })}</div>
          <div className="mt-4 text-xs text-muted">{sport} pictogram</div>
          <div className="mt-1 grid h-28 w-28 place-items-center rounded-lg bg-white p-2">{pic ? <img src={pic.src} alt={`${sport} pictogram, ${ed.name}`} className="max-h-full max-w-full object-contain" /> : <span className="text-center text-[11px] text-neutral-500">not available for this edition</span>}</div>
          <Link to={`/edition/${id}`} className="btn mt-4">Open edition</Link>
        </div>
      </section>);
  };
  return (
    <div>
      <PageHeader title="Compare editions" subtitle="Two Games side by side - the larger value is highlighted in that edition's own accent colour." />
      <CompareTabs active="editions" />
      <Async q={games}>{() => (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            {([["Edition A", a, setA], ["Edition B", b, setB]] as const).map(([label, val, set]) => <label key={label} className="flex w-full items-center gap-2 text-xs text-muted sm:w-auto">{label}<select className="input min-w-0 flex-1 sm:flex-none" value={val} onChange={(e) => set(e.target.value)} aria-label={label}>{list.map((g) => <option key={g.games_id} value={g.games_id}>{g.year} {g.host_city} ({g.season})</option>)}</select></label>)}
            <label className="flex w-full items-center gap-2 text-xs text-muted sm:w-auto">Sport pictogram<select className="input min-w-0 flex-1 sm:flex-none" value={sport} onChange={(e) => setSport(e.target.value)} aria-label="Sport">{[...new Set([sport, ...sportsOf])].sort().map((s) => <option key={s}>{s}</option>)}</select></label>
          </div>
          <div className="grid gap-4 md:grid-cols-2">{col(a, b)}{col(b, a)}</div>
        </>)}</Async>
    </div>
  );
}
