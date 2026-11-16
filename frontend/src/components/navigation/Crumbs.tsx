import { Link, useLocation, useSearchParams } from "react-router-dom";
import { nextParams } from "../../lib/urlState";
import { useCallback } from "react";

export type Crumb = { label: string; to?: string };

/** Full breadcrumb trail for the Olympedia-style pages: Home › Olympic Games › Paris 2024 › Athletics › 100 metres, Men › Heat #3. Every item but the last is a working link. */
export function Crumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3 text-xs text-muted" data-testid="breadcrumbs">
      <ol className="flex flex-wrap items-center gap-1.5">
        {[{ label: "Home", to: "/" }, ...items].map((c, i, all) => (
          <li key={i} className="flex items-center gap-1.5">
            {i > 0 && <span aria-hidden>›</span>}
            {c.to && i < all.length - 1 ? <Link to={c.to} className="hover:text-accent">{c.label}</Link> : <span aria-current={i === all.length - 1 ? "page" : undefined} className="text-ink">{c.label}</span>}
          </li>))}
      </ol>
    </nav>
  );
}

/** One URL search param as state. `push` adds a history entry (dropdowns, tabs: Back returns to the previous choice); typing replaces it. */
export function useParamState(key: string, fallback = ""): [string, (v: string, push?: boolean) => void] {
  const [params, setParams] = useSearchParams();
  const loc = useLocation();
  const value = params.get(key) ?? fallback;
  // several setters called in one handler (sort + order, Clear all) all apply - see lib/urlState
  const set = useCallback((v: string, push = true) => setParams(nextParams(loc.key, params, (n) => {
    if (v && v !== fallback) n.set(key, v); else n.delete(key);
    if (key !== "page") n.delete("page");
  }), { replace: !push }), [key, fallback, setParams, params, loc.key]);
  return [value, set];
}
