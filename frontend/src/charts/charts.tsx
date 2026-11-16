import { ReactNode, useMemo } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Scatter,
  ScatterChart, Sankey, Tooltip, Treemap, XAxis, YAxis, ZAxis, Cell, ReferenceLine, ErrorBar,
} from "recharts";
import { useChartColors } from "../lib/theme";
import { fmtNum, PALETTE } from "../lib/fmt";
import { Empty } from "../components/ui";

type Series = { key: string; name?: string; color?: string; dash?: string; dot?: boolean; stack?: string };
const nf = (v: any) => (typeof v === "number" ? fmtNum(v, 2) : v);

function useAxis() {
  const c = useChartColors();
  return {
    c,
    axis: { stroke: c.axis, tick: { fill: c.axis, fontSize: 11 }, tickLine: false, axisLine: { stroke: c.grid } } as any,
    tip: { contentStyle: { background: c.tooltipBg, border: `1px solid ${c.tooltipBorder}`, borderRadius: 8, color: c.text, fontSize: 12 }, labelStyle: { color: c.text, fontWeight: 600 }, itemStyle: { color: c.text }, formatter: nf } as any,
  };
}

function Frame({ data, height, children }: { data: any[]; height: number; children: ReactNode }) {
  if (!data || !data.length) return <Empty />;
  return <ResponsiveContainer width="100%" height={height}>{children as any}</ResponsiveContainer>;
}

export function LineSeries({ data, x, series, height = 300, xLabel, yLabel, yFormat, refLines = [], onSelect, selected }: { data: any[]; x: string; series: Series[]; height?: number; xLabel?: string; yLabel?: string; yFormat?: (v: any) => string; refLines?: { x: any; label: string }[]; onSelect?: (v: string) => void; selected?: string | null }) {
  const { c, axis, tip } = useAxis();
  return (
    <Frame data={data} height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: xLabel ? 18 : 0 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
        <XAxis dataKey={x} {...axis} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -8, fill: c.axis, fontSize: 11 } : undefined} />
        <YAxis {...axis} tickFormatter={yFormat} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: c.axis, fontSize: 11 } : undefined} />
        <Tooltip {...tip} />
        <Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 11, color: c.axis, paddingBottom: 6, cursor: onSelect ? "pointer" : undefined }} onClick={onSelect ? (e: any) => onSelect(String(e.dataKey)) : undefined} />
        {refLines.map((r) => <ReferenceLine key={r.label} x={r.x} stroke="#DF0024" strokeDasharray="4 4" label={{ value: r.label, fill: "#DF0024", fontSize: 10 }} />)}
        {series.map((s, i) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.name ?? s.key} stroke={s.color ?? PALETTE[i % PALETTE.length]} strokeWidth={selected === s.key ? 4 : 2} strokeOpacity={selected && selected !== s.key ? 0.25 : 1} strokeDasharray={s.dash} dot={s.dot ?? false} activeDot={{ r: 4 }} connectNulls />)}
      </LineChart>
    </Frame>
  );
}

export function StackedArea({ data, x, series, height = 300, xLabel, yLabel, percent }: { data: any[]; x: string; series: Series[]; height?: number; xLabel?: string; yLabel?: string; percent?: boolean }) {
  const { c, axis, tip } = useAxis();
  return (
    <Frame data={data} height={height}>
      <AreaChart data={data} stackOffset={percent ? "expand" : "none"} margin={{ top: 8, right: 12, left: 0, bottom: xLabel ? 18 : 0 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
        <XAxis dataKey={x} {...axis} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -8, fill: c.axis, fontSize: 11 } : undefined} />
        <YAxis {...axis} tickFormatter={percent ? (v) => `${Math.round(v * 100)}%` : undefined} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: c.axis, fontSize: 11 } : undefined} />
        <Tooltip {...tip} />
        <Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 11, color: c.axis, paddingBottom: 6 }} />
        {series.map((s, i) => <Area key={s.key} type="monotone" dataKey={s.key} name={s.name ?? s.key} stackId="1" stroke={s.color ?? PALETTE[i % PALETTE.length]} fill={s.color ?? PALETTE[i % PALETTE.length]} fillOpacity={0.55} />)}
      </AreaChart>
    </Frame>
  );
}

