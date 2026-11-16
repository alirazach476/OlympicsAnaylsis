import { ReactNode } from "react";
import { TableHead } from "./TableHead";

/**
 * The broadcast frame for tables that are not built with DataTable (a saved Olympedia page table, a line-up, a small summary): edition accent rule, a heading band with the
 * selected edition's emblem chip, optional title and actions (the CSV button), and a scrolling body. Same look as DataTable, so every table in the app reads as one system.
 */
export function TableFrame({ title, subtitle, variant = "analytics", actions, children, gamesId, sport }: { title?: ReactNode; subtitle?: ReactNode; variant?: string; actions?: ReactNode; children: ReactNode; /** the edition this table belongs to, when not the selected one */ gamesId?: string; /** the sport, for the pictogram on the right of the header */ sport?: string | null }) {
  return (
    <div data-csv-scope="true" data-variant={variant} data-testid="broadcast-table" className="ed-table overflow-hidden rounded-2xl border border-line bg-surface/95" style={{ borderTop: "3px solid var(--ed-accent)" }}>
      <TableHead title={title} subtitle={subtitle} actions={actions} gamesId={gamesId} sport={sport} />
      <div className="scroll-thin overflow-x-auto">{children}</div>
    </div>
  );
}
