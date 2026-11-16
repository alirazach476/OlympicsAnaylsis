import { useMemo, useState } from "react";
import { useChartColors } from "../../lib/theme";
import { CAT, fmtCell, lum, niceTicks, num, ramp, RDBU, useSize, VIRIDIS } from "../util";
import type { RenderProps } from "../types";

const trunc = (s: any, n: number) => (String(s).length > n ? String(s).slice(0, n - 1) + "…" : String(s));

/* ---------------------------------------------------------------------------------------------------------------- heatmap / calendar */
export function Heatmap({ p, height, onPick }: RenderProps) {
  const d = p.data;
  const c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640;
  const [hover, setHover] = useState<{ r: string; c: string } | null>(null);
  const rowOrder: string[] = d.rowOrder, colOrder: string[] = d.colOrder;
  const cellMap = useMemo(() => new Map<string, any>(d.rows.map((r: any) => [`${r.r}|${r.c}`, r])), [d.rows]);
  const vals = d.rows.map((r: any) => r.v).filter((v: any) => typeof v === "number");
  const clip = d.clipMax ?? Infinity;
  const [lo, hi] = d.domain ?? [Math.min(...vals, 0), Math.min(Math.max(...vals, 1), clip)];
  const left = Math.min(170, 14 + 6.4 * Math.max(...rowOrder.map((r) => String(r).length), 4));
  const rotate = d.rotateCols || colOrder.some((x) => String(x).length > 4) && colOrder.length > 10;
  const bottom = (rotate ? 14 + 5.6 * Math.min(Math.max(...colOrder.map((x) => String(x).length), 4), 24) : 22) + (d.xTitle || d.colLabel ? 16 : 0);
  const legendW = 70;
  const cw = Math.max(6, (W - left - legendW - 8) / colOrder.length);
  const ch = Math.max(14, Math.min(d.cell === "number" ? 46 : 26, rowOrder.length > 30 ? 16 : 28));
  const H = Math.max(height * 0.6, 8 + rowOrder.length * ch + bottom);
  const color = (v: number) => {
    if (d.zeroColor && v === 0) return d.zeroColor;
    const t = (v - lo) / (hi - lo || 1);
    if (d.scale === "div") return ramp(RDBU, (v - lo) / (hi - lo || 1));
    if (d.scale === "seqrev") return ramp(VIRIDIS, 1 - Math.max(0, Math.min(1, t)));
    return ramp(VIRIDIS, t);
  };
  const showNum = (d.cell === "number" || (cw >= 30 && ch >= 18 && colOrder.length <= 16)) && cw >= 22;
  const rowKey = (r: string) => (p.drill?.type === "games" ? r.toLowerCase().replace(" ", "_") : r);
  const clickable = !!p.drill && (p.drill.key === "r" || p.drill.key === "games_id");
  return (
    <div ref={ref} className="w-full overflow-x-auto">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
        {d.yTitle && <text x={6} y={12} fill={c.axis} fontSize={10}>{d.yTitle}</text>}
        {rowOrder.map((r, i) => (
          <text key={r} x={left - 6} y={8 + i * ch + ch / 2 + 3.5} textAnchor="end" fontSize={11} fill={hover?.r === r ? c.text : c.axis} fontWeight={hover?.r === r ? 700 : 400}
            style={{ cursor: clickable ? "pointer" : "default" }} onClick={() => clickable && onPick(p.drill!.type, rowKey(r))}>{trunc(r, 24)}</text>))}
        {colOrder.map((cc, j) => {
          const x = left + j * cw + cw / 2, y = 8 + rowOrder.length * ch + 12;
          const show = colOrder.length <= 24 || j % Math.ceil(colOrder.length / 24) === 0;
          return show ? <text key={cc} x={x} y={y} textAnchor={rotate ? "end" : "middle"} fontSize={10} fill={hover?.c === cc ? c.text : c.axis} transform={rotate ? `rotate(-55 ${x} ${y})` : undefined}>{trunc(cc, 24)}</text> : null;
        })}
        {rowOrder.map((r, i) => colOrder.map((cc, j) => {
          const cell = cellMap.get(`${r}|${cc}`);
          const x = left + j * cw, y = 8 + i * ch;
          if (!cell) return <rect key={`${i}-${j}`} x={x} y={y} width={cw - 1} height={ch - 1} fill={c.grid} fillOpacity={0.25} rx={2} onMouseEnter={() => setHover({ r, c: cc })} onMouseLeave={() => setHover(null)} />;
          const f = color(cell.v);
          const txt = lum(f) > 0.55 ? "#111" : "#fff";
          return (
            <g key={`${i}-${j}`} onMouseEnter={() => setHover({ r, c: cc })} onMouseLeave={() => setHover(null)} onClick={() => clickable && onPick(p.drill!.type, rowKey(r))} style={{ cursor: clickable ? "pointer" : "default" }}>
              <rect x={x} y={y} width={cw - 1} height={ch - 1} fill={f} rx={2} stroke={hover?.r === r && hover?.c === cc ? c.text : "none"} strokeWidth={1.5} />
              {showNum && <text x={x + cw / 2} y={y + ch / 2 + 3.5} textAnchor="middle" fontSize={10} fill={txt} style={{ pointerEvents: "none" }}>
                {d.showPct && cell.pct !== undefined ? `${fmtCell(cell.v, d.format)} (${cell.pct}%)` : d.zeroColor && cell.n !== undefined ? fmtCell(cell.n, "int") : fmtCell(cell.v, d.format)}</text>}
              <title>{cell.label ?? `${r} / ${cc}: ${num(cell.v)}`}</title>
            </g>);
        }))}
        {d.xTitle && <text x={left + (cw * colOrder.length) / 2} y={H - 4} textAnchor="middle" fontSize={11} fill={c.axis}>{d.xTitle}</text>}
        {d.colLabel && <text x={left + (cw * colOrder.length) / 2} y={H - 3} textAnchor="middle" fontSize={11} fill={c.axis}>{d.colLabel}</text>}
        {/* legend */}
        <defs><linearGradient id={`hm-${p.id}`} x1="0" x2="0" y1="1" y2="0">{[0, .25, .5, .75, 1].map((t) => <stop key={t} offset={`${t * 100}%`} stopColor={color(lo + t * (hi - lo))} />)}</linearGradient></defs>
        <g transform={`translate(${W - legendW + 14}, 10)`}>
          <rect width={12} height={Math.min(140, rowOrder.length * ch)} fill={`url(#hm-${p.id})`} rx={2} />
          <text x={16} y={8} fontSize={10} fill={c.axis}>{fmtCell(hi, d.format)}{hi >= clip ? "+" : ""}</text>
          <text x={16} y={Math.min(140, rowOrder.length * ch)} fontSize={10} fill={c.axis}>{fmtCell(lo, d.format)}</text>
          <text x={0} y={Math.min(140, rowOrder.length * ch) + 14} fontSize={9} fill={c.axis}>{trunc(d.vLabel ?? "", 16)}</text>
        </g>
      </svg>
    </div>
  );
}

