import { useEffect, useState } from "react";
import { OlympicRings } from "./OlympicRings";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Award, Home, Medal, Menu, Moon, Search, Snowflake, Sun, Trophy, Users, X, Dumbbell, LineChart } from "lucide-react";
import { motion, MotionConfig } from "framer-motion";
import { useTheme } from "../lib/theme";
import { SearchPalette } from "./navigation/SearchPalette";
import { ScrollManager } from "./navigation/ScrollManager";
import { SelectKeyGuard } from "./navigation/SelectKeyGuard";
import { EditionBrandProvider, useEditionBrand } from "../themes/editionBrand";
import { useRegistry } from "../themes/olympicThemeEngine";
import { EditionBackground, EditionLogo } from "./broadcast/design";

/** Main menu. `match` lists the other paths that belong to the same section (so the item stays active on its sub-pages). Admin pages (/assets, /crawler, /engineering) keep their routes but are not in the public menu. */
export const NAV = [
  { to: "/", label: "Global Overview", icon: Home, match: [] as string[], group: "Olympic Games", ring: "#0085C7" },
  { to: "/summer", label: "Summer Olympics", icon: Sun, match: [] , group: "Olympic Games", ring: "#F4C300" },
  { to: "/winter", label: "Winter Olympics", icon: Snowflake, match: [] , group: "Olympic Games", ring: "#60C8FF" },
  { to: "/olympics", label: "Games & Results", icon: Trophy, match: ["/games/", "/results"] , group: "Olympic Games", ring: "#009F3D" },
  { to: "/sports", label: "Sports", icon: Dumbbell, match: [] , group: "Explore", ring: "#DF0024" },
  { to: "/countries", label: "Countries & Medal Statistics", icon: Medal, match: ["/medals/countries", "/medals/editions/", "/compare/countries"] , group: "Explore", ring: "#0085C7" },
  { to: "/athletes", label: "Athletes", icon: Users, match: [] , group: "Explore", ring: "#F4C300" },
  { to: "/visualizations", label: "Analytics", icon: LineChart, match: [] , group: "Insights", ring: "#009F3D" },
  { to: "/records", label: "Records", icon: Award, match: [] , group: "Insights", ring: "#DF0024" },
];
/** Which menu item a path belongs to: its own path and sub-paths, plus the paths in `match`. An edition page counts under its season. */
export function isActive(pathname: string, item: (typeof NAV)[number]) {
  if (item.to === "/") return pathname === "/";
  if (pathname.startsWith("/edition/")) return item.to === (pathname.endsWith("_winter") ? "/winter" : "/summer");
  const under = (p: string) => (p.endsWith("/") ? pathname.startsWith(p) : pathname === p || pathname.startsWith(p + "/"));
  if (item.to === "/visualizations") return under("/visualizations") || pathname === "/medals" || pathname === "/compare" || ["/statistics", "/machine-learning", "/team-sports", "/engineering"].some(under);
  return under(item.to) || item.match.some(under);
}

const CRUMB: Record<string, string> = { summer: "Summer Olympics", winter: "Winter Olympics", edition: "Editions", countries: "Countries & Medal Statistics", athletes: "Athletes", sports: "Sports", results: "Games & Results", medals: "Analytics",
  statistics: "Statistical Analysis", "machine-learning": "Machine Learning", "team-sports": "Team Sports", records: "Records", visualizations: "Analytics", engineering: "Data Engineering", assets: "Asset Completeness", compare: "Compare", olympics: "Games & Results", crawler: "Wikipedia Crawler" };

const ANALYTICS = [["/visualizations", "Visualization library"], ["/medals", "Medal analytics"], ["/statistics", "Statistical analysis"], ["/machine-learning", "Machine learning"], ["/team-sports", "Team sports"], ["/compare", "Compare editions"], ["/engineering", "Data engineering"]];
/** Sub-sections of Analytics, shown as a strip on every analytics page. */
function AnalyticsNav() {
  const { pathname } = useLocation();
  if (!isActive(pathname, NAV.find((n) => n.to === "/visualizations")!)) return null;
  return (
    <nav aria-label="Analytics sections" className="scroll-thin mb-4 flex gap-1.5 overflow-x-auto pb-1" data-testid="analytics-nav">
      {ANALYTICS.map(([to, label]) => <NavLink key={to} to={to} end className={({ isActive: a }) => `shrink-0 rounded-full border px-3 py-1 text-xs transition ${a ? "border-[var(--ed-accent)] bg-[var(--ed-tint)] font-semibold text-ink" : "border-line text-muted hover:text-ink"}`}>{label}</NavLink>)}
    </nav>
  );
}

