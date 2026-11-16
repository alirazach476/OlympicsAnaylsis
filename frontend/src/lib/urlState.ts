/**
 * Composes several URL-parameter updates made in one event handler (sort + order, "Clear all", sport + event).
 * React Router's functional setSearchParams receives the params of the render that created the setter, so a second call in the same handler
 * would overwrite the first. The first update of a location records its result here; later updates of the SAME location (same key) build on it.
 * Works with BrowserRouter and MemoryRouter alike (it never reads window.location).
 */
let pending: { key: string; base: string; search: string } | null = null;

export function nextParams(locationKey: string, current: URLSearchParams, mutate: (n: URLSearchParams) => void): URLSearchParams {
  const cur = current.toString();
  // reuse only within the same render of the same history entry (same key AND same starting parameters)
  const base = pending && pending.key === locationKey && pending.base === cur ? new URLSearchParams(pending.search) : new URLSearchParams(current);
  mutate(base);
  pending = { key: locationKey, base: cur, search: base.toString() };
  return base;
}
