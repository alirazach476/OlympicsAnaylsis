import { useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, Brush, CartesianGrid, Cell, ComposedChart, ErrorBar, Legend, Line, LineChart, Pie, PieChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, Treemap, XAxis, YAxis, ZAxis,
} from "recharts";
import { useChartColors } from "../../lib/theme";
import { CAT, num } from "../util";
import type { RenderProps } from "../types";

export function useAx() {
  const c = useChartColors();
  return {
    c,
    axis: { stroke: c.axis, tick: { fill: c.axis, fontSize: 11 }, tickLine: false, axisLine: { stroke: c.grid } } as any,
    tip: { contentStyle: { background: c.tooltipBg, border: `1px solid ${c.tooltipBorder}`, borderRadius: 8, color: c.text, fontSize: 12 }, labelStyle: { color: c.text, fontWeight: 600 }, itemStyle: { color: c.text },
      formatter: (v: any) => (typeof v === "number" ? num(v, 3) : v), cursor: { stroke: c.axis, strokeOpacity: 0.3 } } as any,
  };
}

const colorOf = (s: any, i: number) => s.color ?? CAT[i % CAT.length];
/** Fit a rotated axis title to the available plot height so it is never clipped mid-word. */
const fit = (t: string | null | undefined, h: number) => { const n = Math.max(14, Math.floor((h - 170) / 6.3)); return t && t.length > n ? t.slice(0, n - 1) + "…" : t; };
const lab = (t: string | undefined | null, c: any, angle = 0, pos: any = "insideBottom", off = -6) => (t ? { value: t, angle, position: pos, offset: off, fill: c.axis, fontSize: 11 } : undefined);