/* --------------------------------------------------------------------------------------------------------------------- box plot */
function Axis({ x, y, h, ticks, scale, c, label, fmt }: any) {
  return (<g>
    <line x1={x} x2={x} y1={y} y2={y + h} stroke={c.grid} />
    {ticks.map((t: number) => <g key={t}><line x1={x - 3} x2={x} y1={scale(t)} y2={scale(t)} stroke={c.axis} /><text x={x - 6} y={scale(t) + 3.5} textAnchor="end" fontSize={10} fill={c.axis}>{fmt ? fmt(t) : num(t, 2)}</text></g>)}
    {label && <text transform={`translate(12 ${y + h / 2}) rotate(-90)`} textAnchor="middle" fontSize={11} fill={c.axis}>{label}</text>}
  </g>);
}

export function BoxPlot({ p, height, onPick }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640;
  const horiz = d.orientation === "h";
  const g: any[] = d.groups;
  const all = g.flatMap((q) => [q.min, q.max, ...(q.outliers ?? [])]);
  const lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.04;
  if (horiz) {
    const left = 120, top = 8, bot = 34, rh = 28, H = Math.max(height * 0.7, top + bot + g.length * rh);
    const sx = (v: number) => left + ((v - lo + pad) / (hi - lo + 2 * pad)) * (W - left - 14);
    const ticks = niceTicks(lo, hi, 7);
    return (
      <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
        {ticks.map((t) => <g key={t}><line x1={sx(t)} x2={sx(t)} y1={top} y2={H - bot} stroke={c.grid} strokeDasharray="3 3" /><text x={sx(t)} y={H - bot + 14} textAnchor="middle" fontSize={10} fill={c.axis}>{num(t, 1)}</text></g>)}
        <text x={left + (W - left) / 2} y={H - 4} textAnchor="middle" fontSize={11} fill={c.axis}>{d.yLabel}</text>
        {g.map((q, i) => { const y = top + i * rh + rh / 2; const col = CAT[i % CAT.length]; return (
          <g key={q.name} style={{ cursor: p.drill ? "pointer" : "default" }} onClick={() => p.drill && onPick(p.drill.type, q.name)}>
            <text x={left - 8} y={y + 4} textAnchor="end" fontSize={11} fill={c.axis}>{trunc(q.name, 18)}</text>
            <line x1={sx(q.min)} x2={sx(q.max)} y1={y} y2={y} stroke={col} />
            <rect x={sx(q.q1)} y={y - 8} width={Math.max(1, sx(q.q3) - sx(q.q1))} height={16} fill={col} fillOpacity={0.55} stroke={col} rx={2} />
            <line x1={sx(q.median)} x2={sx(q.median)} y1={y - 8} y2={y + 8} stroke={c.text} strokeWidth={2} />
            {(q.outliers ?? []).map((o: number, k: number) => <circle key={k} cx={sx(o)} cy={y} r={1.8} fill={col} fillOpacity={0.5} />)}
            <title>{`${q.name}: median ${num(q.median)}, IQR ${num(q.q1)}-${num(q.q3)}, whiskers ${num(q.min)}-${num(q.max)}, n=${num(q.n, 0)}, outliers ${num(q.n_outliers ?? 0, 0)}`}</title>
          </g>); })}
      </svg></div>);
  }
  const left = 56, top = 10, bot = 56, H = Math.max(height * 0.8, 260);
  const sy = (v: number) => top + (1 - (v - lo + pad) / (hi - lo + 2 * pad)) * (H - top - bot);
  const slot = (W - left - 10) / g.length;
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      <Axis x={left} y={top} h={H - top - bot} ticks={niceTicks(lo, hi, 7)} scale={sy} c={c} label={d.yLabel} />
      {g.map((q, i) => { const x = left + slot * i + slot / 2, bw = Math.min(70, slot * 0.55), col = CAT[i % CAT.length]; return (
        <g key={q.name}>
          <line x1={x} x2={x} y1={sy(q.max)} y2={sy(q.min)} stroke={col} />
          <rect x={x - bw / 2} y={sy(q.q3)} width={bw} height={Math.max(1, sy(q.q1) - sy(q.q3))} fill={col} fillOpacity={0.55} stroke={col} rx={2} />
          <line x1={x - bw / 2} x2={x + bw / 2} y1={sy(q.median)} y2={sy(q.median)} stroke={c.text} strokeWidth={2} />
          {(q.outliers ?? []).map((o: number, k: number) => <circle key={k} cx={x + ((k * 7) % 9 - 4)} cy={sy(o)} r={1.8} fill={col} fillOpacity={0.5} />)}
          <text x={x} y={H - bot + 14} textAnchor="end" fontSize={10} fill={c.axis} transform={`rotate(-30 ${x} ${H - bot + 14})`}>{trunc(q.name, 20)}</text>
          <title>{`${q.name}: median ${num(q.median)}, IQR ${num(q.q1)}-${num(q.q3)}, whiskers ${num(q.min)}-${num(q.max)}, n=${num(q.n, 0)}, outliers ${num(q.n_outliers ?? 0, 0)}`}</title>
        </g>); })}
    </svg></div>);
}

