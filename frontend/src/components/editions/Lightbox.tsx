import { useEffect, useRef } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

export type LightboxItem = { src: string; title: string; caption?: string };

/** Full-size image viewer: Esc closes, ← → move, focus is trapped on the dialog and restored on close. */
export function Lightbox({ items, index, onIndex, onClose }: { items: LightboxItem[]; index: number | null; onIndex: (i: number) => void; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const open = index !== null && index >= 0 && index < items.length;
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") onIndex((index! + 1) % items.length);
      if (e.key === "ArrowLeft") onIndex((index! - 1 + items.length) % items.length);
    };
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("keydown", key); prev?.focus?.(); };
  }, [open, index, items.length, onClose, onIndex]);
  if (!open) return null;
  const it = items[index!];
  return (
    <div ref={ref} role="dialog" aria-modal="true" aria-label={it.title} tabIndex={-1} onClick={onClose}
      className="fixed inset-0 z-50 grid place-items-center bg-black/85 p-4 backdrop-blur-sm outline-none" data-testid="lightbox">
      <button className="btn absolute right-4 top-4" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
      {items.length > 1 && <button className="btn absolute left-4 top-1/2 -translate-y-1/2" onClick={(e) => { e.stopPropagation(); onIndex((index! - 1 + items.length) % items.length); }} aria-label="Previous"><ChevronLeft className="h-4 w-4" /></button>}
      {items.length > 1 && <button className="btn absolute right-4 top-1/2 -translate-y-1/2" onClick={(e) => { e.stopPropagation(); onIndex((index! + 1) % items.length); }} aria-label="Next"><ChevronRight className="h-4 w-4" /></button>}
      <figure className="flex max-h-full max-w-4xl flex-col items-center gap-3" onClick={(e) => e.stopPropagation()}>
        <div className="rounded-xl bg-white/95 p-6 shadow-2xl"><img src={it.src} alt={it.title} className="max-h-[68vh] max-w-full object-contain" /></div>
        <figcaption className="text-center text-sm text-white/90"><div className="font-display text-2xl tracking-wide">{it.title}</div>{it.caption && <div className="mt-1 text-xs text-white/60">{it.caption}</div>}<div className="mt-1 text-[11px] text-white/40">{index! + 1} / {items.length}</div></figcaption>
      </figure>
    </div>
  );
}
