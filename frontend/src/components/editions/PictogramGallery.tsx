import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { groupPictograms, Pictogram } from "../../themes/olympicThemeEngine";
import { Lightbox } from "./Lightbox";

const pretty = (s: string) => s.replace(/\b\w/g, (c) => c.toUpperCase());

/** Pictograms of ONE edition, grouped by sport. A pictogram is attached to a sport only when its file name names that sport; the others are shown, labelled "not linked". */
export function PictogramGallery({ pictograms, editionName }: { pictograms: Pictogram[]; editionName: string }) {
  const [q, setQ] = useState("");
  const [sport, setSport] = useState("");
  const [view, setView] = useState<number | null>(null);
  const groups = useMemo(() => groupPictograms(pictograms), [pictograms]);
  const flat = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return groups
      .filter(([g]) => !sport || g === sport)
      .flatMap(([g, items]) => items.map((p) => ({ g, p })))
      .filter(({ g, p }) => !ql || g.toLowerCase().includes(ql) || (p.label ?? "").includes(ql) || (p.discipline ?? "").includes(ql));
  }, [groups, q, sport]);
  if (!pictograms.length) return <div className="card p-6 text-sm text-muted" data-testid="pictograms-missing">No pictogram images are available for {editionName}.</div>;
  const linked = pictograms.filter((p) => p.sportLinked).length;
  return (
    <div data-testid="pictogram-gallery">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <label className="relative"><Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted" /><input className="input pl-8" placeholder="Search sport…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search pictograms by sport" /></label>
        <select className="input" value={sport} onChange={(e) => setSport(e.target.value)} aria-label="Filter by sport"><option value="">All sports ({groups.length})</option>{groups.map(([g, it]) => <option key={g} value={g}>{g} ({it.length})</option>)}</select>
        <span className="text-xs text-muted">{pictograms.length} images · {linked} linked to a sport by file name{linked < pictograms.length ? ` · ${pictograms.length - linked} not linked` : ""}</span>
      </div>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
        {flat.map(({ g, p }, i) => (
          <li key={p.src}>
            <button onClick={() => setView(i)} className="group card flex h-full w-full flex-col items-center gap-2 p-3 text-center transition hover:border-accent" aria-label={`${g}${p.discipline ? " " + p.discipline : ""} pictogram`}>
              <span className="grid aspect-square w-full place-items-center rounded-lg bg-white p-2"><img src={p.src} alt={`${g} pictogram, ${editionName}`} loading="lazy" className="max-h-full max-w-full object-contain transition group-hover:scale-105" /></span>
              <span className="text-[11px] font-semibold leading-tight">{p.sportLinked ? g : "Not linked to a sport"}</span>
              {p.discipline && <span className="text-[10px] uppercase tracking-wider text-muted">{p.discipline}</span>}
            </button>
          </li>))}
      </ul>
      {!flat.length && <div className="card mt-3 p-4 text-sm text-muted">No pictogram matches your search.</div>}
      <Lightbox items={flat.map(({ g, p }) => ({ src: p.src, title: p.sportLinked ? pretty(g) + (p.discipline ? ` · ${pretty(p.discipline)}` : "") : "Pictogram (sport not recorded)", caption: `${editionName} · user-supplied image, licence not verified${p.sportLinked ? " · sport taken from the file name" : ""}` }))} index={view} onIndex={setView} onClose={() => setView(null)} />
    </div>
  );
}
