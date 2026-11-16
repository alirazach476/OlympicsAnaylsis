import { Link } from "react-router-dom";
import { ReactNode } from "react";
import { EditionRecord } from "../../themes/olympicThemeEngine";
import { Flag } from "../ui";
import { ComingSoon, isUpcoming } from "./EditionGallery";

/**
 * Edition hero: the edition's own background artwork under a colour overlay, the large emblem on the left, name / host / season / dates,
 * and the official mascot standing on the right side of the composition (only when the asset collection has a mascot image).
 */
export function EditionHero({ edition, e, children }: { edition?: EditionRecord; e: any; children?: ReactNode }) {
  const a = edition?.assets;
  const mascot = a?.mascots?.[0];
  const upcoming = isUpcoming(e.year);
  return (
    <section className="relative mb-6 overflow-hidden rounded-2xl border border-line" data-testid="edition-hero" style={{ boxShadow: "0 30px 80px -40px var(--ed-glow)", minHeight: 260 }}>
      {a?.background && <img src={a.background} alt="" className="absolute inset-0 h-full w-full object-cover" />}
      <div className="absolute inset-0" style={{ background: "linear-gradient(100deg, transparent 0%, color-mix(in srgb, var(--ed-primary) 45%, transparent) 60%, color-mix(in srgb, var(--ed-secondary) 25%, transparent) 100%)" }} />
      <div className="absolute inset-0 bg-gradient-to-r from-bg via-bg/75 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-1.5" style={{ background: "linear-gradient(90deg, var(--ed-primary), var(--ed-secondary), var(--ed-accent))" }} />
      {mascot && (
        <img src={mascot.src} alt={`${e.host_city} ${e.year} mascot`} data-testid="hero-mascot"
          className="pointer-events-none absolute bottom-0 right-2 hidden h-[92%] max-w-[34%] object-contain object-bottom drop-shadow-[0_20px_30px_rgba(0,0,0,0.45)] md:block" />
      )}
      <div className={`relative flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:p-8 ${mascot ? "md:pr-[34%]" : ""}`}>
        {a?.logo ? <img src={a.logo} alt={`${e.host_city} ${e.year} emblem`} data-testid="hero-logo" className="h-32 w-32 shrink-0 rounded-2xl bg-white/95 object-contain p-2.5 shadow-2xl sm:h-44 sm:w-44" />
          : <div className="grid h-32 w-32 shrink-0 place-items-center rounded-2xl bg-surface2 text-xs text-muted">emblem not available</div>}
        <div className="min-w-0">
          <Link to={e.season === "summer" ? "/summer" : "/winter"} className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.25em] text-muted hover:text-accent">
            <span className="rounded-full px-2 py-0.5 text-[10px]" style={{ background: "var(--ed-primary)", color: "var(--ed-on-primary, #fff)" }}>{e.season}</span>{edition?.officialName ?? `${e.season} Olympics`}
          </Link>
          <h1 className="h-display mt-2 text-5xl leading-[0.9] sm:text-7xl">{e.host_city} <span style={{ color: "var(--ed-accent)" }}>{e.year}</span></h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span className="inline-flex items-center gap-2 font-semibold"><Flag noc={e.host_noc} /> {e.host_country}</span>
            {e.opening_date && <span className="text-muted">{e.opening_date} → {e.closing_date}</span>}
            {upcoming && <ComingSoon className="text-xs" />}
          </div>
          {children}
        </div>
      </div>
    </section>
  );
}