/** Time-series / category chart: line, step, area, stacked, percent, stream, bar, grouped, composed - one engine, many variants. */
export function XYChart({ p, variant, height, onPick }: RenderProps) {
  const d = p.data;
  const { c, axis, tip } = useAx();
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const v = variant || d.variant || "line";
  const horizontal = !!d.horizontal && ["bar", "grouped", "stacked"].includes(v);
  const numericX = d.xType === "number";
  const logY = !!d.logY;
  const all: any[] = d.series ?? [];
  const series = all.filter((s) => !hidden.has(s.key));
  const rows = useMemo(() => (d.rows ?? []).map((r: any) => {
    if (!logY) return r;
    const o = { ...r };
    all.forEach((s) => { if (typeof o[s.key] === "number" && o[s.key] <= 0) o[s.key] = null; });
    return o;
  }), [d.rows, logY]); // eslint-disable-line react-hooks/exhaustive-deps
  const bars = ["bar", "grouped"].includes(v) || (["stacked", "percent"].includes(v) && (d.barGap !== undefined || !numericX)) || v === "composed";
  const areas = !bars && ["area", "stacked", "percent", "stream"].includes(v);
  const stackOffset = v === "percent" ? "expand" : v === "stream" ? "wiggle" : "none";
  const stack = ["stacked", "percent", "stream"].includes(v);
  const hasRight = series.some((s) => s.axis === "right");
  const pct = v === "percent";
  const yDomain: any = d.yDomain ? d.yDomain : d.yAuto ? ["auto", "auto"] : v === "stream" ? undefined : undefined;
  const yAxis = (
    <YAxis {...axis} yAxisId="l" scale={logY ? "log" : "auto"} domain={logY ? ["auto", "auto"] : yDomain} reversed={!!d.invertY} allowDataOverflow={!!d.yDomain} width={horizontal ? 0 : 56}
      tickFormatter={pct ? (t: number) => `${Math.round(t * 100)}%` : undefined} label={horizontal ? undefined : lab(fit(d.yLabel, height), c, -90, "insideLeft", 4)} hide={horizontal} tick={v === "stream" ? false : axis.tick} />
  );
  const yAxisR = hasRight ? <YAxis {...axis} yAxisId="r" orientation="right" label={lab(d.yLabelRight, c, 90, "insideRight", 4)} /> : null;
  const toggle = (e: any) => { const k = e.dataKey ?? e.value; setHidden((h) => { const n = new Set(h); n.has(k) ? n.delete(k) : n.add(k); return n; }); };
  const legend = all.length > 1 ? <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: 12, color: c.axis, cursor: "pointer" }} onClick={toggle} formatter={(val: any) => <span style={{ opacity: hidden.has(val) ? 0.4 : 1 }}>{(all.find((s) => s.key === val)?.name) ?? val}</span>} /> : null;
  const refs = (d.refs ?? []).map((r: any, i: number) => <ReferenceLine key={i} yAxisId="l" {...(r.y !== undefined ? { y: r.y } : { x: r.x })} stroke="#DF0024" strokeDasharray="4 4" label={{ value: r.label, fill: "#DF0024", fontSize: 10, position: "insideTopRight" }} />);
  const diag = d.diag ? <ReferenceLine yAxisId="l" segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={c.axis} strokeDasharray="5 5" /> : null;
  const brush = numericX && rows.length > 14 && !horizontal && !d.sparse ? <Brush dataKey={d.x} height={18} stroke={c.axis} fill="transparent" travellerWidth={8} /> : null;
  const pick = d.pickKey && p.drill ? (e: any) => { const val = e?.payload?.[d.pickKey] ?? e?.[d.pickKey]; if (val !== undefined) onPick(p.drill!.type, String(val)); } : undefined;
  const lastIdx = rows.length - 1;
  const margin = { top: 10, right: d.endLabels ? 80 : 12, left: 0, bottom: horizontal && d.yLabel ? 26 : 4 };
  const xAxis = (
    <XAxis {...axis} dataKey={d.x} type={numericX && !bars ? "number" : "category"} domain={d.xDomain ?? (numericX && !bars ? ["dataMin", "dataMax"] : undefined)} interval={bars && rows.length > 18 ? "preserveStartEnd" : "preserveEnd"}
      angle={d.rotateX ? -60 : 0} textAnchor={d.rotateX ? "end" : "middle"} height={d.rotateX ? 70 : d.xLabel && !brush ? 46 : 30} allowDuplicatedCategory={false} label={brush ? undefined : lab(d.xLabel, c, 0, "insideBottom", -2)} scale="auto" hide={horizontal ? true : false} />
  );
  const common = { data: rows, margin };
  const seriesEls = series.map((s: any, i: number) => {
    const idx = all.indexOf(s);
    const col = colorOf(s, idx);
    const name = s.name ?? s.key;
    const yId = s.axis === "right" ? "r" : "l";
    if (v === "composed") {
      return s.type === "line" ? <Line key={s.key} yAxisId={yId} type="monotone" dataKey={s.key} name={name} stroke={col} strokeWidth={2} dot isAnimationActive={false} />
        : <Bar key={s.key} yAxisId={yId} dataKey={s.key} name={name} fill={col} isAnimationActive={false} />;
    }
    if (bars) {
      const stk = ["stacked", "percent"].includes(v) ? "a" : undefined;
      if (s.type === "line") return <Line key={s.key} yAxisId={yId} type="monotone" dataKey={s.key} name={name} stroke={col} strokeWidth={2} dot isAnimationActive={false} />;
      return <Bar key={s.key} yAxisId="l" dataKey={s.key} name={name} fill={col} stackId={stk} isAnimationActive={false} onClick={pick} cursor={pick ? "pointer" : undefined} maxBarSize={44}
        radius={horizontal || stk ? 0 : [3, 3, 0, 0]}>{d.colorByIndex ? rows.map((_: any, k: number) => <Cell key={k} fill={CAT[k % CAT.length]} />) : null}</Bar>;
    }
    if (areas) return <Area key={s.key} yAxisId="l" type="monotone" dataKey={s.key} name={name} stroke={col} fill={col} fillOpacity={v === "area" ? 0.35 : 0.7} stackId={stack ? "a" : undefined} connectNulls isAnimationActive={false} />;
    const endLabel = d.endLabels ? { content: (q: any) => (q.index === lastIdx || (rows[q.index]?.[s.key] != null && rows.slice(q.index + 1).every((r: any) => r[s.key] == null))
      ? <text x={q.x + 6} y={q.y + 3} fill={col} fontSize={10}>{name.length > 14 ? name.slice(0, 13) + "…" : name}</text> : null) } : undefined;
    return <Line key={s.key} yAxisId={yId} type={v === "step" ? "stepAfter" : d.curve === "linear" || d.sparse ? "linear" : "monotone"} dataKey={s.key} name={name} stroke={col} strokeWidth={2} dot={d.dot ? { r: 2.5 } : false} activeDot={{ r: 5 }} connectNulls isAnimationActive={false}
      onClick={p.drill?.key === "series" ? () => onPick(p.drill!.type, s.key) : undefined} cursor={p.drill?.key === "series" ? "pointer" : undefined} label={endLabel as any} />;
  });
  const Chart: any = v === "composed" || hasRight ? ComposedChart : bars ? BarChart : areas ? AreaChart : LineChart;
  const extra = horizontal ? { layout: "vertical" } : {};
  const gap = d.barGap !== undefined ? { barGap: d.barGap, barCategoryGap: 0 } : {};
  return (
    <div>
    <ResponsiveContainer width="100%" height={height}>
      <Chart {...common} {...extra} {...gap} stackOffset={areas || (bars && v === "percent") ? stackOffset : undefined}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" vertical={!horizontal} horizontal />
        {horizontal ? <XAxis {...axis} type="number" label={lab(d.yLabel, c)} scale={logY ? "log" : "auto"} domain={logY ? ["auto", "auto"] : undefined} /> : xAxis}
        {horizontal ? <YAxis {...axis} yAxisId="l" type="category" dataKey={d.x} width={Math.min(190, 12 + 7 * Math.max(...rows.map((r: any) => String(r[d.x]).length), 4))} interval={0} /> : yAxis}
        {yAxisR}
        <Tooltip {...tip} />
        {legend}
        {refs}{diag}
        {seriesEls}
        {brush}
      </Chart>
    </ResponsiveContainer>
    {brush && d.xLabel && <div className="-mt-1 text-center text-[11px] text-muted">{d.xLabel}</div>}
    </div>
  );
}

