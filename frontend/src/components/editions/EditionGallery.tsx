import { ReactNode, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { OlympicRings } from "../OlympicRings";
import { useApi } from "../../lib/api";
import { fmtInt } from "../../lib/fmt";
import { useRegistry } from "../../themes/olympicThemeEngine";
import { Flag } from "../ui";
import { SportPictogram } from "../broadcast/design";

/** Last edition with results: anything later is an upcoming Games. */
export const LAST_HELD_YEAR = 2026;
export const isUpcoming = (year: number) => year > LAST_HELD_YEAR;

export function ComingSoon({ className = "" }: { className?: string }) {
  return <span data-testid="coming-soon" className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${className}`} style={{ background: "var(--ed-accent, #c9a227)", color: "#0b0f17" }}>Coming soon</span>;
}

export type GalleryItem = { id: string; name: string; city: string; country: string; noc?: string; year: number; season: string; logo?: string | null; primary?: string; accent?: string; athletes?: number; nocs?: number; events?: number; upcoming: boolean };

/** Every edition, held and upcoming, from /api/games?include_upcoming=1; the asset registry adds each edition's emblem and colours (a tile still shows when the registry is unavailable). */
export function useEditionList(season?: string): { items: GalleryItem[]; loading: boolean } {
  const reg = useRegistry();
  const games = useApi<any[]>("/games", { include_upcoming: 1 });
  const items = (games.data ?? [])
    .filter((g) => !season || g.season === season)
    .map((g): GalleryItem => {
      const e = reg.editions[g.games_id];
      return { id: g.games_id, name: e?.name ?? `${g.host_city} ${g.year}`, city: g.host_city, country: g.host_country, noc: g.host_noc, year: g.year, season: g.season, logo: e?.assets.logo,
        primary: e?.theme?.primary, accent: e?.theme?.accent, athletes: g.athletes, nocs: g.nocs, events: g.events, upcoming: !!g.upcoming || isUpcoming(g.year) };
    })
    .sort((a, b) => a.year - b.year || a.season.localeCompare(b.season));
  // the data server is unreachable: build the gallery from the edition registry shipped with the website (emblems, names, colours; no numbers)
  if (!items.length && games.error && Object.keys(reg.editions).length) {
    const fallback = Object.values(reg.editions)
      .filter((e) => !season || e.season === season)
      .map((e): GalleryItem => ({ id: e.editionId, name: e.name, city: e.hostCity, country: e.hostCountry, noc: HOST_NOC[e.hostCountry], year: e.year, season: e.season, logo: e.assets.logo,
        primary: e.theme?.primary, accent: e.theme?.accent, upcoming: isUpcoming(e.year) }))
      .sort((a, b) => a.year - b.year || a.season.localeCompare(b.season));
    return { items: fallback, loading: false };
  }
  return { items, loading: games.isLoading };
}

/** Host country -> NOC code, for the host flag when only the edition registry is available. */
const HOST_NOC: Record<string, string> = { Italy: "ITA", Japan: "JPN", Mexico: "MEX", "West Germany": "FRG", Germany: "GER", Canada: "CAN", "Soviet Union": "URS", "United States": "USA",
  "South Korea": "KOR", Spain: "ESP", Australia: "AUS", Greece: "GRE", China: "CHN", "United Kingdom": "GBR", "Great Britain": "GBR", Brazil: "BRA", France: "FRA", Austria: "AUT",
  Switzerland: "SUI", Yugoslavia: "YUG", Norway: "NOR", Russia: "RUS" };

/**
 * Edition gallery: one tile per Games with its own emblem (medium size), city, year, host flag and headline numbers, edged in the edition's colours.
 * `to` decides where a tile goes (edition page by default); upcoming Games always open their edition page and say Coming soon.
 */
export function EditionGallery({ items, to = (i) => `/edition/${i.id}`, size = "md", testid = "edition-gallery" }: { items: GalleryItem[]; to?: (i: GalleryItem) => string; size?: "sm" | "md"; testid?: string }) {
  const logo = size === "md" ? "h-24" : "h-16";
  return (
    <div className={`grid gap-3 ${size === "md" ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6" : "grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 2xl:grid-cols-8"}`} data-testid={testid}>
      {items.map((i) => (
        <Link key={i.id} to={i.upcoming ? `/edition/${i.id}` : to(i)} data-testid="edition-tile" data-edition={i.id} data-upcoming={i.upcoming || undefined} aria-label={`${i.name}, ${i.season} Olympics${i.upcoming ? ", coming soon" : ""}`}
          className="group relative flex flex-col overflow-hidden rounded-xl border border-line bg-surface transition hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline focus-visible:outline-2"
          style={{ borderTop: `4px solid ${i.primary ?? "#888"}`, ["--ed-accent" as any]: i.accent ?? "#c9a227" }}>
          <div className={`flex ${logo} items-center justify-center bg-white p-2`}>
            {i.logo ? <img src={i.logo} alt={`${i.name} emblem`} loading="lazy" className={`max-h-full max-w-full object-contain transition group-hover:scale-105 ${i.upcoming ? "opacity-80" : ""}`} /> : <span className="text-[10px] text-neutral-500">emblem not available</span>}
          </div>
          <div className="flex flex-1 flex-col gap-1 p-2.5">
            <div className="flex items-baseline justify-between gap-2"><span className="truncate font-display text-lg font-semibold leading-none">{i.city}</span><span className="font-display text-lg leading-none tabular-nums text-ink" style={{ boxShadow: `inset 0 -3px 0 ${i.primary ?? "#888"}` }}>{i.year}</span></div>
            <div className="flex items-center gap-1.5 text-[11px] text-muted"><Flag noc={i.noc} size={11} /><span className="truncate">{i.country}</span><span className="ml-auto capitalize">{i.season}</span></div>
            {i.upcoming ? <div className="mt-1"><ComingSoon /></div>
              : size === "md" && i.athletes != null && <div className="mt-1 grid grid-cols-3 gap-1 border-t border-line pt-1.5 text-center">
                  {[["Athletes", i.athletes], ["NOCs", i.nocs], ["Events", i.events]].map(([k, v]) => <div key={k as string}><div className="font-display text-sm leading-none tabular-nums">{fmtInt(v as number)}</div><div className="text-[9px] uppercase tracking-wider text-muted">{k}</div></div>)}
                </div>}
          </div>
        </Link>))}
    </div>
  );
}

/**
 * Season page panel for one edition: the header (emblem, city, year, flag, numbers) opens the edition page; below it every sport of that edition is a
 * pictogram link to /games/{edition}/sports/{sport} - that edition's own artwork, resolved in that edition's context. Upcoming Games say Coming soon.
 */
export function EditionSportsPanel({ i, sports }: { i: GalleryItem; sports?: { sport: string; events: number }[] }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-line bg-surface" data-testid="edition-panel" data-panel={i.id}
      style={{ borderTop: `4px solid ${i.primary ?? "#888"}`, ["--ed-accent" as any]: i.accent ?? "#c9a227" }}>
      <Link to={`/edition/${i.id}`} data-testid="edition-tile" data-edition={i.id} data-upcoming={i.upcoming || undefined} aria-label={`${i.name}, ${i.season} Olympics${i.upcoming ? ", coming soon" : ""}`}
        className="group flex items-center gap-3 p-3 transition hover:bg-[var(--ed-tint)]">
        <span className="grid h-20 w-20 shrink-0 place-items-center rounded-lg bg-white p-1.5 shadow">{i.logo ? <img src={i.logo} alt={`${i.name} emblem`} loading="lazy" className="max-h-full max-w-full object-contain transition group-hover:scale-105" /> : <span className="text-[9px] text-neutral-500">no emblem</span>}</span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2"><span className="truncate font-display text-2xl font-semibold leading-none">{i.city}</span><span className="font-display text-2xl leading-none tabular-nums text-ink" style={{ boxShadow: `inset 0 -3px 0 ${i.primary ?? "#888"}` }}>{i.year}</span></span>
          <span className="mt-1 flex items-center gap-1.5 text-xs text-muted"><Flag noc={i.noc} size={12} /><span className="truncate">{i.country}</span></span>
          {i.upcoming ? <span className="mt-1.5 inline-block"><ComingSoon /></span>
            : <span className="mt-1.5 flex gap-3 text-[11px] text-muted"><span><b className="font-display text-sm text-ink">{fmtInt(i.athletes)}</b> athletes</span><span><b className="font-display text-sm text-ink">{fmtInt(i.nocs)}</b> NOCs</span><span><b className="font-display text-sm text-ink">{fmtInt(i.events)}</b> events</span></span>}
        </span>
      </Link>
      {!i.upcoming && sports && sports.length > 0 && (
        <nav aria-label={`${i.name} sports`} className="flex flex-wrap gap-1.5 border-t border-line p-2.5" data-testid="edition-pictograms">
          {sports.map((s) => (
            <Link key={s.sport} to={`?ed=${i.id}&sport=${encodeURIComponent(s.sport)}`} title={`${s.sport} · ${s.events} event${s.events === 1 ? "" : "s"} · ${i.name}`} aria-label={`${s.sport} at ${i.name}`}
              data-testid="pictogram-link" data-sport={s.sport} className="rounded-md ring-[var(--ed-accent)] transition hover:-translate-y-0.5 hover:ring-2 focus-visible:ring-2">
              <SportPictogram sport={s.sport} gamesId={i.id} size={34} />
            </Link>))}
        </nav>)}
    </article>
  );
}