/** Home › section › detail, derived from the URL (the page itself shows the full name). */
function Breadcrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length) return null;
  // Olympedia-style pages draw their own full trail (edition › sport › event › match)
  if (parts[0] === "games" || (parts[0] === "medals" && parts.length > 1) || (parts[0] === "countries" && parts[2] === "editions")) return null;
  const first = parts[0];
  const section = first === "edition" ? (parts[1]?.endsWith("winter") ? "/winter" : "/summer") : "/" + first;
  return (
    <nav aria-label="Breadcrumb" className="mb-3 text-xs text-muted" data-testid="breadcrumbs">
      <ol className="flex flex-wrap items-center gap-1.5"><li><NavLink to="/" className="hover:text-accent">Home</NavLink></li>
        <li aria-hidden>›</li><li>{parts.length > 1 ? <NavLink to={section} className="hover:text-accent">{CRUMB[first === "edition" ? (parts[1]?.endsWith("winter") ? "winter" : "summer") : first] ?? first}</NavLink> : <span aria-current="page" className="text-ink">{CRUMB[first] ?? first}</span>}</li>
        {parts.length > 1 && <><li aria-hidden>›</li><li aria-current="page" className="text-ink"><span className="capitalize">{decodeURIComponent(parts[parts.length - 1]).replace(/_/g, " ")}</span></li></>}
      </ol>
    </nav>
  );
}

/** Global overview background: the Olympic-wide image at /assets/backgrounds/overview.(webp|jpg|png) when it is present, under a readable veil; otherwise a clean treatment in the five ring colours. */
function OverviewBackground() {
  const [src, setSrc] = useState<string | null>("/assets/backgrounds/overview.png");
  const next: Record<string, string | null> = { "/assets/backgrounds/overview.png": "/assets/backgrounds/overview.webp", "/assets/backgrounds/overview.webp": "/assets/backgrounds/overview.jpg", "/assets/backgrounds/overview.jpg": null };
  return (
    <div aria-hidden data-testid="overview-background" data-image={src ?? "none"} className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {src && <img src={src} alt="" className="absolute inset-0 h-full w-full object-cover opacity-70" onError={() => setSrc(next[src] ?? null)} />}
      <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgb(var(--bg) / 0.35) 0%, rgb(var(--bg) / 0.62) 35%, rgb(var(--bg) / 0.80) 100%)" }} />
      <div className="absolute inset-0" style={{ background: "radial-gradient(700px 380px at 10% 0%, #0085C733, transparent 70%), radial-gradient(700px 380px at 50% -10%, #F4C30026, transparent 70%), radial-gradient(700px 380px at 90% 0%, #DF002433, transparent 70%), radial-gradient(900px 420px at 30% 100%, #009F3D22, transparent 70%)" }} />
      <div className="ed-stripe absolute inset-x-0 top-0 h-1.5" style={{ background: "linear-gradient(90deg, #0085C7 0 20%, #F4C300 20% 40%, #1a1a1a 40% 60%, #009F3D 60% 80%, #DF0024 80%)" }} />
    </div>
  );
}

/** Every page lives inside the selected edition's broadcast identity: one provider, one background, one switcher. */
export default function Shell() {
  return <EditionBrandProvider><ShellInner /></EditionBrandProvider>;
}

