import { ReactNode, useContext, useMemo, useState } from "react";
import { TableContext } from "./TableHead";
import { Link } from "react-router-dom";
import { Flag } from "../ui";
import { CsvButton } from "../CsvButton";
import { TableFrame } from "./TableFrame";
import { BroadcastCountryFlag, MedalChip, SportPictogram } from "../broadcast/design";
import { ScoreboardFrame } from "../broadcast/SportScoreboards";

/**
 * Broadcast renderers for the saved Olympedia tables. Every column and every cell of the saved table is kept ("as it is"); the renderers only change how cells LOOK:
 *  - BroadcastHeatTable / BroadcastResultsTable / BroadcastRankingTable: ranking tables (Pos + competitor) with place discs, lane / bib chips, flags, the mark in display type,
 *    and the trailing marker column turned into badges: Q / q qualification, OR / WR / OB records, medals, DNF / DQ / lapped statuses.
 *  - BroadcastMatchTable / BroadcastBoutTable: lists of matches (Match # link, both sides with flags, the score with the winner highlighted).
 *  - BroadcastBoutBoard: the scoreboard of ONE bout / duel built from the bout page's own tables (main score, games / sets / rounds / judges, other numbers as bars).
 * Nothing is computed that the page does not show; a winner is only highlighted when both main scores are numbers and differ.
 */
export type SavedTable = { index: number; section: string; headers: string[] | null; rows: string[][]; links: { [k: string]: string }[][][] };
type L = { [k: string]: string }[] | undefined;

const NOC = /^[A-Z]{3}$/;
const MEDAL = /^(Gold|Silver|Bronze)$/;
const medalClass: Record<string, string> = { Gold: "bg-[#D4AF37]/20 text-[#D4AF37]", Silver: "bg-[#C0C7D1]/20 text-[#C0C7D1]", Bronze: "bg-[#CD7F32]/20 text-[#CD7F32]" };
export const MEDAL_HEX: Record<string, string> = { Gold: "#D4AF37", Silver: "#C0C7D1", Bronze: "#CD7F32" };

export function Cell({ v, links }: { v: string; links?: L }) {
  const res = links?.find((l) => l.results && l.route);
  if (res) return <Link className="font-semibold text-[var(--ed-accent)] hover:underline" to={res.route} data-testid="subpage-link">{v}</Link>;
  const country = links?.find((l) => l.countries);
  if (NOC.test(v)) return <Link to={country?.route ?? `/countries/${v}`} className="inline-flex items-center gap-1.5 hover:text-accent hover:underline"><Flag noc={v} size={12} />{v}</Link>;
  if (MEDAL.test(v)) return <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${medalClass[v]}`}>{v}</span>;
  const aths = links?.filter((l) => l.athletes) ?? [];
  if (aths.length === 1) {
    const a = aths[0];
    return a.route ? <Link className="hover:text-accent hover:underline" to={a.route}>{v}</Link>
      : <a className="hover:text-accent hover:underline" href={`https://www.olympedia.org/athletes/${a.athletes}`} target="_blank" rel="noreferrer">{v}</a>;
  }
  if (aths.length > 1) // a crew cell 'A • B • C': one link per named athlete
    return <>{aths.map((a, i) => <span key={i}>{i > 0 && " • "}{a.route ? <Link className="hover:text-accent hover:underline" to={a.route}>{a.text}</Link> : <a className="hover:underline" href={`https://www.olympedia.org/athletes/${a.athletes}`} target="_blank" rel="noreferrer">{a.text}</a>}</span>)}</>;
  return <>{v}</>;
}

