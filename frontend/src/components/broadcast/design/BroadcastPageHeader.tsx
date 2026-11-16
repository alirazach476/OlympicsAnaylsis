import { ReactNode } from "react";
import { useEditionBrand } from "../../../themes/editionBrand";
import { EditionBranding, EditionLogo, EditionWatermark } from "./EditionBranding";

/**
 * Header of every page: section colour + title on the left, the selected edition's branding (emblem, name, season badge, host) on the right, edition accent rule and a low-opacity emblem watermark.
 * `section` supplies the page's own accent/icon; the edition supplies the broadcast identity. Dense data below never sits on the photo - this band has its own dark surface.
 */
export function BroadcastPageHeader({ title, subtitle, kicker, right, accent, icon, children }: { title: string; subtitle?: ReactNode; kicker?: string; right?: ReactNode; accent?: string; icon?: ReactNode; children?: ReactNode }) {
  const b = useEditionBrand();
  return (
    <header className="relative mb-6 min-w-0 max-w-full overflow-hidden rounded-2xl border border-line bg-surface" data-testid="page-header" data-edition={b.gamesId}>
      <div className="absolute inset-y-0 left-0 w-1.5" style={{ background: accent ?? "var(--ed-accent)" }} />
      <div className="absolute inset-x-0 bottom-0 h-0.5" style={{ background: "linear-gradient(90deg, var(--ed-primary), var(--ed-secondary), var(--ed-accent))" }} />
      <EditionWatermark gamesId={b.gamesId} className="absolute -right-6 -top-10 h-56 w-56" />
      <div className="relative flex flex-wrap items-end justify-between gap-4 p-5 pl-7 sm:p-6 sm:pl-8">
        <div className="min-w-0 max-w-3xl">
          {kicker && <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: accent ?? "var(--ed-accent)" }}>{icon}{kicker}</div>}
          <h1 className="h-display text-4xl leading-none sm:text-5xl">{title}</h1>
          {subtitle}
          {children}
        </div>
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-3">{right}{b.edition && <div className="hidden sm:block"><EditionBranding variant="compact" /></div>}{b.edition && <div className="sm:hidden"><EditionLogo size={40} /></div>}</div>
      </div>
    </header>
  );
}
