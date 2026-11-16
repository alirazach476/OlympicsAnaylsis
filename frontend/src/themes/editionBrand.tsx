import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo } from "react";
import { useLocation, useMatch, useNavigate, useSearchParams } from "react-router-dom";
import { useTheme } from "../lib/theme";
import { EditionRecord, Pictogram, themeVars, useRegistry } from "./olympicThemeEngine";
import type { CSSProperties } from "react";

export const DEFAULT_EDITION = "2024_summer";
const KEY = "selectedEdition";

/** Which sport name does a pictogram file name stand for? 'Artistic Gymnastics' -> Gymnastics, 'Cycling Track' -> Cycling (track), 'Swimming' -> Swimming. Returns the best verified match for ONE edition, or undefined. */
export function matchPictogram(pictograms: Pictogram[] | undefined, sportName: string | null | undefined): Pictogram | undefined {
  if (!pictograms?.length || !sportName) return undefined;
  const key = sportName.toLowerCase().trim();
  const linked = pictograms.filter((p) => p.sportLinked && p.sport);
  const exact = linked.filter((p) => p.sport!.toLowerCase() === key);
  // a more specific warehouse name stands for the base sport ('Artistic Gymnastics' -> Gymnastics, 'Cycling BMX Racing' -> Cycling); whole words only
  const loose = linked.filter((p) => new RegExp(`\\b${p.sport!.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(key) || p.sport!.toLowerCase().startsWith(key));
  // same word stem, at least 5 letters: 'Canoe Slalom' -> Canoeing (discipline slalom), 'Canoe Sprint' -> Canoeing (sprint)
  const first = key.split(/\s+/)[0];
  const stem = linked.filter((p) => { const w = p.sport!.toLowerCase().split(/\s+/)[0]; return (first.length >= 5 && w.startsWith(first)) || (w.length >= 5 && first.startsWith(w)); });
  // the requested name is a discipline filed under its parent sport: 'Trampolining' -> Gymnastics (discipline trampoline); shared prefix of 6+ letters
  const prefix = (a: string, b: string) => { let i = 0; while (i < a.length && a[i] === b[i]) i++; return i; };
  const disc = linked.filter((p) => p.discipline && prefix(p.discipline.toLowerCase(), first) >= 6);
  const pool = exact.length ? exact : loose.length ? loose : stem.length ? stem : disc;
  if (!pool.length) return undefined;
  // several pictograms for one sport (disciplines): prefer the one whose discipline words appear in the requested name, else the plain sport pictogram, else the first
  const byDiscipline = pool.find((p) => p.discipline && key.includes(p.discipline.toLowerCase()));
  return byDiscipline ?? pool.find((p) => !p.discipline) ?? pool[0];
}

export type EditionBrand = {
  gamesId: string;
  setGamesId: (id: string) => void;
  edition?: EditionRecord;
  style: CSSProperties;
  neutral: boolean;
  pictogramFor: (sportName?: string | null, gamesId?: string) => Pictogram | undefined;
  /** the registry record of any edition (not only the selected one) */
  editionOf: (gamesId?: string) => EditionRecord | undefined;
};

const Ctx = createContext<EditionBrand | null>(null);

/**
 * The selected edition for the WHOLE app. Source order: the edition in the route (/edition/:id), then ?games= in the URL, then the last choice (localStorage), then Paris 2024.
 * Every branded component (header, background, watermark, tables, scoreboards, pictograms) reads from here, so switching the edition restyles everything at once.
 */
export function EditionBrandProvider({ children }: { children: ReactNode }) {
  const reg = useRegistry();
  const { theme: mode } = useTheme();
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const loc = useLocation();
  // an edition in the path: /edition/:id, /games/:id/..., /medals/editions/:id, /countries/:noc/editions/:id
  const pathEdition = /^\/(?:edition|games|medals\/editions)\/([^/]+)/.exec(loc.pathname)?.[1] ?? /^\/countries\/[^/]+\/editions\/([^/]+)/.exec(loc.pathname)?.[1];
  const routeEdition = useMatch("/edition/:gamesId")?.params.gamesId ?? pathEdition;
  let stored = "";
  try { stored = localStorage.getItem(KEY) ?? ""; } catch { /* storage unavailable */ }
  // an edition that has not taken place yet (2028+) can be VIEWED on its own page but is never the app-wide selection: data pages would have nothing to show
  const hasData = (id?: string | null) => !!id && (!reg.editions[id] || reg.editions[id].year <= 2026);
  const wanted = routeEdition || [params.get("games"), stored].find((x) => hasData(x) && x) || DEFAULT_EDITION;
  const gamesId = reg.editions[wanted] || !Object.keys(reg.editions).length ? wanted : DEFAULT_EDITION;
  useEffect(() => { try { if (gamesId && Object.keys(reg.editions).length && hasData(gamesId)) localStorage.setItem(KEY, gamesId); } catch { /* storage unavailable */ } }, [gamesId, reg]);  // eslint-disable-line react-hooks/exhaustive-deps
  const setGamesId = useCallback((id: string) => {
    try { localStorage.setItem(KEY, id); } catch { /* storage unavailable */ }
    if (/^\/games\//.test(loc.pathname)) nav(/^\/games\/[^/]+\/?$/.test(loc.pathname) ? `/games/${id}` : `/games/${id}/results`);   // an event of another edition has another id: go to that edition's event index
    else if (pathEdition && loc.pathname !== `/edition/${routeEdition}`) nav(loc.pathname.replace(`/${routeEdition}`, `/${id}`) + loc.search);
    else if (routeEdition) nav(`/edition/${id}${loc.search}`);
    else setParams((p) => { const n = new URLSearchParams(p); n.set("games", id); return n; }, { replace: true });
  }, [routeEdition, pathEdition, nav, loc.pathname, loc.search, setParams]);
  const edition = reg.editions[gamesId];
  const theme = edition?.theme ?? reg.neutralTheme;
  const style = useMemo(() => themeVars(theme, mode, edition?.assets), [theme, mode, edition]);
  const value = useMemo<EditionBrand>(() => ({
    gamesId, setGamesId, edition, style, neutral: !edition || !edition.completeness.theme,
    pictogramFor: (sport, g) => matchPictogram((g ? reg.editions[g] : edition)?.assets.pictograms, sport),
    editionOf: (g) => (g ? reg.editions[g] : edition),
  }), [gamesId, setGamesId, edition, style, reg]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

const FALLBACK: EditionBrand = { gamesId: DEFAULT_EDITION, setGamesId: () => undefined, style: {}, neutral: true, pictogramFor: () => undefined, editionOf: () => undefined };
/** Safe outside the provider (unit tests render components alone): neutral theme, no assets. */
export const useEditionBrand = () => useContext(Ctx) ?? FALLBACK;
