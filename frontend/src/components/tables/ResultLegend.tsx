import { useMemo } from "react";
import { Info } from "lucide-react";

/**
 * Result notation used in the saved Olympedia tables, with its meaning. `sports` limits a code to the sports where that meaning holds
 * (the same letters mean different things in different sports, so a code outside its sports is not explained).
 * Only codes whose meaning is established by the source's conventions are listed; anything else is left unexplained rather than guessed.
 */
export const RESULT_CODES: { code: string; meaning: string; sports?: RegExp }[] = [
  { code: "Q", meaning: "Qualified for the next round (automatic qualifying place)" },
  { code: "q", meaning: "Qualified for the next round on result (non-automatic place, e.g. fastest losers)" },
  { code: "AC", meaning: "Also competed: took part, but no final place was recorded" },
  { code: "DNS", meaning: "Did not start" },
  { code: "DNF", meaning: "Did not finish" },
  { code: "DQ", meaning: "Disqualified" },
  { code: "DSQ", meaning: "Disqualified" },
  { code: "DNQ", meaning: "Did not qualify" },
  { code: "NM", meaning: "No mark: no valid attempt recorded" },
  { code: "NH", meaning: "No height: no height cleared", sports: /jump|vault|athlon/i },
  { code: "OR", meaning: "Olympic record" },
  { code: "WR", meaning: "World record" },
  { code: "OB", meaning: "Olympic best (a mark in an event without official Olympic records)" },
  { code: "AET", meaning: "After extra time" },
  { code: "PS", meaning: "Decided by penalty shoot-out" },
  { code: "OCS", meaning: "On course side at the start signal (premature start)", sports: /sailing|yachting|board|windsurf|kite|470|laser|finn|nacra|49er|star|tornado|soling|dragon|flying|mistral|rs:x|ilca|formula kite|iqfoil/i },
  { code: "BFD", meaning: "Black flag disqualification (start rule)", sports: /sailing|yachting|board|windsurf|kite|470|laser|finn|nacra|49er|star|tornado|soling|dragon|flying|mistral|rs:x|ilca|iqfoil/i },
  { code: "UFD", meaning: "U flag disqualification (start rule)", sports: /sailing|yachting|board|windsurf|kite|470|laser|finn|nacra|49er|star|tornado|soling|dragon|flying|mistral|rs:x|ilca|iqfoil/i },
  { code: "o", meaning: "Height cleared at this attempt", sports: /high jump|pole vault/i },
  { code: "x", meaning: "Failed attempt", sports: /high jump|pole vault|throw|jump|put|weightlifting/i },
  { code: "xo", meaning: "Cleared at the second attempt (one failure, then clear)", sports: /high jump|pole vault/i },
  { code: "xxo", meaning: "Cleared at the third attempt", sports: /high jump|pole vault/i },
  { code: "xxx", meaning: "Three failed attempts: eliminated at this height", sports: /high jump|pole vault/i },
  { code: "Match a/b", meaning: "Placing match between the competitors for places a and b: Match 1/2 is the gold-medal match, Match 3/4 the bronze-medal match" },
  { code: "=", meaning: "Tied place (shared with another competitor)" },
];

const TOKEN = /(?<![\w/])(=?[A-Za-z]{1,4}=?)(?![\w/])/g;

/** Codes present in a set of table rows (cells as strings). */
export function codesIn(rows: unknown[][], context: string) {
  const found = new Set<string>();
  for (const row of rows) for (const cell of row) {
    if (typeof cell !== "string" || cell.length > 24) continue;
    if (/^=\d|^\d+=$/.test(cell.trim())) found.add("=");
    if (/^(match|bout|game) \d+\/\d+$/i.test(cell.trim())) found.add("Match a/b");
    for (const m of cell.matchAll(TOKEN)) found.add(m[1].replace(/=/g, ""));
  }
  return RESULT_CODES.filter((c) => found.has(c.code) && (!c.sports || c.sports.test(context)));
}

/** Small legend of the result abbreviations that appear on this page (nothing when none appear). */
export function ResultLegend({ tables, context }: { tables: { rows?: unknown[][] }[]; context: string }) {
  const codes = useMemo(() => codesIn(tables.flatMap((t) => t.rows ?? []), context), [tables, context]);
  if (!codes.length) return null;
  return (
    <details open className="card mb-4 px-4 py-2 text-xs" data-testid="result-legend">
      <summary className="flex cursor-pointer select-none items-center gap-2 font-semibold text-muted"><Info className="h-3.5 w-3.5" />Abbreviations on this page ({codes.length})</summary>
      <dl className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
        {codes.map((c) => <div key={c.code} className="flex gap-2"><dt className="min-w-[2.5rem] shrink-0 whitespace-nowrap font-mono font-bold" style={{ color: "var(--ed-accent)" }}>{c.code}</dt><dd className="text-muted">{c.meaning}</dd></div>)}
      </dl>
    </details>
  );
}
