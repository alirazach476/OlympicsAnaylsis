import { ReactNode } from "react";
import { useApi } from "../../lib/api";
import { Async } from "../ui";
import { BroadcastCountryFlag, EditionBranding, MedalChip, BroadcastRecordBadge, SportPictogram } from "./design";
import { useEditionBrand } from "../../themes/editionBrand";
import { TableFrame } from "../tables/TableFrame";
import { MatchScoreboard, stageInfo } from "./SportScoreboards";
import { CsvButton } from "../CsvButton";

export type Period = { label: string; scores: (number | null)[] };

/** How a sport's period columns are to be read. Football's "Half #n" columns are the running score after each half (Morocco 4-0: 1-0, then 4-0);
 *  basketball, handball, hockey, water polo and volleyball list the points of each half / period / set. */
export function family(sport?: string | null) {
  const s = (sport ?? "").toLowerCase();
  if (s === "football") return { kind: "football", cumulative: true, heading: "Score after each half", mainLabel: "Goals" };
  if (s === "volleyball" || s === "beach volleyball") return { kind: "volleyball", cumulative: false, heading: "Set by set", mainLabel: "Sets" };
  if (s === "basketball" || s === "3x3 basketball") return { kind: "basketball", cumulative: false, heading: "By half", mainLabel: "Points" };
  if (s === "ice hockey") return { kind: "icehockey", cumulative: false, heading: "By period", mainLabel: "Goals" };
  return { kind: "generic", cumulative: false, heading: "By period", mainLabel: "Score" };
}

const hasScore = (m: any) => m.home_score !== null && m.home_score !== undefined && m.away_score !== null && m.away_score !== undefined && !Number.isNaN(Number(m.home_score));
const num = (v: any) => (v === null || v === undefined ? "–" : String(v));
const shortLabel = (l: string) => l.replace(/Period #(\d+)/, "P$1").replace(/Half #(\d+)/, "H$1").replace(/Set #(\d+)/, "Set $1").replace(/Quarter #(\d+)/, "Q$1");

function Ribbon({ m }: { m: any }) {
  const st = stageInfo(m.stage);
  const stage = st.label;
  const gold = st.medal === "gold", bronze = st.medal === "bronze";
  return (
    <div className="flex items-center justify-between gap-2 px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider" style={{ background: gold ? "#D4AF37" : bronze ? "#CD7F32" : "var(--ed-primary)", color: gold || bronze ? "#1a1405" : "var(--ed-on-primary)" }}>
      <span className="flex min-w-0 items-center gap-2"><SportPictogram sport={m.sport_name} gamesId={m.games_id} size={20} /><span className="truncate">{stage}</span></span>
      <span className="shrink-0 opacity-90">{m.match_date}</span>
    </div>
  );
}

function PeriodStrip({ m, big = false }: { m: any; big?: boolean }) {
  const fam = family(m.sport_name);
  const periods: Period[] = m.periods ?? [];
  if (!periods.length) return null;
  const winner = (p: Period) => { const [a, b] = p.scores; if (a == null || b == null) return -1; return fam.cumulative ? -1 : a > b ? 0 : b > a ? 1 : -1; };
  return (
    <div className={big ? "mt-4" : "mt-2"} data-testid="period-strip" data-kind={fam.kind}>
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted">{fam.heading}</div>
      <div className="flex flex-wrap gap-1.5">
        {periods.map((p) => (
          <div key={p.label} className={`rounded-md border border-line bg-black/40 text-center ${big ? "px-3 py-2" : "px-2 py-1"}`} title={p.label}>
            <div className="text-[9px] uppercase tracking-wider text-muted">{shortLabel(p.label)}</div>
            <div className={`font-display tabular-nums text-white ${big ? "text-2xl" : "text-base"}`}>
              <span className={winner(p) === 0 ? "text-[var(--ed-accent)]" : ""}>{num(p.scores[0])}</span><span className="px-1 text-white/40">–</span><span className={winner(p) === 1 ? "text-[var(--ed-accent)]" : ""}>{num(p.scores[1])}</span>
            </div>
          </div>))}
      </div>
    </div>
  );
}

function TeamSide({ name, noc, win, dim, big }: { name: string; noc: string; win: boolean; dim: boolean; big?: boolean }) {
  return (
    <div className={`flex min-w-0 flex-col items-center gap-1.5 text-center ${dim ? "opacity-70" : ""}`}>
      <BroadcastCountryFlag noc={noc} size={big ? 40 : 28} />
      <span className={`w-full truncate ${big ? "text-lg" : "text-sm"} ${win ? "font-extrabold" : "font-medium"}`} title={name}>{name}</span>
      {win && <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "var(--ed-accent)" }}>Winner</span>}
    </div>
  );
}

