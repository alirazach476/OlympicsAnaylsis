import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { useApi } from "../../lib/api";
import { Flag } from "../ui";

type Hit = { key: string; to: string; label: string; sub?: string; noc?: string; group: string };

/** Global search (Ctrl/Cmd+K or the header button): editions, countries, sports and athletes from the live API. ↑ ↓ to move, Enter to open, Esc to close. */
export function SearchPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [debounced, setDebounced] = useState("");
  const nav = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { const t = setTimeout(() => setDebounced(q.trim()), 180); return () => clearTimeout(t); }, [q]);
  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => input.current?.focus(), 30); } }, [open]);
  const res = useApi<any>(open && debounced.length >= 2 ? "/search" : null, { q: debounced, limit: 6 });
  const hits: Hit[] = !res.data ? [] : [
    ...res.data.editions.map((e: any) => ({ key: "e" + e.games_id, group: "Editions", to: `/edition/${e.games_id}`, label: `${e.host_city} ${e.year}`, sub: `${e.season} · ${e.host_country}` })),
    ...res.data.countries.map((c: any) => ({ key: "c" + c.noc_code, group: "Countries", to: `/countries/${c.noc_code}`, label: c.historical_name, sub: c.noc_code, noc: c.noc_code })),
    ...res.data.sports.map((s: any) => ({ key: "s" + s.sport_id, group: "Sports", to: `/sports/${s.sport_id}`, label: s.sport_name })),
    ...res.data.athletes.map((a: any) => ({ key: "a" + a.athlete_id, group: "Athletes", to: `/athletes/${a.athlete_id}`, label: a.full_name, sub: [a.nocs, a.sports, a.medals ? `${a.medals} medals` : ""].filter(Boolean).join(" · ") })),
  ];
  const go = (h: Hit) => { onClose(); nav(h.to); };
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 pt-[12vh] backdrop-blur-sm" onClick={onClose} role="presentation">
      <div role="dialog" aria-modal="true" aria-label="Search" className="w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl" onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
          if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
          if (e.key === "Enter" && hits[sel]) go(hits[sel]);
        }}>
        <label className="flex items-center gap-3 border-b border-line px-4 py-3"><Search className="h-4 w-4 text-muted" /><input ref={input} className="w-full bg-transparent text-base outline-none placeholder:text-muted" placeholder="Search editions, countries, sports, athletes…" value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} aria-label="Search" aria-controls="search-results" /><kbd className="rounded border border-line px-1.5 text-[10px] text-muted">Esc</kbd></label>
        <ul id="search-results" role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
          {debounced.length < 2 && <li className="px-3 py-6 text-center text-sm text-muted">Type at least two letters.</li>}
          {debounced.length >= 2 && res.isLoading && <li className="px-3 py-6 text-center text-sm text-muted">Searching…</li>}
          {debounced.length >= 2 && !res.isLoading && !hits.length && <li className="px-3 py-6 text-center text-sm text-muted">Nothing found for “{debounced}”.</li>}
          {hits.map((h, i) => (
            <li key={h.key} role="option" aria-selected={i === sel}>
              {(i === 0 || hits[i - 1].group !== h.group) && <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted">{h.group}</div>}
              <button className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm ${i === sel ? "bg-accent/15 text-accent" : "hover:bg-surface2"}`} onMouseEnter={() => setSel(i)} onClick={() => go(h)}>
                {h.noc && <Flag noc={h.noc} size={14} />}<span className="font-medium">{h.label}</span>{h.sub && <span className="truncate text-xs text-muted">{h.sub}</span>}
              </button>
            </li>))}
        </ul>
      </div>
    </div>
  );
}