// ------------------------------------------------------------------ markers of the trailing column
const QUAL: Record<string, string> = { Q: "Qualified by place", q: "Qualified by time / as a fastest loser", QB: "Qualified for Final B", QF: "Qualified for the final", SF: "To the semi-final", FA: "Final A", FB: "Final B", FC: "Final C", ADV: "Advanced by the referee", "[Q]": "Qualified (later reinstated / annotated)", R: "To the repechage" };
const RECORD: Record<string, string> = { WR: "World record", "=WR": "Equalled the world record", OR: "Olympic record", "=OR": "Equalled the Olympic record", OB: "Olympic best", "=OB": "Equalled the Olympic best", IOR: "Inaugural Olympic record", AR: "Area record", NR: "National record" };
export const STATUS = /^(DNF|DNS|DQ|DSQ|DNQ|AC|NM|NP|WD|NC|lapped|overtaken|fall|non-scoring|RDG|DNC|OCS|BFD|UFD|RET|DNE)$/i;

export function MarkerBadges({ v }: { v: string }) {
  const toks = v.split(/\s+/).filter(Boolean);
  if (!toks.length) return null;
  const known = toks.every((t) => QUAL[t] || RECORD[t] || MEDAL.test(t) || STATUS.test(t));
  if (!known) return <span>{v}</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {toks.map((t, i) => QUAL[t] ? <span key={i} data-testid="qual-badge" title={QUAL[t]} className="rounded px-1.5 py-0.5 font-display text-xs font-bold leading-none" style={{ background: "var(--ed-accent)", color: "#000" }}>{t}</span>
        : RECORD[t] ? <span key={i} data-testid="record-badge" title={RECORD[t]} className={`rounded px-1.5 py-0.5 text-[10px] font-bold leading-none text-white ${t.includes("WR") ? "bg-red-600" : "bg-blue-600"}`}>{t}</span>
        : MEDAL.test(t) ? <MedalChip key={i} medal={t} />
        : <span key={i} title="Status" className="rounded border border-amber-500/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase leading-none text-amber-500">{t}</span>)}
    </span>
  );
}

// ------------------------------------------------------------------ classification
export const lower = (h: string[] | null) => (h ?? []).map((x) => String(x ?? "").trim().toLowerCase());
export const COMP = ["competitor", "competitors", "team", "pair", "crew", "athlete", "boat", "horse", "rider", "nation"];
export const MARKS = ["time (automatic)", "time", "result", "total", "points", "total points", "net points", "score", "distance", "height", "best height cleared", "weight (kg)", "final", "total score"];
const isRanking = (t: SavedTable) => { const h = lower(t.headers); return h.includes("pos") && !h.includes("match") && COMP.some((c) => h.includes(c)); };
const isMatchList = (t: SavedTable) => lower(t.headers).includes("match");
const isKV = (t: SavedTable) => !t.headers && t.rows.length > 0 && t.rows.every((r) => r.filter(Boolean).length === 2 && r.length === 2);
const isVersus = (t: SavedTable) => !!t.headers && t.headers.length === 3 && !t.headers[0] && !!t.headers[1] && !!t.headers[2];
export const isBoutTable = (t: SavedTable) => { const h = lower(t.headers); return h.includes("competitor") && h.includes("noc") && !h.includes("pos") && !h.includes("match") && t.rows.length >= 1 && t.rows.length <= 2; };
export type TableKind = "kv" | "heat" | "results" | "ranking" | "matches" | "versus" | "bout" | "generic";
export function tableKind(t: SavedTable): TableKind {
  if (isKV(t)) return "kv";
  if (isMatchList(t)) return "matches";
  if (isRanking(t)) {
    const s = (t.section || "").toLowerCase();
    if (!s || /final|medal|standings/.test(s) && !/semi|quarter/.test(s)) return "results";
    if (/heat|round|qualif|semi|quarter|repechage|race|run|elimination|pool|group|preliminar/.test(s)) return "heat";
    return "ranking";
  }
  if (isVersus(t)) return "versus";
  if (isBoutTable(t)) return "bout";
  return "generic";
}

function Frame({ t, title, variant, children }: { t: SavedTable; title: string; variant: string; children: ReactNode }) {
  const csv = <CsvButton headers={t.headers ?? (t.rows[0]?.map((_, i) => `column ${i + 1}`) ?? [])} rows={t.rows} name={`${t.section || "table"}_${t.index}`} />;
  return <TableFrame title={title} variant={variant} actions={csv}>{children}</TableFrame>;
}

