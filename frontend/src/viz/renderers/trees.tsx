import { useEffect, useMemo, useRef, useState } from "react";
import { useChartColors } from "../../lib/theme";
import { CAT, num, useSize } from "../util";
import type { RenderProps } from "../types";

const trunc = (s: any, n: number) => (String(s).length > n ? String(s).slice(0, n - 1) + "…" : String(s));

/* ------------------------------------------------------------------------------------------------------------------------ bracket */
function MatchBox({ m, x, y, w, c, tag }: any) {
  const h = 46;
  const row = (team: string, score: number, y0: number, win: boolean) => (
    <g>
      <text x={x + 8} y={y0} fontSize={11.5} fontWeight={win ? 700 : 400} fill={win ? c.text : c.axis}>{trunc(team, Math.floor((w - 40) / 6.4))}</text>
      <text x={x + w - 8} y={y0} textAnchor="end" fontSize={12} fontWeight={win ? 700 : 400} fill={win ? c.text : c.axis}>{score}</text>
    </g>);
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={7} fill={c.tooltipBg} stroke={tag === "Gold" ? "#D4AF37" : tag === "Bronze" ? "#CD7F32" : c.grid} strokeWidth={tag ? 2 : 1} />
      <line x1={x} x2={x + w} y1={y + h / 2} y2={y + h / 2} stroke={c.grid} />
      {row(m.a, m.sa, y + 17, m.winner === m.a)}
      {row(m.b, m.sb, y + 38, m.winner === m.b)}
      {m.date && <text x={x + w} y={y - 3} textAnchor="end" fontSize={9} fill={c.axis}>{m.date}</text>}
      <title>{`${m.a} ${m.sa} - ${m.sb} ${m.b}${m.date ? ` (${m.date})` : ""}`}</title>
    </g>
  );
}

