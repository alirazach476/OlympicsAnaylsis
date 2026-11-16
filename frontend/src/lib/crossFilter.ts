import { useCallback } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { nextParams } from "./urlState";

/**
 * Cross-filter state shared by every chart, table and list of a page. It lives in the URL (?noc=USA&sport=12), so a filtered view can be shared, survives a reload and works with the back button.
 * Clicking a bar, a table row or a legend entry calls set(); every panel that reads the same key reacts.
 */
export function useCrossFilter(keys: string[] = ["noc", "sport"]) {
  const [params, setParams] = useSearchParams();
  const loc = useLocation();
  const values: Record<string, string> = {};
  keys.forEach((k) => { values[k] = params.get(k) ?? ""; });
  const set = useCallback((key: string, value: string | null | undefined, toggle = true) => {
    setParams(nextParams(loc.key, params, (next) => {
      if (!value || (toggle && next.get(key) === value)) next.delete(key); // clicking the active item again clears it
      else next.set(key, value);
    }));   // a discrete choice: its own history entry, so Back returns to the previous selection
  }, [setParams, params, loc.key]);
  const clear = useCallback(() => setParams((prev) => { const next = new URLSearchParams(prev); keys.forEach((k) => next.delete(k)); return next; }, { replace: true }), [setParams, keys.join(",")]);  // eslint-disable-line react-hooks/exhaustive-deps
  return { values, set, clear, active: keys.filter((k) => values[k]) };
}
