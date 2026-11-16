import { Download } from "lucide-react";
import { downloadCsv } from "../lib/fmt";

export const slug = (s: string) => (s || "table").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 60) || "table";

/** Export a table's rows (as shown, in the shown order) as CSV. `headers` are the visible column titles; every table in the app offers this. */
export function CsvButton({ headers, rows, name, label = "CSV" }: { headers: string[]; rows: (string | number | null | undefined)[][]; name: string; label?: string }) {
  const clean = headers.map((h, i) => h || `column_${i + 1}`);
  return (
    <button type="button" className="btn !px-2 !py-1 text-xs" data-csv="true" disabled={!rows.length} onClick={() => downloadCsv(rows.map((r) => Object.fromEntries(clean.map((h, i) => [h, r[i] ?? ""]))), slug(name))} aria-label={`Download ${name} as CSV`}>
      <Download className="h-3.5 w-3.5" /> {label}
    </button>
  );
}