/**
 * Season page wall: one large card per edition - the official emblem on white, the edition's own background artwork faintly behind it, city, year,
 * host flag and headline numbers - edged and lit in the edition's colours. A card opens the edition page; upcoming Games say Coming soon.
 */
export function EditionLogoWall({ items }: { items: GalleryItem[] }) {
  const reg = useRegistry();
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5" data-testid="edition-gallery">
      {items.map((i) => {
        const bg = reg.editions[i.id]?.assets.background;
        return (
          <Link key={i.id} to={`/edition/${i.id}`} data-testid="edition-tile" data-edition={i.id} data-upcoming={i.upcoming || undefined} aria-label={`${i.name}, ${i.season} Olympics${i.upcoming ? ", coming soon" : ""}`}
            className="group relative flex flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-lg transition duration-300 hover:-translate-y-1 hover:shadow-2xl focus-visible:outline focus-visible:outline-2"
            style={{ ["--c" as any]: i.primary ?? "#888", boxShadow: "0 18px 40px -28px var(--c)" }}>
            <div className="relative flex aspect-[4/3] items-center justify-center overflow-hidden">
              {bg && <img src={bg} alt="" aria-hidden loading="lazy" className="absolute inset-0 h-full w-full object-cover opacity-60 transition duration-500 group-hover:scale-110 group-hover:opacity-80" />}
              <div className="absolute inset-0" style={{ background: "linear-gradient(160deg, color-mix(in srgb, var(--c) 55%, transparent), transparent 55%), linear-gradient(0deg, rgb(var(--surface)) 0%, transparent 45%)" }} />
              <span className="relative flex h-[68%] w-[68%] items-center justify-center overflow-hidden rounded-2xl bg-white p-3 shadow-2xl ring-4 ring-white/40 transition duration-300 group-hover:scale-105">
                {i.logo ? <img src={i.logo} alt={`${i.name} emblem`} loading="lazy" className={`h-full w-full object-contain ${i.upcoming ? "opacity-85" : ""}`} /> : <span className="text-xs text-neutral-500">emblem not available</span>}
              </span>
              <span className="absolute right-2 top-2 rounded-full px-2.5 py-0.5 font-display text-sm font-bold tabular-nums text-white shadow" style={{ background: "var(--c)" }}>{i.year}</span>
            </div>
            <div className="relative flex flex-1 flex-col gap-1 px-3 pb-3 pt-1">
              <span className="truncate font-display text-xl font-semibold uppercase leading-tight tracking-wide">{i.city}</span>
              <span className="flex items-center gap-1.5 text-xs text-muted"><Flag noc={i.noc} size={12} /><span className="truncate">{i.country}</span></span>
              {i.upcoming ? <span className="mt-1"><ComingSoon /></span>
                : i.athletes != null && <span className="mt-1.5 grid grid-cols-3 gap-1 border-t border-line pt-1.5 text-center">
                    {[["Athletes", i.athletes], ["NOCs", i.nocs], ["Events", i.events]].map(([k, v]) => <span key={k as string}><span className="block font-display text-base leading-none tabular-nums">{fmtInt(v as number)}</span><span className="text-[9px] uppercase tracking-wider text-muted">{k}</span></span>)}
                  </span>}
            </div>
            <span className="absolute inset-x-0 bottom-0 h-1 origin-left scale-x-0 transition duration-300 group-hover:scale-x-100" style={{ background: "var(--c)" }} />
          </Link>);
      })}
    </div>
  );
}