export function LorenzChart({ p, height }: RenderProps) {
  const d = p.data;
  const { c, axis, tip } = useAx();
  const rows = d.rows.map((r: any) => ({ ...r, eq: r[d.x] }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={rows} margin={{ top: 10, right: 12, left: 0, bottom: 24 }}>
          <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
          <XAxis {...axis} dataKey={d.x} type="number" domain={[0, 1]} tickFormatter={(t: number) => `${Math.round(t * 100)}%`} label={lab(d.xLabel, c)} />
          <YAxis {...axis} domain={[0, 1]} tickFormatter={(t: number) => `${Math.round(t * 100)}%`} width={50} label={lab(d.yLabel, c, -90, "insideLeft", 4)} />
          <Tooltip {...tip} formatter={(v: any) => `${(Number(v) * 100).toFixed(1)}%`} />
          <Area type="monotone" dataKey="eq" name="Perfect equality" stroke={c.axis} strokeDasharray="5 5" fill="transparent" dot={false} isAnimationActive={false} />
          <Area type="monotone" dataKey={d.y} name="Lorenz curve" stroke="#D55E00" fill="#D55E00" fillOpacity={0.2} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Legend wrapperStyle={{ fontSize: 12, color: c.axis }} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-1 text-center text-sm font-semibold">Gini coefficient: {num(d.gini, 3)}</div>
    </div>
  );
}

export function ParetoChart({ p, height, onPick }: RenderProps) {
  const d = p.data;
  const { c, axis, tip } = useAx();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={d.rows} margin={{ top: 10, right: 8, left: 0, bottom: 24 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis {...axis} dataKey={d.x} interval={0} angle={-50} textAnchor="end" height={54} label={lab(d.xLabel, c)} />
        <YAxis {...axis} yAxisId="l" width={52} label={lab(d.barLabel, c, -90, "insideLeft", 4)} />
        <YAxis {...axis} yAxisId="r" orientation="right" domain={[0, 1]} tickFormatter={(t: number) => `${Math.round(t * 100)}%`} width={46} />
        <Tooltip {...tip} />
        <Legend wrapperStyle={{ fontSize: 12, color: c.axis }} />
        <ReferenceLine yAxisId="r" y={0.8} stroke="#DF0024" strokeDasharray="4 4" label={{ value: "80%", fill: "#DF0024", fontSize: 10, position: "insideTopRight" }} />
        <Bar yAxisId="l" dataKey={d.bar} name={d.barLabel} fill="#0072B2" isAnimationActive={false} cursor="pointer" onClick={(e: any) => p.drill && onPick(p.drill.type, e.payload[d.pickKey])} />
        <Line yAxisId="r" type="monotone" dataKey={d.line} name={d.lineLabel} stroke="#D55E00" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function DonutChart({ p, height, onPick }: RenderProps) {
  const d = p.data;
  const { c, tip } = useAx();
  const rows = d.rows as any[];
  const total = d.total ?? rows.reduce((a, r) => a + (r.value ?? r.size ?? 0), 0);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={rows} dataKey="value" nameKey="name" innerRadius="52%" outerRadius="82%" paddingAngle={1} isAnimationActive={false} onClick={(e: any) => e?.noc && p.drill && onPick(p.drill.type, e.noc)} cursor={p.drill ? "pointer" : undefined}
          label={(q: any) => (q.percent > 0.04 ? `${(q.percent * 100).toFixed(0)}%` : "")} labelLine={false}>
          {rows.map((_, i) => <Cell key={i} fill={i === rows.length - 1 && String(rows[i].name).startsWith("Other") ? "#9AA3AF" : CAT[i % CAT.length]} stroke={c.tooltipBg} />)}
        </Pie>
        <Tooltip {...tip} formatter={(v: any, n: any) => [`${num(v, 0)} ${d.valueLabel ?? ""} (${((Number(v) / total) * 100).toFixed(1)}%)`, n]} />
        <Legend wrapperStyle={{ fontSize: 12, color: c.axis }} layout="vertical" align="right" verticalAlign="middle" />
        <text x="38%" y="50%" textAnchor="middle" dominantBaseline="middle" fill={c.text} fontSize={20} fontWeight={700}>{num(total, 0)}</text>
        <text x="38%" y="50%" dy="20" textAnchor="middle" fill={c.axis} fontSize={11}>{d.valueLabel ?? "total"}</text>
      </PieChart>
    </ResponsiveContainer>
  );
}

export function TreemapChart({ p, height, onPick }: RenderProps) {
  const d = p.data;
  const { c, tip } = useAx();
  const groups = useMemo(() => {
    const g = new Map<string, any[]>();
    d.rows.forEach((r: any) => { const k = r.group ?? "All"; if (!g.has(k)) g.set(k, []); g.get(k)!.push({ name: r.name, size: r.size, noc: r.noc }); });
    return Array.from(g.entries()).map(([name, children], i) => ({ name, color: CAT[i % CAT.length], children }));
  }, [d.rows]);
  const Cell: any = (q: any) => {
    const { x, y, width: w, height: h, name, depth, root } = q;
    const col = depth === 1 ? "transparent" : (groups.find((g) => g.name === (root?.name ?? q.parent?.name))?.color ?? CAT[0]);
    return (
      <g onClick={() => q.noc && p.drill && onPick(p.drill.type, q.noc)} style={{ cursor: q.noc ? "pointer" : "default" }}>
        <rect x={x} y={y} width={w} height={h} fill={col} fillOpacity={depth === 1 ? 0 : 0.85} stroke={c.tooltipBg} strokeWidth={depth === 1 ? 3 : 1} />
        {depth === 2 && w > 54 && h > 20 && <text x={x + 5} y={y + 14} fill="#fff" fontSize={11} style={{ pointerEvents: "none" }}>{String(name).length * 6.2 > w ? String(name).slice(0, Math.floor(w / 6.2)) + "…" : name}</text>}
        {depth === 1 && w > 80 && <text x={x + 6} y={y + 16} fill={c.text} fontSize={12} fontWeight={700} style={{ pointerEvents: "none" }}>{name}</text>}
      </g>
    );
  };
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Treemap data={groups as any} dataKey="size" nameKey="name" isAnimationActive={false} content={<Cell />} aspectRatio={1.6}>
        <Tooltip {...tip} formatter={(v: any) => `${num(v, 0)} ${d.sizeLabel ?? ""}`} />
      </Treemap>
    </ResponsiveContainer>
  );
}

export function RadarViz({ p, height }: RenderProps) {
  const d = p.data;
  const { c, tip } = useAx();
  const data = d.axes.map((a: string) => ({ axis: a, ...Object.fromEntries(d.series.map((s: any) => [s.name, +(s.values[a] ?? 0).toFixed(1)])) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke={c.grid} />
        <PolarAngleAxis dataKey="axis" tick={{ fill: c.axis, fontSize: 11 }} />
        <PolarRadiusAxis angle={90} domain={[0, d.max ?? 100]} tick={{ fill: c.axis, fontSize: 9 }} />
        {d.series.map((s: any, i: number) => <Radar key={s.name} name={s.name} dataKey={s.name} stroke={CAT[i % CAT.length]} fill={CAT[i % CAT.length]} fillOpacity={0.22} isAnimationActive={false} />)}
        <Tooltip {...tip} formatter={(v: any) => `${num(v, 1)} / 100`} />
        <Legend wrapperStyle={{ fontSize: 12, color: c.axis }} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export function ScatterViz({ p, height, onPick }: RenderProps) {
  const d = p.data;
  const { c, axis, tip } = useAx();
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const rows: any[] = d.rows;
  const groups = useMemo(() => {
    const m = new Map<string, any[]>();
    rows.forEach((r) => { const g = d.groupLabel ? String(r.group ?? "") : "All"; if (!m.has(g)) m.set(g, []); m.get(g)!.push(r); });
    return Array.from(m.entries());
  }, [rows, d.groupLabel]);
  const colorFor = (g: string, i: number) => d.colors?.[g] ?? CAT[i % CAT.length];
  const zs = rows.map((r) => r.z).filter((z) => typeof z === "number");
  const zRange: [number, number] = zs.length && !d.noSize ? [Math.min(...zs), Math.max(...zs)] : [1, 1];
  const cats: string[] | undefined = d.xCategories;
  const xs = rows.map((r) => r.x), ys = rows.map((r) => r.y);
  const logX = !!d.logX, logY = !!d.logY;
  const xDomain: any = cats ? [-0.5, cats.length - 0.5] : logX ? ["auto", "auto"] : ["auto", "auto"];
  // a log axis gets clean powers of ten as ticks (otherwise every data value becomes a tick: cluttered, and equal values repeat)
  const pos = xs.filter((v) => typeof v === "number" && v > 0);
  const logTicks = logX && pos.length ? Array.from({ length: Math.floor(Math.log10(Math.max(...pos))) - Math.floor(Math.log10(Math.min(...pos))) + 1 }, (_, i) => 10 ** (Math.floor(Math.log10(Math.min(...pos))) + i)) : undefined;
  const line: any[] = d.line ?? [];
  const band = line.length && line[0].lo !== undefined;
  const Tip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const r = payload[0].payload;
    return (
      <div style={tip.contentStyle} className="max-w-xs">
        {r.name && <div className="font-semibold">{r.name}</div>}
        <div>{d.xLabel?.split(" (")[0] ?? "x"}: {cats ? cats[Math.round(r.x)] : num(r.x, 3)}</div>
        <div>{d.yLabel?.split(" (")[0] ?? "y"}: {num(r.y, 3)}</div>
        {r.z !== undefined && !d.noSize && <div>{d.sizeLabel ?? "size"}: {num(r.z, 0)}</div>}
        {(d.extra ?? []).map((k: string) => r[k] !== undefined && <div key={k}>{k}: {typeof r[k] === "number" ? num(r[k], 2) : r[k]}</div>)}
        {d.groupLabel && r.group && <div>{d.groupLabel}: {r.group}</div>}
      </div>
    );
  };
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart margin={{ top: 10, right: 14, left: 0, bottom: 26 }}>
        <CartesianGrid stroke={c.grid} strokeDasharray="3 3" />
        <XAxis {...axis} type="number" dataKey="x" domain={xDomain} scale={logX ? "log" : "auto"} ticks={cats ? cats.map((_, i) => i) : logTicks} tickFormatter={cats ? (t: number) => cats[t] ?? "" : logX ? (t: number) => num(t, 0) : undefined}
          interval={cats || logTicks ? 0 : "preserveEnd"} label={lab(d.xLabel, c)} allowDataOverflow={logX} />
        <YAxis {...axis} type="number" dataKey="y" scale={logY ? "log" : "auto"} domain={["auto", "auto"]} width={54} label={lab(fit(d.yLabel, height), c, -90, "insideLeft", 4)} allowDataOverflow={logY} />
        <ZAxis type="number" dataKey="z" range={d.noSize ? [22, 22] : [28, 520]} domain={zRange} />
        <Tooltip content={<Tip />} cursor={{ strokeDasharray: "3 3", stroke: c.axis }} />
        {groups.length > 1 && <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: 12, color: c.axis, cursor: "pointer" }} onClick={(e: any) => setHidden((h) => { const n = new Set(h); n.has(e.value) ? n.delete(e.value) : n.add(e.value); return n; })} />}
        {d.diag && <ReferenceLine segment={[{ x: Math.min(...xs), y: d.diag.slope * Math.min(...xs) }, { x: Math.max(...xs), y: d.diag.slope * Math.max(...xs) }]} stroke={c.axis} strokeDasharray="5 5" label={{ value: d.diag.label, fill: c.axis, fontSize: 10, position: "insideTopLeft" }} />}
        {d.refY !== undefined && <ReferenceLine y={d.refY} stroke={c.axis} strokeDasharray="4 4" />}
        {band && <Area data={line} dataKey={(r: any) => [r.lo, r.hi]} type="monotone" stroke="none" fill="#D55E00" fillOpacity={0.18} isAnimationActive={false} legendType="none" xAxisId={0} yAxisId={0} />}
        {line.length > 0 && <Line data={line} dataKey="y" type="monotone" stroke="#D55E00" strokeWidth={2.5} dot={false} name={d.lineLabel ?? "fit"} isAnimationActive={false} legendType="none" />}
        {groups.map(([g, pts], i) => !hidden.has(g) && (
          <Scatter key={g} name={g} data={pts} fill={colorFor(g, i)} fillOpacity={d.noSize ? 0.55 : 0.6} isAnimationActive={false} cursor={p.drill ? "pointer" : undefined}
            onClick={(e: any) => { const k = p.drill?.key; const val = k && e?.payload?.[k]; if (val !== undefined && val !== null) onPick(p.drill!.type, String(val)); }} />))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
