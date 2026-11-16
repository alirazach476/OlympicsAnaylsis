/**
 * The Olympic rings: five interlaced rings in the official colours (blue, yellow, black, green, red), drawn as SVG so they stay sharp at any size.
 * The black ring uses the text colour of the theme, so it remains visible on the dark theme (the official guidelines allow the black ring to turn white on dark backgrounds).
 */
const R = 60;          // ring centre-line radius
const W = 12;          // ring thickness
const GAP = 132;       // distance between neighbouring top-row centres (2.2 R)
const TOP = [{ x: 72, y: 72, c: "#0081C8" }, { x: 72 + GAP, y: 72, c: "currentColor" }, { x: 72 + 2 * GAP, y: 72, c: "#EE334E" }];
const BOTTOM = [{ x: 72 + GAP / 2, y: 132, c: "#FCB131" }, { x: 72 + GAP * 1.5, y: 132, c: "#00A651" }];

type P = { x: number; y: number };
function crossings(a: P, b: P): [P, P] {
  const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy), h = Math.sqrt(R * R - (d / 2) ** 2);
  const mx = a.x + dx / 2, my = a.y + dy / 2, ux = -dy / d, uy = dx / d;
  const p1 = { x: mx + ux * h, y: my + uy * h }, p2 = { x: mx - ux * h, y: my - uy * h };
  return p1.y < p2.y ? [p1, p2] : [p2, p1];   // [upper, lower]
}
/** a short arc of the ring centred at `c`, around point `p` (where this ring passes IN FRONT of the other) */
function arc(c: P, p: P, span = 0.42) {
  const t = Math.atan2(p.y - c.y, p.x - c.x);
  const s = { x: c.x + R * Math.cos(t - span), y: c.y + R * Math.sin(t - span) }, e = { x: c.x + R * Math.cos(t + span), y: c.y + R * Math.sin(t + span) };
  return `M${s.x.toFixed(2)} ${s.y.toFixed(2)} A${R} ${R} 0 0 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
}
// the interlace: in each overlapping pair one ring is in front at one crossing and behind at the other
const FRONT: { ring: P & { c: string }; at: P }[] = [];
BOTTOM.forEach((b, i) => {
  const left = TOP[i], right = TOP[i + 1];
  FRONT.push({ ring: left, at: crossings(left, b)[0] });   // the top-left ring passes over the bottom ring at their upper crossing
  FRONT.push({ ring: right, at: crossings(b, right)[1] }); // the top-right ring passes over the bottom ring at their lower crossing
});

export function OlympicRings({ size = 64, className = "", title = "Olympic rings" }: { size?: number; className?: string; title?: string }) {
  const w = 72 * 2 + GAP * 2, h = 132 + 72;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={size} height={(size * h) / w} className={`text-ink ${className}`} role="img" aria-label={title} data-testid="olympic-rings">
      <title>{title}</title>
      <g fill="none" strokeWidth={W}>
        {TOP.map((r, i) => <circle key={`t${i}`} cx={r.x} cy={r.y} r={R} stroke={r.c} />)}
        {BOTTOM.map((r, i) => <circle key={`b${i}`} cx={r.x} cy={r.y} r={R} stroke={r.c} />)}
        {FRONT.map((f, i) => <path key={`f${i}`} d={arc(f.ring, f.at)} stroke={f.ring.c} strokeLinecap="butt" />)}
      </g>
    </svg>
  );
}