function EditionSwitcher({ onPick }: { onPick?: () => void }) {
  const b = useEditionBrand();
  const reg = useRegistry();
  const nav = useNavigate();
  const loc = useLocation();
  // choosing a Games opens it: its edition page (on a Games & Results page, that edition's results - handled by setGamesId)
  const pick = (id: string) => {
    if (!id) return;
    if (/^\/(games|edition)\//.test(loc.pathname)) b.setGamesId(id);   // already navigates to the chosen edition's page / results
    else nav(`/edition/${id}`);
    onPick?.();
  };
  const list = Object.values(reg.editions).filter((e) => e.year <= 2026).sort((a, c) => c.year - a.year || (a.season > c.season ? 1 : -1));
  if (!list.length) return null;
  const ed = b.edition;
  return (
    <label className="group relative mb-4 block shrink-0 cursor-pointer overflow-hidden rounded-2xl border border-white/10 shadow-lg" data-testid="edition-switcher">
      {ed?.assets.background && <img src={ed.assets.background} alt="" aria-hidden className="absolute inset-0 h-full w-full object-cover opacity-70 transition duration-500 group-hover:scale-105" />}
      <span className="absolute inset-0" style={{ background: "linear-gradient(100deg, color-mix(in srgb, var(--ed-deep, var(--ed-primary, #1e3a5f)) 92%, #04060b) 30%, color-mix(in srgb, var(--ed-deep, var(--ed-primary, #1e3a5f)) 40%, transparent))" }} />
      <span className="relative flex items-center gap-3 p-2.5">
        <EditionLogo size={46} className="!rounded-xl ring-2 ring-white/30" />
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block text-[9px] font-bold uppercase tracking-[0.25em] text-white/70">Selected Games</span>
          <span className="block truncate font-display text-lg font-semibold text-white">{ed?.name ?? "Choose an edition"}</span>
          <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--ed-accent)" }}>{ed?.season} {ed?.year}</span>
        </span>
        <span className="grid h-7 w-7 place-items-center rounded-full bg-white/15 text-white transition group-hover:bg-white/25" aria-hidden>▾</span>
      </span>
      <select aria-label="Selected edition" className="absolute inset-0 cursor-pointer opacity-0" value={b.gamesId} onChange={(e) => pick(e.target.value)}>
        {list.map((e) => <option key={e.editionId} value={e.editionId} className="bg-surface text-ink">{e.name} · {e.season}</option>)}
      </select>
    </label>
  );
}

/** One menu entry: an icon chip in its Olympic-ring colour, the label, and - when active - a glowing pill in the edition colours with a lit accent bar. */
function MenuItem({ item, active, onClick }: { item: (typeof NAV)[number]; active: boolean; onClick: () => void }) {
  const Icon = item.icon;
  return (
    <NavLink to={item.to} end onClick={onClick} aria-current={active ? "page" : undefined} data-active={active || undefined}
      className={`menu-item group relative flex items-center gap-3 rounded-xl px-2.5 py-2 text-[13.5px] transition duration-200 ${active ? "font-semibold text-white" : "text-ink/75 hover:translate-x-0.5 hover:text-ink"}`}
      style={{ ["--ring" as any]: item.ring, ...(active ? { background: "linear-gradient(100deg, color-mix(in srgb, var(--ed-primary, #1e3a5f) 85%, #04060b), color-mix(in srgb, var(--ed-accent, #c9a227) 35%, transparent))", boxShadow: "0 10px 28px -12px var(--ed-glow, rgba(0,0,0,.6)), inset 0 1px 0 rgb(255 255 255 / 0.12)" } : {}) }}>
      <span className="absolute -left-3 top-1/2 h-7 w-1 -translate-y-1/2 rounded-r-full transition" style={{ background: active ? "var(--ed-accent)" : "transparent", boxShadow: active ? "0 0 12px var(--ed-accent)" : "none" }} />
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg transition duration-200 group-hover:scale-105"
        style={active ? { background: "rgb(255 255 255 / 0.18)", color: "#fff" } : { background: "color-mix(in srgb, var(--ring) 16%, transparent)", color: "var(--ring)", boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--ring) 35%, transparent)" }}>
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 leading-tight">{item.label}</span>
      {active && <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--ed-accent)", boxShadow: "0 0 8px var(--ed-accent)" }} />}
    </NavLink>
  );
}