/** Broadcast scoreboard for a team sport. Same skeleton (stage ribbon, flags, score bug, venue) but the lower strip is the sport's own: halves for football and basketball, sets for volleyball, periods for ice hockey. */
export function BroadcastScoreboard({ m, onOpen, big = false }: { m: any; onOpen?: (id: string) => void; big?: boolean }) {
  const fam = family(m.sport_name);
  const has = hasScore(m);
  const hs = Number(m.home_score), as = Number(m.away_score);
  const hw = has && hs > as, aw = has && as > hs;
  const body = (
    <>
      <Ribbon m={m} />
      <div className="px-4 py-4">
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
          <TeamSide name={m.home_team} noc={m.home_noc} win={hw} dim={has && aw} big={big} />
          <div className="text-center">
            <div className={`rounded-xl bg-black/75 font-display leading-none tabular-nums text-white shadow-inner ring-1 ring-white/10 ${big ? "px-6 py-3 text-6xl" : "px-4 py-2 text-4xl"}`} aria-label={has ? `${hs} to ${as}` : "no score recorded"}>
              <span className={hw ? "text-[var(--ed-accent)]" : ""}>{has ? hs : "–"}</span><span className="px-1.5 text-white/40">:</span><span className={aw ? "text-[var(--ed-accent)]" : ""}>{has ? as : "–"}</span>
            </div>
            <div className="mt-1 text-[9px] font-semibold uppercase tracking-widest text-muted">{fam.mainLabel}</div>
          </div>
          <TeamSide name={m.away_team} noc={m.away_noc} win={aw} dim={has && hw} big={big} />
        </div>
        <PeriodStrip m={m} big={big} />
      </div>
      {m.location && <div className="flex items-center justify-between gap-2 border-t border-line px-3 py-1.5 text-[11px] text-muted"><span className="truncate" title={m.location}>{m.location}</span>{m.event_name && <span className="shrink-0">{m.event_name}</span>}</div>}
    </>
  );
  return onOpen && m.result_id
    ? <button className="card w-full overflow-hidden text-left transition hover:border-[var(--ed-accent)]" data-testid="scorecard" data-family={fam.kind} onClick={() => onOpen(String(m.result_id))} aria-label={`${m.home_team} versus ${m.away_team}, ${m.stage}`}>{body}</button>
    : <div className="card overflow-hidden" data-testid="scorecard" data-family={fam.kind}>{body}</div>;
}

/** A compact fixture card for lists and brackets (same data, smaller). */
export const BroadcastMatchCard = (p: { m: any; onOpen?: (id: string) => void }) => <BroadcastScoreboard {...p} />;

