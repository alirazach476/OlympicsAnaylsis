import { Flag } from "../ui";

const STAGE_TONE = (s = "") => (/final/i.test(s) && !/semi|quarter/i.test(s) ? ["#D4AF37", "#1a1405"] : /bronze/i.test(s) ? ["#CD7F32", "#190e04"] : /semi/i.test(s) ? ["#C0C7D1", "#10141a"] : ["rgb(var(--surface2))", "inherit"]);

function Ribbon({ stage, date, extra }: { stage: string; date?: string; extra?: string }) {
  const [bg, fg] = STAGE_TONE(stage);
  return (
    <div className="flex items-center justify-between gap-2 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider" style={{ background: bg, color: fg }}>
      <span className="truncate">{stage || "Match"}</span><span className="shrink-0 opacity-80">{[extra, date].filter(Boolean).join(" · ")}</span>
    </div>
  );
}

/** Team-sport scoreboard: big flags, scores in a broadcast score bug, stage ribbon, venue, period scores (only when the source gives them). */
export function TeamScoreboard({ m, onOpen }: { m: any; onOpen?: (id: string) => void }) {
  const hs = Number(m.home_score), as = Number(m.away_score), has = Number.isFinite(hs) && Number.isFinite(as) && m.home_score !== null && m.away_score !== null;
  const hw = has && hs > as, aw = has && as > hs;
  const periods = String(m.period_scores ?? "").split(/[;,]\s*|\s{2,}/).filter(Boolean);
  const Side = ({ name, noc, win, right }: { name: string; noc: string; win: boolean; right?: boolean }) => (
    <div className={`flex min-w-0 flex-col items-center gap-1.5 text-center ${win ? "" : has ? "opacity-70" : ""}`}>
      <Flag noc={noc} size={28} /><span className={`w-full truncate text-sm ${win ? "font-bold" : "font-medium"}`} title={name}>{name}</span>{win && <span className="text-[10px] font-bold uppercase tracking-widest text-accent">{right ? "Winner" : "Winner"}</span>}
    </div>
  );
  const body = (
    <>
      <Ribbon stage={m.stage} date={m.match_date} />
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-3 py-4">
        <Side name={m.home_team} noc={m.home_noc} win={hw} />
        <div className="rounded-xl bg-black/70 px-4 py-1.5 font-display text-4xl leading-none tabular-nums text-white shadow-inner" aria-label={has ? `${hs} to ${as}` : "no score recorded"}>
          <span className={hw ? "text-accent" : ""}>{has ? hs : "–"}</span><span className="px-1.5 text-white/40">:</span><span className={aw ? "text-accent" : ""}>{has ? as : "–"}</span>
        </div>
        <Side name={m.away_team} noc={m.away_noc} win={aw} right />
      </div>
      {(periods.length > 1 || m.location) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-3 py-1.5 text-[11px] text-muted">
          <span className="truncate" title={m.location}>{m.location}</span>
          {periods.length > 1 && <span className="flex gap-1">{periods.map((p, i) => <span key={i} className="rounded bg-surface2 px-1.5 py-0.5 tabular-nums text-ink">{p}</span>)}</span>}
        </div>)}
    </>
  );
  return onOpen && m.result_id
    ? <button className="card w-full overflow-hidden text-left transition hover:border-accent" data-testid="scorecard" onClick={() => onOpen(String(m.result_id))} aria-label={`${m.home_team} versus ${m.away_team}, ${m.stage}`}>{body}</button>
    : <div className="card overflow-hidden" data-testid="scorecard">{body}</div>;
}

const SKIP = new Set(["athlete_id", "bib", "number", "role", "team"]);

/** Bout / duel scoreboard for individual sports (fencing, judo, wrestling, boxing ...): two competitors with the sport's own statistic (touches delivered, bad points, classification points ...). No winner is inferred unless the statistic defines one (touches / points: higher wins). */
export function BoutScoreboard({ b, onOpen }: { b: any; onOpen?: (id: string) => void }) {
  const p: any[] = (b.participants ?? []).slice(0, 2);
  const keys = Array.from(new Set(p.flatMap((x) => Object.keys(x.extra ?? {})))).filter((k) => !SKIP.has(k));
  const higherWins = keys.find((k) => /touches|points scored|score|classification/i.test(k) && !/bad|penalt/i.test(k));
  const val = (x: any) => Number(String(x?.extra?.[higherWins!] ?? "").replace(",", "."));
  const win = higherWins && p.length === 2 && Number.isFinite(val(p[0])) && Number.isFinite(val(p[1])) && val(p[0]) !== val(p[1]) ? (val(p[0]) > val(p[1]) ? 0 : 1) : -1;
  const body = (
    <>
      <Ribbon stage={b.stage || b.label} date={b.match_date} />
      <div className="px-3 py-3">
        {p.map((x, i) => (
          <div key={i} className={`flex items-center gap-3 py-1.5 ${i ? "border-t border-line/60" : ""} ${win === i ? "" : win >= 0 ? "opacity-70" : ""}`}>
            <Flag noc={x.noc} size={20} />
            <div className="min-w-0 flex-1"><div className={`truncate text-sm ${win === i ? "font-bold" : "font-medium"}`}>{x.competitor}</div><div className="text-[11px] text-muted">{x.noc}</div></div>
            {keys.slice(0, 2).map((k) => <div key={k} className="text-right"><div className={`font-display text-2xl leading-none tabular-nums ${win === i ? "text-accent" : ""}`}>{x.extra?.[k] ?? "–"}</div><div className="text-[9px] uppercase tracking-wider text-muted">{k}</div></div>)}
          </div>))}
        {!p.length && <div className="text-xs text-muted">No competitors recorded on this page.</div>}
      </div>
      {b.location && <div className="truncate border-t border-line px-3 py-1.5 text-[11px] text-muted" title={b.location}>{b.location}</div>}
    </>
  );
  return onOpen ? <button className="card w-full overflow-hidden text-left transition hover:border-accent" onClick={() => onOpen(String(b.result_id))} data-testid="bout-card" aria-label={`${p.map((x) => x.competitor).join(" versus ")}, ${b.stage || b.label}`}>{body}</button> : <div className="card overflow-hidden" data-testid="bout-card">{body}</div>;
}
