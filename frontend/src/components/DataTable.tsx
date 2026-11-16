import { useMemo, useRef, useState, ReactNode } from "react";
import { ColumnDef, flexRender, getCoreRowModel, getSortedRowModel, SortingState, useReactTable } from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, Download, Search } from "lucide-react";
import { downloadCsv } from "../lib/fmt";
import { slug } from "./CsvButton";
import { Empty } from "./ui";
import { TableHead } from "./tables/TableHead";

export type Col = { key: string; header?: string; render?: (row: any) => ReactNode; align?: "left" | "right"; width?: number; sortable?: boolean };

/** Sortable, virtualised table (only the visible rows are in the DOM) with client CSV export of the loaded rows. */
export function DataTable({ rows: allRows, columns, height = 480, exportName, csvHref, rowKey, onRowClick, empty, selectedKey, title, subtitle, variant = "analytics", searchable, branding = true, rowMedal, sport }: {
  rows: any[]; columns: Col[]; height?: number; exportName?: string; csvHref?: string; rowKey?: (r: any, i: number) => string; onRowClick?: (r: any) => void; empty?: string; selectedKey?: (r: any) => boolean;
  /** broadcast table band: heading, optional sub-heading, table variant (medal | results | ranking | match | sport | records | analytics) and the row filter (on by default for more than 8 rows) */
  title?: ReactNode; subtitle?: ReactNode; variant?: string; searchable?: boolean;
  /** false for tables that are not about one edition (a country across all Games): no edition chip in the header */
  branding?: boolean;
  /** a medal for the row (Gold / Silver / Bronze): the row card is tinted in that medal's colour */
  rowMedal?: (r: any) => string | null | undefined;
  /** the sport of the table (its pictogram is shown on the right of the header) */
  sport?: string | null;
}) {
  const [q, setQ] = useState("");
  const canSearch = searchable ?? allRows.length > 8;
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return t ? allRows.filter((r) => columns.some((c) => String(r[c.key] ?? "").toLowerCase().includes(t))) : allRows;
  }, [allRows, q, columns]);
  const [sorting, setSorting] = useState<SortingState>([]);
  const defs = useMemo<ColumnDef<any>[]>(
    () => columns.map((c) => ({ id: c.key, accessorFn: (r) => r[c.key], header: c.header ?? c.key.replace(/_/g, " "), enableSorting: c.sortable !== false,
      cell: (ctx) => (c.render ? c.render(ctx.row.original) : ctx.getValue() ?? "–"), meta: c })),
    [columns]
  );
  const table = useReactTable({ data: rows, columns: defs, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  const parent = useRef<HTMLDivElement>(null);
  const model = table.getRowModel().rows;
  const virt = useVirtualizer({ count: model.length, getScrollElement: () => parent.current, estimateSize: () => 46, overscan: 12 });
  if (!allRows.length) return <Empty message={empty} />;
  // columns keep their designed width as a minimum and share the rest of the row, so every table fills its frame
  const grid = { gridTemplateColumns: columns.map((c) => (c.width ? `minmax(${c.width}px, ${c.width}fr)` : "minmax(110px, 110fr)")).join(" ") };
  const items = virt.getVirtualItems();
  const rendered = items.length ? items : model.slice(0, 30).map((_, i) => ({ index: i, start: i * 46, size: 46, key: i }));  // jsdom / first paint fallback
  return (
    <div data-csv-scope="true" data-variant={variant} data-testid="broadcast-table" className="ed-table overflow-hidden rounded-2xl border border-line bg-surface/95" style={{ borderTop: "3px solid var(--ed-accent)" }}>
      <TableHead title={title} subtitle={subtitle} branding={branding} sport={sport}
        meta={<>{rows.length.toLocaleString()}{rows.length !== allRows.length ? ` of ${allRows.length.toLocaleString()}` : ""} rows</>}
        actions={<>
          {canSearch && <label className="relative"><Search className="pointer-events-none absolute left-2 top-1.5 h-3.5 w-3.5" /><input className="input !py-1 pl-7 text-xs" placeholder="Filter rows…" aria-label="Filter rows" value={q} onChange={(e) => setQ(e.target.value)} /></label>}
          {csvHref && <a className="btn" href={csvHref} download><Download className="h-3.5 w-3.5" /> CSV (all matching)</a>}
          <button className="btn" data-csv="true" onClick={() => downloadCsv(model.map((r) => Object.fromEntries(columns.map((c) => [c.header ?? c.key.replace(/_/g, " "), r.original[c.key] ?? ""]))), slug(exportName ?? columns[0]?.key ?? "table"))}><Download className="h-3.5 w-3.5" /> CSV (this view)</button>
        </>} />
      <div ref={parent} className="scroll-thin overflow-auto" style={{ maxHeight: height }}>
        <table className="w-full" style={{ display: "block" }} role="table">
          <thead style={{ display: "block", position: "sticky", top: 0, zIndex: 2, boxShadow: "0 1px 0 var(--ed-accent)" }} className="bg-surface2">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="grid" style={grid} role="row">
                {hg.headers.map((h) => {
                  const m: Col = (h.column.columnDef.meta as any) ?? {};
                  const dir = h.column.getIsSorted();
                  return (
                    <th key={h.id} className={`th ${m.align === "right" ? "text-right" : ""} ${h.column.getCanSort() ? "cursor-pointer select-none" : ""}`} onClick={h.column.getToggleSortingHandler()} aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"}>
                      <span className="inline-flex items-center gap-1">{flexRender(h.column.columnDef.header, h.getContext())}{dir === "asc" ? <ArrowUp className="h-3 w-3" /> : dir === "desc" ? <ArrowDown className="h-3 w-3" /> : null}</span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody style={{ display: "block", position: "relative", height: Math.max(virt.getTotalSize(), rendered.length * 46) + 6 }}>
            {rendered.map((v: any) => {
              const row = model[v.index];
              if (!row) return null;
              return (
                <tr key={rowKey ? rowKey(row.original, v.index) : row.id} role="row" data-medal={rowMedal?.(row.original) || undefined} onClick={() => onRowClick?.(row.original)} {...(onRowClick ? { tabIndex: 0, onKeyDown: (e: any) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onRowClick(row.original)), "aria-selected": selectedKey?.(row.original) } : {})}
                  className={`grid absolute left-0 w-full ${v.index % 2 ? "ed-row-alt" : ""} ed-row ${onRowClick ? "cursor-pointer" : ""} ${selectedKey?.(row.original) ? "bg-accent/15 shadow-[inset_3px_0_0_var(--ed-accent)]" : ""}`} style={{ ...grid, top: 3, transform: `translateY(${v.start}px)`, height: 46 }}>
                  {row.getVisibleCells().map((cell) => {
                    const m: Col = (cell.column.columnDef.meta as any) ?? {};
                    return <td key={cell.id} className={`td flex min-w-0 items-center !py-0 tabnum ${m.align === "right" ? "justify-end text-right" : ""}`}><span className="min-w-0 truncate">{flexRender(cell.column.columnDef.cell, cell.getContext())}</span></td>;
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