export function Bars({ data, x, series, height = 300, horizontal, xLabel, yLabel, stacked, colorByIndex, yFormat, maxBars = 30, onSelect, selected }: { data: any[]; x: string; series: Series[]; height?: number; horizontal?: boolean; xLabel?: string; yLabel?: string; stacked?: boolean; colorByIndex?: boolean; yFormat?: (v: any) => string; maxBars?: number; onSelect?: (v: string) => void; selected?: string | null }) {
  const { c, axis, tip } = useAxis();
  const d = (data || []).slice(0, maxBars);
  const h = horizontal ? Math.max(height, d.length * 26 + 40) : height;
  return (
    <Frame data={d} height={h}>
      <BarChart data={d} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 8, right: 16, left: horizontal ? 24 : 0, bottom: xLabel ? 18 : 0 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" horizontal={!horizontal} vertical={!!horizontal} />
        {horizontal ? <XAxis type="number" {...axis} tickFormatter={yFormat} /> : <XAxis dataKey={x} {...axis} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -8, fill: c.axis, fontSize: 11 } : undefined} />}
        {horizontal ? <YAxis type="category" dataKey={x} width={96} {...axis} /> : <YAxis {...axis} tickFormatter={yFormat} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: c.axis, fontSize: 11 } : undefined} />}
        <Tooltip {...tip} cursor={{ fill: c.grid, opacity: 0.4 }} />
        {series.length > 1 && <Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 11, color: c.axis, paddingBottom: 6 }} />}
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.name ?? s.key} stackId={stacked ? "a" : undefined} fill={s.color ?? PALETTE[i % PALETTE.length]} radius={stacked ? 0 : [3, 3, 0, 0]}
            cursor={onSelect ? "pointer" : undefined} onClick={onSelect ? (e: any) => onSelect(String(e?.[x] ?? e?.payload?.[x])) : undefined}>
            {(colorByIndex || selected) && d.map((r, j) => <Cell key={j} fill={colorByIndex ? PALETTE[j % PALETTE.length] : s.color ?? PALETTE[i % PALETTE.length]} fillOpacity={selected && String(r[x]) !== selected ? 0.25 : 1} stroke={selected && String(r[x]) === selected ? "#fff" : undefined} strokeWidth={selected && String(r[x]) === selected ? 1.5 : 0} />)}
          </Bar>
        ))}
      </BarChart>
    </Frame>
  );
}

export function Pareto({ data, label, value, cum, height = 300 }: { data: any[]; label: string; value: string; cum: string; height?: number }) {
  const { c, axis, tip } = useAxis();
  return (
    <Frame data={data} height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
        <XAxis dataKey={label} {...axis} interval={0} tick={{ fill: c.axis, fontSize: 9 }} angle={-60} textAnchor="end" height={50} />
        <YAxis yAxisId="l" {...axis} /><YAxis yAxisId="r" orientation="right" domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} {...axis} />
        <Tooltip {...tip} /><Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 11, color: c.axis, paddingBottom: 6 }} />
        <Bar yAxisId="l" dataKey={value} name="Medals" fill="#0085C7" radius={[3, 3, 0, 0]} />
        <Line yAxisId="r" dataKey={cum} name="Cumulative share" stroke="#F4C300" strokeWidth={2} dot={false} />
        <ReferenceLine yAxisId="r" y={0.8} stroke="#DF0024" strokeDasharray="4 4" label={{ value: "80%", fill: "#DF0024", fontSize: 10 }} />
      </ComposedChart>
    </Frame>
  );
}

export function Scatter2({ data, x, y, z, name, xLabel, yLabel, height = 320, colorKey, groups, trend }: { data: any[]; x: string; y: string; z?: string; name?: string; xLabel?: string; yLabel?: string; height?: number; colorKey?: string; groups?: Record<string, string>; trend?: boolean }) {
  const { c, axis, tip } = useAxis();
  const grouped = useMemo(() => {
    if (!colorKey) return [{ key: "all", rows: data || [] }];
    const m = new Map<string, any[]>();
    (data || []).forEach((r) => { const k = String(r[colorKey]); m.set(k, [...(m.get(k) || []), r]); });
    return [...m.entries()].map(([key, rows]) => ({ key, rows }));
  }, [data, colorKey]);
  return (
    <Frame data={data} height={height}>
      <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 22 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
        <XAxis type="number" dataKey={x} name={xLabel ?? x} {...axis} label={{ value: xLabel ?? x, position: "insideBottom", offset: -10, fill: c.axis, fontSize: 11 }} />
        <YAxis type="number" dataKey={y} name={yLabel ?? y} {...axis} label={{ value: yLabel ?? y, angle: -90, position: "insideLeft", fill: c.axis, fontSize: 11 }} />
        {z && <ZAxis type="number" dataKey={z} range={[40, 400]} />}
        <Tooltip {...tip} cursor={{ strokeDasharray: "3 3" }} content={({ active, payload }: any) => active && payload?.length ? (
          <div style={tip.contentStyle} className="px-2 py-1">{name && <div className="font-semibold">{payload[0].payload[name]}</div>}{payload.map((p: any) => <div key={p.name}>{p.name}: {nf(p.value)}</div>)}</div>) : null} />
        {grouped.length > 1 && <Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 11, color: c.axis, paddingBottom: 6 }} />}
        {grouped.map((g, i) => <Scatter key={g.key} name={groups?.[g.key] ?? g.key} data={g.rows} fill={PALETTE[i % PALETTE.length]} fillOpacity={0.75} />)}
      </ScatterChart>
    </Frame>
  );
}