function StatBar({ label, a, b }: { label: string; a: any; b: any }) {
  const na = typeof a === "number" ? a : NaN, nb = typeof b === "number" ? b : NaN;
  const tot = na + nb;
  return (
    <div className="py-1.5" data-testid="stat-row">
      <div className="flex items-center justify-between text-sm"><b className="w-16 tabular-nums">{num(a)}</b><span className="px-2 text-center text-[11px] uppercase tracking-wider text-muted">{label}</span><b className="w-16 text-right tabular-nums">{num(b)}</b></div>
      {tot > 0 && <div className="mt-1 flex h-1.5 gap-1 overflow-hidden rounded-full"><div className="rounded-full" style={{ width: `${(100 * na) / tot}%`, background: "var(--ed-primary)" }} /><div className="rounded-full" style={{ width: `${(100 * nb) / tot}%`, background: "rgb(var(--ink) / 0.55)" }} /></div>}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="rounded-xl border border-line bg-surface p-4"><h3 className="h-display mb-2 text-xl">{title}</h3>{children}</section>;
}

/** Full broadcast view of ONE match, from the saved match page: score, labelled periods, team totals, goals with side and minute, cards, line-ups, officials. Only recorded data is shown. */
export function MatchBroadcastView({ resultId }: { resultId: string }) {
  const q = useApi<any>(`/matches/${resultId}`);
  const brand = useEditionBrand();
  return (
    <Async q={q}>{(d) => {
      const m = { ...d, home_team: d.teams[0]?.name ?? d.home_team, away_team: d.teams[1]?.name ?? d.away_team, home_noc: d.teams[0]?.noc ?? d.home_noc, away_noc: d.teams[1]?.noc ?? d.away_noc, periods: d.periods };
      const fam = family(d.sport_name);
      return (
        <div className="space-y-4" data-testid="match-broadcast" data-family={fam.kind}>
          <MatchScoreboard d={d} />
          {d.stats.length > 0 && (
            <Panel title="Team statistics">
              <div className="mb-1 flex justify-between text-xs font-semibold"><span className="flex items-center gap-1.5"><BroadcastCountryFlag noc={m.home_noc} size={12} />{m.home_team}</span><span className="flex items-center gap-1.5">{m.away_team}<BroadcastCountryFlag noc={m.away_noc} size={12} /></span></div>
              {d.stats.map((s: any) => <StatBar key={s.label} label={s.label} a={s.values[0]} b={s.values[1]} />)}
            </Panel>)}
          {d.goals.length > 0 && (
            <Panel title={fam.kind === "basketball" ? "Scoring" : "Goals"}>
              <ol className="space-y-1" data-testid="goal-list">{d.goals.map((g: any, i: number) => (
                <li key={i} className={`flex items-center gap-2 text-sm ${g.side === "away" ? "flex-row-reverse text-right" : ""}`}>
                  <span className="w-20 shrink-0 text-[11px] tabular-nums text-muted">{g.time}</span><span className="min-w-0 flex-1 truncate font-medium">{g.player}</span>
                  {g.score && <b className="rounded bg-black/60 px-1.5 font-display text-sm tabular-nums text-white">{g.score}</b>}{g.note && <span className="text-[10px] uppercase text-muted">{g.note}</span>}
                </li>))}</ol>
              <p className="mt-2 text-[11px] text-muted">The side of each goal comes from matching the scorer to the line-ups (or from which score rose).</p>
            </Panel>)}
          {d.cards.length > 0 && (
            <Panel title="Cards and penalties"><ul className="grid gap-1 sm:grid-cols-2">{d.cards.map((c: any, i: number) => <li key={i} className="flex items-center gap-2 text-sm"><i className={`inline-block h-4 w-3 rounded-sm ${c.card.startsWith("red") ? "bg-red-600" : c.card.startsWith("yellow") ? "bg-yellow-400" : "bg-muted"}`} aria-hidden /><span className="w-16 text-[11px] tabular-nums text-muted">{c.time}</span><span className="truncate">{c.player}</span><span className="text-[10px] uppercase text-muted">{c.card}{c.note ? ` · ${c.note}` : ""}</span></li>)}</ul></Panel>)}
          {d.lineups.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2" data-testid="lineups">{d.lineups.map((l: any, i: number) => (
              <Panel key={i} title={`${l.team} line-up`}>
                <TableFrame title="Line-up" variant="match" actions={<CsvButton name={`${l.team}_lineup`} headers={["number", "player", "position"]} rows={l.rows.filter((r: string[]) => String(r[0]).toLowerCase() !== "team totals" && String(r[0]).toLowerCase() !== "coach").map((r: string[]) => [r[1], r[2], r[0]])} />}><div className="scroll-thin max-h-72 overflow-auto"><table className="w-full text-sm"><thead><tr><th className="th">#</th><th className="th">Player</th><th className="th">Pos</th></tr></thead>
                  <tbody>{l.rows.filter((r: string[]) => String(r[0]).toLowerCase() !== "team totals" && String(r[0]).toLowerCase() !== "coach").map((r: string[], k: number) => <tr key={k}><td className="td tabular-nums">{r[1]}</td><td className="td font-medium">{r[2]}</td><td className="td text-muted">{r[0]}</td></tr>)}</tbody></table></div></TableFrame>
                {l.rows.find((r: string[]) => String(r[0]).toLowerCase() === "coach") && <div className="mt-2 text-xs text-muted">Coach: {l.rows.find((r: string[]) => String(r[0]).toLowerCase() === "coach")[1]}</div>}
              </Panel>))}</div>)}
          {Object.keys(d.officials).length > 0 && <Panel title="Match officials"><dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">{Object.entries<string>(d.officials).map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd>{v}</dd></div>)}</dl></Panel>}
          <p className="text-[11px] text-muted">{d.notes} <a className="underline hover:text-[var(--ed-accent)]" href={d.source_url} target="_blank" rel="noreferrer">Source page</a></p>
          <span className="sr-only" data-edition={brand.gamesId} />
        </div>
      );
    }}</Async>
  );
}

/** Individual-sport result card: athlete, flag, pictogram, event / round, position, official result with unit, record badge, medal. Never a team scoreboard. */
export function IndividualResultCard({ r, round, big = false }: { r: any; round?: string; big?: boolean }) {
  return (
    <div className={`card overflow-hidden ${big ? "p-5" : "p-4"}`} data-testid="individual-card">
      <div className="flex items-center gap-3">
        <SportPictogram sport={r.sport_name} gamesId={r.games_id} size={big ? 44 : 32} />
        <div className="min-w-0 flex-1"><div className="truncate text-[11px] font-semibold uppercase tracking-widest text-muted">{r.event_name}{round ? ` · ${round}` : ""}</div>
          <div className={`truncate font-display ${big ? "text-3xl" : "text-xl"}`}>{r.competitor}</div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-muted"><BroadcastCountryFlag noc={r.noc} size={14} showCode /></div></div>
        <div className="text-center"><div className="text-[10px] uppercase tracking-widest text-muted">Pos</div><div className={`font-display tabular-nums ${big ? "text-5xl" : "text-3xl"}`} style={{ color: "var(--ed-accent)" }}>{r.position ?? "–"}</div></div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-2 text-sm">
        <span className="inline-flex items-baseline gap-2"><b className="font-display text-2xl tabular-nums">{r.result_text ?? r.result_value ?? "–"}</b>{r.result_unit && <span className="text-[10px] uppercase tracking-wider text-muted">{r.result_unit}</span>}</span>
        <span className="inline-flex items-center gap-2">{r.record_level && <BroadcastRecordBadge level={r.record_level} />}<MedalChip medal={r.medal} /></span>
      </div>
    </div>
  );
}
