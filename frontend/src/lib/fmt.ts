export const PALETTE = ["#0085C7", "#F4C300", "#009F3D", "#DF0024", "#8E6BBF", "#FF8A3D", "#2BB3B1", "#B0B7C3", "#E86AA6", "#7BA05B"];
export const MEDAL_COLORS = { gold: "#D4AF37", silver: "#C0C7D1", bronze: "#CD7F32" };

export function fmtInt(v: any): string {
  if (v === null || v === undefined || v === "" || Number.isNaN(Number(v))) return "–";
  return Math.round(Number(v)).toLocaleString("en-US");
}

export function fmtNum(v: any, digits = 2): string {
  if (v === null || v === undefined || v === "" || Number.isNaN(Number(v))) return "–";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function fmtPct(v: any, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "–";
  return `${(Number(v) * 100).toFixed(digits)}%`;
}

/** p-values: never print 0 (underflow) - show <1e-16 instead */
export function fmtP(p: any): string {
  if (p === null || p === undefined || Number.isNaN(Number(p))) return "–";
  const n = Number(p);
  if (n < 1e-16) return "< 1e-16";
  return n < 0.001 ? n.toExponential(2) : n.toFixed(4);
}

export function gamesLabel(id?: string | null): string {
  if (!id) return "";
  const [y, s] = id.split("_");
  return `${y} ${s ? s[0].toUpperCase() + s.slice(1) : ""}`;
}

/** Local flag collection (scripts/download_flags.py): every NOC code of the data has a file under public/assets/flags */
export const flagUrl = (noc: string) => `/assets/flags/${encodeURIComponent(noc)}.svg`;

export function safe<T>(fn: () => T, fallback: T): T {
  try {
    const v = fn();
    return v === undefined || v === null ? fallback : v;
  } catch {
    return fallback;
  }
}

export function downloadCsv(rows: Record<string, any>[], name: string) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const esc = (v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const body = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([body], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