// ------------------------------------------------------------------ ranking: heats, rounds, final standings
function RankingTable({ t, title, variant }: { t: SavedTable; title: string; variant: "heat" | "results" | "ranking" }) {
  const h = lower(t.headers);
  const ip = h.indexOf("pos"), ilane = h.indexOf("lane"), inum = h.findIndex((x) => x === "number" || x === "bib" || x === "start order");
  const ic = h.findIndex((x) => COMP.includes(x));
  const inoc = h.indexOf("noc");
  const scope = useContext(TableContext);
  const imark = MARKS.map((m) => h.indexOf(m)).find((i) => i >= 0) ?? -1;
  const markers = h.map((x, i) => (x === "" && i > 0 ? i : -1)).filter((i) => i >= 0);
  // team events: Olympedia lists each team (NOC, place) followed by its squad / crew rows (no NOC). Like Olympedia, the squad stays folded under the team's "+".
  const { owner, members } = useMemo(() => {
    const owner: number[] = [], members: Record<number, number[]> = {};
    let team = -1;
    t.rows.forEach((r, i) => {
      const pos = (r[ip] ?? "").trim(), noc = inoc >= 0 ? (r[inoc] ?? "").trim() : "";
      const hasAthlete = (t.links[i]?.[ic] ?? []).some((l) => l.athletes);
      const member = team >= 0 && !noc && hasAthlete && !/^=?\d/.test(pos) && !STATUS.test(pos.split(" ")[0] ?? "");
      if (member) { owner[i] = team; (members[team] ??= []).push(i); } else { owner[i] = -1; team = noc || /^=?\d/.test(pos) ? i : -1; }
    });
    return { owner, members };
  }, [t, ip, inoc, ic]);
  const grouped = Object.keys(members).length > 0;
  const [open, setOpen] = useState<Set<number>>(new Set());
  const toggle = (i: number) => setOpen((o) => { const n = new Set(o); n.has(i) ? n.delete(i) : n.add(i); return n; });
  const allOpen = grouped && Object.keys(members).every((k) => open.has(+k));
  const head = (t.headers ?? []).map((x, i) => ({ x, i })).filter(({ x, i }) => !(i === 0 && x === "" && grouped));
  return (
    <Frame t={t} title={title} variant={variant}>
      {grouped && <div className="flex items-center justify-end gap-2 border-b border-line px-3 py-1.5 text-xs text-muted"><span>{Object.keys(members).length} teams · squads folded</span>
        <button type="button" className="btn !py-0.5 text-xs" onClick={() => setOpen(allOpen ? new Set() : new Set(Object.keys(members).map(Number)))} data-testid="toggle-all-squads">{allOpen ? "Hide all squads" : "Show all squads"}</button></div>}
      <table className="w-full text-sm" data-testid={`broadcast-${variant}-table`} data-grouped={grouped || undefined}>
        {t.headers && <thead><tr>{grouped && <th className="th w-8" aria-label="Squad" />}{head.map(({ x, i }) => <th key={i} className={`th ${i === imark ? "text-right" : ""}`}>{x}</th>)}</tr></thead>}
        <tbody>{t.rows.map((r, i) => {
          const links = t.links[i] ?? [];
          if (owner[i] >= 0) {   // a squad / crew member row: only when its team is unfolded
            if (!open.has(owner[i])) return null;
            return <tr key={i} className="bg-[var(--ed-tint)] text-xs text-muted" data-testid="squad-row">{grouped && <td className="td py-1" />}
              {r.map((c, j) => (j === 0 && t.headers?.[0] === "" ? null : <td key={j} className="td py-1">{c ? <Cell v={c} links={links[j]} /> : null}</td>))}</tr>;
          }
          const pos = (r[ip] ?? "").trim();
          const crew = !pos && (links[ic]?.filter((l) => l.athletes).length ?? 0) > 1 && !(r[inoc] ?? "");
          if (crew) return <tr key={i} className="text-xs text-muted">{grouped && <td className="td" />}<td className="td" />{r.slice(1).map((c, j) => <td key={j} className="td py-1">{c ? <Cell v={c} links={links[j + 1]} /> : null}</td>)}</tr>;
          const tail = markers.map((k) => r[k] ?? "").join(" ");
          const medal = tail.match(/\b(Gold|Silver|Bronze)\b/)?.[1];
          const qual = /(^|\s)(Q|q|QB|QF|SF|FA|ADV|\[Q\])(\s|$)/.test(tail);
          const st = STATUS.test(pos.split(" ")[0] ?? "");
          const squad = members[i];
          return (
            <tr key={i} data-qualified={qual || undefined} data-medal={medal || undefined} data-team-row={squad ? "true" : undefined}>
              {grouped && <td className="td w-8 pr-0">{squad ? <button type="button" onClick={() => toggle(i)} aria-expanded={open.has(i)} aria-label={`${open.has(i) ? "Hide" : "Show"} squad of ${r[ic]}`} data-testid="squad-toggle"
                className="grid h-6 w-6 place-items-center rounded-md border border-line font-bold leading-none transition hover:border-[var(--ed-accent)] hover:text-[var(--ed-accent)]">{open.has(i) ? "−" : "+"}</button> : null}</td>}
              {r.map((c, j) => {
                if (j === 0 && t.headers?.[0] === "" && grouped) return null;
                if (j === ip) return <td key={j} className="td">{st ? <span className="rounded border border-amber-500/50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-500">{pos}</span>
                  : pos ? <span data-testid="place" className="inline-grid h-7 min-w-[1.75rem] place-items-center rounded-full px-1 font-display text-base font-bold tabular-nums" style={medal ? { background: `radial-gradient(circle at 30% 25%, #fff7, ${MEDAL_HEX[medal]} 62%)`, color: "#000" } : { background: "var(--ed-tint)" }}>{pos}</span> : null}</td>;
                if ((j === ilane || j === inum) && c && c !== "–") return <td key={j} className="td"><span data-testid="lane-chip" className="inline-grid h-6 min-w-[1.5rem] place-items-center rounded bg-black/70 px-1 font-display text-sm tabular-nums text-white">{c}</span></td>;
                if (j === ic) { const noc = (r[inoc] ?? "").trim(); const linked = (links[j] ?? []).some((l) => l.athletes || l.results || l.countries);
                  return <td key={j} className="td font-semibold">{c ? (!linked && /^[A-Z]{3}$/.test(noc) ? <Link className="hover:text-[var(--ed-accent)] hover:underline" to={scope.gamesId ? `/countries/${noc}/editions/${scope.gamesId}` : `/countries/${noc}`}>{c}</Link> : <Cell v={c} links={links[j]} />) : null}</td>; }
                if (j === imark) return <td key={j} className="td text-right font-display text-lg tabular-nums" style={{ color: medal ? MEDAL_HEX[medal] : undefined }}>{c}</td>;
                if (markers.includes(j)) return <td key={j} className="td">{c ? <MarkerBadges v={c} /> : null}</td>;
                return <td key={j} className="td tabnum">{c ? <Cell v={c} links={links[j]} /> : null}</td>;
              })}
            </tr>);
        })}</tbody>
      </table>
    </Frame>
  );
}
export const BroadcastHeatTable = ({ t, title }: { t: SavedTable; title?: string }) => <RankingTable t={t} title={title ?? (t.section || "Heat")} variant="heat" />;
export const BroadcastResultsTable = ({ t, title }: { t: SavedTable; title?: string }) => <RankingTable t={t} title={title ?? (t.section || "Final standings")} variant="results" />;
export const BroadcastRankingTable = ({ t, title }: { t: SavedTable; title?: string }) => <RankingTable t={t} title={title ?? (t.section || "Standings")} variant="ranking" />;

