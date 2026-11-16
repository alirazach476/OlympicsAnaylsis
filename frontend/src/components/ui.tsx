import { ReactNode, useEffect, useState } from "react";
import { useInRouterContext, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { AlertTriangle, Brain, Database, Dumbbell, Globe2, Inbox, Loader2, Maximize2, Medal, Minimize2, Search, Sigma, Swords, Trophy, Users, LineChart, X } from "lucide-react";
import { flagUrl, fmtInt } from "../lib/fmt";
import { BroadcastPageHeader } from "./broadcast/design/BroadcastPageHeader";
import { useAssets } from "../lib/assets";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center gap-2 p-8 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function Empty({ message = "No data for this selection." }: { message?: string }) {
  return (
    <div data-testid="empty" className="flex flex-col items-center justify-center gap-2 p-8 text-center text-sm text-muted">
      <Inbox className="h-6 w-6" /> {message}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = String((error as any)?.message ?? error);
  const local = typeof window !== "undefined" && /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname);
  // the data server is unreachable (gateway errors / network failure): say so plainly instead of a developer hint
  // (our API's own 404s always carry a reason, e.g. "404 unknown games_id"; a bare "404 Not Found" means the server itself is missing)
  const offline = /^(502|503|504)\b|^404( Not Found)?$|Failed to fetch|NetworkError/i.test(msg.trim());
  if (offline && !local) return (
    <div role="alert" data-testid="api-offline" className="flex items-start gap-3 rounded-xl border border-yellow/40 bg-yellow/10 p-4 text-sm">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-yellow" />
      <div>
        <div className="font-semibold">Live results are temporarily unavailable</div>
        <div className="text-muted">The Olympic data server is offline right now, so results, medal tables and charts cannot load. Edition logos and artwork are still available. Please check back soon.</div>
      </div>
    </div>
  );
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-red/40 bg-red/10 p-4 text-sm">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red" />
      <div>
        <div className="font-semibold">Could not load data</div>
        <div className="text-muted">{msg}</div>
        {local && <div className="mt-1 text-xs text-muted">Is the API running? <code>uvicorn backend.api.main:app --port 8000</code></div>}
      </div>
    </div>
  );
}

/** Wraps any query result: loading / error / empty states, then children(data). */
export function Async<T>({ q, children, isEmpty }: { q: { data?: T; isLoading: boolean; error: unknown }; children: (d: T) => ReactNode; isEmpty?: (d: T) => boolean }) {
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  if (q.data === undefined || q.data === null || (isEmpty && isEmpty(q.data))) return <Empty />;
  return <>{children(q.data)}</>;
}

export function ChartCard({ title, subtitle, children, right, height = 320, id }: { title: string; subtitle?: string; children: ReactNode; right?: ReactNode; height?: number; id?: string }) {
  const [full, setFull] = useState(false);
  useEffect(() => {
    if (!full) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && setFull(false);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [full]);
  return (
    <section className={full ? "fixed inset-3 z-50 flex flex-col overflow-hidden rounded-2xl border border-line bg-surface p-5 shadow-2xl" : "card p-4"} aria-label={title} data-testid={id} {...(full ? { role: "dialog", "aria-modal": true } : {})}>
      <header className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 basis-48">
          <h3 className="h-display text-lg leading-tight">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">
          {right}
          <button className="btn !px-2 !py-1" onClick={() => setFull(!full)} aria-label={full ? "Exit fullscreen" : "Fullscreen"} title={full ? "Exit fullscreen (Esc)" : "Fullscreen"}>{full ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}</button>
        </div>
      </header>
      <div className={full ? "min-h-0 flex-1 overflow-auto" : undefined} style={{ minHeight: full ? undefined : height }}>{full ? <div style={{ minHeight: "70vh" }}>{children}</div> : children}</div>
    </section>
  );
}

export function Counter({ value }: { value: number }) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => fmtInt(v));
  useEffect(() => {
    const c = animate(mv, value || 0, { duration: 1.1, ease: "easeOut" });
    return () => c.stop();
  }, [value, mv]);
  return <motion.span className="tabnum">{text}</motion.span>;
}

