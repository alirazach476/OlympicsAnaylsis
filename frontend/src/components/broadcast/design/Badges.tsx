import { ReactNode, useState } from "react";
import { useInRouterContext, useNavigate } from "react-router-dom";
import { flagUrl, MEDAL_COLORS } from "../../../lib/fmt";

/** Country flag from the local collection with its NOC code. Falls back to the code when no flag file exists. */
export function BroadcastCountryFlag({ noc, name, size = 20, showCode = false, className = "", link = true }: { noc?: string | null; name?: string | null; size?: number; showCode?: boolean; className?: string; /** false: not clickable */ link?: boolean }) {
  const [bad, setBad] = useState(false);
  const inRouter = useInRouterContext();
  const nav = inRouter ? useNavigate() : null;   // eslint-disable-line react-hooks/rules-of-hooks
  if (!noc) return null;
  // a flag or country name opens that country's page; inside another link (a row that already links somewhere) the outer link wins
  const go = (e: React.MouseEvent | React.KeyboardEvent) => { if (!nav || (e.currentTarget as HTMLElement).parentElement?.closest("a")) return; e.preventDefault(); e.stopPropagation(); nav(`/countries/${noc}`); };
  const clickable = link && !!nav && /^[A-Z]{3}$/.test(noc);
  return (
    <span data-testid="country-flag" className={`inline-flex items-center gap-1.5 ${clickable ? "cursor-pointer hover:text-[var(--ed-accent)] hover:underline" : ""} ${className}`} title={name ? `${name} (${noc})` : noc}
      {...(clickable ? { role: "link", tabIndex: 0, "data-href": `/countries/${noc}`, onClick: go, onKeyDown: (e: React.KeyboardEvent) => { if (e.key === "Enter") go(e); } } : {})}>
      {bad ? <span className="inline-grid place-items-center rounded-sm bg-surface2 text-[9px] font-semibold text-muted" style={{ width: size * 1.4, height: size }}>{noc}</span>
        : <img src={flagUrl(noc)} alt={`${name ?? noc} flag`} loading="lazy" onError={() => setBad(true)} className="inline-block rounded-sm object-cover shadow ring-1 ring-black/20" style={{ width: size * 1.4, height: size }} />}
      {(showCode || name) && <span className="truncate">{name ?? noc}{name && showCode ? <span className="ml-1 text-muted">{noc}</span> : null}</span>}
    </span>
  );
}

const MEDAL_TONE: Record<string, { c: string; label: string }> = { gold: { c: MEDAL_COLORS.gold, label: "Gold" }, silver: { c: MEDAL_COLORS.silver, label: "Silver" }, bronze: { c: MEDAL_COLORS.bronze, label: "Bronze" } };

/** Gold / silver / bronze as a recognisable medal disc (with the word, for accessibility and colour-blind readers). */
export function MedalChip({ medal, compact = false }: { medal?: string | null; compact?: boolean }) {
  const t = medal ? MEDAL_TONE[medal.toLowerCase()] : undefined;
  if (!t) return null;
  return (
    <span data-testid="medal-chip" data-medal={t.label} className="inline-flex items-center gap-1.5 font-semibold" title={t.label}>
      <i className="inline-block h-4 w-4 rounded-full shadow" style={{ background: `radial-gradient(circle at 30% 25%, #fff8, ${t.c} 60%)`, boxShadow: `0 0 0 1px ${t.c}66` }} aria-hidden />
      {!compact && <span style={{ color: t.c }}>{t.label}</span>}
    </span>
  );
}

/** Strong medal count: the big number inside a medal-coloured disc (used in medal tables). */
export function MedalCount({ medal, value }: { medal: "gold" | "silver" | "bronze"; value: number | string | null | undefined }) {
  const t = MEDAL_TONE[medal];
  return <span data-medal={t.label} className="inline-grid h-8 min-w-[2rem] place-items-center rounded-full px-1.5 font-display text-lg font-bold leading-none text-black tabular-nums" style={{ background: `radial-gradient(circle at 30% 25%, #fff7, ${t.c} 62%)` }} aria-label={`${value ?? 0} ${t.label.toLowerCase()}`}>{value ?? 0}</span>;
}

/** Record badge: shown only for a VERIFIED record (the record book lists this athlete, event and value). */
export function BroadcastRecordBadge({ level, title }: { level?: string | null; title?: string }) {
  if (!level) return null;
  const world = level.toLowerCase().startsWith("w");
  return <span data-testid="record-badge" data-level={world ? "world" : "olympic"} title={title ?? (world ? "World record" : "Olympic record")} className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-extrabold tracking-wider" style={{ background: world ? "#DF0024" : "var(--ed-accent)", color: world ? "#fff" : "var(--ed-on-primary, #000)" }}>{world ? "WR" : "OR"}</span>;
}

export function BroadcastSectionHeader({ title, kicker, right, children }: { title: string; kicker?: string; right?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2" data-testid="section-header">
      <div className="flex items-center gap-3"><span className="h-8 w-1.5 rounded-full" style={{ background: "var(--ed-accent)" }} /><div>{kicker && <div className="text-[10px] font-semibold uppercase tracking-[0.2em]" style={{ color: "var(--ed-accent)" }}>{kicker}</div>}<h2 className="h-display text-2xl leading-none sm:text-3xl">{title}</h2></div></div>
      <div className="flex items-center gap-2">{right}{children}</div>
    </div>
  );
}

/** A key number: edition-accent rule, big figure, label, optional hint. */
export function BroadcastStatPanel({ label, value, hint, accent }: { label: string; value: ReactNode; hint?: string; accent?: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-surface p-4" data-testid="stat-panel">
      <div className="absolute inset-y-0 left-0 w-1" style={{ background: accent ?? "var(--ed-accent)" }} />
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-1 font-display text-4xl font-bold leading-none tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}
