import { ReactNode } from "react";
import { flagUrl } from "../../../lib/fmt";
import { useEditionBrand } from "../../../themes/editionBrand";

/** The edition's official emblem exactly as supplied: never stretched (object-contain), never recoloured, on a light tile so every emblem stays legible on the dark page. */
export function EditionLogo({ gamesId, size = 56, className = "", bare = false }: { gamesId?: string; size?: number; className?: string; bare?: boolean }) {
  const b = useEditionBrand();
  const ed = b.editionOf(gamesId);
  const src = ed?.assets.logo;
  if (!src) return <div data-testid="edition-logo" data-state="missing" title="Emblem not available" className={`grid shrink-0 place-items-center rounded-lg bg-surface2 text-[9px] text-muted ${className}`} style={{ width: size, height: size }}>no emblem</div>;
  return (
    <span data-testid="edition-logo" data-edition={ed.editionId} className={`inline-flex shrink-0 items-center justify-center overflow-hidden ${bare ? "" : "rounded-lg bg-white/95 p-1 shadow"} ${className}`} style={{ width: size, height: size }}>
      <img src={src} alt={`${ed.name} emblem`} className="max-h-full max-w-full object-contain" loading="lazy" />
    </span>
  );
}

const flagOf = (n?: string | null) => (n ? flagUrl(n) : undefined);

/** Edition name + year, season badge, host - in three sizes. `chip` for headers and table bands, `banner` for page tops. */
export function EditionBranding({ gamesId, variant = "chip", children }: { gamesId?: string; variant?: "chip" | "compact" | "banner"; children?: ReactNode }) {
  const b = useEditionBrand();
  const ed = b.editionOf(gamesId);
  if (!ed) return null;
  const season = <span className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest" style={{ background: "var(--ed-primary)", color: "var(--ed-on-primary)" }}>{ed.season}</span>;
  if (variant === "chip")
    return <span data-testid="edition-branding" className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/80 py-1 pl-1 pr-3 text-xs"><EditionLogo gamesId={ed.editionId} size={26} bare /><b className="max-w-[9rem] truncate font-display text-sm leading-none" title={ed.name}>{ed.name}</b>{season}</span>;
  if (variant === "compact")
    return <div data-testid="edition-branding" className="flex items-center gap-3"><EditionLogo gamesId={ed.editionId} size={48} /><div className="min-w-0 leading-tight"><div className="max-w-[16rem] truncate font-display text-xl" title={ed.name}>{ed.name}</div><div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted">{season}<span>{ed.hostCountry}</span></div></div>{children}</div>;
  return (
    <div data-testid="edition-branding" className="flex items-center gap-4"><EditionLogo gamesId={ed.editionId} size={84} /><div><div className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: "var(--ed-accent)" }}>{ed.season} Olympic Games</div>
      <div className="h-display text-4xl leading-none">{ed.hostCity} <span style={{ color: "var(--ed-accent)" }}>{ed.year}</span></div><div className="mt-1 text-sm text-muted">{ed.hostCountry}</div></div>{children}</div>
  );
}

/** A low-opacity emblem watermark. It decorates only: aria-hidden, never receives clicks, never covers text (very low opacity, behind content). */
export function EditionWatermark({ gamesId, className = "" }: { gamesId?: string; className?: string }) {
  const b = useEditionBrand();
  const src = b.editionOf(gamesId)?.assets.logo;
  if (!src) return null;
  return <img data-testid="edition-watermark" src={src} alt="" aria-hidden className={`pointer-events-none select-none object-contain opacity-[0.05] ${className}`} />;
}

/**
 * Page-wide branded background, in layers: the edition's own background image, a controlled dark overlay tinted with the edition colour, a subtle pattern in the edition colours and a low-opacity emblem watermark.
 * It sits BEHIND the content; panels and tables keep their own solid / translucent dark surfaces, so a busy photo is never directly behind text.
 */
export function EditionBackground() {
  const b = useEditionBrand();
  const ed = b.edition;
  return (
    <div aria-hidden data-testid="edition-background" data-edition={b.gamesId} className="pointer-events-none fixed inset-0 z-0 overflow-hidden" style={b.style}>
      {/* the edition's own background artwork, full page, under a readable veil */}
      {ed?.assets.background && <img src={ed.assets.background} alt="" className="absolute inset-0 h-full w-full scale-105 object-cover opacity-[0.30] blur-[1px] dark:opacity-[0.30]" />}
      <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgb(var(--bg) / 0.55), rgb(var(--bg) / 0.86) 45%, rgb(var(--bg) / 0.96))" }} />
      <div className="absolute inset-0" style={{ background: "var(--ed-wash)" }} />
      <div className="absolute inset-0" style={{ background: "radial-gradient(1000px 480px at 85% -5%, var(--ed-glow), transparent 70%), radial-gradient(800px 400px at 0% 100%, var(--ed-tint), transparent 70%)" }} />
      <EditionWatermark gamesId={b.gamesId} className="absolute -bottom-16 -right-16 h-[560px] w-[560px]" />
      <div className="ed-stripe absolute inset-x-0 top-0 h-1.5" />
    </div>
  );
}

/** Sport pictogram of the SELECTED (or given) edition, linked by verified file name. When no verified pictogram exists a neutral icon is shown and the asset is labelled unavailable. */
export function SportPictogram({ sport, gamesId, size = 28, label = false, className = "" }: { sport?: string | null; gamesId?: string; size?: number; label?: boolean; className?: string }) {
  const b = useEditionBrand();
  const p = b.pictogramFor(sport, gamesId);
  const ed = b.editionOf(gamesId);
  return (
    <span data-testid="sport-pictogram" data-state={p ? "verified" : "unavailable"} data-sport={sport ?? ""} className={`inline-flex items-center gap-2 ${className}`}>
      {p ? <span className="grid shrink-0 place-items-center overflow-hidden rounded bg-white p-0.5" style={{ width: size, height: size }} title={`${sport} pictogram, ${ed?.name ?? ""}`}><img src={p.src} alt={`${sport} pictogram, ${ed?.name ?? ""}`} className="max-h-full max-w-full object-contain" loading="lazy" /></span>
        : <span className="grid shrink-0 place-items-center rounded bg-surface2 text-muted" style={{ width: size, height: size }} title={`No verified ${sport ?? "sport"} pictogram for ${ed?.name ?? "this edition"}`}><span aria-label="pictogram unavailable" className="font-display font-bold leading-none" style={{ fontSize: Math.max(9, size * 0.36) }}>{String(sport ?? "?").split(/[\s-]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase()}</span></span>}
      {label && <span className="truncate">{sport}</span>}
    </span>
  );
}