/* ------------------------------------------------------------------------------------------------------------------------ violin */
export function Violin({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640, H = Math.max(height * 0.9, 280), left = 56, top = 10, bot = 48;
  const g: any[] = d.groups;
  const lo = Math.min(...g.map((q) => q.x[0])), hi = Math.max(...g.map((q) => q.x[q.x.length - 1]));
  const sy = (v: number) => top + (1 - (v - lo) / (hi - lo)) * (H - top - bot);
  const slot = (W - left - 10) / g.length, half = slot * 0.42;
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      <Axis x={left} y={top} h={H - top - bot} ticks={niceTicks(lo, hi, 7)} scale={sy} c={c} label={d.yLabel} />
      {g.map((q, i) => {
        const x = left + slot * i + slot / 2, col = q.color ?? CAT[i % CAT.length];
        const right = q.x.map((v: number, k: number) => `${x + q.density[k] * half},${sy(v)}`);
        const leftp = q.x.map((v: number, k: number) => `${x - q.density[k] * half},${sy(v)}`).reverse();
        return (<g key={q.name}>
          <polygon points={[...right, ...leftp].join(" ")} fill={col} fillOpacity={0.5} stroke={col} />
          <line x1={x - half * 0.5} x2={x + half * 0.5} y1={sy(q.median)} y2={sy(q.median)} stroke={c.text} strokeWidth={2.5} />
          <text x={x} y={H - bot + 16} textAnchor="middle" fontSize={11} fill={c.axis}>{trunc(q.name, 22)}</text>
          <text x={x} y={H - bot + 30} textAnchor="middle" fontSize={9} fill={c.axis}>n={num(q.n, 0)}, median {num(q.median, 1)}</text>
          <title>{`${q.name}: median ${num(q.median)}, n=${num(q.n, 0)}`}</title>
        </g>);
      })}
      {d.note && <text x={W - 8} y={14} textAnchor="end" fontSize={10} fill={c.axis}>{d.note}</text>}
    </svg></div>);
}