function TreemapCell(props: any) {
  const { x, y, width, height, index, name, size, stroke } = props;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={PALETTE[(index ?? 0) % PALETTE.length]} fillOpacity={0.85} stroke={stroke} />
      {width > 60 && height > 28 && <text x={x + 6} y={y + 16} fill="#fff" fontSize={11} fontWeight={600}>{name}</text>}
      {width > 60 && height > 44 && <text x={x + 6} y={y + 31} fill="#fff" fontSize={10} opacity={0.85}>{fmtNum(size, 0)}</text>}
    </g>
  );
}

export function TreemapChart({ data, height = 320 }: { data: { name: string; size: number }[]; height?: number }) {
  const c = useChartColors();
  if (!data?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Treemap data={data as any} dataKey="size" stroke={c.tooltipBg} aspectRatio={4 / 3} isAnimationActive={false} content={<TreemapCell stroke={c.tooltipBg} />} />
    </ResponsiveContainer>
  );
}

export function RadarCompare({ data, series, height = 320 }: { data: any[]; series: Series[]; height?: number }) {
  const { c, tip } = useAxis();
  return (
    <Frame data={data} height={height}>
      <RadarChart data={data} outerRadius="75%">
        <PolarGrid stroke={c.grid} /><PolarAngleAxis dataKey="axis" tick={{ fill: c.axis, fontSize: 11 }} /><PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: c.axis, fontSize: 9 }} />
        {series.map((s, i) => <Radar key={s.key} name={s.name ?? s.key} dataKey={s.key} stroke={s.color ?? PALETTE[i % PALETTE.length]} fill={s.color ?? PALETTE[i % PALETTE.length]} fillOpacity={0.25} />)}
        <Tooltip {...tip} /><Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: 11, color: c.axis, paddingBottom: 6 }} />
      </RadarChart>
    </Frame>
  );
}

export function SankeyChart({ nodes, links, height = 340 }: { nodes: { name: string }[]; links: { source: number; target: number; value: number }[]; height?: number }) {
  const c = useChartColors();
  if (!links?.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Sankey data={{ nodes, links }} nodePadding={24} margin={{ top: 8, right: 100, bottom: 8, left: 8 }} link={{ stroke: "#0085C7", strokeOpacity: 0.25 }}
        node={({ x, y, width, height: h, index, payload }: any) => (
          <g><rect x={x} y={y} width={width} height={h} fill={PALETTE[index % PALETTE.length]} />
            <text x={x + width + 6} y={y + h / 2} fill={c.text} fontSize={11} dominantBaseline="middle">{payload.name}</text></g>)}>
        <Tooltip />
      </Sankey>
    </ResponsiveContainer>
  );
}

/** Matrix heat-map (correlations, completeness). cells are real CSS grid so it scales and is keyboard/screen-reader friendly. */
export function Heat({ rowsLabels, colLabels, values, format = (v: number) => fmtNum(v, 2), domain = [-1, 1], diverging = true, cell = 56 }: { rowsLabels: string[]; colLabels: string[]; values: (number | null)[][]; format?: (v: number) => string; domain?: [number, number]; diverging?: boolean; cell?: number }) {
  if (!values?.length) return <Empty />;
  const [lo, hi] = domain;
  const colour = (v: number | null) => {
    if (v === null || v === undefined || Number.isNaN(v)) return "transparent";
    const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
    if (diverging) return t >= 0.5 ? `rgba(0,133,199,${(t - 0.5) * 2 * 0.9 + 0.05})` : `rgba(223,0,36,${(0.5 - t) * 2 * 0.9 + 0.05})`;
    return `rgba(244,195,0,${t * 0.9 + 0.05})`;
  };
  return (
    <div className="scroll-thin overflow-auto">
      <div className="inline-grid text-[11px]" style={{ gridTemplateColumns: `130px repeat(${colLabels.length}, ${cell}px)` }}>
        <div />{colLabels.map((l) => <div key={l} className="truncate px-1 pb-1 text-center text-muted" title={l}>{l}</div>)}
        {rowsLabels.map((r, i) => (<>
          <div key={`r${r}`} className="truncate pr-2 text-right text-muted self-center" title={r}>{r}</div>
          {values[i].map((v, j) => <div key={`${r}-${j}`} className="tabnum grid place-items-center border border-bg/40" style={{ height: cell * 0.62, background: colour(v) }} title={`${r} × ${colLabels[j]}: ${v === null ? "n/a" : format(v)}`}>{v === null ? "" : format(v)}</div>)}
        </>))}
      </div>
    </div>
  );
}