/** Horizontal strip of edition emblems with left / right arrows: a visual edition picker. `href(id)` builds each choice's link ("" = all editions). */
export function EditionLogoStrip({ items, selected, href, allLabel = "All editions" }: { items: { games_id: string; name: string; year: number; season: string }[]; selected: string; href: (id: string) => string; allLabel?: string }) {
  const reg = useRegistry();
  const box = useRef<HTMLDivElement>(null);
  const move = (dir: number) => box.current?.scrollBy({ left: dir * box.current.clientWidth * 0.8, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  useEffect(() => { const el = box.current?.querySelector<HTMLElement>("[aria-current=true]"); const p = box.current; if (el && p) p.scrollLeft = el.offsetLeft - p.clientWidth / 2 + el.clientWidth / 2; }, [selected]);
  const tile = (id: string, top: ReactNode, label: string, sub: string, color?: string) => {
    const on = selected === id;
    return (
      <Link key={id || "all"} to={href(id)} aria-current={on ? "true" : undefined} data-testid="strip-edition" data-edition={id || "all"} title={label}
        className={`group flex w-[104px] shrink-0 snap-start flex-col items-center gap-1.5 rounded-xl border p-2 text-center transition ${on ? "border-[var(--ed-accent)] bg-[var(--ed-tint)] shadow-lg ring-2 ring-[var(--ed-accent)]" : "border-line bg-surface hover:-translate-y-0.5 hover:border-[var(--ed-accent)]"}`}
        style={{ borderTop: `3px solid ${color ?? "var(--ed-accent)"}` }}>
        <span className="grid h-16 w-16 place-items-center rounded-lg bg-white p-1 shadow">{top}</span>
        <span className="w-full truncate text-[11px] font-semibold leading-tight">{label}</span>
        <span className="text-[10px] uppercase tracking-wider text-muted">{sub}</span>
      </Link>);
  };
  return (
    <div className="relative" data-testid="edition-strip">
      <button type="button" onClick={() => move(-1)} aria-label="Previous editions" className="absolute left-0 top-1/2 z-10 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full border border-line bg-surface/95 shadow-lg transition hover:border-[var(--ed-accent)] hover:text-[var(--ed-accent)]"><ChevronLeft className="h-5 w-5" /></button>
      <div ref={box} className="scroll-thin mx-12 flex snap-x gap-2 overflow-x-auto scroll-smooth py-1">
        {tile("", <OlympicRings size={52} />, allLabel, "every entry")}
        {items.map((e) => { const ed = reg.editions[e.games_id]; return tile(e.games_id, ed?.assets.logo ? <img src={ed.assets.logo} alt={`${e.name} emblem`} loading="lazy" className="max-h-full max-w-full object-contain" /> : <span className="text-[9px] text-neutral-500">no emblem</span>, e.name, `${e.season} ${e.year}`, ed?.theme.primary); })}
      </div>
      <button type="button" onClick={() => move(1)} aria-label="Next editions" className="absolute right-0 top-1/2 z-10 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full border border-line bg-surface/95 shadow-lg transition hover:border-[var(--ed-accent)] hover:text-[var(--ed-accent)]"><ChevronRight className="h-5 w-5" /></button>
    </div>
  );
}
