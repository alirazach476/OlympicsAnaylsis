import { useState } from "react";
import { Mascot } from "../../themes/olympicThemeEngine";
import { Lightbox } from "./Lightbox";

/** Mascot artwork of one edition. Names / descriptions are shown only when they are recorded; otherwise the card says so instead of inventing text. */
export function MascotGallery({ mascots, editionName }: { mascots: Mascot[]; editionName: string }) {
  const [view, setView] = useState<number | null>(null);
  if (!mascots.length) return <div className="card p-6 text-sm text-muted" data-testid="mascot-missing">No mascot artwork is available for {editionName}. This does not mean the edition had no mascot - the image has not been collected yet.</div>;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="mascot-gallery">
      {mascots.map((m, i) => (
        <figure key={m.src} className="card overflow-hidden">
          <button className="group block w-full" onClick={() => setView(i)} aria-label={`Open ${editionName} mascot`}>
            <div className="grid h-72 place-items-center bg-gradient-to-b from-[var(--ed-tint)] to-transparent p-4"><img src={m.src} alt={`${editionName} mascot`} loading="lazy" className="max-h-full max-w-full object-contain drop-shadow-xl transition group-hover:scale-105" /></div>
          </button>
          <figcaption className="border-t border-line p-4">
            <div className="font-display text-2xl leading-none text-accent">{m.name ?? "Name not recorded"}</div>
            <div className="mt-1 text-xs text-muted">{editionName}</div>
            <div className="mt-2 text-[11px] text-muted">Image supplied for this project · licence {m.verification === "unverified" ? "not verified" : m.verification}. Historical description not available.</div>
          </figcaption>
        </figure>))}
      <Lightbox items={mascots.map((m) => ({ src: m.src, title: m.name ?? `${editionName} mascot`, caption: "licence not verified" }))} index={view} onIndex={setView} onClose={() => setView(null)} />
    </div>
  );
}
