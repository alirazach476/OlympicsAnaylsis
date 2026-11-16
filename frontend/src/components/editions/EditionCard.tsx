import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Flag } from "../ui";
import { fmtInt, fmtPct } from "../../lib/fmt";
import { useTheme } from "../../lib/theme";
import { themeVars, useRegistry } from "../../themes/olympicThemeEngine";

/** One edition painted with its own colours, emblem, background and mascot (from the asset registry). `g` is a row of /api/games. */
export function EditionCard({ g, index = 0, id }: { g: any; index?: number; id?: string }) {
  const reg = useRegistry();
  const { theme: mode } = useTheme();
  const ed = reg.editions[g.games_id];
  const th = ed?.theme ?? reg.neutralTheme;
  return (
    <motion.div id={id} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index * 0.03, 0.5) }} style={themeVars(th, mode)}>
      <Link to={`/edition/${g.games_id}`} className="group relative block overflow-hidden rounded-2xl border border-line bg-surface transition hover:-translate-y-0.5" data-testid="edition-card" style={{ boxShadow: "0 18px 50px -34px var(--ed-glow)" }}>
        <div className="relative h-36 overflow-hidden">
          {ed?.assets.background && <img src={ed.assets.background} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105" />}
          <div className="absolute inset-0" style={{ background: "linear-gradient(135deg, var(--ed-primary) 0%, transparent 70%)", opacity: ed?.assets.background ? 0.55 : 0.9 }} />
          <div className="absolute inset-0 bg-gradient-to-t from-surface via-surface/10 to-transparent" />
          <div className="absolute left-4 top-3 font-display text-6xl font-bold leading-none tracking-tight text-white drop-shadow-lg">{g.year}</div>
          {ed?.assets.mascots?.[0] && <img src={ed.assets.mascots[0].src} alt="" loading="lazy" className="absolute bottom-0 right-3 h-28 max-w-[42%] rounded-lg object-contain drop-shadow-xl" />}
        </div>
        <div className="relative -mt-9 px-4 pb-4">
          <div className="flex items-end gap-3">
            {ed?.assets.logo ? <img src={ed.assets.logo} alt={`${g.host_city} ${g.year} emblem`} loading="lazy" className="h-[72px] w-[72px] rounded-xl bg-white/95 object-contain p-1.5 shadow-lg" /> : <div className="grid h-[72px] w-[72px] place-items-center rounded-xl bg-surface2 text-[10px] text-muted">no emblem</div>}
            <div className="min-w-0 pb-1"><div className="truncate font-display text-2xl font-semibold leading-none" style={{ color: "var(--ed-accent)" }}>{g.host_city}</div><div className="mt-1 flex items-center gap-2 text-xs text-muted"><Flag noc={g.host_noc} size={13} /> {g.host_country}</div></div>
          </div>
          <dl className="mt-4 grid grid-cols-4 gap-2 text-center">
            {[["Athletes", fmtInt(g.athletes)], ["NOCs", fmtInt(g.nocs)], ["Sports", fmtInt(g.sports)], ["Events", fmtInt(g.events)]].map(([k, v]) => (
              <div key={k}><dd className="font-display text-xl leading-none">{v}</dd><dt className="mt-0.5 text-[10px] uppercase tracking-wider text-muted">{k}</dt></div>))}
          </dl>
          <div className="mt-3 border-t border-line pt-2 text-xs text-muted">
            <span className="mr-2 font-semibold uppercase tracking-wider">Medal table</span>
            {(g.podium_preview || "").split(" ").filter(Boolean).map((p: string) => { const [noc, gsb] = p.split(":"); return <span key={noc} className="mr-3 inline-flex items-center gap-1"><Flag noc={noc} size={11} />{noc} <span className="tabnum text-ink">{gsb}</span></span>; })}
          </div>
          <div className="mt-1 flex items-center justify-between text-[11px] text-muted"><span>Women {fmtPct(g.female_share, 0)} of athletes</span><span>{ed ? `${ed.assets.pictograms.length} pictograms · ${ed.assets.mascots.length ? "mascot" : "no mascot image"}` : ""}</span></div>
        </div>
      </Link>
    </motion.div>
  );
}
