import { useEffect, useMemo, useRef, useState } from "react";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import countries from "i18n-iso-countries";
import world from "world-atlas/countries-110m.json";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useChartColors } from "../../lib/theme";
import { num, ramp, VIRIDIS } from "../util";
import type { RenderProps } from "../types";

let GEO: { id: string; d: string }[] | null = null;
function geometry() {
  if (GEO) return GEO;
  const fc: any = feature(world as any, (world as any).objects.countries);
  const path = geoPath(geoNaturalEarth1().fitSize([900, 460], fc));
  GEO = fc.features.map((f: any) => ({ id: String(Number(f.id)).padStart(3, "0"), d: path(f) as string }));
  return GEO!;
}

/** Choropleth with zoom / pan (wheel + drag) and, for multi-frame payloads, a year slider with play / pause. */
export function MapViz({ p, height, onPick }: RenderProps) {
  const d = p.data, c = useChartColors();
  const frames: any[] = d.frames;
  const [fi, setFi] = useState(frames.length - 1);
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState({ k: 1, x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => setFi(frames.length - 1), [frames.length]);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setFi((i) => { if (i >= frames.length - 1) { setPlaying(false); return i; } return i + 1; }), 650);
    return () => clearInterval(id);
  }, [playing, frames.length]);
  const geo = useMemo(geometry, []);
  const frame = frames[Math.min(fi, frames.length - 1)];
  const max = useMemo(() => Math.max(1, ...(d.fixedScale ? frames[frames.length - 1] : frame).rows.map((r: any) => r.v)), [frame, frames, d.fixedScale]);
  const byNum = useMemo(() => {
    const m = new Map<string, any>();
    frame.rows.forEach((r: any) => { const n = r.iso3 ? countries.alpha3ToNumeric(r.iso3) : undefined; if (n) m.set(String(n).padStart(3, "0"), r); });
    return m;
  }, [frame]);
  const color = (v: number) => (v <= 0 ? "rgba(148,163,184,0.18)" : ramp(VIRIDIS, Math.sqrt(v / max)));
  const zoom = (f: number) => setT((s) => ({ ...s, k: Math.max(1, Math.min(8, s.k * f)) }));
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        {frames.length > 1 && (<>
          <button className="btn" onClick={() => { if (fi >= frames.length - 1) setFi(0); setPlaying((x) => !x); }} aria-label={playing ? "Pause animation" : "Play animation"}>{playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />} {playing ? "Pause" : "Play"}</button>
          <input type="range" min={0} max={frames.length - 1} value={fi} onChange={(e) => { setPlaying(false); setFi(+e.target.value); }} className="w-56 accent-yellow-400" aria-label="Frame" />
          <span className="font-semibold">{frame.label}</span></>)}
        {frames.length === 1 && <span className="text-muted">{frame.label}</span>}
        <span className="ml-auto flex gap-1"><button className="btn" onClick={() => zoom(1.5)} aria-label="Zoom in">+</button><button className="btn" onClick={() => zoom(1 / 1.5)} aria-label="Zoom out">-</button><button className="btn" onClick={() => setT({ k: 1, x: 0, y: 0 })} aria-label="Reset view"><RotateCcw className="h-3.5 w-3.5" /></button></span>
      </div>
      <svg viewBox="0 0 900 460" role="img" aria-label={`World map: ${d.vLabel}`} className="w-full touch-none" style={{ maxHeight: height + 40, cursor: drag.current ? "grabbing" : "grab" }}
        onWheel={(e) => { e.preventDefault?.(); zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15); }}
        onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY }; }}
        onPointerMove={(e) => { if (!drag.current) return; const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y; drag.current = { x: e.clientX, y: e.clientY }; setT((s) => ({ ...s, x: s.x + dx / s.k, y: s.y + dy / s.k })); }}
        onPointerUp={() => (drag.current = null)} onPointerLeave={() => (drag.current = null)}>
        <rect width={900} height={460} fill="transparent" />
        <g transform={`scale(${t.k}) translate(${t.x} ${t.y})`}>
          {geo.map((g, gi) => { const r = byNum.get(g.id); return (
            <path key={`${g.id ?? "geo"}-${gi}`} d={g.d} fill={r ? color(r.v) : c.grid} fillOpacity={r ? 1 : 0.5} stroke={c.tooltipBg} strokeWidth={0.4 / t.k} style={{ cursor: r ? "pointer" : "default" }}
              onClick={() => r && p.drill && onPick(p.drill.type, r.noc)}>{r && <title>{`${r.name}: ${num(r.v, 0)} ${d.vLabel?.toLowerCase() ?? ""}`}</title>}</path>); })}
        </g>
        <defs><linearGradient id={`mapleg-${p.id}`}>{[0, .25, .5, .75, 1].map((q) => <stop key={q} offset={`${q * 100}%`} stopColor={ramp(VIRIDIS, q)} />)}</linearGradient></defs>
        <g transform="translate(20,430)"><rect width={160} height={8} fill={`url(#mapleg-${p.id})`} rx={2} /><text y={-3} fontSize={10} fill={c.axis}>{d.vLabel} (sqrt scale)</text><text y={20} fontSize={9} fill={c.axis}>0</text><text x={160} y={20} fontSize={9} fill={c.axis} textAnchor="end">{num(max, 0)}</text></g>
      </svg>
    </div>
  );
}
