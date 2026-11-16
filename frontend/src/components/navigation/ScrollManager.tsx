import { useEffect, useLayoutEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

const KEY = "scroll-positions";
const read = (): Record<string, number> => { try { return JSON.parse(sessionStorage.getItem(KEY) || "{}"); } catch { return {}; } };
const write = (m: Record<string, number>) => { try { sessionStorage.setItem(KEY, JSON.stringify(m)); } catch { /* storage blocked: positions are only kept in memory */ } };
const mem: Record<string, number> = read();

/**
 * Browser-like scroll handling for the client-side router:
 *  - a new page (push / replace to another path) starts at the top;
 *  - Back / Forward (POP) returns to where that history entry was scrolled, waiting for its data to render;
 *  - a filter change on the same page (only ?query changes) keeps the scroll position.
 */
export function ScrollManager() {
  const loc = useLocation();
  const type = useNavigationType();
  useEffect(() => {
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    const save = () => { mem[history.state?.key ?? "init"] = window.scrollY; };
    const persist = () => { save(); write(mem); };
    window.addEventListener("scroll", save, { passive: true });
    window.addEventListener("pagehide", persist);
    return () => { window.removeEventListener("scroll", save); window.removeEventListener("pagehide", persist); };
  }, []);
  // remember the path of the previous render to tell a page change from a filter change
  useLayoutEffect(() => {
    const prev = (ScrollManager as any).last as string | undefined;
    (ScrollManager as any).last = loc.pathname;
    write(mem);
    if (type === "POP") {
      const y = mem[loc.key] ?? mem[history.state?.key] ?? 0;
      let tries = 0;
      const restore = () => {
        // keep trying while the page is still shorter than the saved position (data loading), for up to ~3 s
        if (document.documentElement.scrollHeight - window.innerHeight >= y - 2 || tries > 60) { window.scrollTo(0, y); return; }
        tries++; window.scrollTo(0, y); setTimeout(restore, 50);
      };
      restore();
    } else if (prev !== loc.pathname && !loc.hash) {
      window.scrollTo(0, 0);
    }
  }, [loc.key]);  // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}
