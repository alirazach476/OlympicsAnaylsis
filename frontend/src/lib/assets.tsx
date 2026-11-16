import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Manifest = { logos: Record<string, string>; backgrounds: Record<string, string>; pictograms: Record<string, string[]> };
const Ctx = createContext<Manifest>({ logos: {}, backgrounds: {}, pictograms: {} });

/** Loads /assets/manifest.json (written by scripts/sync_assets.py) once. Missing manifest => components fall back gracefully. */
export function AssetProvider({ children }: { children: ReactNode }) {
  const [m, setM] = useState<Manifest>({ logos: {}, backgrounds: {}, pictograms: {} });
  useEffect(() => {
    fetch("/assets/manifest.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => j && setM(j))
      .catch(() => undefined);
  }, []);
  return <Ctx.Provider value={m}>{children}</Ctx.Provider>;
}

export const useAssets = () => useContext(Ctx);
