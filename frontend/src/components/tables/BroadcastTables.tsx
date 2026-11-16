import { ReactNode } from "react";
import { Col, DataTable } from "../DataTable";
import { BroadcastCountryFlag, BroadcastRecordBadge, MedalChip, MedalCount, SportPictogram } from "../broadcast/design";
import { fmtInt, gamesLabel } from "../../lib/fmt";
import { Link } from "react-router-dom";
import { useApi } from "../../lib/api";

/** A sport name (with its pictogram) that opens the sport's page: resolved against /api/sports by name. */
function SportLink({ sport, size = 22 }: { sport: string; size?: number }) {
  const q = useApi<any[]>("/sports");
  const id = q.data?.find((s) => s.sport_name === sport)?.sport_id;
  const pic = <SportPictogram sport={sport} label size={size} />;
  return id ? <Link className="hover:text-[var(--ed-accent)] hover:underline" to={`/sports/${id}`} onClick={(e) => e.stopPropagation()}>{pic}</Link> : pic;
}

type Base = { rows: any[]; title?: ReactNode; subtitle?: ReactNode; height?: number; exportName?: string; onRowClick?: (r: any) => void; selectedKey?: (r: any) => boolean; csvHref?: string; gamesId?: string; searchable?: boolean };
const norm = (s: any) => String(s ?? "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

/** Olympic medal table: broadcast-style ranking with medal discs and a strong total. Rows: rank_by_gold_silver_bronze | rank, noc_code, country_name | historical_name, gold, silver, bronze, total. */
export function MedalTable({ rows, title = "Medal table", ...rest }: Base) {
  const cols: Col[] = [
    { key: "rank", header: "Rank", width: 64, render: (r) => <span className="font-display text-2xl font-bold leading-none" style={{ color: "var(--ed-accent)" }}>{r.rank_by_gold_silver_bronze ?? r.rank ?? "–"}</span> },
    { key: "noc_code", header: "Country", width: 230, render: (r) => <span className="inline-flex items-center gap-2 font-semibold"><BroadcastCountryFlag noc={r.noc_code} name={r.country_name ?? r.historical_name} size={18} />{r.is_host ? <span className="chip !py-0 text-[10px]">host</span> : null}</span> },
    { key: "gold", header: "Gold", align: "right", width: 70, render: (r) => <MedalCount medal="gold" value={r.gold} /> },
    { key: "silver", header: "Silver", align: "right", width: 70, render: (r) => <MedalCount medal="silver" value={r.silver} /> },
    { key: "bronze", header: "Bronze", align: "right", width: 70, render: (r) => <MedalCount medal="bronze" value={r.bronze} /> },
    { key: "total", header: "Total", align: "right", width: 80, render: (r) => <span className="font-display text-2xl font-bold tabular-nums">{fmtInt(r.total ?? r.total_medals)}</span> },
  ];
  return <DataTable variant="medal" title={title} rows={rows} columns={cols} rowMedal={(r) => (["", "Gold", "Silver", "Bronze"][r.rank_by_gold_silver_bronze ?? r.rank] || null)} {...rest} />;
}

/** Event results: position (medal disc for the podium), optional sport pictogram + event, athlete, flag, official result with its unit, verified record badge.
 *  `records` is /api/records/for-games for the same Games: a badge appears only when the record book lists this athlete, event AND value. */
export function ResultsTable({ rows, title = "Results", showSport = false, showEvent = false, records = [], ...rest }: Base & { showSport?: boolean; showEvent?: boolean; records?: any[] }) {
  const recordOf = (r: any) => {
    if (!records.length) return undefined;
    const val = String(r.result_text ?? r.result_value ?? "").trim();
    return records.find((x) => norm(x.event) === norm(r.event_name) && norm(x.athlete).includes(norm(r.competitor)) && val && String(x.value).trim() === val);
  };
  const cols: Col[] = [
    { key: "position", header: "Pos", width: 96, render: (r) => r.medal ? <span className="inline-flex items-center gap-2"><MedalChip medal={r.medal} compact /><b className="tabular-nums">{r.position}</b></span> : <b className="tabular-nums">{r.position ?? "–"}</b> },
    ...(showSport ? [{ key: "sport_name", header: "Sport", width: 190, render: (r: any) => <SportPictogram sport={r.sport_name} gamesId={r.games_id ?? rest.gamesId} label size={24} /> } as Col] : []),
    ...(showEvent ? [{ key: "event_name", header: "Event", width: 230 } as Col] : []),
    { key: "competitor", header: "Athlete", width: 240, render: (r) => (r.athlete_id ? <Link className="font-semibold hover:text-[var(--ed-accent)] hover:underline" to={`/athletes/${r.athlete_id}`}>{r.competitor}</Link> : <span className="font-semibold">{r.competitor}</span>) },
    { key: "noc", header: "Country", width: 110, render: (r) => <BroadcastCountryFlag noc={r.noc} size={15} showCode /> },
    { key: "result_text", header: "Result", align: "right", width: 150, render: (r) => <span className="inline-flex items-center justify-end gap-2"><b className="font-display text-xl tabular-nums">{r.result_text ?? r.result_value ?? "–"}</b>{r.result_unit ? <span className="text-[10px] uppercase tracking-wider text-muted">{r.result_unit}</span> : null}</span> },
    { key: "record", header: "Record", width: 80, sortable: false, render: (r) => { const x = recordOf(r); return x ? <BroadcastRecordBadge level={x.level} title={`${x.level} record - ${x.type}`} /> : null; } },
  ];
  return <DataTable rowMedal={(r: any) => r.medal} variant="results" title={title} rows={rows} columns={cols} {...rest} />;
}

/** Athlete ranking (career medals). Rows: full_name, nocs, sports, gold, silver, bronze, medals, games_count, first_year, last_year. */
export function AthleteRankingTable({ rows, title = "Athletes", ...rest }: Base) {
  const cols: Col[] = [
    { key: "rank", header: "#", width: 52, sortable: false, render: (r) => <span className="font-display text-xl font-bold" style={{ color: "var(--ed-accent)" }}>{r._rank ?? ""}</span> },
    { key: "full_name", header: "Athlete", width: 250, render: (r) => <Link className="font-semibold hover:text-[var(--ed-accent)] hover:underline" to={`/athletes/${r.athlete_id}`} onClick={(e) => e.stopPropagation()}>{r.full_name}</Link> },
    { key: "nocs", header: "Country", width: 100, render: (r) => <BroadcastCountryFlag noc={String(r.nocs ?? "").split(",")[0]} size={15} showCode /> },
    { key: "sports", header: "Sport", width: 190, render: (r) => <SportLink sport={String(r.sports ?? "").split(",")[0]} /> },
    { key: "gold", header: "G", align: "right", width: 56, render: (r) => <MedalCount medal="gold" value={r.gold} /> },
    { key: "silver", header: "S", align: "right", width: 56, render: (r) => <MedalCount medal="silver" value={r.silver} /> },
    { key: "bronze", header: "B", align: "right", width: 56, render: (r) => <MedalCount medal="bronze" value={r.bronze} /> },
    { key: "medals", header: "Medals", align: "right", width: 84, render: (r) => <b className="font-display text-xl tabular-nums">{r.medals}</b> },
    { key: "games_count", header: "Games", align: "right", width: 70 },
  ];
  return <DataTable variant="ranking" title={title} rows={rows.map((r, i) => ({ ...r, _rank: i + 1 }))} columns={cols} {...rest} />;
}

/** Country ranking. Rows: noc_code, historical_name, gold, silver, bronze, total_medals, appearances, athletes. */
export function CountryRankingTable({ rows, title = "Countries", ...rest }: Base) {
  const cols: Col[] = [
    { key: "rank", header: "#", width: 52, sortable: false, render: (r) => <span className="font-display text-xl font-bold" style={{ color: "var(--ed-accent)" }}>{r._rank}</span> },
    { key: "historical_name", header: "Country", width: 240, render: (r) => <BroadcastCountryFlag noc={r.noc_code} name={r.historical_name} size={18} /> },
    { key: "gold", header: "G", align: "right", width: 56, render: (r) => <MedalCount medal="gold" value={r.gold} /> },
    { key: "silver", header: "S", align: "right", width: 56, render: (r) => <MedalCount medal="silver" value={r.silver} /> },
    { key: "bronze", header: "B", align: "right", width: 56, render: (r) => <MedalCount medal="bronze" value={r.bronze} /> },
    { key: "total_medals", header: "Total", align: "right", width: 84, render: (r) => <b className="font-display text-xl tabular-nums">{fmtInt(r.total_medals)}</b> },
    { key: "appearances", header: "Games", align: "right", width: 70 },
    { key: "athletes", header: "Athletes", align: "right", width: 90, render: (r) => fmtInt(r.athletes) },
  ];
  return <DataTable variant="ranking" title={title} rows={rows.map((r, i) => ({ ...r, _rank: i + 1 }))} columns={cols} {...rest} />;
}

/** Match results as a table (fixtures and results). Rows from /api/matches. */
export function MatchResultsTable({ rows, title = "Match results", ...rest }: Base) {
  const score = (r: any) => (r.home_score === null || r.home_score === undefined || r.away_score === null || r.away_score === undefined ? "–" : `${r.home_score} – ${r.away_score}`);
  const cols: Col[] = [
    { key: "stage", header: "Stage", width: 130 },
    { key: "match_date", header: "Date", width: 190 },
    { key: "home_team", header: "Home", width: 200, align: "right", render: (r) => <span className={`inline-flex items-center justify-end gap-2 ${Number(r.home_score) > Number(r.away_score) ? "font-bold" : ""}`}>{r.home_team}<BroadcastCountryFlag noc={r.home_noc} size={15} /></span> },
    { key: "home_score", header: "Score", width: 140, align: "right", render: (r) => <b className="whitespace-nowrap rounded bg-black/60 px-2 py-0.5 font-display text-lg tabular-nums text-white">{score(r)}</b> },
    { key: "away_team", header: "Away", width: 200, render: (r) => <span className={`inline-flex items-center gap-2 ${Number(r.away_score) > Number(r.home_score) ? "font-bold" : ""}`}><BroadcastCountryFlag noc={r.away_noc} size={15} />{r.away_team}</span> },
    { key: "location", header: "Venue", width: 260 },
  ];
  return <DataTable variant="match" title={title} rows={rows} columns={cols} {...rest} />;
}

/** Sport statistics: the edition's pictogram beside every sport. Rows: sport_name, athletes, nocs, events, medal_awards ... */
export function SportStatisticsTable({ rows, title = "Sports", extra = [], numeric, ...rest }: Base & { extra?: Col[]; numeric?: Col[] }) {
  const cols: Col[] = [
    { key: "sport_name", header: "Sport", width: 260, render: (r) => { const g = r.games_id ?? rest.gamesId; const pic = <SportPictogram sport={r.sport_name} gamesId={g} label size={28} />; return g ? <Link className="hover:text-[var(--ed-accent)] hover:underline" to={`/games/${g}/sports/${encodeURIComponent(r.sport_name)}`} onClick={(e) => e.stopPropagation()}>{pic}</Link> : <SportLink sport={r.sport_name} size={28} />; } },
    ...(numeric ?? [{ key: "athletes", header: "Athletes", align: "right", render: (r: any) => fmtInt(r.athletes) } as Col, { key: "nocs", header: "NOCs", align: "right" } as Col, { key: "events", header: "Events", align: "right" } as Col]),
    ...extra,
  ];
  return <DataTable variant="sport" title={title} rows={rows} columns={cols} {...rest} />;
}

/** Historical records: level badge, event / athlete from the record description, country, value, date. Rows: gold_records. */
export function RecordsTable({ rows, title = "Records", ...rest }: Base) {
  const part = (r: any, i: number) => String(r.description ?? "").split(" | ")[i] ?? "";
  const cols: Col[] = [
    { key: "record_level", header: "Level", width: 90, render: (r) => <BroadcastRecordBadge level={r.record_level} /> },
    { key: "event", header: "Event", width: 280, sortable: false, render: (r) => { const id = `${r.description ?? ""} ${r.source_url ?? ""}`.match(/results\/(\d+)/)?.[1]; return id && r.games_id ? <Link className="font-semibold hover:text-[var(--ed-accent)] hover:underline" to={`/games/${r.games_id}/events/${id}`}>{part(r, 0)}</Link> : <span className="font-semibold">{part(r, 0)}</span>; } },
    { key: "athlete", header: "Athlete", width: 230, sortable: false, render: (r) => (r.athlete_id ? <Link className="hover:text-[var(--ed-accent)] hover:underline" to={`/athletes/${r.athlete_id}`}>{part(r, 2)}</Link> : part(r, 2)) },
    { key: "noc_code", header: "Country", width: 110, render: (r) => <BroadcastCountryFlag noc={r.noc_code} size={15} showCode /> },
    { key: "record_value", header: "Mark", align: "right", width: 120, render: (r) => <b className="font-display text-xl tabular-nums" style={{ color: "var(--ed-accent)" }}>{r.record_value}</b> },
    { key: "record_date", header: "Date", width: 170 },
    { key: "games_id", header: "Games", width: 130, render: (r) => (r.games_id ? <Link className="hover:text-[var(--ed-accent)] hover:underline" to={`/edition/${r.games_id}`}>{gamesLabel(r.games_id)}</Link> : "–") },
  ];
  return <DataTable variant="records" title={title} rows={rows} columns={cols} {...rest} />;
}

/** Statistical results, model comparisons, data-quality reports: the same branded table, plain analytical columns. */
export function AnalyticsTable({ rows, columns, title, ...rest }: Base & { columns: Col[] }) {
  return <DataTable variant="analytics" title={title} rows={rows} columns={columns} {...rest} />;
}