// ------------------------------------------------------------------ match / bout lists
const SCORE = /^\s*(\d+)\s*[–-]\s*(\d+)\s*$/;
function MatchList({ t, title, variant }: { t: SavedTable; title: string; variant: "match" | "bout" }) {
  const h = lower(t.headers);
  const ires = h.indexOf("result");
  return (
    <Frame t={t} title={title} variant={variant}>
      <table className="w-full text-sm" data-testid={`broadcast-${variant}-table`}>
        {t.headers && <thead className="bg-surface2"><tr>{t.headers.map((x, i) => <th key={i} className={`th ${i === ires ? "text-center" : ""}`}>{x}</th>)}</tr></thead>}
        <tbody>{t.rows.map((r, i) => {
          const m = SCORE.exec(r[ires] ?? "");
          const a = m ? +m[1] : NaN, b = m ? +m[2] : NaN;
          const win = m && a !== b ? (a > b ? "a" : "b") : null;
          return (
            <tr key={i} className="hover:bg-[var(--ed-tint)]">
              {r.map((c, j) => {
                const links = t.links[i]?.[j];
                if (j === ires) return <td key={j} className="td text-center">{m ? <span className="inline-flex items-center gap-1 rounded-md bg-black/80 px-2 py-0.5 font-display text-lg tabular-nums text-white"><b style={{ color: win === "a" ? "var(--ed-accent)" : undefined }}>{a}</b><span className="text-white/50">:</span><b style={{ color: win === "b" ? "var(--ed-accent)" : undefined }}>{b}</b></span> : c}</td>;
                const side = ires >= 0 ? (j < ires ? "a" : "b") : null;
                const isName = links?.some((l) => l.athletes) || (h[j] && COMP.includes(h[j]));
                return <td key={j} className={`td ${isName && win && side === win ? "font-bold" : ""} ${isName && win && side !== win ? "text-muted" : ""}`}>{c ? (h[j] === "" ? <MarkerBadges v={c} /> : <Cell v={c} links={links} />) : null}</td>;
              })}
            </tr>);
        })}</tbody>
      </table>
    </Frame>
  );
}
export const BroadcastMatchTable = ({ t, title }: { t: SavedTable; title?: string }) => <MatchList t={t} title={title ?? (t.section || "Matches")} variant="match" />;
export const BroadcastBoutTable = ({ t, title }: { t: SavedTable; title?: string }) => <MatchList t={t} title={title ?? (t.section || "Bouts")} variant="bout" />;

