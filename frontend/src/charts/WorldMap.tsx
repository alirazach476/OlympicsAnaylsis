import { useMemo } from "react";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import countries from "i18n-iso-countries";
import world from "world-atlas/countries-110m.json";
import { useChartColors } from "../lib/theme";
import { fmtNum } from "../lib/fmt";

/** Choropleth of any per-country value. Geometry is bundled (world-atlas) so no map tiles are fetched.
 *  `rows` need an ISO alpha-3 code; historical delegations without one are listed under the map, never silently dropped. */
export default function WorldMap({ rows, valueKey, label, height = 360, onPick }: { rows: any[]; valueKey: string; label: string; height?: number; onPick?: (r: any) => void }) {
  const c = useChartColors();
  const { shapes, unmapped } = useMemo(() => {
    const fc: any = feature(world as any, (world as any).objects.countries);
    const proj = geoNaturalEarth1().fitSize([900, 460], fc);
    const path = geoPath(proj);
    const byNum = new Map<string, any>();
    const miss: any[] = [];
    rows.forEach((r) => {
      const n = r.iso_alpha3 ? countries.alpha3ToNumeric(r.iso_alpha3) : undefined;
      if (n) byNum.set(String(n), r); else if (Number(r[valueKey]) > 0) miss.push(r);
    });
    const max = Math.max(1, ...[...byNum.values()].map((r) => Number(r[valueKey]) || 0));
    return {
      shapes: fc.features.map((f: any) => {
        const r = byNum.get(String(Number(f.id)).padStart(3, "0")) ?? byNum.get(String(f.id));
        const v = r ? Number(r[valueKey]) || 0 : null;
        return { id: f.id, d: path(f) as string, r, v, t: v === null ? null : Math.sqrt(v / max) };
      }),
      unmapped: miss.sort((a, b) => b[valueKey] - a[valueKey]),
    };
  }, [rows, valueKey]);
  return (
    <div>
      <svg viewBox="0 0 900 460" role="img" aria-label={`World map: ${label}`} className="w-full" style={{ maxHeight: height }}>
        {shapes.map((s: any, i: number) => (
          <path key={s.id ?? `shape-${i}`} d={s.d} onClick={() => s.r && onPick?.(s.r)} className={s.r ? "cursor-pointer" : ""}
            fill={s.t === null ? c.grid : s.t === 0 ? "rgba(148,163,184,0.18)" : `rgba(244,195,0,${0.18 + s.t * 0.8})`} stroke={c.tooltipBg} strokeWidth={0.4}>
            {s.r && <title>{`${s.r.historical_name ?? s.r.noc_code}: ${fmtNum(s.v, 0)} ${label}`}</title>}
          </path>))}
      </svg>
      {unmapped.length > 0 && <p className="mt-2 text-xs text-muted">Not drawn (no modern ISO code - historical or neutral delegations): {unmapped.slice(0, 12).map((r) => `${r.historical_name ?? r.noc_code} (${fmtNum(r[valueKey], 0)})`).join(", ")}{unmapped.length > 12 ? "…" : ""}</p>}
    </div>
  );
}