/* ---------------------------------------------------------------------------------------------------------------------- timeline */
export function Timeline({ p, height, onPick }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640;
  const lanes: string[] = d.laneOrder ?? Array.from(new Set<string>(d.rows.map((r: any) => r.lane)));
  const lh = lanes.length > 40 ? 12 : lanes.length > 24 ? 16 : 22, left = Math.min(170, 14 + 6.2 * Math.max(...lanes.map((l) => l.length), 5)), top = 6, bot = 38;
  const H = Math.max(height * 0.5, top + bot + lanes.length * lh);
  const lo = Math.min(...d.rows.map((r: any) => r.start)), hi = Math.max(...d.rows.map((r: any) => r.end));
  const sx = (v: number) => left + ((v - lo) / (hi - lo || 1)) * (W - left - 14);
  const ticks = niceTicks(lo, hi, 9);
  const idx = new Map(lanes.map((l, i) => [l, i]));
  return (
    <div ref={ref} className="w-full overflow-x-auto"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      {ticks.map((t) => <g key={t}><line x1={sx(t)} x2={sx(t)} y1={top} y2={H - bot} stroke={c.grid} strokeDasharray="3 3" /><text x={sx(t)} y={H - bot + 13} textAnchor="middle" fontSize={10} fill={c.axis}>{d.unit === "year" ? Math.round(t) : num(t, 0)}</text></g>)}
      <text x={left + (W - left) / 2} y={H - 16} textAnchor="middle" fontSize={11} fill={c.axis}>{d.xLabel}</text>
      {lanes.map((l, i) => <text key={l} x={left - 6} y={top + i * lh + lh / 2 + 3.5} textAnchor="end" fontSize={lh < 14 ? 9 : 11} fill={c.axis} style={{ cursor: p.drill?.key === "lane" ? "pointer" : "default" }} onClick={() => p.drill?.key === "lane" && onPick(p.drill.type, l)}>{trunc(l, 26)}</text>)}
      {d.rows.map((r: any, k: number) => { const i = idx.get(r.lane); if (i === undefined) return null; return (
        <rect key={k} x={sx(r.start)} y={top + i * lh + 2} width={Math.max(3, sx(r.end) - sx(r.start) - 1)} height={lh - 4} rx={2} fill={r.color ?? CAT[0]} fillOpacity={0.9}
          style={{ cursor: p.drill?.key === "athlete_id" ? "pointer" : "default" }} onClick={() => p.drill?.key === "athlete_id" && r.athlete_id && onPick(p.drill.type, String(r.athlete_id))}><title>{r.label}</title></rect>); })}
      {(d.legend ?? []).length > 0 && <g transform={`translate(${left}, ${H - 8})`}>{d.legend.map((l: any, i: number) => <g key={l.name} transform={`translate(${i * 90}, 0)`}><rect width={10} height={10} y={-9} fill={l.color} rx={2} /><text x={14} y={0} fontSize={10} fill={c.axis}>{l.name}</text></g>)}</g>}
    </svg></div>);
}