/** The right renderer for one saved table. */
export function OlympediaTable({ t, untitled, kindHint }: { t: SavedTable; untitled: string; kindHint?: "bout" | "match" }) {
  const k = tableKind(t);
  const title = t.section || untitled;
  if (k === "heat") return <BroadcastHeatTable t={t} title={title} />;
  if (k === "results") return <BroadcastResultsTable t={t} title={title} />;
  if (k === "ranking") return <BroadcastRankingTable t={t} title={title} />;
  if (k === "matches") return kindHint === "bout" ? <BroadcastBoutTable t={t} title={title} /> : <BroadcastMatchTable t={t} title={title} />;
  return (
    <Frame t={t} title={title} variant="results">
      <table className="w-full text-sm">
        {t.headers && <thead className="bg-surface2"><tr>{t.headers.map((x, i) => <th key={i} className="th">{x}</th>)}</tr></thead>}
        <tbody>{t.rows.map((r, i) => <tr key={i} className="hover:bg-[var(--ed-tint)]">{r.map((c, j) => <td key={j} className="td tabnum">{c ? (t.headers?.[j] === "" ? <MarkerBadges v={c} /> : <Cell v={c} links={t.links[i]?.[j]} />) : null}</td>)}</tr>)}</tbody>
      </table>
    </Frame>
  );
}

// ------------------------------------------------------------------ the bout scoreboard
const MAIN = ["score", "games won", "sets won", "matches won", "touches delivered", "set points", "judges favoring", "classification points", "total points", "points", "total"];
const PERIOD = /^(game|set|round|period|judge|end|bout|half)\s*#?\s*\d+/i;
const IDENT = ["competitor", "noc", "color", "seed", "number", "start order", "bib", ""];
const corner = (c?: string) => { const s = (c ?? "").toLowerCase(); return /red|hong|aka/.test(s) ? "#dc2626" : /blue|chung|ao\b/.test(s) ? "#2563eb" : /white|shiro/.test(s) ? "#e5e7eb" : undefined; };
const num = (v?: string) => (v != null && /^-?\d+(\.\d+)?$/.test(v.trim()) ? +v : NaN);

