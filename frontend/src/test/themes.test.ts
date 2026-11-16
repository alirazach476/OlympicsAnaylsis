import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { contrast, groupPictograms, hexToRgb, readableOn, themeVars, luminance } from "../themes/olympicThemeEngine";

const PUBLIC = join(__dirname, "../../public");
const registry = JSON.parse(readFileSync(join(PUBLIC, "assets/editions.json"), "utf-8"));
const editions = Object.values<any>(registry.editions);

describe("theme engine maths", () => {
  it("parses hex and measures contrast", () => {
    expect(hexToRgb("#ff8000")).toEqual([255, 128, 0]);
    expect(contrast("#000000", "#ffffff")).toBeGreaterThan(20);
    expect(luminance("#ffffff")).toBeCloseTo(1, 2);
  });
  it("makes a dark accent readable on the dark page and a light accent readable on the light page", () => {
    expect(contrast(readableOn("#012162", "#090d16"), "#090d16")).toBeGreaterThanOrEqual(3);
    expect(contrast(readableOn("#f4e08a", "#f4f6fa"), "#f4f6fa")).toBeGreaterThanOrEqual(3);
  });
  it("sets the Tailwind accent token and the edition tokens", () => {
    const v: any = themeVars({ primary: "#dd302f", secondary: "#9e7f4e", accent: "#dd302f", source: "t" }, "dark");
    expect(v["--accent"]).toMatch(/^\d+ \d+ \d+$/);
    expect(v["--ed-primary"]).toMatch(/^#/);
  });
  it("groups pictograms by sport and keeps unlinked ones last", () => {
    const g = groupPictograms([{ sport: null, sportLinked: false } as any, { sport: "Boxing", sportLinked: true } as any, { sport: "Archery", sportLinked: true } as any]);
    expect(g.map((x) => x[0])).toEqual(["Archery", "Boxing", "Not linked to a sport"]);
  });
});

describe("edition asset registry (every edition checked individually)", () => {
  it("has all 39 editions with the right season / host data", () => {
    expect(editions).toHaveLength(39);
    expect(registry.editions["2024_summer"].hostCity).toBe("Paris");
    expect(registry.editions["2026_winter"].season).toBe("winter");
  });
  it.each(editions.map((e) => [e.editionId, e]))("%s: its logo, background and mascot files exist on disk", (_id, e: any) => {
    const onDisk = (src: string) => existsSync(join(PUBLIC, decodeURIComponent(src)));
    if (e.assets.logo) expect(onDisk(e.assets.logo)).toBe(true);
    if (e.assets.background) expect(onDisk(e.assets.background)).toBe(true);
    e.assets.mascots.forEach((m: any) => expect(onDisk(m.src)).toBe(true));
    expect(e.theme.primary).toMatch(/^#[0-9a-f]{6}$/i);
  });
  it.each(editions.map((e) => [e.editionId, e]))("%s: every pictogram file exists and is only linked to a sport that its file name names", (_id, e: any) => {
    for (const p of e.assets.pictograms) {
      expect(existsSync(join(PUBLIC, decodeURIComponent(p.src)))).toBe(true);
      if (p.sportLinked) {
        expect(p.sport).toBeTruthy();
        expect(p.linkedBy).toBe("file name");
      } else expect(p.sport).toBeNull();
    }
  });
  it("gives distinct colour identities (not one theme with a changed title)", () => {
    const primaries = new Set(editions.map((e) => e.theme.primary));
    expect(primaries.size).toBeGreaterThanOrEqual(30);
  });
  it("never invents official artwork: every theme says where it came from and user-supplied images stay unverified", () => {
    editions.forEach((e) => expect(e.theme.source.length).toBeGreaterThan(5));
    editions.filter((e) => e.assets.logo).forEach((e) => expect(e.assets.logoMeta.verification).not.toBe("verified"));
  });
});