/* ------------------------------------------------------------------------------------------------------------------ forest plot */
export function Forest({ p }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640, left = 210, right = 24, labelW = 150, rh = 28;
  const rows: any[] = d.rows;
  const panels: string[] = d.panels ? Array.from(new Set(rows.map((r) => r.panel))) : [""];
  const blocks = panels.map((pn) => {
    const rs = d.panels ? rows.filter((r) => r.panel === pn) : rows;
    const lows = rs.map((r) => r.lo ?? r.est), highs = rs.map((r) => r.hi ?? r.est);
    let lo = Math.min(...lows, d.ref ?? Infinity), hi = Math.max(...highs, d.ref ?? -Infinity);
    if (d.log) { lo = Math.min(lo, 0.9); }
    const pad = (hi - lo || 1) * 0.12;
    return { pn, rs, lo: lo - (d.log ? 0 : pad), hi: hi + (d.log ? 0 : pad) };
  });
  const sec = (b: any) => 30 + b.rs.length * rh + 26;
  const H = blocks.reduce((a, b) => a + sec(b), 6);
  let y0 = 6;
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      {blocks.map((b) => {
        const top = y0; y0 += sec(b);
        const sx = d.log ? (v: number) => left + ((Math.log(Math.max(v, 1e-6)) - Math.log(b.lo)) / (Math.log(b.hi) - Math.log(b.lo))) * (W - left - right - labelW) : (v: number) => left + ((v - b.lo) / (b.hi - b.lo)) * (W - left - right - labelW);
        const ticks = d.log ? [0.25, 0.5, 1, 1.5, 2, 3, 5].filter((t) => t >= b.lo && t <= b.hi) : niceTicks(b.lo, b.hi, 6);
        const ay = top + 30 + b.rs.length * rh;
        return (<g key={b.pn}>
          {d.panels && <text x={6} y={top + 14} fontSize={12} fontWeight={700} fill={c.text}>{b.pn}</text>}
          {ticks.map((t: number) => <g key={t}><line x1={sx(t)} x2={sx(t)} y1={top + 24} y2={ay} stroke={c.grid} strokeDasharray="3 3" /><text x={sx(t)} y={ay + 12} textAnchor="middle" fontSize={10} fill={c.axis}>{num(t, 2)}</text></g>)}
          {d.ref !== undefined && sx(d.ref) >= left && <line x1={sx(d.ref)} x2={sx(d.ref)} y1={top + 24} y2={ay} stroke="#DF0024" strokeWidth={1.5} strokeDasharray="4 3" />}
          {b.rs.map((r: any, i: number) => { const y = top + 24 + i * rh + rh / 2, col = CAT[(d.panels ? 0 : i) % CAT.length]; return (
            <g key={r.name + i}>
              <text x={left - 8} y={y + 4} textAnchor="end" fontSize={11} fill={c.text}>{trunc(r.name, 32)}</text>
              {r.lo !== undefined && !d.noInterval && <line x1={sx(r.lo)} x2={sx(r.hi)} y1={y} y2={y} stroke={col} strokeWidth={2.5} />}
              {r.lo !== undefined && !d.noInterval && <><line x1={sx(r.lo)} x2={sx(r.lo)} y1={y - 5} y2={y + 5} stroke={col} /><line x1={sx(r.hi)} x2={sx(r.hi)} y1={y - 5} y2={y + 5} stroke={col} /></>}
              <rect x={sx(r.est) - 5} y={y - 5} width={10} height={10} fill={col} transform={`rotate(45 ${sx(r.est)} ${y})`} />
              <text x={W - right} y={y + 4} textAnchor="end" fontSize={10} fill={c.axis}>{num(r.est, 3)}{r.lo !== undefined && !d.noInterval ? ` [${num(r.lo, 3)}, ${num(r.hi, 3)}]` : ""}</text>
              <title>{`${r.name}: ${num(r.est, 4)}${r.lo !== undefined && !d.noInterval ? ` (95% CI ${num(r.lo, 4)} to ${num(r.hi, 4)})` : ""}${r.p !== undefined ? `, p = ${r.p < 1e-4 ? r.p.toExponential(2) : r.p.toFixed(4)}` : ""} ${r.unit ?? ""}`}</title>
            </g>); })}
          <text x={left + (W - left - right - labelW) / 2} y={ay + 24} textAnchor="middle" fontSize={10} fill={c.axis}>{d.panels ? b.rs[0]?.unit?.split("(")[0] : d.xLabel}</text>
        </g>);
      })}
    </svg></div>);
}

/* ----------------------------------------------------------------------------------------------------------------- error bars */
export function ErrorBars({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640, H = Math.max(height * 0.9, 300), left = 56, top = 10, bot = 96;
  const rows: any[] = d.rows;
  const lo0 = Math.min(...rows.map((r) => r.lo)), hi0 = Math.max(...rows.map((r) => r.hi)), pad = (hi0 - lo0) * 0.25 || 1;
  const lo = lo0 - pad, hi = hi0 + pad;
  const sy = (v: number) => top + (1 - (v - lo) / (hi - lo)) * (H - top - bot);
  const slot = (W - left - 10) / rows.length;
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      <Axis x={left} y={top} h={H - top - bot} ticks={niceTicks(lo, hi, 6)} scale={sy} c={c} label={d.yLabel} />
      {rows.map((r, i) => { const x = left + slot * i + slot / 2, col = r.color ?? CAT[i % CAT.length]; return (
        <g key={r.name}>
          <line x1={x} x2={x} y1={sy(r.hi)} y2={sy(r.lo)} stroke={col} strokeWidth={2.5} />
          <line x1={x - 7} x2={x + 7} y1={sy(r.hi)} y2={sy(r.hi)} stroke={col} strokeWidth={2.5} /><line x1={x - 7} x2={x + 7} y1={sy(r.lo)} y2={sy(r.lo)} stroke={col} strokeWidth={2.5} />
          <circle cx={x} cy={sy(r.value)} r={5.5} fill={col} stroke={c.tooltipBg} />
          <text x={x} y={H - bot + 14} textAnchor="end" fontSize={10} fill={c.axis} transform={`rotate(-40 ${x} ${H - bot + 14})`}>{trunc(r.name, 26)}</text>
          <title>{`${r.name}: mean ${num(r.value, 2)} (95% CI ${num(r.lo, 2)} to ${num(r.hi, 2)}), n = ${num(r.n, 0)}`}</title>
        </g>); })}
    </svg></div>);
}

