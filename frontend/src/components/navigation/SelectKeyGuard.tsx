import { useEffect } from "react";

const OPEN_KEYS = new Set([" ", "F4"]);
const NAV_KEYS: Record<string, (h: number) => number> = { ArrowDown: () => 60, ArrowUp: () => -60, PageDown: (h) => h * 0.85, PageUp: (h) => -h * 0.85, Home: () => -1e7, End: () => 1e7, ArrowLeft: () => 0, ArrowRight: () => 0 };

/**
 * A focused but CLOSED dropdown must not change its filter on arrow / page keys (browsers do that natively, so after picking an option with the mouse
 * the next ArrowDown would silently change the data). Those keys scroll the page instead. Once the dropdown is opened - by a click, Space, F4 or
 * Alt+ArrowDown - the keys move through its options as usual.
 */
export function SelectKeyGuard() {
  useEffect(() => {
    const open = new WeakSet<EventTarget>();
    const isSelect = (t: EventTarget | null): t is HTMLSelectElement => !!t && (t as HTMLElement).tagName === "SELECT";
    const onDown = (e: MouseEvent) => { if (isSelect(e.target)) { if (open.has(e.target)) open.delete(e.target); else open.add(e.target); } };
    const close = (e: Event) => { if (isSelect(e.target)) open.delete(e.target); };
    const onKey = (e: KeyboardEvent) => {
      const t = e.target;
      if (!isSelect(t)) return;
      if (OPEN_KEYS.has(e.key) || (e.altKey && (e.key === "ArrowDown" || e.key === "ArrowUp"))) { open.add(t); return; }
      if (e.key === "Escape" || e.key === "Enter" || e.key === "Tab") { open.delete(t); return; }
      const step = NAV_KEYS[e.key];
      if (!step || open.has(t)) return;
      e.preventDefault();
      const dy = step(window.innerHeight);
      if (dy) window.scrollBy({ top: dy, behavior: "auto" });
    };
    document.addEventListener("mousedown", onDown, true);
    document.addEventListener("change", close, true);
    document.addEventListener("blur", close, true);
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("mousedown", onDown, true);
      document.removeEventListener("change", close, true);
      document.removeEventListener("blur", close, true);
      document.removeEventListener("keydown", onKey, true);
    };
  }, []);
  return null;
}
