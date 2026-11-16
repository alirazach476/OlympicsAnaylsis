import { useEffect, useRef, useState } from "react";

export const MEDAL = { Gold: "#D4AF37", Silver: "#9AA3AF", Bronze: "#CD7F32" } as Record<string, string>;
/** Okabe-Ito based categorical palette: distinguishable under the common forms of colour-vision deficiency. */
export const CAT = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#999999", "#882255", "#44AA99", "#117733", "#AA4499"];

export function useSize<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const set = () => setW(Math.round(el.getBoundingClientRect().width));
    set();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const hex = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
export function ramp(stops: string[], t: number): string {
  const x = Math.max(0, Math.min(1, t)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const a = hex(stops[i]), b = hex(stops[i + 1]);
  const f = x - i;
  return `rgb(${Math.round(lerp(a[0], b[0], f))},${Math.round(lerp(a[1], b[1], f))},${Math.round(lerp(a[2], b[2], f))})`;
}
// viridis (sequential, colour-blind safe) and RdBu (diverging)
export const VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"];
export const RDBU = ["#2166ac", "#92c5de", "#f7f7f7", "#f4a582", "#b2182b"];
export function lum(rgb: string) {
  const m = rgb.match(/\d+/g)?.map(Number) ?? [0, 0, 0];
  return (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) / 255;
}

export function niceTicks(lo: number, hi: number, n = 5): number[] {
  if (!isFinite(lo) || !isFinite(hi)) return [];
  if (hi === lo) return [lo];
  const raw = (hi - lo) / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

export const num = (v: any, d = 2) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "–" : Number(v).toLocaleString("en-US", { maximumFractionDigits: d }));

export function fmtCell(v: number, f?: string) {
  if (v === null || v === undefined) return "";
  if (f === "pct0") return `${Math.round(v)}%`;
  if (f === "pct1") return `${v.toFixed(1)}%`;
  if (f === "dec2") return v.toFixed(2);
  if (f === "int") return Math.round(v).toLocaleString("en-US");
  return num(v, 2);
}
