import { CSSProperties, createContext, createElement, ReactNode, useContext, useEffect, useMemo, useState } from "react";

/** One pictogram image of one edition. `sport` is set only when the file name names the sport (checked against the warehouse sports list). */
export type Pictogram = { src: string; label: string | null; sport: string | null; sportId: number | null; discipline: string | null; sportLinked: boolean; linkedBy: string | null; duplicateOf: string | null; file_format: string; image_width?: number; image_height?: number };
export type Mascot = { src: string; name: string | null; nameRecorded: boolean; file_format: string; license: string; verification: string; image_width?: number; image_height?: number };
export type Meta = { file_format?: string; image_width?: number; image_height?: number; license: string; verification: string };
export type EditionTheme = { primary: string; secondary: string; accent: string; palette?: string[]; on_primary?: string; source: string };
export type EditionRecord = {
  editionId: string; name: string; officialName: string | null; season: "summer" | "winter"; year: number; hostCity: string; hostCountry: string;
  assets: { logo: string | null; logoMeta?: Meta; background: string | null; backgroundMeta?: Meta; mascots: Mascot[]; pictograms: Pictogram[]; posters: string[]; venues: string[] };
  theme: EditionTheme;
  completeness: { logo: boolean; background: boolean; mascot: boolean; pictograms: boolean; sportLinkedPictograms: boolean; theme: boolean; level: "complete" | "partial" | "neutral" };
};
export type Registry = { generatedAt: string; neutralTheme: EditionTheme; editions: Record<string, EditionRecord> };

const EMPTY: Registry = { generatedAt: "", neutralTheme: { primary: "#8a7a52", secondary: "#3f4a5c", accent: "#c9a227", source: "neutral historical theme" }, editions: {} };
export type Mode = "dark" | "light";