export function Bracket({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640;
  const main = d.rounds.filter((r: any) => !/bronze/i.test(r.name)), bronze = d.rounds.find((r: any) => /bronze/i.test(r.name));
  const bw = Math.min(210, (W - 40) / (main.length + 0.2) - 30), gap = Math.max(30, (W - 20 - main.length * bw) / Math.max(main.length - 1, 1));
  const H = Math.max(height * 0.8, 300);
  const colX = (i: number) => 10 + i * (bw + gap);
  const centers: Record<string, number> = {};
  const els: any[] = [];
  main.forEach((r: any, i: number) => {
    const n = r.matches.length;
    r.matches.forEach((m: any, k: number) => {
      const cy = i === main.length - 1 ? 46 + (H - 150) / 2 : 46 + ((k + 0.5) * (H - 150)) / n;
      centers[`${i}-${k}`] = cy;
      els.push(<MatchBox key={`${i}-${k}`} m={m} x={colX(i)} y={cy - 23} w={bw} c={c} tag={m.label} />);
    });
    els.push(<text key={`t${i}`} x={colX(i)} y={16} fontSize={11} fontWeight={700} fill={c.text}>{r.name}</text>);
  });
  const lines: any[] = [];
  for (let i = 0; i < main.length - 1; i++) main[i].matches.forEach((_: any, k: number) => {
    const y1 = centers[`${i}-${k}`], y2 = centers[`${i + 1}-0`], x1 = colX(i) + bw, x2 = colX(i + 1), mx = (x1 + x2) / 2;
    lines.push(<path key={`l${i}-${k}`} d={`M${x1} ${y1} H${mx} V${y2} H${x2}`} fill="none" stroke={c.axis} strokeOpacity={0.7} />);
  });
  return (
    <div ref={ref} className="w-full overflow-x-auto"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      <text x={W - 6} y={H - 4} textAnchor="end" fontSize={10} fill={c.axis}>{d.title}</text>
      {lines}{els}
      {bronze && <g><text x={colX(main.length - 1)} y={H - 74} fontSize={11} fontWeight={700} fill={c.text}>{bronze.name}</text>
        <MatchBox m={bronze.matches[0]} x={colX(main.length - 1)} y={H - 64} w={bw} c={c} tag="Bronze" /></g>}
    </svg></div>
  );
}

/* -------------------------------------------------------------------------------------------------------------------------- tree */
export function KnockoutTree({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640;
  const { nodes, links, depth, leaves } = useMemo(() => {
    const nodes: any[] = [], links: any[] = [];
    let leafIdx = 0, maxDepth = 0;
    const walk = (n: any, dep: number, parent: any) => {
      maxDepth = Math.max(maxDepth, dep);
      const me: any = { n, dep, y: 0 };
      nodes.push(me);
      if (parent) links.push([parent, me]);
      if (!n.children?.length) me.y = leafIdx++;
      else { n.children.forEach((ch: any) => walk(ch, dep + 1, me)); const ys = nodes.filter((q) => links.some(([a, b]: any) => a === me && b === q)).map((q) => q.y); me.y = ys.reduce((a: number, b: number) => a + b, 0) / ys.length; }
      return me;
    };
    walk(d.root, 0, null);
    return { nodes, links, depth: maxDepth, leaves: Math.max(leafIdx, 1) };
  }, [d.root]);
  const nw = Math.min(190, (W - 20) / (depth + 1) - 24), cols = depth + 1, gx = (W - 20 - cols * nw) / Math.max(cols - 1, 1);
  const rh = 44, H = Math.max(height * 0.6, leaves * rh + 20);
  const X = (dep: number) => W - 10 - nw - dep * (nw + gx), Y = (y: number) => 12 + y * rh;
  return (
    <div ref={ref} className="w-full overflow-x-auto"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      {links.map(([a, b]: any, i: number) => <path key={i} d={`M${X(a.dep)} ${Y(a.y) + 17} H${(X(a.dep) + X(b.dep) + nw) / 2} V${Y(b.y) + 17} H${X(b.dep) + nw}`} fill="none" stroke={c.axis} strokeOpacity={0.6} />)}
      {nodes.map((q, i) => (<g key={i}>
        <rect x={X(q.dep)} y={Y(q.y)} width={nw} height={34} rx={6} fill={c.tooltipBg} stroke={q.dep === 0 ? "#D4AF37" : c.grid} strokeWidth={q.dep === 0 ? 2 : 1} />
        <text x={X(q.dep) + 7} y={Y(q.y) + 15} fontSize={10.5} fontWeight={600} fill={c.text}>{trunc(q.n.name, Math.floor(nw / 5.8))}</text>
        <text x={X(q.dep) + 7} y={Y(q.y) + 28} fontSize={9} fill={c.axis}>{q.n.meta ?? ""}{q.n.winner ? `  winner: ${trunc(q.n.winner, 16)}` : q.n.meta ? "  draw" : ""}</text>
        <title>{`${q.n.name} (${q.n.meta ?? ""})`}</title></g>))}
      <text x={10} y={H - 4} fontSize={10} fill={c.axis}>{d.note}</text>
    </svg></div>
  );
}

/* ---------------------------------------------------------------------------------------------------------------------- dendrogram */
export function Dendrogram({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640, left = 46, top = 10, bot = 62, H = Math.max(height, 340);
  const ic: number[][] = d.icoord, dc: number[][] = d.dcoord, leaves: string[] = d.leaves;
  const maxY = Math.max(...dc.flat()), maxX = Math.max(...ic.flat());
  const sx = (v: number) => left + (v / maxX) * (W - left - 8), sy = (v: number) => top + (1 - v / maxY) * (H - top - bot);
  const fs = Math.max(5.5, Math.min(9, (W - left) / leaves.length - 0.5));
  return (
    <div ref={ref} className="w-full"><svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title}>
      <text transform={`translate(12 ${top + (H - top - bot) / 2}) rotate(-90)`} textAnchor="middle" fontSize={11} fill={c.axis}>{d.yLabel}</text>
      {[0, 0.25, 0.5, 0.75, 1].map((t) => <g key={t}><line x1={left} x2={W - 8} y1={sy(t * maxY)} y2={sy(t * maxY)} stroke={c.grid} strokeDasharray="3 3" /><text x={left - 4} y={sy(t * maxY) + 3} textAnchor="end" fontSize={9} fill={c.axis}>{num(t * maxY, 0)}</text></g>)}
      {ic.map((xs, i) => <polyline key={i} points={xs.map((x, k) => `${sx(x)},${sy(dc[i][k])}`).join(" ")} fill="none" stroke={CAT[0]} strokeWidth={1.3} strokeOpacity={0.85} />)}
      {leaves.map((l, i) => { const x = sx(5 + i * 10); return <text key={l + i} x={x} y={H - bot + 8} fontSize={fs} fill={c.axis} textAnchor="end" transform={`rotate(-90 ${x} ${H - bot + 8})`}>{l}</text>; })}
    </svg></div>
  );
}

/* ------------------------------------------------------------------------------------------------------------------------- pca 3d */
export function Pca3D({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors();
  const [ref, w0] = useSize<HTMLDivElement>();
  const W = w0 || 640, H = Math.max(height, 380);
  const [rot, setRot] = useState({ yaw: 0.6, pitch: 0.35 });
  const [spin, setSpin] = useState(false);
  const drag = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => { if (!spin) return; const t = setInterval(() => setRot((r) => ({ ...r, yaw: r.yaw + 0.012 })), 33); return () => clearInterval(t); }, [spin]);
  const rows: any[] = d.rows;
  const norm = useMemo(() => {
    const mx = (k: string) => Math.max(...rows.map((r) => Math.abs(r[k])), 1e-9);
    const [a, b, e] = [mx("x"), mx("y"), mx("z")];
    return rows.map((r) => ({ ...r, nx: r.x / a, ny: r.y / b, nz: r.z / e }));
  }, [rows]);
  const groups = Array.from(new Set(rows.map((r) => r.group))).sort();
  const col = (g: string) => CAT[groups.indexOf(g) % CAT.length];
  const R = Math.min(W, H) * 0.38, cx = W / 2, cy = H / 2;
  const proj = (x: number, y: number, z: number) => {
    const cyw = Math.cos(rot.yaw), syw = Math.sin(rot.yaw), cp = Math.cos(rot.pitch), sp = Math.sin(rot.pitch);
    const x1 = x * cyw + z * syw, z1 = -x * syw + z * cyw;
    const y1 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;
    const f = 1 / (1 - z2 * 0.28);
    return { px: cx + x1 * R * f, py: cy - y1 * R * f, depth: z2, f };
  };
  const pts = norm.map((r) => ({ r, ...proj(r.nx, r.ny, r.nz) })).sort((a, b) => a.depth - b.depth);
  const axes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]].map((v, i) => ({ end: proj(v[0] * 1.15, v[1] * 1.15, v[2] * 1.15), org: proj(-v[0], -v[1], -v[2]), label: d.axes[i] }));
  return (
    <div ref={ref} className="w-full select-none">
      <div className="mb-1 flex gap-2 text-xs"><button className="btn" onClick={() => setSpin((s) => !s)}>{spin ? "Stop rotation" : "Auto-rotate"}</button><button className="btn" onClick={() => { setSpin(false); setRot({ yaw: 0.6, pitch: 0.35 }); }}>Reset view</button><span className="self-center text-muted">Drag to rotate</span></div>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={p.title} style={{ cursor: "grab", touchAction: "none" }}
        onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY }; (e.target as Element).setPointerCapture?.(e.pointerId); }}
        onPointerMove={(e) => { if (!drag.current) return; const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y; drag.current = { x: e.clientX, y: e.clientY }; setRot((r) => ({ yaw: r.yaw + dx * 0.01, pitch: Math.max(-1.4, Math.min(1.4, r.pitch + dy * 0.01)) })); }}
        onPointerUp={() => (drag.current = null)} onPointerLeave={() => (drag.current = null)}>
        {axes.map((a, i) => <g key={i}><line x1={a.org.px} y1={a.org.py} x2={a.end.px} y2={a.end.py} stroke={c.axis} strokeOpacity={0.5} /><text x={a.end.px} y={a.end.py} fontSize={11} fill={c.axis} dx={4}>{a.label}</text></g>)}
        {pts.map(({ r, px, py, f }, i) => <circle key={i} cx={px} cy={py} r={Math.max(2.2, (2.2 + (r.size ?? 1) * 0.9) * f)} fill={col(r.group)} fillOpacity={0.75} stroke={c.tooltipBg} strokeWidth={0.5}><title>{`${r.name} (${r.noc}) - ${r.group}`}</title></circle>)}
      </svg>
      <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted">{groups.map((g) => <span key={g} className="inline-flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-full" style={{ background: col(g) }} />{g}</span>)}</div>
    </div>
  );
}
