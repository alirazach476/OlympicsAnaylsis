import { useEffect, useRef } from "react";
import { ExternalLink, X } from "lucide-react";
import { useApi } from "../../lib/api";
import { Async } from "../ui";

import { OlympediaTable, SavedTable } from "../tables/OlympediaTables";
export type { SavedTable } from "../tables/OlympediaTables";

/** Every table of an Olympedia page exactly as saved: section heading, header row, all cells. A two-column table without header (e.g. "Match Result | Ippon") renders as a key / value strip. */
export function SavedTables({ tables, untitled = "Table", sectionMeta, kindHint }: { tables: SavedTable[]; untitled?: string; sectionMeta?: Record<string, Record<string, string>>; kindHint?: "bout" | "match" }) {
  const firstOf = new Set<number>();
  { const seen = new Set<string>(); for (const t of tables) if (!seen.has(t.section)) { seen.add(t.section); firstOf.add(t.index); } }
  return (
    <div className="space-y-5" data-testid="saved-tables">
      {tables.map((t) => {
        const kv = !t.headers && t.rows.length > 0 && t.rows.every((r) => r.filter(Boolean).length === 2 && r.length === 2);
        return (
          <section key={t.index}>
            {firstOf.has(t.index) && sectionMeta?.[t.section] && (   // the round's own facts (Date, Format ...) as Olympedia prints them above its tables
              <dl className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-xs" data-testid="section-meta"><span className="font-display text-base">{t.section}</span>{Object.entries(sectionMeta[t.section]).map(([k, v]) => <div key={k} className="flex gap-1.5"><dt className="font-semibold text-muted">{k}</dt><dd>{v}</dd></div>)}</dl>)}
            {kv ? (
              <>
                {t.section && <h3 className="h-display mb-1 text-xl">{t.section}</h3>}
                <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 rounded-lg border border-line bg-surface2 px-4 py-3 text-sm" style={{ borderLeft: "3px solid var(--ed-accent)" }}>{t.rows.map((r, i) => <div key={i} className="contents"><dt className="font-semibold text-muted">{r[0]}</dt><dd className="font-display text-xl" style={{ color: "var(--ed-accent)" }}>{r[1]}</dd></div>)}</dl>
              </>
            ) : <OlympediaTable t={t} untitled={untitled} kindHint={kindHint} />}
          </section>);
      })}
    </div>
  );
}

/** Slide-over with one saved results page (a bout, a heat sheet, an event ...). Esc closes; focus moves to the panel and returns afterwards. */
export function PageDrawer({ resultId, onClose }: { resultId: string | null; onClose: () => void }) {
  const q = useApi<any>(resultId ? `/pages/${resultId}` : null);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!resultId) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => { window.removeEventListener("keydown", k); prev?.focus?.(); };
  }, [resultId, onClose]);
  if (!resultId) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm" onClick={onClose} role="presentation">
      <aside ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Saved results page" onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-3xl overflow-y-auto bg-bg p-5 shadow-2xl outline-none" data-testid="page-drawer">
        <div className="mb-3 flex items-start justify-between gap-3">
          <Async q={q}>{(d) => <div><div className="text-[11px] uppercase tracking-widest text-muted">{d.breadcrumb}</div><h2 className="h-display text-3xl leading-tight">{d.title}</h2>
            <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted">{Object.entries<string>(d.meta ?? {}).map(([k, v]) => <span key={k}><b className="text-ink">{k}</b> {v}</span>)}<a className="inline-flex items-center gap-1 underline hover:text-accent" href={d.source_url} target="_blank" rel="noreferrer">Olympedia <ExternalLink className="h-3 w-3" /></a></div></div>}</Async>
          <button className="btn shrink-0" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <Async q={q}>{(d) => <SavedTables tables={d.tables} />}</Async>
      </aside>
    </div>
  );
}