function ShellInner() {
  const { theme, toggle } = useTheme();
  const brand = useEditionBrand();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState(false);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearch(true); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  const loc = useLocation();
  const home = loc.pathname === "/";   // the global overview has its own Olympic-wide identity, not an edition's
  const season = loc.pathname.includes("winter") ? "winter" : loc.pathname.includes("summer") ? "summer" : undefined;
  return (
    <MotionConfig reducedMotion="user">
    <ScrollManager />
    <SelectKeyGuard />
    <div className="relative min-h-screen lg:grid lg:grid-cols-[272px_1fr]" data-season={season} data-edition={home ? undefined : brand.gamesId} style={home ? undefined : brand.style}>
      {home ? <OverviewBackground /> : <EditionBackground />}
      <a href="#main" className="sr-only z-50 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-black focus:not-sr-only focus:fixed focus:left-3 focus:top-3">Skip to content</a>
      <SearchPalette open={search} onClose={() => setSearch(false)} />
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-bg/90 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex items-center gap-2"><OlympicRings size={44} /><div className="h-display text-xl">Olympic <span className="text-accent">Intelligence</span></div></div>
        <div className="flex gap-2">
          <button className="btn" onClick={() => setSearch(true)} aria-label="Search"><Search className="h-4 w-4" /></button>
          <button className="btn" onClick={toggle} aria-label="Toggle theme">{theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
          <button className="btn" onClick={() => setOpen(!open)} aria-label="Menu" aria-expanded={open}>{open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}</button>
        </div>
      </header>
      <aside className={`${open ? "flex" : "hidden"} fixed inset-x-0 top-[57px] z-20 max-h-[calc(100vh-57px)] flex-col overflow-y-auto border-b border-line bg-surface px-3 pb-3 lg:sticky lg:top-0 lg:flex lg:h-screen lg:max-h-none lg:border-b-0 lg:border-r ${home ? "" : "ed-nav"}`}
        data-testid="menu-bar" style={home ? { backgroundImage: "linear-gradient(180deg, rgb(var(--surface) / 0.82), rgb(var(--surface) / 0.94)), url(/assets/backgrounds/overview.png)", backgroundSize: "cover", backgroundPosition: "center" } : undefined}>
        <div className="ed-stripe -mx-3 mb-3 h-1.5 shrink-0" data-testid="nav-stripe" />
        {/* brand */}
        <NavLink to="/" onClick={() => setOpen(false)} className="relative mb-4 hidden shrink-0 overflow-hidden rounded-2xl border border-white/10 bg-black/25 px-4 pb-4 pt-3 text-center shadow-lg backdrop-blur-sm lg:block" aria-label="Olympic Intelligence, home">
          <span className="pointer-events-none absolute -top-10 left-1/2 h-24 w-40 -translate-x-1/2 rounded-full opacity-40 blur-2xl" style={{ background: "var(--ed-accent, #c9a227)" }} />
          <OlympicRings size={132} className="relative mx-auto mb-2" />
          <div className="relative font-display text-[26px] font-bold uppercase leading-none tracking-wide">
            Olympic <span className="bg-clip-text text-transparent" style={{ backgroundImage: "linear-gradient(90deg, #0085C7, #F4C300 45%, #009F3D 70%, #DF0024)" }}>Intelligence</span>
          </div>
          <div className="relative mt-1.5 whitespace-nowrap text-[9.5px] font-semibold uppercase tracking-[0.16em] text-muted">Summer &amp; Winter · 1960–2026</div>
        </NavLink>
        <EditionSwitcher onPick={() => setOpen(false)} />
        <button className="mb-4 hidden w-full shrink-0 items-center justify-between rounded-xl border border-line bg-surface2/70 px-3 py-2 text-sm text-muted transition hover:border-[var(--ed-accent)] hover:text-ink lg:flex" onClick={() => setSearch(true)} aria-label="Search">
          <span className="inline-flex items-center gap-2"><Search className="h-4 w-4" /> Search everything</span><kbd className="rounded-md border border-line bg-surface px-1.5 py-0.5 text-[10px]">Ctrl K</kbd>
        </button>
        <nav className="flex shrink-0 flex-col gap-0.5" aria-label="Main">
          {NAV.map((item, i) => (
            <div key={item.to}>
              {(i === 0 || NAV[i - 1].group !== item.group) && <div className="mb-1.5 mt-3 flex items-center gap-2 px-2.5 text-[10px] font-bold uppercase tracking-[0.25em] text-muted first:mt-0"><span>{item.group}</span><span className="h-px flex-1 bg-line" /></div>}
              <MenuItem item={item} active={isActive(loc.pathname, item)} onClick={() => setOpen(false)} />
            </div>))}
        </nav>
        <div className="mt-auto hidden shrink-0 pt-5 lg:block">
          <div className="flex rounded-xl border border-line bg-surface2/70 p-1 text-xs font-semibold" role="group" aria-label="Colour theme">
            {(["dark", "light"] as const).map((m) => <button key={m} type="button" onClick={() => theme !== m && toggle()} aria-pressed={theme === m}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-1.5 transition ${theme === m ? "bg-[var(--ed-accent)] text-black shadow" : "text-muted hover:text-ink"}`}>{m === "dark" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}{m === "dark" ? "Dark" : "Light"}</button>)}
          </div>
          <p className="mt-2 text-center text-[10px] text-muted">Data: Olympedia · Wikipedia</p>
        </div>
      </aside>
      <main id="main" tabIndex={-1} className="relative z-10 min-w-0 px-4 py-6 outline-none sm:px-6 lg:px-8"><Breadcrumbs /><AnalyticsNav />
        <motion.div key={loc.pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}><Outlet /></motion.div></main>
    </div>
    </MotionConfig>
  );
}
