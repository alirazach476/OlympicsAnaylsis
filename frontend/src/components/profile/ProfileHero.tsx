import { Link } from "react-router-dom";
import { ReactNode } from "react";
import { MEDAL_COLORS, fmtInt } from "../../lib/fmt";
import { flagUrl } from "../../lib/fmt";
import { useRegistry } from "../../themes/olympicThemeEngine";

export function MedalStrip({ gold, silver, bronze }: { gold?: number; silver?: number; bronze?: number }) {
  return (
    <div className="flex items-center gap-3" aria-label={`${gold ?? 0} gold, ${silver ?? 0} silver, ${bronze ?? 0} bronze`}>
      {([["Gold", gold, MEDAL_COLORS.gold], ["Silver", silver, MEDAL_COLORS.silver], ["Bronze", bronze, MEDAL_COLORS.bronze]] as const).map(([k, v, c]) => (
        <div key={k} className="text-center"><div className="grid h-12 w-12 place-items-center rounded-full font-display text-xl font-bold text-black shadow-lg" style={{ background: `radial-gradient(circle at 30% 25%, #fff6, ${c} 55%)` }}>{fmtInt(v ?? 0)}</div><div className="mt-1 text-[10px] uppercase tracking-wider text-muted">{k}</div></div>))}
    </div>
  );
}

/** Editorial header for a country / athlete / sport: kicker, huge name, facts, optional flag backdrop and picture tile, medal strip. */
export function ProfileHero({ back, kicker, title, facts, flagNoc, tile, medals, children }: { back: { to: string; label: string }; kicker?: string; title: string; facts?: ReactNode; flagNoc?: string | null; tile?: ReactNode; medals?: { gold?: number; silver?: number; bronze?: number }; children?: ReactNode }) {
  return (
    <section className="relative mb-6 overflow-hidden rounded-2xl border border-line" data-testid="profile-hero">
      {flagNoc && <img src={flagUrl(flagNoc)} alt="" aria-hidden className="absolute -right-10 top-0 h-full w-2/3 object-cover opacity-25 [mask-image:linear-gradient(to_left,black,transparent)]" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />}
      <div className="absolute inset-0 bg-gradient-to-r from-bg via-bg/85 to-transparent" />
      <div className="relative grid gap-5 p-6 sm:p-8 md:grid-cols-[auto_1fr_auto] md:items-center">
        {tile && <div className="grid h-28 w-28 place-items-center rounded-2xl bg-white p-3 shadow-xl sm:h-32 sm:w-32">{tile}</div>}
        <div className="min-w-0">
          <Link to={back.to} className="text-xs uppercase tracking-widest text-muted hover:text-accent">← {back.label}</Link>
          {kicker && <div className="mt-2 text-xs font-semibold uppercase tracking-widest text-accent">{kicker}</div>}
          <h1 className="h-display text-4xl leading-[0.95] sm:text-6xl">{title}</h1>
          {facts && <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">{facts}</div>}
        </div>
        {medals && <MedalStrip {...medals} />}
      </div>
      {children}
    </section>
  );
}

/** Editions a country / athlete took part in, as emblem cards with their own colours (from the asset registry); click opens the edition. */
export function EditionStrip({ items }: { items: { gamesId: string; line1?: string; line2?: string; medals?: number }[] }) {
  const reg = useRegistry();
  if (!items.length) return null;
  return (
    <div className="scroll-thin mb-6 flex gap-3 overflow-x-auto pb-2" data-testid="edition-strip" aria-label="Editions">
      {items.map((it) => {
        const ed = reg.editions[it.gamesId];
        const c = ed?.theme.primary ?? "#888";
        return (
          <Link key={it.gamesId} to={`/edition/${it.gamesId}`} className="group card w-36 shrink-0 overflow-hidden transition hover:-translate-y-0.5 hover:border-accent" style={{ borderTop: `4px solid ${c}` }}>
            <div className="flex h-20 items-center justify-center overflow-hidden bg-white/95 p-2">{ed?.assets.logo ? <img src={ed.assets.logo} alt="" loading="lazy" className="h-16 w-full object-contain" /> : <span className="text-xs text-muted">no emblem</span>}</div>
            <div className="p-2.5"><div className="font-display text-xl leading-none">{ed?.year ?? it.gamesId.slice(0, 4)}<span className="ml-1 text-[10px] uppercase tracking-wider text-muted">{ed?.season ?? ""}</span></div>
              <div className="mt-0.5 truncate text-xs text-muted">{ed?.hostCity}</div>
              {it.line1 && <div className="mt-1 text-[11px]">{it.line1}</div>}{it.line2 && <div className="text-[11px] text-muted">{it.line2}</div>}
              {!!it.medals && <div className="mt-1 text-[11px] font-semibold" style={{ color: MEDAL_COLORS.gold }}>{it.medals} medal{it.medals > 1 ? "s" : ""}</div>}</div>
          </Link>);
      })}
    </div>
  );
}