/* ----------------------------------------------------------------------------------------------------------- prediction interval */
export function IntervalChart({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const rows: any[] = d.rows, W = w0 || 640, left = 70, rh = 30, top = 8, bot = 52, H = Math.max(height * 0.6, top + bot + rows.length * rh);
  const lo = Math.min(...rows.flatMap((r) => [r.lo, r.actual, r.pred])), hi = Math.max(...rows.flatMap((r) => [r.hi, r.actual, r.pred]));
  const pad = (hi - lo) * 0.05;
  const sx = (v: number) => left + ((v - lo + pad) / (hi - lo + 2 * pad)) * (W - left - 16);
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      {niceTicks(lo, hi, 8).map((t) => <g key={t}><line x1={sx(t)} x2={sx(t)} y1={top} y2={H - bot} stroke={c.grid} strokeDasharray="3 3" /><text x={sx(t)} y={H - bot + 13} textAnchor="middle" fontSize={10} fill={c.axis}>{num(t, 0)}</text></g>)}
      <text x={left + (W - left) / 2} y={H - bot + 28} textAnchor="middle" fontSize={11} fill={c.axis}>{d.xLabel}</text>
      {rows.map((r, i) => { const y = top + i * rh + rh / 2; return (<g key={r.name}>
        <text x={left - 8} y={y + 4} textAnchor="end" fontSize={11} fill={c.text}>{r.name}</text>
        <line x1={sx(r.lo)} x2={sx(r.hi)} y1={y} y2={y} stroke="#56B4E9" strokeWidth={6} strokeLinecap="round" opacity={0.7} />
        <circle cx={sx(r.pred)} cy={y} r={4.5} fill="#0072B2" />
        <rect x={sx(r.actual) - 5} y={y - 5} width={10} height={10} fill={r.inside ? "#009E73" : "#D55E00"} transform={`rotate(45 ${sx(r.actual)} ${y})`} />
        <title>{`${r.name}: actual ${num(r.actual, 0)}, predicted ${num(r.pred, 1)}, 80% interval ${num(r.lo, 1)} to ${num(r.hi, 1)} - ${r.inside ? "inside" : "outside"}`}</title>
      </g>); })}
      <g transform={`translate(${left}, ${H - 8})`} fontSize={10} fill={c.axis}>
        <rect y={-9} width={22} height={6} rx={3} fill="#56B4E9" /><text x={28}>{d.intervalLabel}</text>
        <circle cx={186} cy={-6} r={4.5} fill="#0072B2" /><text x={196}>{d.predLabel}</text>
        <rect x={262} y={-11} width={9} height={9} fill="#009E73" transform="rotate(45 266 -6)" /><text x={278}>{d.actualLabel} (inside)</text>
        <rect x={390} y={-11} width={9} height={9} fill="#D55E00" transform="rotate(45 394 -6)" /><text x={406}>{d.actualLabel} (outside)</text>
      </g>
    </svg></div>);
}

/* -------------------------------------------------------------------------------------------------------------------- beeswarm */
export function Beeswarm({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const feats: string[] = d.features, pts: any[] = d.points;
  const W = w0 || 640, left = 130, top = 8, bot = 52, lh = 38, H = Math.max(height * 0.7, top + bot + feats.length * lh);
  const m = Math.max(...pts.map((q) => Math.abs(q.shap)), 0.01) * 1.05;
  const sx = (v: number) => left + ((v + m) / (2 * m)) * (W - left - 70);
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      {niceTicks(-m, m, 6).map((t) => <g key={t}><line x1={sx(t)} x2={sx(t)} y1={top} y2={H - bot} stroke={t === 0 ? c.axis : c.grid} strokeDasharray={t === 0 ? undefined : "3 3"} /><text x={sx(t)} y={H - bot + 13} textAnchor="middle" fontSize={10} fill={c.axis}>{num(t, 1)}</text></g>)}
      <text x={left + (W - left - 70) / 2} y={H - bot + 30} textAnchor="middle" fontSize={11} fill={c.axis}>{d.xLabel}</text>
      {feats.map((f, i) => <text key={f} x={left - 8} y={top + i * lh + lh / 2 + 4} textAnchor="end" fontSize={11} fill={c.text}>{f}</text>)}
      {pts.map((q, k) => <circle key={k} cx={sx(q.shap)} cy={top + q.lane * lh + lh / 2 + q.jit * lh} r={2} fill={ramp(["#2166ac", "#b8a8d8", "#b2182b"], q.v)} fillOpacity={0.7}><title>{`${feats[q.lane]} = ${num(q.raw, 3)}: SHAP ${num(q.shap, 3)}`}</title></circle>)}
      <defs><linearGradient id="shapleg" x1="0" x2="0" y1="1" y2="0"><stop offset="0" stopColor="#2166ac" /><stop offset="0.5" stopColor="#b8a8d8" /><stop offset="1" stopColor="#b2182b" /></linearGradient></defs>
      <g transform={`translate(${W - 54}, ${top + 4})`}><rect width={10} height={90} fill="url(#shapleg)" rx={2} /><text x={14} y={8} fontSize={10} fill={c.axis}>high</text><text x={14} y={90} fontSize={10} fill={c.axis}>low</text><text x={-2} y={106} fontSize={9} fill={c.axis}>feature value</text></g>
    </svg></div>);
}