/** One bout / duel as a broadcast scoreboard, from the bout page's competitor table, its 'A vs B' table and the 'Match Result' line. */
export function BroadcastBoutBoard({ tables, sport, gamesId, event, label, date }: { tables: SavedTable[]; sport?: string | null; gamesId?: string; event?: string; label?: string; date?: string }) {
  const bt = tables.find(isBoutTable);
  if (!bt) return null;
  const h = lower(bt.headers);
  const ic = h.indexOf("competitor"), inoc = h.indexOf("noc");
  const imain = MAIN.map((m) => h.indexOf(m)).find((i) => i >= 0) ?? -1;
  const side = (r: string[], i: number) => ({ name: r[ic], noc: r[inoc], links: bt.links[i]?.[ic], color: corner(r[h.indexOf("color")]), colorLabel: r[h.indexOf("color")],
    seed: r[h.indexOf("seed")] ?? r[h.indexOf("number")], main: imain >= 0 ? r[imain] : undefined, bye: r.some((c) => /^bye$/i.test(c ?? "")) });
  const [A, B] = [side(bt.rows[0], 0), bt.rows[1] ? side(bt.rows[1], 1) : undefined];
  const a = num(A.main), b = num(B?.main);
  const win = !isNaN(a) && !isNaN(b) && a !== b ? (a > b ? "A" : "B") : null;
  // periods: game / set / round / judge columns of the competitor table, then 'A vs B' rows not already there
  const periods: { label: string; a: string; b: string }[] = [];
  h.forEach((x, i) => { if (PERIOD.test(x)) periods.push({ label: bt.headers![i], a: bt.rows[0][i] ?? "", b: bt.rows[1]?.[i] ?? "" }); });
  const stats: { label: string; a: string; b: string }[] = [];
  h.forEach((x, i) => { if (!PERIOD.test(x) && !IDENT.includes(x) && i !== imain) stats.push({ label: bt.headers![i], a: bt.rows[0][i] ?? "", b: bt.rows[1]?.[i] ?? "" }); });
  const vs = tables.find(isVersus);
  vs?.rows.forEach((r) => { const lab = r[0]; if (!lab || lower([lab])[0] === (imain >= 0 ? h[imain] : "")) return; const tgt = PERIOD.test(lab) ? periods : stats; if (!periods.concat(stats).some((p) => p.label.toLowerCase() === lab.toLowerCase())) tgt.push({ label: lab, a: r[1] ?? "", b: r[2] ?? "" }); });
  const result = tables.filter(isKV).flatMap((t) => t.rows).find((r) => /match result|result|decision|win by/i.test(r[0]))?.[1];
  const Side = ({ s, w, right }: { s: typeof A; w: boolean; right?: boolean }) => (
    <div className={`flex min-w-0 flex-col items-center gap-2 rounded-xl px-2 py-3 text-center ${win && !w ? "opacity-60" : ""}`} style={s.color ? { background: `linear-gradient(180deg, ${s.color}40, transparent)`, boxShadow: `inset 0 3px 0 ${s.color}` } : undefined} data-corner={s.colorLabel || undefined}>
      <div className="relative">{s.noc ? <BroadcastCountryFlag noc={s.noc} size={40} /> : null}{s.color && <i className="absolute -bottom-1 left-1/2 h-1.5 w-12 -translate-x-1/2 rounded-full" style={{ background: s.color }} title={s.colorLabel} />}</div>
      <div className="max-w-full truncate font-display text-xl leading-tight sm:text-2xl">{s.name ? <Cell v={s.name} links={s.links} /> : "—"}</div>
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-white/60">{s.noc}{s.seed && s.seed !== "–" ? <span>· seed {s.seed}</span> : null}{s.colorLabel ? <span>· {s.colorLabel}</span> : null}</div>
      {w && <span className="text-[10px] font-bold uppercase tracking-[0.2em]" style={{ color: "var(--ed-accent)" }}>Winner</span>}
      <span className="sr-only">{right ? "right" : "left"}</span>
    </div>
  );
  return (
    <div className="mb-5"><ScoreboardFrame gamesId={gamesId} sport={sport} event={event} stage={label} date={date} testid="bout-board" family="bout">
      {B ? (
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 p-4 sm:p-6">
          <Side s={A} w={win === "A"} />
          <div className="flex flex-col items-center gap-1">
            <div className="rounded-xl bg-black/80 px-5 py-2 font-display text-6xl font-bold tabular-nums text-white shadow-[0_10px_40px_-10px_rgba(0,0,0,0.9)] ring-1 ring-white/15 sm:text-7xl" data-testid="bout-score">
              {A.main != null || B.main != null ? <><span style={{ color: win === "A" ? "var(--ed-accent)" : undefined }}>{A.main ?? "–"}</span><span className="mx-2 text-white/40">:</span><span style={{ color: win === "B" ? "var(--ed-accent)" : undefined }}>{B.main ?? "–"}</span></> : <span className="text-3xl">VS</span>}
            </div>
            {imain >= 0 && <div className="text-[10px] font-semibold uppercase tracking-widest text-muted">{bt.headers![imain]}</div>}
            {result && <div className="mt-1 rounded-full px-3 py-0.5 text-xs font-bold uppercase tracking-wider" style={{ background: "var(--ed-tint)", color: "var(--ed-accent)" }} data-testid="bout-result">{result}</div>}
          </div>
          <Side s={B} w={win === "B"} right />
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 p-6"><Side s={A} w={false} /><span className="rounded-full px-3 py-0.5 text-xs font-bold uppercase tracking-wider" style={{ background: "var(--ed-tint)", color: "var(--ed-accent)" }}>{A.bye ? "Bye — advances without a bout" : result ?? ""}</span></div>
      )}
      {B && periods.length > 0 && (
        <div className="scroll-thin overflow-x-auto border-t border-line px-4 py-3" data-testid="bout-periods">
          <table className="mx-auto text-sm"><thead><tr><th className="th" />{periods.map((p) => <th key={p.label} className="th text-center">{p.label}</th>)}</tr></thead>
            <tbody>{[["a", A], ["b", B]].map(([k, s]: any) => <tr key={k}><td className="td whitespace-nowrap font-semibold"><span className="inline-flex items-center gap-1.5"><BroadcastCountryFlag noc={s.noc} size={12} />{s.noc}</span></td>
              {periods.map((p: any) => { const mine = num(p[k]), other = num(p[k === "a" ? "b" : "a"]); return <td key={p.label} className={`td text-center font-display text-lg tabular-nums ${!isNaN(mine) && !isNaN(other) && mine > other ? "text-[var(--ed-accent)]" : ""}`}>{p[k] || "–"}</td>; })}</tr>)}</tbody></table>
        </div>)}
      {B && stats.filter((s) => s.a || s.b).length > 0 && (
        <div className="grid gap-2 border-t border-line px-4 py-3 sm:grid-cols-2" data-testid="bout-stats">
          {stats.filter((s) => s.a || s.b).map((s) => { const x = num(s.a), y = num(s.b), tot = (isNaN(x) ? 0 : x) + (isNaN(y) ? 0 : y); return (
            <div key={s.label} className="text-xs"><div className="flex justify-between"><b className="tabular-nums">{s.a || "–"}</b><span className="uppercase tracking-wider text-muted">{s.label}</span><b className="tabular-nums">{s.b || "–"}</b></div>
              {tot > 0 && <div className="mt-1 flex h-1.5 gap-0.5 overflow-hidden rounded-full"><i style={{ width: `${(x / tot) * 100}%`, background: "var(--ed-primary)" }} /><i style={{ width: `${(y / tot) * 100}%`, background: "var(--ed-secondary)" }} /></div>}</div>); })}
        </div>)}
    </ScoreboardFrame></div>
  );
}
