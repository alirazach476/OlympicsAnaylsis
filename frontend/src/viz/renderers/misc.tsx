import { CsvButton } from "../../components/CsvButton";
import { TableFrame } from "../../components/tables/TableFrame";
import { useMemo, useState } from "react";
import { ResponsiveContainer, Sankey, Tooltip } from "recharts";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { useChartColors } from "../../lib/theme";
import { CAT, num } from "../util";
import { useAx } from "./xy";
import type { RenderProps } from "../types";

export function SimpleTable({ columns, rows, onCell, max = 300 }: { columns: { key: string; label: string }[]; rows: any[]; onCell?: (col: string, v: any) => void; max?: number }) {
  const [sort, setSort] = useState<{ k: string; dir: 1 | -1 } | null>(null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => { const x = a[sort.k], y = b[sort.k]; return (typeof x === "number" && typeof y === "number" ? x - y : String(x ?? "").localeCompare(String(y ?? ""))) * sort.dir; });
  }, [rows, sort]);
  return (
    <TableFrame variant="analytics" actions={<CsvButton name="table" label="Table CSV" headers={columns.map((c) => c.label)} rows={sorted.map((r) => columns.map((c) => (r[c.key] === null || r[c.key] === undefined ? "" : typeof r[c.key] === "object" ? JSON.stringify(r[c.key]) : r[c.key])))} />}>
    <div className="scroll-thin max-h-[420px] overflow-auto rounded-lg border border-line">
      <table className="w-full text-left">
        <thead className="sticky top-0 bg-surface2"><tr>{columns.map((c) => (
          <th key={c.key} className="th cursor-pointer select-none" onClick={() => setSort((s) => (s?.k === c.key ? { k: c.key, dir: (-s.dir as 1 | -1) } : { k: c.key, dir: 1 }))} aria-sort={sort?.k === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
            {c.label}{sort?.k === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}</th>))}</tr></thead>
        <tbody>{sorted.slice(0, max).map((r, i) => (
          <tr key={i} className="hover:bg-surface2/60">{columns.map((c) => (
            <td key={c.key} className={`td tabnum ${typeof r[c.key] === "number" ? "text-right" : ""} ${onCell && (c.key === "NOC" || c.key === "noc") ? "cursor-pointer text-accent" : ""}`} onClick={() => onCell?.(c.key, r[c.key])}>
              {typeof r[c.key] === "number" ? num(r[c.key], 3) : r[c.key] === null || r[c.key] === undefined ? "–" : typeof r[c.key] === "object" ? JSON.stringify(r[c.key]) : String(r[c.key])}</td>))}</tr>))}</tbody>
      </table>
      {sorted.length > max && <div className="p-2 text-xs text-muted">Showing the first {max} of {sorted.length.toLocaleString()} rows - the CSV button exports all of them.</div>}
    </div>
    </TableFrame>
  );
}

export function TableViz({ p, onPick }: RenderProps) {
  const d = p.data;
  return <SimpleTable columns={d.columns} rows={d.rows} onCell={(col, v) => p.drill && onPick(p.drill.type, String(v))} />;
}

const TONE: Record<string, { cls: string; Icon: any }> = { ok: { cls: "border-green/40", Icon: CheckCircle2 }, warn: { cls: "border-yellow/50", Icon: AlertTriangle }, bad: { cls: "border-red/50", Icon: XCircle } };
export function Scorecard({ p }: RenderProps) {
  const d = p.data;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {d.tiles.map((t: any) => { const { cls, Icon } = TONE[t.status] ?? TONE.ok; return (
          <div key={t.label} className={`rounded-lg border ${cls} bg-surface2 p-3`} data-testid="score-tile">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted"><Icon className="h-3.5 w-3.5" aria-hidden /> {t.label}</div>
            <div className="mt-1 text-xl font-bold leading-tight">{t.value}</div>
            <div className="mt-1 text-xs text-muted">{t.hint}</div>
          </div>); })}
      </div>
      {(d.tables ?? []).map((tb: any) => (
        <div key={tb.title}><h4 className="mb-1 text-sm font-semibold">{tb.title}</h4>
          <SimpleTable columns={tb.columns.map((c: string) => ({ key: c, label: c }))} rows={tb.rows.map((r: any) => ({ ...r }))} /></div>))}
    </div>
  );
}

export function SankeyViz({ p, height }: RenderProps) {
  const d = p.data, c = useChartColors(), { tip } = useAx();
  const nodes = d.nodes.map((n: any, i: number) => ({ ...n, fill: n.name.endsWith("(to)") ? CAT[1] : CAT[0] }));
  const Node = ({ x, y, width, height: h, index, payload }: any) => {
    const left = payload.name.endsWith("(from)");
    return (<g><rect x={x} y={y} width={width} height={h} fill={left ? CAT[0] : CAT[1]} rx={2} />
      <text x={left ? x - 6 : x + width + 6} y={y + h / 2 + 4} textAnchor={left ? "end" : "start"} fontSize={11} fill={c.text}>{payload.name.replace(/ \((from|to)\)$/, "")}</text></g>);
  };
  return (
    <ResponsiveContainer width="100%" height={Math.max(height, 380)}>
      <Sankey data={{ nodes, links: d.links }} node={<Node />} nodePadding={14} nodeWidth={10} margin={{ left: 150, right: 150, top: 10, bottom: 10 }} link={{ stroke: CAT[7], strokeOpacity: 0.35 }} iterations={32}>
        <Tooltip {...tip} formatter={(v: any) => `${num(v, 0)} ${d.valueLabel ?? ""}`} />
      </Sankey>
    </ResponsiveContainer>
  );
}