/** Violin from precomputed densities (backend KDE). */
export function Violin({ items, height = 280, xLabel }: { items: { label: string; x: number[]; density: number[]; median?: number; color?: string }[]; height?: number; xLabel?: string }) {
  const c = useChartColors();
  if (!items?.length) return <Empty />;
  const W = 640, pad = 36, rowH = (height - 30) / items.length;
  const xmin = Math.min(...items.map((i) => i.x[0])), xmax = Math.max(...items.map((i) => i.x[i.x.length - 1]));
  const sx = (v: number) => pad + ((v - xmin) / (xmax - xmin)) * (W - pad - 10);
  return (
    <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label="Violin plot" className="w-full">
      {items.map((it, k) => {
        const dmax = Math.max(...it.density), mid = 12 + rowH * k + rowH / 2, half = rowH * 0.42;
        const top = it.x.map((v, i) => `${sx(v)},${mid - (it.density[i] / dmax) * half}`);
        const bot = it.x.map((v, i) => `${sx(v)},${mid + (it.density[i] / dmax) * half}`).reverse();
        return (<g key={it.label}>
          <polygon points={[...top, ...bot].join(" ")} fill={it.color ?? PALETTE[k % PALETTE.length]} fillOpacity={0.55} stroke={it.color ?? PALETTE[k % PALETTE.length]} />
          {it.median !== undefined && <line x1={sx(it.median)} x2={sx(it.median)} y1={mid - half} y2={mid + half} stroke={c.text} strokeWidth={2} />}
          <text x={pad - 4} y={mid} textAnchor="end" fontSize={10} fill={c.axis} dominantBaseline="middle">{it.label}</text></g>);
      })}
      <line x1={pad} x2={W - 10} y1={height - 18} y2={height - 18} stroke={c.grid} />
      {[0, 0.25, 0.5, 0.75, 1].map((t) => { const v = xmin + (xmax - xmin) * t; return <text key={t} x={sx(v)} y={height - 5} fontSize={10} textAnchor="middle" fill={c.axis}>{Math.round(v)}</text>; })}
      {xLabel && <text x={W - 10} y={height - 20} fontSize={10} textAnchor="end" fill={c.axis}>{xLabel}</text>}
    </svg>
  );
}

export function BoxStrip({ items, height = 160 }: { items: { label: string; q1: number; median: number; q3: number; low: number; high: number; outliers?: number }[]; height?: number }) {
  const c = useChartColors();
  if (!items?.length) return <Empty />;
  const W = 640, pad = 90, rowH = (height - 24) / items.length;
  const xmin = Math.min(...items.map((i) => i.low)), xmax = Math.max(...items.map((i) => i.high));
  const sx = (v: number) => pad + ((v - xmin) / (xmax - xmin || 1)) * (W - pad - 14);
  return (
    <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label="Box plots" className="w-full">
      {items.map((b, k) => { const y = 10 + rowH * k + rowH / 2; return (<g key={b.label}>
        <line x1={sx(b.low)} x2={sx(b.high)} y1={y} y2={y} stroke={c.axis} />
        <rect x={sx(b.q1)} y={y - rowH * 0.28} width={Math.max(1, sx(b.q3) - sx(b.q1))} height={rowH * 0.56} fill={PALETTE[k % PALETTE.length]} fillOpacity={0.55} stroke={PALETTE[k % PALETTE.length]} />
        <line x1={sx(b.median)} x2={sx(b.median)} y1={y - rowH * 0.28} y2={y + rowH * 0.28} stroke={c.text} strokeWidth={2} />
        <text x={pad - 6} y={y} textAnchor="end" fontSize={10} fill={c.axis} dominantBaseline="middle">{b.label}{b.outliers ? ` (${b.outliers} outl.)` : ""}</text></g>); })}
      {[0, 0.5, 1].map((t) => { const v = xmin + (xmax - xmin) * t; return <text key={t} x={sx(v)} y={height - 4} fontSize={10} textAnchor="middle" fill={c.axis}>{fmtNum(v, 0)}</text>; })}
    </svg>
  );
}

export { ErrorBar };
