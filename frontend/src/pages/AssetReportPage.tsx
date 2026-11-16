import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Minus } from "lucide-react";
import { PageHeader, Note } from "../components/ui";
import { CsvButton } from "../components/CsvButton";
import { TableFrame } from "../components/tables/TableFrame";
import { useRegistry } from "../themes/olympicThemeEngine";

const Cell = ({ ok, n }: { ok: boolean; n?: number }) => ok ? <span className="inline-flex items-center gap-1 text-green"><Check className="h-4 w-4" aria-label="available" />{n ?? ""}</span> : <span className="inline-flex items-center gap-1 text-yellow"><Minus className="h-4 w-4" aria-label="missing" />missing</span>;

/** Visual asset completeness report: which editions have a complete, partial or unavailable collection (from the asset registry - the files really on disk). */
export default function AssetReportPage() {
  const reg = useRegistry();
  const [season, setSeason] = useState("");
  const [level, setLevel] = useState("");
  const rows = useMemo(() => Object.values(reg.editions).filter((e) => (!season || e.season === season) && (!level || e.completeness.level === level)), [reg, season, level]);
  const all = Object.values(reg.editions);
  const count = (f: (e: any) => boolean) => all.filter(f).length;
  return (
    <div>
      <PageHeader title="Asset completeness" subtitle="Logos, backgrounds, mascots and pictograms per edition. Nothing is invented: a missing item stays missing, and user-supplied images are marked as licence-unverified." />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5" data-testid="asset-summary">
        {[["Editions", all.length], ["Logos", count((e) => e.completeness.logo)], ["Backgrounds", count((e) => e.completeness.background)], ["Mascot images", count((e) => e.completeness.mascot)], ["With pictograms", count((e) => e.completeness.pictograms)]].map(([k, v]) => <div key={k} className="card p-3"><div className="font-display text-3xl leading-none">{v}</div><div className="mt-1 text-[11px] uppercase tracking-wider text-muted">{k}</div></div>)}
      </div>
      <div className="mb-3 flex flex-wrap gap-3">
        <select className="input" value={season} onChange={(e) => setSeason(e.target.value)} aria-label="Season"><option value="">Summer &amp; Winter</option><option value="summer">Summer</option><option value="winter">Winter</option></select>
        <select className="input" value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Level"><option value="">All levels</option><option value="complete">Complete</option><option value="partial">Partial</option><option value="neutral">Neutral theme</option></select>
      </div>
      <TableFrame title="Asset completeness by edition" variant="analytics" actions={<CsvButton name="asset_completeness" headers={["edition", "season", "logo", "background", "mascot_images", "pictograms", "sport_linked", "level"]} rows={rows.map((e) => [e.name, e.season, e.completeness.logo ? "yes" : "missing", e.completeness.background ? "yes" : "missing", e.assets.mascots.length, e.assets.pictograms.length, e.assets.pictograms.filter((p) => p.sportLinked).length, e.completeness.level])} />}>
        <table className="w-full text-sm"><thead><tr>{["Edition", "Colours", "Logo", "Background", "Mascot", "Pictograms", "Sport-linked", "Level"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>{rows.map((e) => (
            <tr key={e.editionId} data-testid="asset-row">
              <td className="td"><Link className="hover:text-accent" to={`/edition/${e.editionId}`}>{e.name}</Link> <span className="text-xs text-muted">{e.season}</span></td>
              <td className="td"><span className="inline-flex gap-1">{[e.theme.primary, e.theme.secondary, e.theme.accent].map((c, i) => <i key={i} className="inline-block h-4 w-4 rounded-full border border-line" style={{ background: c }} title={c} />)}</span></td>
              <td className="td"><Cell ok={e.completeness.logo} /></td><td className="td"><Cell ok={e.completeness.background} /></td>
              <td className="td"><Cell ok={e.completeness.mascot} n={e.assets.mascots.length} /></td><td className="td"><Cell ok={e.completeness.pictograms} n={e.assets.pictograms.length} /></td>
              <td className="td tabnum">{e.assets.pictograms.filter((p) => p.sportLinked).length}/{e.assets.pictograms.length}</td>
              <td className="td"><span className={`chip ${e.completeness.level === "complete" ? "text-green" : "text-yellow"}`}>{e.completeness.level}</span></td>
            </tr>))}</tbody></table>
      </TableFrame>
      <div className="mt-4"><Note tone="warn">Mascot names are not recorded for any edition, and Tokyo 1964 pictograms are called image (n).jpg so they cannot be linked to a sport. Licences of all supplied images are unverified.</Note></div>
    </div>
  );
}
