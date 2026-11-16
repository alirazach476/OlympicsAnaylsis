import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { SportPictogram } from "../broadcast/design";

const GENDER_TONE: Record<string, string> = { Men: "#3b82f6", Women: "#ec4899", Mixed: "#a855f7", Open: "#64748b" };
export const GenderChip = ({ g }: { g: string }) => <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider" style={{ background: `${GENDER_TONE[g] ?? "#64748b"}22`, color: GENDER_TONE[g] ?? "#64748b" }}>{g}</span>;

/**
 * Sports of one edition as medium pictogram cards (the edition's own pictogram artwork; a sport without a verified pictogram shows its name only - no substitute icon).
 * A card is a real link: `href(sport)` decides where it goes; `selected` marks the open sport.
 */
export function SportGrid({ sports, gamesId, href, selected, compact }: { sports: { sport: string; events: any[] }[]; gamesId: string; href: (sport: string) => string; selected?: string; compact?: boolean }) {
  return (
    <div className={`grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 ${compact ? "xl:grid-cols-4 2xl:grid-cols-5" : "xl:grid-cols-6"}`} data-testid="sport-grid">
      {sports.map((s) => {
        const on = selected === s.sport;
        return (
          <Link key={s.sport} to={href(s.sport)} data-testid="sport-card" data-sport={s.sport} aria-current={on ? "true" : undefined}
            className={`group flex flex-col items-center gap-2 rounded-xl border bg-surface p-3 text-center transition hover:-translate-y-0.5 hover:border-[var(--ed-accent)] ${on ? "border-[var(--ed-accent)] bg-[var(--ed-tint)] shadow-lg" : "border-line"}`}
            style={{ borderTop: "3px solid var(--ed-primary)" }}>
            <SportPictogram sport={s.sport} gamesId={gamesId} size={64} />
            <span className="font-display text-base font-semibold leading-tight">{s.sport}</span>
            <span className="text-[11px] text-muted">{s.events.length} event{s.events.length === 1 ? "" : "s"}</span>
          </Link>);
      })}
    </div>
  );
}

/** The events of one sport, each a link to its full results page. */
export function SportEventList({ sport, events, gamesId, compact }: { sport: string; events: any[]; gamesId: string; compact?: boolean }) {
  return (
    <section className="card overflow-hidden" data-testid="sport-section" style={{ borderTop: "3px solid var(--ed-accent)" }}>
      <header className="flex items-center justify-between gap-3 border-b border-line bg-surface2/70 px-4 py-2">
        <span className="flex items-center gap-3"><SportPictogram sport={sport} gamesId={gamesId} size={34} /><h2 className="h-display text-2xl">{sport}</h2></span>
        <span className="text-xs text-muted">{events.length} events</span>
      </header>
      <ul className="divide-y divide-line">
        {events.map((e: any) => (
          <li key={e.result_id}>
            {compact ? (
              <Link to={`/games/${gamesId}/events/${e.result_id}`} className="group flex items-center gap-3 px-4 py-3 text-sm transition hover:bg-[var(--ed-tint)]" data-testid="event-row">
                <span className="min-w-0 flex-1">
                  <span className="flex items-start justify-between gap-2"><span className="font-semibold leading-snug">{e.title}</span><GenderChip g={e.gender} /></span>
                  <span className="mt-1 block text-xs text-muted">{[e.date, e.participants, e.matches ? `${e.matches} matches` : "", e.heats ? `${e.heats} heats` : ""].filter(Boolean).join(" · ")}</span>
                </span>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-[var(--ed-accent)]" />
              </Link>
            ) : (
            <Link to={`/games/${gamesId}/events/${e.result_id}`} className="grid gap-1 px-4 py-2.5 text-sm transition hover:bg-[var(--ed-tint)] sm:grid-cols-[1fr_auto_auto_auto_auto] sm:items-center sm:gap-4" data-testid="event-row">
              <span className="font-semibold">{e.title}{e.status && e.status !== "Olympic" ? <span className="ml-2 text-[10px] uppercase text-muted">{e.status}</span> : null}</span>
              <GenderChip g={e.gender} />
              <span className="text-xs text-muted tabular-nums">{e.date ?? ""}</span>
              <span className="text-xs text-muted">{[e.participants, e.matches ? `${e.matches} matches` : "", e.heats ? `${e.heats} heats` : "", e.parts ? `${e.parts} parts` : ""].filter(Boolean).join(" · ")}</span>
              <ChevronRight className="hidden h-4 w-4 text-muted sm:block" />
            </Link>)}
          </li>))}
      </ul>
    </section>
  );
}