// ---- colour maths ---------------------------------------------------------------------------------------------------------------------------------------
export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return [parseInt(n.slice(0, 2), 16), parseInt(n.slice(2, 4), 16), parseInt(n.slice(4, 6), 16)];
}
export function rgbToHex(r: number, g: number, b: number) {
  return "#" + [r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
}
export function luminance(hex: string) {
  const [r, g, b] = hexToRgb(hex).map((v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
export function contrast(a: string, b: string) {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
function hslOf(hex: string): [number, number, number] {
  const [r, g, b] = hexToRgb(hex).map((v) => v / 255);
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
  if (mx === mn) return [0, 0, l];
  const d = mx - mn, s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
  const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, s, l];
}
function hexOfHsl(h: number, s: number, l: number) {
  const f = (n: number) => { const k = (n + h / 30) % 12; const a = s * Math.min(l, 1 - l); return l - a * Math.max(-1, Math.min(k - 3, Math.min(9 - k, 1))); };
  return rgbToHex(f(0) * 255, f(8) * 255, f(4) * 255);
}
/** Moves a colour's lightness (hue kept) until it reads against the page background (WCAG 3:1 for large text / UI), so an edition accent is never unreadable. */
export function readableOn(hex: string, bg: string, min = 3) {
  let [h, s, l] = hslOf(hex);
  const dark = luminance(bg) < 0.4;
  for (let i = 0; i < 40 && contrast(hexOfHsl(h, s, l), bg) < min; i++) l = Math.max(0.04, Math.min(0.96, l + (dark ? 0.02 : -0.02)));
  return hexOfHsl(h, s, l);
}
const BG = { dark: "#090d16", light: "#f4f6fa" };

/** CSS custom properties for an edition: the existing Tailwind tokens (--accent ...) are re-pointed at the edition's own colours, plus --ed-* tokens for the edition artwork. */
/** `assets` (the edition's own background and emblem) become --ed-bg-img / --ed-logo-img, used by the menu bar and every table header band. */
export function themeVars(theme: EditionTheme, mode: Mode, assets?: { background?: string | null; logo?: string | null }): CSSProperties {
  const accent = readableOn(theme.accent, BG[mode]);
  const primary = readableOn(theme.primary, BG[mode], 2.2);
  const triplet = (h: string) => hexToRgb(h).join(" ");
  const [r, g, b] = hexToRgb(theme.primary);
  // the edition's colour runs through every surface: page, cards, table heads, borders (mixed into the neutral tokens, so text contrast stays within WCAG)
  const mix = (base: string, c: string, t: number) => { const [a1, a2, a3] = hexToRgb(base), [b1, b2, b3] = hexToRgb(c); return `${Math.round(a1 + (b1 - a1) * t)} ${Math.round(a2 + (b2 - a2) * t)} ${Math.round(a3 + (b3 - a3) * t)}`; };
  const P = theme.primary, S = theme.secondary;
  const surfaces = mode === "dark"
    ? { "--bg": mix("#090d16", P, 0.07), "--surface": mix("#111827", P, 0.13), "--surface2": mix("#182134", P, 0.2), "--line": mix("#28344c", P, 0.32) }
    : { "--bg": mix("#f4f6fa", P, 0.05), "--surface": mix("#ffffff", P, 0.025), "--surface2": mix("#eef1f7", P, 0.09), "--line": mix("#d6dde9", P, 0.28) };
  const pal = (theme.palette?.length ? theme.palette : [P, S, theme.accent]).slice(0, 4);
  // the edition's darkest palette colour: the deep band behind table headers and panel titles (Paris 2024 -> its blue, not its gold)
  const deep = [...pal].sort((a, b) => luminance(a) - luminance(b))[0] ?? P;
  const stripe = pal.map((c, i) => `${c} ${(i * 100) / pal.length}% ${((i + 1) * 100) / pal.length}%`).join(", ");
  const url = (u?: string | null) => (u ? `url("${u}")` : "none");
  return {
    ...surfaces,
    "--ed-bg-img": url(assets?.background), "--ed-logo-img": url(assets?.logo),
    "--ed-stripe": `linear-gradient(90deg, ${stripe})`,
    "--ed-deep": deep,
    "--ed-wash": `linear-gradient(135deg, color-mix(in srgb, ${P} ${mode === "dark" ? 26 : 14}%, transparent) 0%, transparent 45%, color-mix(in srgb, ${S} ${mode === "dark" ? 20 : 10}%, transparent) 100%)`,
    "--ed-head": `color-mix(in srgb, ${primary} ${mode === "dark" ? 30 : 16}%, rgb(${surfaces["--surface2"]}))`,
    "--accent": triplet(accent),
    "--ed-accent": accent, "--ed-primary": primary, "--ed-secondary": theme.secondary, "--ed-on-primary": theme.on_primary ?? "#ffffff",
    "--ed-glow": `rgb(${r} ${g} ${b} / ${mode === "dark" ? 0.22 : 0.12})`,
    "--ed-tint": `rgb(${r} ${g} ${b} / ${mode === "dark" ? 0.10 : 0.06})`,
  } as CSSProperties;
}

// ---- registry ------------------------------------------------------------------------------------------------------------------------------------------
let cache: Promise<Registry> | null = null;
export function loadRegistry(): Promise<Registry> {
  cache ??= fetch("/assets/editions.json").then((r) => (r.ok ? r.json() : EMPTY)).catch(() => EMPTY);
  return cache;
}
const Ctx = createContext<Registry>(EMPTY);
export function EditionRegistryProvider({ children }: { children: ReactNode }) {
  const [reg, setReg] = useState<Registry>(EMPTY);
  useEffect(() => { loadRegistry().then(setReg); }, []);
  return createElement(Ctx.Provider, { value: reg }, children);
}
export const useRegistry = () => useContext(Ctx);

/** The edition record + its theme variables (neutral historical theme when the edition has no readable artwork). */
export function useEditionTheme(gamesId: string | undefined, mode: Mode = "dark") {
  const reg = useRegistry();
  const edition = gamesId ? reg.editions[gamesId] : undefined;
  const theme = edition?.theme ?? reg.neutralTheme;
  const style = useMemo(() => themeVars(theme, mode, edition?.assets), [theme, mode, edition]);
  return { edition, theme, style, neutral: !edition || !edition.completeness.theme };
}

export const SEASON_ORDER = ["summer", "winter"] as const;
export function groupPictograms(list: Pictogram[]) {
  const by = new Map<string, Pictogram[]>();
  for (const p of list) { const k = p.sportLinked ? (p.sport as string) : "Not linked to a sport"; by.set(k, [...(by.get(k) ?? []), p]); }
  return [...by.entries()].sort((a, b) => (a[0] === "Not linked to a sport" ? 1 : b[0] === "Not linked to a sport" ? -1 : a[0].localeCompare(b[0])));
}
