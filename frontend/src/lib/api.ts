import { keepPreviousData, QueryClient, useQuery } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60_000, retry: 1, refetchOnWindowFocus: false } },
});

export const API_BASE = (typeof window !== "undefined" && (window as any).__API_BASE__) || "/api";

export type Params = Record<string, string | number | boolean | null | undefined>;

export function qs(params: Params = {}): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function getJSON<T = any>(path: string, params?: Params): Promise<T> {
  const res = await fetch(`${API_BASE}${path}${qs(params)}`, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).detail ?? "";
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status} ${detail || res.statusText}`);
  }
  return res.json();
}

/** Backend URL for CSV export of any list endpoint that supports ?format=csv */
export const csvUrl = (path: string, params: Params = {}) => `${API_BASE}${path}${qs({ ...params, format: "csv" })}`;

export function useApi<T = any>(path: string | null, params?: Params, enabled = true, opts?: { keepPrevious?: boolean }) {
  return useQuery<T>({
    queryKey: [path, params ?? {}],
    queryFn: () => getJSON<T>(path as string, params),
    enabled: enabled && !!path,
    // a filter change on the same endpoint keeps the current data on screen until the new data arrives, so the page never collapses to a spinner and jumps;
    // a different endpoint (another page / event) never shows the previous page's data
    placeholderData: (opts?.keepPrevious ? keepPreviousData : (prev: T | undefined, prevQuery: any) => (prevQuery?.queryKey?.[0] === path ? prev : undefined)) as any,
  });
}
