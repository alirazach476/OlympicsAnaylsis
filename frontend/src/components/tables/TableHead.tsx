import { createContext, ReactNode, useContext } from "react";
import { useEditionBrand } from "../../themes/editionBrand";
import { EditionLogo, SportPictogram } from "../broadcast/design";

/**
 * Which edition and sport the tables of a page belong to. A result / match / bout / heat page provides it, so every table header on that page
 * shows that edition's emblem on the left and that sport's pictogram on the right.
 */
export const TableContext = createContext<{ gamesId?: string; sport?: string | null }>({});
export const TableScope = ({ gamesId, sport, children }: { gamesId?: string; sport?: string | null; children: ReactNode }) => <TableContext.Provider value={{ gamesId, sport }}>{children}</TableContext.Provider>;

/**
 * The heading band of every broadcast table: on a dark ground made of the edition's own background artwork and its deepest colour, the edition emblem
 * (white tile) and name on the left, the title in the middle, the sport pictogram and the table's actions (CSV, filter) on the right.
 */
export function TableHead({ title, subtitle, meta, actions, gamesId, sport, branding = true }: {
  title?: ReactNode; subtitle?: ReactNode; meta?: ReactNode; actions?: ReactNode; gamesId?: string; sport?: string | null; branding?: boolean;
}) {
  const ctx = useContext(TableContext);
  const b = useEditionBrand();
  const gid = gamesId ?? ctx.gamesId;
  const sp = sport ?? ctx.sport;
  const ed = b.editionOf(gid);
  return (
    <div className="ed-table-head flex flex-wrap items-center justify-between gap-3 px-3 py-3 text-xs sm:px-4" data-testid="table-head" data-edition={branding ? ed?.editionId : undefined} data-sport={sp ?? undefined}>
      <span className="flex min-w-0 items-center gap-3">
        {branding && ed && <EditionLogo gamesId={gid} size={48} className="!rounded-xl ring-2 ring-white/25" />}
        <span className="min-w-0">
          {branding && ed && <span className="block text-[10px] font-bold uppercase tracking-[0.22em] text-white/70" data-testid="table-edition">{ed.name} · {ed.season}</span>}
          {title ? <b className="block truncate font-display text-lg leading-tight text-white">{title}</b> : null}
          {(subtitle || meta) && <span className="block truncate text-white/70">{subtitle}{subtitle && meta ? " · " : ""}{meta}</span>}
        </span>
      </span>
      <span className="flex flex-wrap items-center gap-2">
        {actions}
        {sp && <span className="rounded-xl bg-white/10 p-1 ring-1 ring-white/20" data-testid="table-pictogram"><SportPictogram sport={sp} gamesId={gid} size={44} /></span>}
      </span>
    </div>
  );
}
