import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useEditionBrand } from "../../themes/editionBrand";
import { BroadcastCountryFlag, EditionLogo, SportPictogram } from "./design";
import { Cell, COMP, lower, MARKS, MarkerBadges, MEDAL_HEX, SavedTable, STATUS } from "../tables/OlympediaTables";

/**
 * Broadcast scoreboards, one layout per sport family. Every board sits in the same edition-branded frame (edition emblem, sport pictogram,
 * event, stage, date, venue, edition background and colours), and the body is the sport's own: halves and goal scorers for football,
 * a line score for basketball and ice hockey, sets for volleyball and tennis, ends and the hammer for curling, innings with R-H-E for baseball,
 * a leaderboard for athletics, swimming and gymnastics. Only values recorded on the saved Olympedia page are shown.
 */

// ------------------------------------------------------------------ stage names (Olympedia notation)
/** 'Match 1/2' is Olympedia's name for the match between places 1 and 2 (the gold-medal match), 'Match 3/4' for places 3 and 4 (the bronze-medal match). */
export function stageInfo(stage?: string | null): { label: string; medal: "gold" | "bronze" | null; raw: string } {
  const raw = String(stage ?? "").trim();
  if (/^match 1\/2$/i.test(raw) || (/\bfinal\b/i.test(raw) && !/semi|quarter|1\/8|round/i.test(raw))) return { label: /^match 1\/2$/i.test(raw) ? "Gold medal match" : raw, medal: "gold", raw };
  if (/^match 3\/4$/i.test(raw) || /bronze/i.test(raw)) return { label: /^match 3\/4$/i.test(raw) ? "Bronze medal match" : raw, medal: "bronze", raw };
  const m = raw.match(/^(match|bout|game) (\d+)\/(\d+)$/i);
  if (m) return { label: `Classification · places ${m[2]}–${m[3]}`, medal: null, raw };
  return { label: raw.replace(/#/g, "") || "Match", medal: null, raw };
}

const MEDAL_BG = { gold: "linear-gradient(90deg,#b8901f,#f3d36b,#b8901f)", bronze: "linear-gradient(90deg,#8a4f1d,#d99a5b,#8a4f1d)" };

// ------------------------------------------------------------------ the frame every board shares
export function ScoreboardFrame({ gamesId, sport, event, stage, date, venue, children, testid = "scoreboard", family }: {
  gamesId?: string; sport?: string | null; event?: string; stage?: string | null; date?: string | null; venue?: string | null; children: ReactNode; testid?: string; family?: string;
}) {
  const b = useEditionBrand();
  const ed = b.editionOf(gamesId);
  const st = stageInfo(stage);
  return (
    <section className="relative overflow-hidden rounded-2xl border border-white/10 text-white shadow-2xl" data-testid={testid} data-family={family} data-edition={gamesId}
      style={{ background: "linear-gradient(135deg, color-mix(in srgb, var(--ed-primary) 70%, #05070c) 0%, #05070c 55%, color-mix(in srgb, var(--ed-secondary) 45%, #05070c) 100%)" }}>
      {ed?.assets.background && <img src={ed.assets.background} alt="" aria-hidden className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-[0.16] mix-blend-luminosity" />}
      <div className="pointer-events-none absolute inset-0" style={{ background: "repeating-linear-gradient(115deg, transparent 0 22px, rgba(255,255,255,0.025) 22px 44px)" }} />
      {/* top bar: edition | sport + event | date */}
      <header className="relative flex flex-wrap items-center gap-3 border-b border-white/10 bg-black/35 px-4 py-2.5 backdrop-blur-sm">
        <EditionLogo gamesId={gamesId} size={42} />
        <div className="min-w-0 leading-tight">
          <div className="font-display text-base font-bold">{ed?.name ?? gamesId}</div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-white/60">{ed?.season ? `${ed.season} Olympics` : ""}</div>
        </div>
        <div className="mx-auto flex min-w-0 items-center gap-2.5">
          <SportPictogram sport={sport} gamesId={gamesId} size={38} />
          <div className="min-w-0 leading-tight"><div className="truncate font-display text-lg font-bold uppercase tracking-wide">{sport}</div><div className="truncate text-xs text-white/70">{event}</div></div>
        </div>
        {date && <div className="ml-auto text-right text-[11px] font-semibold uppercase tracking-wider text-white/75">{date}</div>}
      </header>
      {/* stage ribbon: gold / bronze medal matches in medal colours */}
      <div className="relative px-4 py-1.5 text-center text-[11px] font-extrabold uppercase tracking-[0.3em]" data-testid="stage-ribbon" data-medal={st.medal ?? undefined} title={st.raw !== st.label ? `Olympedia: ${st.raw}` : undefined}
        style={{ background: st.medal ? MEDAL_BG[st.medal] : "var(--ed-accent)", color: "#0b0f17" }}>{st.label}</div>
      <div className="relative">{children}</div>
      {venue && <footer className="relative truncate border-t border-white/10 bg-black/35 px-4 py-1.5 text-center text-[11px] text-white/70" title={venue}>{venue}</footer>}
    </section>
  );
}

// ------------------------------------------------------------------ shared pieces
type Side = { name: string; noc?: string };
const n = (v: any) => (v === null || v === undefined || v === "" ? NaN : Number(String(v).replace("%", "")));
const show = (v: any) => (v === null || v === undefined || v === "" ? "–" : String(v));

function TeamBlock({ s, win, lose, children, align = "center" }: { s: Side; win: boolean; lose: boolean; children?: ReactNode; align?: "left" | "right" | "center" }) {
  return (
    <div className={`flex min-w-0 flex-col items-center gap-2 text-center ${lose ? "opacity-60" : ""}`} data-winner={win || undefined}>
      <span className="rounded-md p-0.5 shadow-lg ring-2" style={{ ["--tw-ring-color" as any]: win ? "var(--ed-accent)" : "rgba(255,255,255,0.15)" }}><BroadcastCountryFlag noc={s.noc} size={46} /></span>
      <span className={`w-full truncate font-display text-xl leading-tight sm:text-2xl ${win ? "font-extrabold" : "font-semibold"}`} title={s.name}>{s.name}</span>
      <span className="text-[11px] font-semibold uppercase tracking-[0.25em] text-white/60">{s.noc}</span>
      {win && <span className="rounded-full px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-[0.25em]" style={{ background: "var(--ed-accent)", color: "#0b0f17" }}>Winner</span>}
      {children && <div className={`w-full ${align === "right" ? "text-right" : align === "left" ? "text-left" : ""}`}>{children}</div>}
    </div>
  );
}

function ScoreBug({ a, b, label, note }: { a: any; b: any; label: string; note?: string }) {
  const x = n(a), y = n(b), has = !isNaN(x) && !isNaN(y);
  return (
    <div className="flex flex-col items-center gap-1.5" data-testid="score-bug">
      <div className="flex items-stretch overflow-hidden rounded-xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.9)] ring-1 ring-white/15" aria-label={has ? `${x} to ${y}` : "no score recorded"}>
        <span className="grid min-w-[4.5rem] place-items-center bg-black/80 px-3 py-2 font-display text-6xl font-bold tabular-nums sm:text-7xl" style={{ color: has && x > y ? "var(--ed-accent)" : undefined }}>{has ? x : "–"}</span>
        <span className="w-1" style={{ background: "var(--ed-accent)" }} />
        <span className="grid min-w-[4.5rem] place-items-center bg-black/80 px-3 py-2 font-display text-6xl font-bold tabular-nums sm:text-7xl" style={{ color: has && y > x ? "var(--ed-accent)" : undefined }}>{has ? y : "–"}</span>
      </div>
      <span className="text-[10px] font-bold uppercase tracking-[0.3em] text-white/60">{label}</span>
      {note && <span className="rounded-full border border-white/25 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest" data-testid="score-note">{note}</span>}
    </div>
  );
}

/** Line score: one row per team, one column per period / set / end / inning, then the totals. `strong` columns (sets, HT/FT) are emphasised. */
function LineScore({ teams, cols, totals, testid = "line-score", higherWins = true }: { teams: Side[]; cols: { label: string; a: any; b: any; title?: string }[]; totals?: { label: string; a: any; b: any }[]; testid?: string; higherWins?: boolean }) {
  if (!cols.length && !totals?.length) return null;
  const best = (p: { a: any; b: any }, k: "a" | "b") => { const x = n(p.a), y = n(p.b); if (isNaN(x) || isNaN(y) || x === y) return false; return higherWins ? (k === "a" ? x > y : y > x) : (k === "a" ? x < y : y < x); };
  return (
    <div className="scroll-thin overflow-x-auto px-3 pb-1" data-testid={testid}>
      <table className="mx-auto border-separate border-spacing-x-1 border-spacing-y-1 text-sm">
        <thead><tr><th />{cols.map((c) => <th key={c.label} title={c.title} className="px-2 text-center text-[10px] font-bold uppercase tracking-wider text-white/60">{c.label}</th>)}{totals?.map((t) => <th key={t.label} className="px-2 text-center text-[10px] font-extrabold uppercase tracking-wider" style={{ color: "var(--ed-accent)" }}>{t.label}</th>)}</tr></thead>
        <tbody>{teams.map((s, i) => { const k = i === 0 ? "a" : "b"; return (
          <tr key={i}>
            <td className="whitespace-nowrap pr-2 text-left font-semibold"><span className="inline-flex items-center gap-1.5"><BroadcastCountryFlag noc={s.noc} size={14} />{s.noc ?? s.name}</span></td>
            {cols.map((c) => <td key={c.label} className={`min-w-[2.4rem] rounded bg-white/[0.07] px-2 py-1 text-center font-display text-lg tabular-nums ${best(c, k) ? "font-bold text-[var(--ed-accent)]" : ""}`}>{show((c as any)[k])}</td>)}
            {totals?.map((t) => <td key={t.label} className="min-w-[2.6rem] rounded px-2 py-1 text-center font-display text-xl font-bold tabular-nums" style={{ background: "color-mix(in srgb, var(--ed-primary) 55%, black)" }}>{show((t as any)[k])}</td>)}
          </tr>); })}</tbody>
      </table>
    </div>
  );
}

/** Head-to-head stat bars for the stats that matter in this sport (others stay in the full statistics panel). */
function KeyStats({ stats, want }: { stats: { label: string; values: any[] }[]; want: RegExp[] | "first" }) {
  const picked = want === "first" ? stats.filter((s) => !/^(goals|points|score)$/i.test(s.label)).slice(0, 6) : want.map((rx) => stats.find((s) => rx.test(s.label))).filter(Boolean) as { label: string; values: any[] }[];
  const uniq = picked.filter((s, i) => picked.indexOf(s) === i);
  if (!uniq.length) return null;
  return (
    <div className="grid gap-x-8 gap-y-2 border-t border-white/10 px-5 py-3 sm:grid-cols-2" data-testid="key-stats">
      {uniq.map((s) => { const x = n(s.values[0]), y = n(s.values[1]), tot = (isNaN(x) ? 0 : x) + (isNaN(y) ? 0 : y); return (
        <div key={s.label} className="text-xs">
          <div className="flex items-baseline justify-between"><b className="font-display text-base tabular-nums">{show(s.values[0])}</b><span className="px-2 text-center text-[10px] uppercase tracking-widest text-white/60">{s.label}</span><b className="font-display text-base tabular-nums">{show(s.values[1])}</b></div>
          {tot > 0 && <div className="mt-1 flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-white/10"><i style={{ width: `${(100 * (isNaN(x) ? 0 : x)) / tot}%`, background: "var(--ed-accent)" }} /><i className="ml-auto" style={{ width: `${(100 * (isNaN(y) ? 0 : y)) / tot}%`, background: "rgba(255,255,255,0.55)" }} /></div>}
        </div>); })}
    </div>
  );
}

/** Scorers under each team (football, hockey, handball, water polo, rugby, ice hockey): minute, player, note. */
function Scorers({ goals, side }: { goals: any[]; side: "home" | "away" }) {
  const list = goals.filter((g) => g.side === side);
  if (!list.length) return null;
  return (
    <ul className={`mt-1 space-y-0.5 text-[11px] text-white/80 ${side === "away" ? "text-right" : "text-left"}`} data-testid={`scorers-${side}`}>
      {list.slice(0, 12).map((g, i) => <li key={i} className="truncate"><span className="tabular-nums text-white/55">{String(g.time).replace(/\s*\(\d+\)$/, "")}′</span> {String(g.player).replace(/\s*\(.*\)\s*$/, "")}{g.note ? <span className="ml-1 text-[9px] uppercase text-white/50">{g.note}</span> : null}</li>)}
      {list.length > 12 && <li className="text-white/50">+{list.length - 12} more</li>}
    </ul>
  );
}

// ------------------------------------------------------------------ team-sport families
export function sportFamily(sport?: string | null) {
  const s = (sport ?? "").toLowerCase();
  if (s === "football") return "football";
  if (s === "rugby sevens" || s === "rugby") return "rugby";
  if (s === "3x3 basketball") return "basketball3x3";
  if (s === "basketball") return "basketball";
  if (s === "volleyball" || s === "beach volleyball") return "volleyball";
  if (s === "tennis" || s === "table tennis" || s === "badminton") return "sets";
  if (s === "ice hockey") return "icehockey";
  if (s === "handball") return "handball";
  if (s === "water polo") return "waterpolo";
  if (s === "hockey") return "hockey";
  if (s === "curling") return "curling";
  if (s === "baseball" || s === "softball") return "baseball";
  return "generic";
}

const short = (l: string) => l.replace(/Period #(\d+)/, "P$1").replace(/Half #(\d+)/, "H$1").replace(/Set #(\d+)/, "S$1").replace(/End #(\d+)/, "$1").replace(/(\d+)(st|nd|rd|th) Inning/, "$1").replace(/Quarter #(\d+)/, "Q$1");

/** One match from /api/matches/{id}, drawn with its sport's layout. */
export function MatchScoreboard({ d }: { d: any }) {
  const fam = sportFamily(d.sport_name);
  const A: Side = { name: d.teams?.[0]?.name ?? d.home_team, noc: d.teams?.[0]?.noc ?? d.home_noc };
  const B: Side = { name: d.teams?.[1]?.name ?? d.away_team, noc: d.teams?.[1]?.noc ?? d.away_noc };
  const stats: { label: string; values: any[] }[] = d.stats ?? [];
  const stat = (rx: RegExp) => stats.find((s) => rx.test(s.label));
  const periods: { label: string; scores: any[] }[] = d.periods ?? [];
  const goals: any[] = d.goals ?? [];
  let a: any = d.home_score, b: any = d.away_score, label = d.score_label || "Score", note: string | undefined;
  let body: ReactNode = null;
  const cols = periods.map((p) => ({ label: short(p.label), title: p.label, a: p.scores[0], b: p.scores[1] }));
  const extra = (rx: RegExp, lab: (l: string) => string) => stats.filter((s) => rx.test(s.label)).map((s) => ({ label: lab(s.label), title: s.label, a: s.values[0], b: s.values[1] }));

  if (fam === "football" || fam === "rugby") {
    // Olympedia's half columns are the running score: HT, then FT; extra-time halves (also running) and a shoot-out come from the statistics
    const run = cols.map((c, i) => ({ ...c, label: i === 0 ? "HT" : i === cols.length - 1 ? "FT" : c.label }));
    const et = extra(/^extra-time half #\d+/i, (l) => l.replace(/extra-time half #(\d+)/i, "ET$1"));
    const so = extra(/shoot-?out|penalt(y|ies) shoot/i, () => "PSO");
    if (so.length) note = "after penalty shoot-out"; else if (et.length) note = "after extra time";
    body = <LineScore teams={[A, B]} cols={[...run, ...et, ...so]} />;
    body = <>{body}<KeyStats stats={stats} want={fam === "football" ? [/^shots$/i, /shots-on-goal/i, /fouls/i, /yellow/i, /red cards/i, /corner/i, /possession/i] : [/tries/i, /conversions/i, /penalty goals/i, /yellow/i, /red/i]} /></>;
  } else if (fam === "basketball" || fam === "basketball3x3") {
    const ot = extra(/overtime|extra period/i, (l) => l.replace(/overtime\s*#?(\d+)?/i, "OT$1"));
    body = <>
      <LineScore teams={[A, B]} cols={[...cols, ...ot]} totals={cols.length || ot.length ? [{ label: "T", a, b }] : undefined} />
      <KeyStats stats={stats} want={fam === "basketball" ? [/3-point field goals$/i, /2-point field goals$/i, /^assists$/i, /^steals$/i, /^(drb|defensive rebounds)$/i, /^(blk|blocks)$/i] : [/^1p$/i, /^2p$/i, /^ft%?$/i, /^fg%$/i, /^(drb|defensive rebounds)$/i, /^blk$/i]} />
    </>;
  } else if (fam === "volleyball" || fam === "sets") {
    label = "Sets";
    const setCols = cols.map((c, i) => ({ ...c, label: `Set ${i + 1}` }));
    body = <>
      <div className="flex flex-wrap justify-center gap-2 px-4 pb-1" data-testid="set-boxes">
        {setCols.map((c) => { const x = n(c.a), y = n(c.b); return (
          <div key={c.label} className="min-w-[4.5rem] overflow-hidden rounded-lg border border-white/15 bg-black/50 text-center">
            <div className="bg-white/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white/70">{c.label}</div>
            <div className="px-2 py-1 font-display text-2xl tabular-nums"><span className={x > y ? "text-[var(--ed-accent)]" : ""}>{show(c.a)}</span><span className="px-1 text-white/40">–</span><span className={y > x ? "text-[var(--ed-accent)]" : ""}>{show(c.b)}</span></div>
          </div>); })}
      </div>
      <KeyStats stats={stats} want={[/^(points|total points)$/i, /spike points|attack successes/i, /block points|block successes/i, /service points|service aces/i, /opponent errors/i, /dig/i]} />
    </>;
  } else if (fam === "icehockey") {
    const ot = extra(/overtime/i, () => "OT"), so = extra(/shoot-?out/i, () => "SO");
    if (so.length) note = "after shoot-out"; else if (ot.length) note = "after overtime";
    body = <>
      <LineScore teams={[A, B]} cols={[...cols, ...ot, ...so]} totals={[{ label: "T", a, b }]} />
      <KeyStats stats={stats} want={[/shots-on-goal/i, /^saves$/i, /save %/i, /penalties in minutes|pim/i, /power.?play/i, /faceoff/i]} />
    </>;
  } else if (fam === "handball" || fam === "waterpolo" || fam === "hockey") {
    body = <>
      <LineScore teams={[A, B]} cols={cols} totals={cols.length ? [{ label: "T", a, b }] : undefined} />
      <KeyStats stats={stats} want={fam === "handball" ? [/^attempts$/i, /7-metre goals/i, /^steals$/i, /2-minute/i, /yellow/i, /red/i]
        : fam === "waterpolo" ? [/^attempts$/i, /extra.?player goals|man.?up/i, /counter-attack goals/i, /^steals$/i, /^blocks$/i, /penalty goals/i]
        : [/field goal attempts/i, /^field goals$/i, /penalty corner attempts/i, /penalty corner goals/i, /green cards/i, /yellow cards/i]} />
    </>;
  } else if (fam === "curling") {
    const xe = extra(/^extra end/i, (l) => l.replace(/extra end #?(\d+)/i, "X$1"));
    const hammer = stat(/last stone first end/i);
    const pct = stat(/^percentage$/i);
    body = <>
      <LineScore teams={[A, B]} cols={[...cols, ...xe]} totals={[{ label: "T", a, b }]} testid="end-score" />
      <div className="flex flex-wrap justify-center gap-6 border-t border-white/10 px-4 py-2 text-xs" data-testid="curling-extra">
        {hammer && [A, B].map((s, i) => String(hammer.values[i]).toLowerCase() === "yes" ? <span key={i} title="Last stone in the first end (the hammer)">🔨 Hammer in end 1: <b>{s.noc}</b></span> : null)}
        {pct && <span>Shot percentage <b className="tabular-nums">{show(pct.values[0])}</b> – <b className="tabular-nums">{show(pct.values[1])}</b></span>}
      </div>
    </>;
  } else if (fam === "baseball") {
    // the saved R-H-E box is the authority for runs (the match header can carry a different figure)
    const R = stat(/team runs/i), H = stat(/team hits/i), E = stat(/team errors/i);
    if (R) { a = R.values[0]; b = R.values[1]; }
    label = "Runs";
    body = <LineScore teams={[A, B]} cols={cols} totals={[R && { label: "R", a: R.values[0], b: R.values[1] }, H && { label: "H", a: H.values[0], b: H.values[1] }, E && { label: "E", a: E.values[0], b: E.values[1] }].filter(Boolean) as any} testid="innings" />;
  } else {
    body = <><LineScore teams={[A, B]} cols={cols} totals={cols.length ? [{ label: "T", a, b }] : undefined} /><KeyStats stats={stats} want="first" /></>;
  }

  const x = n(a), y = n(b), aw = !isNaN(x) && !isNaN(y) && x > y, bw = !isNaN(x) && !isNaN(y) && y > x;
  const scorers = ["football", "rugby", "icehockey", "handball", "waterpolo", "hockey"].includes(fam);
  return (
    <ScoreboardFrame gamesId={d.games_id} sport={d.sport_name} event={d.event_name} stage={d.stage} date={d.match_date} venue={d.location} family={fam}>
      <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-3 px-4 py-5 sm:px-8">
        <TeamBlock s={A} win={aw} lose={bw} align="left">{scorers && <Scorers goals={goals} side="home" />}</TeamBlock>
        <div className="pt-3"><ScoreBug a={a} b={b} label={label} note={note} /></div>
        <TeamBlock s={B} win={bw} lose={aw} align="right">{scorers && <Scorers goals={goals} side="away" />}</TeamBlock>
      </div>
      {body}
    </ScoreboardFrame>
  );
}

// ------------------------------------------------------------------ individual sports: broadcast leaderboard
/** Columns a leaderboard shows besides the main mark, by sport: the gymnastics score breakdown, reaction time on the track and in the pool, field-event attempts are left to the full table. */
function secondary(sport: string, h: string[]): number[] {
  const s = sport.toLowerCase();
  const want = /gymnastic|trampolin/.test(s) ? [/difficulty|^d score$|^d$/, /execution|^e score$|^e$/, /penalty|^pen/]
    : /swimming|athletics|speed skating|short track|canoe|rowing|cycling track/.test(s) ? [/reaction/, /lane/]
    : /diving/.test(s) ? [/dive|dd|difficulty/]
    : /shooting|archery/.test(s) ? [/^10s$|^x$|inner|shoot-?off/]
    : /weightlifting/.test(s) ? [/snatch/, /clean|jerk/, /bodyweight|body weight/]
    : /ski|biathlon|luge|bobsleigh|skeleton|snowboard/.test(s) ? [/run #1|run 1/, /run #2|run 2/, /shooting|penalt/]
    : [];
  return want.map((rx) => h.findIndex((x) => rx.test(x))).filter((i, k, all) => i >= 0 && all.indexOf(i) === k);
}

/** A saved ranking table (final, heat, round) as a broadcast leaderboard: position (medal colours), lane / bib, flag and name, the mark in display type, the sport's breakdown columns and the Q / record / status badges.
 *  `limit` rows are shown (all of them when the table is short); the full table stays below on the page. */
export function ResultLeaderboard({ t, sport, gamesId, event, stage, date, limit = 8 }: { t: SavedTable; sport?: string | null; gamesId?: string; event?: string; stage?: string; date?: string; limit?: number }) {
  const h = lower(t.headers);
  const ip = h.indexOf("pos"), ic = h.findIndex((x) => COMP.includes(x)), inoc = h.indexOf("noc");
  const ilane = h.findIndex((x) => x === "lane"), inum = h.findIndex((x) => x === "number" || x === "bib" || x === "start order");
  const imark = MARKS.map((m) => h.indexOf(m)).find((i) => i >= 0) ?? -1;
  const extra = secondary(sport ?? "", h).filter((i) => i !== imark && i !== ilane);
  const markers = h.map((x, i) => (x === "" ? i : -1)).filter((i) => i >= 0);
  const rows = t.rows.map((r, i) => ({ r, i })).filter(({ r }) => (r[ic] ?? "").trim() && ((r[ip] ?? "").trim() || (r[inoc] ?? "").trim()));
  if (ip < 0 || ic < 0 || !rows.length) return null;
  const shown = rows.length <= limit + 4 ? rows : rows.slice(0, limit);
  return (
    <ScoreboardFrame gamesId={gamesId} sport={sport} event={event} stage={stage || t.section} date={date} testid="leaderboard" family="leaderboard">
      <ol className="divide-y divide-white/10" data-testid="leaderboard-rows">
        {shown.map(({ r, i }) => {
          const pos = (r[ip] ?? "").trim();
          const tail = markers.map((k) => r[k] ?? "").join(" ").trim();
          const medal = tail.match(/\b(Gold|Silver|Bronze)\b/)?.[1];
          const st = STATUS.test(pos.split(" ")[0] ?? "");
          const lane = ilane >= 0 ? r[ilane] : inum >= 0 ? r[inum] : "";
          return (
            <li key={i} className="grid grid-cols-[2.5rem_auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-2 sm:grid-cols-[2.75rem_auto_minmax(0,1fr)_auto_auto]" style={medal ? { background: `linear-gradient(90deg, ${MEDAL_HEX[medal]}33, transparent 60%)` } : undefined}>
              <span className="grid h-9 w-9 place-items-center rounded-full font-display text-lg font-bold tabular-nums" style={medal ? { background: `radial-gradient(circle at 30% 25%, #fff8, ${MEDAL_HEX[medal]} 62%)`, color: "#000" } : st ? { border: "1px solid #f59e0b", color: "#f59e0b", fontSize: 10 } : { background: "rgba(255,255,255,0.1)" }}>{pos || "–"}</span>
              {lane ? <span className="grid h-7 min-w-[1.9rem] place-items-center rounded bg-white px-1 font-display text-sm font-bold tabular-nums text-black" title={ilane >= 0 ? "Lane" : "Number"} data-testid="lane-chip">{lane}</span> : <span />}
              <span className="flex min-w-0 items-center gap-2"><BroadcastCountryFlag noc={r[inoc]} size={22} /><span className="truncate font-display text-lg font-semibold uppercase tracking-wide"><Cell v={r[ic]} links={t.links[i]?.[ic]} /></span><span className="hidden text-[11px] font-bold text-white/55 sm:inline">{r[inoc]}</span></span>
              <span className="hidden items-center gap-3 sm:flex">
                {extra.map((k) => r[k] ? <span key={k} className="text-center leading-none"><span className="block text-[9px] uppercase tracking-wider text-white/50">{t.headers![k]}</span><span className="font-display text-sm tabular-nums">{r[k]}</span></span> : null)}
                {tail && <MarkerBadges v={tail} />}
              </span>
              <span className="text-right font-display text-2xl font-bold tabular-nums" style={{ color: medal ? MEDAL_HEX[medal] : undefined }}>{imark >= 0 ? r[imark] : ""}</span>
            </li>);
        })}
      </ol>
      {shown.length < rows.length && <div className="border-t border-white/10 px-4 py-1.5 text-center text-[11px] text-white/60">Top {shown.length} of {rows.length} · full table below</div>}
      {imark >= 0 && <div className="sr-only">Main mark column: {t.headers![imark]}</div>}
    </ScoreboardFrame>
  );
}

/** A compact team-match card for lists: same frame, same score bug, smaller. */
export function MatchCardLink({ m, to }: { m: any; to: string }) {
  const st = stageInfo(m.stage);
  const x = n(m.home_score), y = n(m.away_score);
  return (
    <Link to={to} className="block overflow-hidden rounded-xl border border-line bg-surface transition hover:border-[var(--ed-accent)]" data-testid="match-card">
      <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-widest" style={{ background: st.medal ? MEDAL_BG[st.medal] : "var(--ed-primary)", color: st.medal ? "#0b0f17" : "var(--ed-on-primary)" }}>{st.label}</div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 px-3 py-2 text-sm">
        <span className="flex min-w-0 items-center gap-1.5"><BroadcastCountryFlag noc={m.home_noc} size={16} /><span className="truncate">{m.home_team}</span></span>
        <b className="rounded bg-black px-2 font-display text-lg tabular-nums text-white"><span className={x > y ? "text-[var(--ed-accent)]" : ""}>{show(m.home_score)}</span>:<span className={y > x ? "text-[var(--ed-accent)]" : ""}>{show(m.away_score)}</span></b>
        <span className="flex min-w-0 items-center justify-end gap-1.5"><span className="truncate">{m.away_team}</span><BroadcastCountryFlag noc={m.away_noc} size={16} /></span>
      </div>
    </Link>
  );
}
