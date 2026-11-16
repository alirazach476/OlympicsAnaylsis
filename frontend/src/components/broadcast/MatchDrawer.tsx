import { useEffect, useRef } from "react";
import { ExternalLink, X } from "lucide-react";
import { useApi } from "../../lib/api";
import { Async } from "../ui";
import { MatchBroadcastView } from "./MatchBoards";
import { SavedTables } from "./SavedTables";

/** Slide-over with the full broadcast view of one match; the saved Olympedia page (every table, as it appears) is one click away. Esc closes; focus returns afterwards. */
export function MatchDrawer({ resultId, onClose }: { resultId: string | null; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const page = useApi<any>(resultId ? `/pages/${resultId}` : null, undefined, false);
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
    <div className="fixed inset-0 z-50 flex justify-end bg-black/65 backdrop-blur-sm" onClick={onClose} role="presentation">
      <aside ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Match" onClick={(e) => e.stopPropagation()} className="h-full w-full max-w-3xl overflow-y-auto bg-bg p-5 shadow-2xl outline-none" data-testid="match-drawer">
        <div className="mb-3 flex justify-between gap-3"><span className="text-[11px] uppercase tracking-widest text-muted">Match broadcast</span><button className="btn" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button></div>
        <MatchBroadcastView resultId={resultId} />
        <details className="mt-5 rounded-xl border border-line bg-surface p-3" onToggle={(e) => (e.currentTarget as HTMLDetailsElement).open && page.refetch()}>
          <summary className="cursor-pointer text-sm font-semibold">Every table of the saved page, as it appears <a className="ml-2 inline-flex items-center gap-1 text-xs font-normal underline" href={`https://www.olympedia.org/results/${resultId}`} target="_blank" rel="noreferrer">Olympedia <ExternalLink className="h-3 w-3" /></a></summary>
          <div className="mt-3">{page.data ? <SavedTables tables={page.data.tables} /> : page.isFetching ? <Async q={page}>{() => null}</Async> : null}</div>
        </details>
      </aside>
    </div>
  );
}