/* ----------------------------------------------------------------------------------------------------------------------- pair plot */
export function PairPlot({ p }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const vars: string[] = d.vars, rows: any[] = d.rows, n = vars.length;
  const W = w0 || 640, left = 8, cell = Math.min(170, (W - left - 8) / n), H = cell * n + 22;
  const ext = vars.map((v) => { const a = rows.map((r) => r[v]); return [Math.min(...a), Math.max(...a)]; });
  const groups = Array.from(new Set(rows.map((r) => r.group)));
  const col = (g: string) => d.colors?.[g] ?? CAT[groups.indexOf(g) % CAT.length];
  return (
    <div ref={ref} className="w-full overflow-x-auto"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      {vars.map((vy, i) => vars.map((vx, j) => {
        const x0 = left + j * cell, y0 = 4 + i * cell, pad = 5;
        const sx = (v: number) => x0 + pad + ((v - ext[j][0]) / (ext[j][1] - ext[j][0] || 1)) * (cell - 2 * pad);
        const sy = (v: number) => y0 + cell - pad - ((v - ext[i][0]) / (ext[i][1] - ext[i][0] || 1)) * (cell - 2 * pad);
        let inner: any;
        if (i === j) {
          const bins = 14, cnt = new Array(bins).fill(0);
          rows.forEach((r) => { cnt[Math.min(bins - 1, Math.floor(((r[vx] - ext[j][0]) / (ext[j][1] - ext[j][0] || 1)) * bins))]++; });
          const mx = Math.max(...cnt);
          inner = cnt.map((k, b) => <rect key={b} x={x0 + pad + (b * (cell - 2 * pad)) / bins} width={(cell - 2 * pad) / bins - 1} y={y0 + cell - pad - (k / mx) * (cell - 2 * pad - 14)} height={(k / mx) * (cell - 2 * pad - 14)} fill="#9AA3AF" fillOpacity={0.7} />);
        } else inner = rows.map((r, k) => <circle key={k} cx={sx(r[vx])} cy={sy(r[vy])} r={1.6} fill={col(r.group)} fillOpacity={0.55}><title>{`${r.name}: ${vx} ${num(r[vx], 2)}, ${vy} ${num(r[vy], 2)}`}</title></circle>);
        return (<g key={`${i}-${j}`}><rect x={x0} y={y0} width={cell - 2} height={cell - 2} fill="none" stroke={c.grid} />{inner}
          {i === n - 1 && <text x={x0 + cell / 2} y={H - 6} textAnchor="middle" fontSize={10} fill={c.axis}>{vx}</text>}
          {j === 0 && <text x={x0 + 4} y={y0 + 12} fontSize={10} fill={c.axis}>{vy}</text>}</g>);
      }))}
    </svg>
    <div className="mt-1 flex gap-3 text-xs text-muted">{groups.map((g) => <span key={g} className="inline-flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-full" style={{ background: col(g) }} />{g}</span>)}</div></div>);
}