export function Kpi({ label, value, hint, accent }: { label: string; value: number | string | null | undefined; hint?: string; accent?: string }) {
  return (
    <div className="card relative overflow-hidden p-4" data-testid="kpi">
      <div className="absolute inset-y-0 left-0 w-1" style={{ background: accent || "rgb(var(--accent))" }} />
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-1 font-display text-4xl font-bold leading-none">
        {typeof value === "number" ? <Counter value={value} /> : value ?? "–"}
      </div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function Flag({ noc, size = 20 }: { noc?: string | null; size?: number }) {
  const [bad, setBad] = useState(false);
  if (!noc) return null;
  if (bad)
    return (
      <span className="inline-grid place-items-center rounded bg-surface2 text-[9px] font-semibold text-muted" style={{ width: size * 1.4, height: size }}>
        {noc}
      </span>
    );
  return <img src={flagUrl(noc)} alt={`${noc} flag`} loading="lazy" onError={() => setBad(true)} className="inline-block rounded-sm object-cover shadow" style={{ width: size * 1.4, height: size }} />;
}

export function EditionLogo({ gamesId, size = 64, className = "" }: { gamesId?: string | null; size?: number; className?: string }) {
  const { logos } = useAssets();
  const src = gamesId ? logos[gamesId] : undefined;
  if (!src) return <div className={`grid place-items-center rounded-lg bg-surface2 text-xs text-muted ${className}`} style={{ width: size, height: size }}>{gamesId?.slice(0, 4)}</div>;
  return <img src={src} alt={`${gamesId} logo`} loading="lazy" className={`object-contain ${className}`} style={{ width: size, height: size }} />;
}

export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: string }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div role="tablist" className="scroll-thin sticky top-[57px] z-20 mb-4 flex gap-1 overflow-x-auto border-b border-line bg-bg/90 backdrop-blur lg:top-0">
      {tabs.map((t) => (
        <button type="button" key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={`whitespace-nowrap px-4 py-2 text-sm font-medium transition ${value === t.id ? "border-b-2 border-accent text-accent" : "text-muted hover:text-ink"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

const SECTION: Record<string, { color: string; label: string; Icon: any }> = {
  medals: { color: "#D4AF37", label: "Medal analytics", Icon: Medal }, statistics: { color: "#0085C7", label: "Statistics", Icon: Sigma }, "machine-learning": { color: "#8E6BBF", label: "Machine learning", Icon: Brain },
  records: { color: "#DF0024", label: "Records", Icon: Trophy }, engineering: { color: "#009F3D", label: "Data engineering", Icon: Database }, countries: { color: "#2BB3B1", label: "Countries", Icon: Globe2 },
  athletes: { color: "#E86AA6", label: "Athletes", Icon: Users }, sports: { color: "#FF8A3D", label: "Sports", Icon: Dumbbell }, results: { color: "#F4C300", label: "Event results", Icon: Search },
  "team-sports": { color: "#0085C7", label: "Team sports", Icon: Swords }, visualizations: { color: "#7BA05B", label: "Visualization library", Icon: LineChart }, assets: { color: "#B0B7C3", label: "Assets", Icon: Database },
};

/** What the numbers on an analytics page are built from (live from the API, so it never drifts from the data). */
function DataBasis() {
  const q = useQuery<any>({ queryKey: ["/overview-basis"], queryFn: () => fetch("/api/overview").then((r) => (r.ok ? r.json() : null)), staleTime: 10 * 60_000, retry: 0 });
  const k = q.data?.kpis;
  if (!k) return null;
  return <div className="mt-3 flex flex-wrap gap-2 text-[11px]" data-testid="data-basis">{[[`${k.editions} Games`, "1960–2026"], [fmtInt(k.participations), "participations"], [fmtInt(k.unique_athletes), "athletes"], [fmtInt(k.nocs), "NOCs"]].map(([a, b]) => <span key={a} className="chip"><b className="mr-1 text-ink">{a}</b>{b}</span>)}</div>;
}

/** Page hero: section colour + icon, title, a short summary and the full methodology text on demand. Works outside a router (tests) by falling back to a neutral look. */
export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  const inRouter = useInRouterContext();
  const path = inRouter ? useLocation().pathname : ""; // eslint-disable-line react-hooks/rules-of-hooks
  const sec = SECTION[path.split("/").filter(Boolean)[0] ?? ""];
  const long = (subtitle ?? "").length > 170;
  return (
    <BroadcastPageHeader title={title} right={right} kicker={sec?.label} accent={sec?.color} icon={sec ? <sec.Icon className="h-3.5 w-3.5" /> : undefined}
      subtitle={subtitle ? (long ? (
        <details className="group mt-2 text-sm text-muted"><summary className="cursor-pointer list-none"><span className="line-clamp-2 group-open:line-clamp-none">{subtitle}</span><span className="mt-1 inline-block text-xs underline group-open:hidden">Read the full method note</span></summary></details>
      ) : <p className="mt-2 text-sm text-muted">{subtitle}</p>) : undefined}>
      {sec && <DataBasis />}
    </BroadcastPageHeader>
  );
}

export function Note({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" }) {
  return <div className={`rounded-lg border p-3 text-xs ${tone === "warn" ? "border-yellow/40 bg-yellow/10" : "border-line bg-surface2 text-muted"}`}>{children}</div>;
}

export function Select({ value, onChange, options, label, allLabel = "All" }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label: string; allLabel?: string }) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted">
      {label}
      <select aria-label={label} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SeasonToggle({ value, onChange, label = "Season" }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <div className="inline-flex overflow-hidden rounded-lg border border-line text-sm" role="group" aria-label={label}>
      {[["", "All"], ["summer", "Summer"], ["winter", "Winter"]].map(([v, l]) => (
        <button key={v} aria-pressed={value === v} onClick={() => onChange(v)} className={`px-3 py-1.5 ${value === v ? "bg-accent/15 text-accent" : "text-muted hover:text-ink"}`}>
          {l}
        </button>
      ))}
    </div>
  );
}
