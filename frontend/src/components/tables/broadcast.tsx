import { Link } from "react-router-dom";
import { TableFrame } from "./TableFrame";
import { CsvButton } from "../CsvButton";
import { BroadcastCountryFlag, MedalChip, MedalCount, SportPictogram } from "../broadcast/design";
import { AthleteRankingTable } from "./BroadcastTables";

/**
 * The broadcast table set, under one import:
 *   BroadcastResultsTable · BroadcastHeatTable · BroadcastRankingTable   saved Olympedia ranking tables (final standings / heats & rounds / standings)
 *   BroadcastMatchTable · BroadcastBoutTable                             saved Olympedia match lists (team matches / individual bouts)
 *   BroadcastBoutBoard                                                   scoreboard of one bout
 *   BroadcastMedalTable · BroadcastCountryTable · BroadcastAthleteTable  medal table by NOC, a NOC's entries at one edition, athlete rankings
 */
export { BroadcastResultsTable, BroadcastHeatTable, BroadcastRankingTable, BroadcastMatchTable, BroadcastBoutTable, BroadcastBoutBoard, OlympediaTable, MarkerBadges } from "./OlympediaTables";
export const BroadcastAthleteTable = AthleteRankingTable;

const SORTS: [string, string][] = [["rank", "Rank"], ["noc", "Country"], ["gold", "Gold"], ["silver", "Silver"], ["bronze", "Bronze"], ["total", "Total"], ["appearances", "Appearances"], ["editions", "Medal editions"], ["sports", "Medal sports"]];
const PODIUM = ["#D4AF37", "#C0C7D1", "#CD7F32"];

/** Medal table by NOC: rank disc (podium colours for ranks 1-3), flag + name, medal discs, sortable headers (aria-sort). Rows come from /api/medals/countries. */
export function BroadcastMedalTable({ rows, total, page, pageSize, sort, order, onSort, linkFor }: { rows: any[]; total: number; page: number; pageSize: number; sort: string; order: string; onSort: (k: string) => void; linkFor: (noc: string) => string }) {
  return (
    <TableFrame title="Medal table" subtitle={`${total} NOCs`} variant="medals" actions={<CsvButton name="medal_table" headers={["rank", "noc", "country", "gold", "silver", "bronze", "total", "appearances"]} rows={rows.map((r: any) => [r.rank ?? "", r.noc, r.country, r.gold, r.silver, r.bronze, r.total, r.appearances ?? ""])} />}>
      <table className="w-full text-sm" data-testid="medal-table">
        <thead className="bg-surface2"><tr>{SORTS.map(([k, l]) => <th key={k} className="th cursor-pointer select-none" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSort(k); } }} aria-sort={sort === k ? (order === "asc" ? "ascending" : "descending") : "none"} onClick={() => onSort(k)}>{l}{sort === k ? (order === "asc" ? " ▲" : " ▼") : ""}</th>)}</tr></thead>
        <tbody>{rows.map((r: any) => (
          <tr key={r.noc} data-medal={r.total > 0 && r.rank && r.rank <= 3 ? ["Gold", "Silver", "Bronze"][r.rank - 1] : undefined}>
            <td className="td"><span className="inline-grid h-8 min-w-[2rem] place-items-center rounded-full px-1 font-display text-lg font-bold tabular-nums" style={r.rank && r.rank <= 3 ? { background: `radial-gradient(circle at 30% 25%, #fff7, ${PODIUM[r.rank - 1]} 62%)`, color: "#000" } : { background: "var(--ed-tint)" }}>{r.rank ?? "–"}</span></td>
            <td className="td font-semibold"><Link className="hover:text-accent hover:underline" to={linkFor(r.noc)}><BroadcastCountryFlag noc={r.noc} name={r.country} size={18} showCode /></Link></td>
            <td className="td"><MedalCount medal="gold" value={r.gold} /></td><td className="td"><MedalCount medal="silver" value={r.silver} /></td><td className="td"><MedalCount medal="bronze" value={r.bronze} /></td>
            <td className="td font-display text-2xl tabular-nums">{r.total}</td><td className="td tabular-nums">{r.appearances ?? "–"}</td><td className="td tabular-nums">{r.editions}</td><td className="td tabular-nums">{r.sports}</td>
          </tr>))}</tbody>
      </table>
    </TableFrame>
  );
}

const STATUS_TONE: Record<string, string> = { Ranked: "", DNF: "text-amber-500", DNS: "text-muted", DQ: "text-red-500", DSQ: "text-red-500", AC: "text-amber-500" };
const MEDAL_HEX: Record<string, string> = { Gold: "#D4AF37", Silver: "#C0C7D1", Bronze: "#CD7F32" };

/** One NOC's entries in one sport at one edition: event (linked), athlete (linked), the place disc (medal colours), status and medal. */
export function BroadcastCountryTable({ sport, events, gamesId }: { sport: string; events: any[]; gamesId: string }) {
  return (
    <TableFrame title={sport} subtitle={`${events.length} events`} variant="country" gamesId={gamesId} sport={sport}>
      <table className="w-full text-sm" data-testid="country-sport-table">
        <thead className="bg-surface2"><tr><th className="th">Event</th><th className="th">Athlete</th><th className="th">Position</th><th className="th">Status</th><th className="th">Medal</th></tr></thead>
        <tbody>{events.flatMap((e: any) => e.entries.map((en: any, i: number) => (
          <tr key={`${e.result_id}-${i}`} data-medal={en.medal || undefined}>
            <td className="td">{i === 0 ? (e.route ? <Link className="font-semibold hover:text-accent hover:underline" to={e.route}>{e.event}</Link> : <span className="font-semibold">{e.event}</span>) : null}</td>
            <td className="td">{en.route ? <Link className="hover:text-accent hover:underline" to={en.route}>{en.athlete}</Link> : en.athlete}</td>
            <td className="td tabular-nums">{en.medal ? <span className="inline-grid h-7 min-w-[1.75rem] place-items-center rounded-full px-1 font-display text-base font-bold" style={{ background: `radial-gradient(circle at 30% 25%, #fff7, ${MEDAL_HEX[en.medal]} 62%)`, color: "#000" }}>{en.position}</span> : en.position}</td>
            <td className={`td text-xs ${STATUS_TONE[en.status] ?? ""}`}>{en.status}</td>
            <td className="td">{en.medal ? <MedalChip medal={en.medal} /> : null}</td>
          </tr>)))}</tbody>
      </table>
    </TableFrame>
  );
}