/* ------------------------------------------------------------------------------------------------------------------------- flow */
const FLOW_COL: Record<string, string> = { source: "#0072B2", blocked: "#999999", bronze: "#CD7F32", core: "#44AA99", silver: "#9AA3AF", gold: "#D4AF37", analytics: "#882255", serve: "#117733" };
export function Flow({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 760, nodes: any[] = d.nodes, cols = d.cols, rowsN = d.rows;
  const nw = Math.min(170, (W - 20) / cols - 22), nh = 62, gx = (W - 20 - cols * nw) / Math.max(cols - 1, 1), gy = 22, H = Math.max(height * 0.8, rowsN * (nh + gy) + 16);
  const pos = (n: any) => ({ x: 10 + n.col * (nw + gx), y: 8 + n.row * (nh + gy) });
  const byId = new Map(nodes.map((n) => [n.id, n]));
  return (
    <div ref={ref} className="w-full overflow-x-auto"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill={c.axis} /></marker></defs>
      {d.edges.map((e: any, i: number) => { const a = byId.get(e.from), b = byId.get(e.to); if (!a || !b) return null; const pa = pos(a), pb = pos(b);
        const x1 = pa.x + nw, y1 = pa.y + nh / 2, x2 = pb.x, y2 = pb.y + nh / 2, mx = (x1 + x2) / 2;
        return <path key={i} d={`M${x1} ${y1} C${mx} ${y1}, ${mx} ${y2}, ${x2 - 3} ${y2}`} fill="none" stroke={c.axis} strokeOpacity={0.6} strokeWidth={1.5} markerEnd="url(#arr)" />; })}
      {nodes.map((n) => { const q = pos(n), col = FLOW_COL[n.kind] ?? "#999"; const sub = String(n.sub ?? ""); const lines = sub.match(/.{1,27}(\s|$)/g)?.slice(0, 3) ?? [sub]; return (
        <g key={n.id}><rect x={q.x} y={q.y} width={nw} height={nh} rx={8} fill={col} fillOpacity={n.kind === "blocked" ? 0.15 : 0.18} stroke={col} strokeWidth={1.6} strokeDasharray={n.kind === "blocked" ? "5 3" : undefined} />
          <text x={q.x + 8} y={q.y + 16} fontSize={11.5} fontWeight={700} fill={c.text}>{trunc(n.label, Math.floor(nw / 6.6))}</text>
          {lines.map((l, i) => <text key={i} x={q.x + 8} y={q.y + 31 + i * 11} fontSize={9.5} fill={c.axis}>{l.trim()}</text>)}
          <title>{`${n.label}: ${n.sub}`}</title></g>); })}
    </svg></div>);
}

/* ------------------------------------------------------------------------------------------------------------------------ slope */
export function Slope({ p, height, onPick }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const rows: any[] = d.rows, W = w0 || 640, H = Math.max(height, 320), top = 28, bot = 14, lx = Math.min(210, W * 0.36), rx = W - Math.min(210, W * 0.36);
  const mx = Math.max(...rows.flatMap((r) => [r.from, r.to]), 1);
  const sy = (v: number) => top + (1 - v / mx) * (H - top - bot);
  const nudge = (vals: number[]) => { const idx = vals.map((v, i) => [sy(v), i]).sort((a, b) => a[0] - b[0]); const out = new Array(vals.length).fill(0); let last = -99; idx.forEach(([y, i]) => { const yy = Math.max(y, last + 13); out[i] = yy; last = yy; }); return out; };
  const ly = nudge(rows.map((r) => r.from)), ry = nudge(rows.map((r) => r.to));
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H + 20} viewBox={`0 0 ${W} ${H + 20}`} role="img" aria-label={p.title}>
      <text x={lx} y={14} textAnchor="middle" fontSize={12} fontWeight={700} fill={c.text}>{d.left}</text>
      <text x={rx} y={14} textAnchor="middle" fontSize={12} fontWeight={700} fill={c.text}>{d.right}</text>
      {rows.map((r, i) => { const col = r.to > r.from ? "#009E73" : r.to < r.from ? "#D55E00" : "#999"; return (
        <g key={r.name} style={{ cursor: p.drill ? "pointer" : "default" }} onClick={() => p.drill && onPick(p.drill.type, r.noc)}>
          <line x1={lx} y1={sy(r.from)} x2={rx} y2={sy(r.to)} stroke={col} strokeWidth={2} strokeOpacity={0.85} />
          <circle cx={lx} cy={sy(r.from)} r={3.5} fill={col} /><circle cx={rx} cy={sy(r.to)} r={3.5} fill={col} />
          <text x={lx - 8} y={ly[i] + 3.5} textAnchor="end" fontSize={10.5} fill={c.text}>{trunc(r.name, 28)} {num(r.from, 0)}</text>
          <text x={rx + 8} y={ry[i] + 3.5} fontSize={10.5} fill={c.text}>{num(r.to, 0)} {trunc(r.name, 28)}</text>
          <title>{`${r.name}: ${num(r.from, 0)} to ${num(r.to, 0)} (${r.to - r.from >= 0 ? "+" : ""}${num(r.to - r.from, 0)})`}</title>
        </g>); })}
      <text x={W / 2} y={H + 14} textAnchor="middle" fontSize={10} fill={c.axis}>{d.yLabel} (green = more medals, orange = fewer)</text>
    </svg></div>);
}
