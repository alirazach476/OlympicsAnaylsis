/** Chart export helpers: CSV (from the chart's own data table), SVG and PNG (serialised from the rendered chart). */

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function tableToCsv(columns: string[], rows: Record<string, any>[]): string {
  const esc = (v: any) => {
    const s = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.join(","), ...rows.map((r) => columns.map((c) => esc(r[c])).join(","))].join("\n");
}

export function downloadCsv(name: string, columns: string[], rows: Record<string, any>[]) {
  save(new Blob([tableToCsv(columns, rows)], { type: "text/csv;charset=utf-8" }), `${name}.csv`);
}

function findSvg(root: HTMLElement): SVGSVGElement | null {
  const all = Array.from(root.querySelectorAll("svg")) as SVGSVGElement[];
  // the chart is the largest svg that is not an icon
  return all.filter((s) => s.getBoundingClientRect().width > 120).sort((a, b) => b.getBoundingClientRect().width * b.getBoundingClientRect().height - a.getBoundingClientRect().width * a.getBoundingClientRect().height)[0] ?? null;
}

function serialise(svg: SVGSVGElement, bg: string): { text: string; w: number; h: number } {
  const r = svg.getBoundingClientRect();
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(Math.round(r.width)));
  clone.setAttribute("height", String(Math.round(r.height)));
  if (!clone.getAttribute("viewBox")) clone.setAttribute("viewBox", `0 0 ${Math.round(r.width)} ${Math.round(r.height)}`);
  // inline computed text/stroke styles so the file looks the same outside the page
  const src = svg.querySelectorAll("*"), dst = clone.querySelectorAll("*");
  src.forEach((el, i) => {
    const cs = getComputedStyle(el as Element), d = dst[i] as SVGElement;
    ["fill", "stroke", "stroke-width", "font-size", "font-family", "opacity", "text-anchor"].forEach((p) => {
      const v = cs.getPropertyValue(p);
      if (v && !d.getAttribute(p)) d.style.setProperty(p, v);
    });
  });
  const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  rect.setAttribute("width", "100%"); rect.setAttribute("height", "100%"); rect.setAttribute("fill", bg);
  clone.insertBefore(rect, clone.firstChild);
  return { text: new XMLSerializer().serializeToString(clone), w: Math.round(r.width), h: Math.round(r.height) };
}

const bgColor = () => (document.documentElement.getAttribute("data-theme") === "light" ? "#ffffff" : "#111827");

export function exportSvg(root: HTMLElement, name: string): boolean {
  const svg = findSvg(root);
  if (!svg) return false;
  save(new Blob([serialise(svg, bgColor()).text], { type: "image/svg+xml;charset=utf-8" }), `${name}.svg`);
  return true;
}

export function exportPng(root: HTMLElement, name: string): Promise<boolean> {
  return new Promise((resolve) => {
    const svg = findSvg(root);
    if (!svg) return resolve(false);
    const { text, w, h } = serialise(svg, bgColor());
    const img = new Image();
    const url = URL.createObjectURL(new Blob([text], { type: "image/svg+xml;charset=utf-8" }));
    img.onload = () => {
      const scale = 2;
      const c = document.createElement("canvas");
      c.width = w * scale; c.height = h * scale;
      const ctx = c.getContext("2d");
      if (!ctx) { URL.revokeObjectURL(url); return resolve(false); }
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      c.toBlob((b) => { if (b) save(b, `${name}.png`); resolve(!!b); }, "image/png");
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(false); };
    img.src = url;
  });
}
