import type { ReactNode } from "react";

// Regulation NBA half court in feet, hoop at the origin (same geometry as viz/court.py).
export const BASELINE_Y = -5.25;
export const VIEW_TOP = 33;
export const THREE_R = 23.75;
export const CORNER_X = 22;
export const CORNER_Y = Math.sqrt(THREE_R ** 2 - CORNER_X ** 2);
export const VIEW_W = 51;
export const VIEW_H = VIEW_TOP - (BASELINE_Y - 0.5);

export const sx = (x: number) => x + 25.5;
export const sy = (y: number) => VIEW_TOP - y;
/** Court feet to % of the drawing, for HTML overlays positioned over the SVG. */
export const pctX = (x: number) => (sx(x) / VIEW_W) * 100;
export const pctY = (y: number) => (sy(y) / VIEW_H) * 100;

function arc(r: number, a0: number, a1: number, cx = 0, cy = 0, n = 48): string {
  const pts = Array.from({ length: n + 1 }, (_, i) => {
    const t = a0 + ((a1 - a0) * i) / n;
    return `${sx(cx + r * Math.cos(t)).toFixed(3)},${sy(cy + r * Math.sin(t)).toFixed(3)}`;
  });
  return `M ${pts.join(" L ")}`;
}

const th = Math.asin(CORNER_Y / THREE_R);
export const THREE_PATH = `M ${sx(CORNER_X)},${sy(BASELINE_Y)} L ${sx(CORNER_X)},${sy(CORNER_Y)} ${arc(THREE_R, th, Math.PI - th).replace("M", "L")} L ${sx(-CORNER_X)},${sy(BASELINE_Y)}`;

export function CourtLines({ stroke = "var(--ink)" }: { stroke?: string }) {
  const w = 0.16;
  return (
    <g fill="none" stroke={stroke} strokeWidth={w} strokeLinecap="round">
      <rect x={sx(-25)} y={sy(VIEW_TOP)} width={50} height={VIEW_TOP - BASELINE_Y} />
      <rect x={sx(-8)} y={sy(13.75)} width={16} height={13.75 - BASELINE_Y} />
      <rect x={sx(-6)} y={sy(13.75)} width={12} height={13.75 - BASELINE_Y} />
      <circle cx={sx(0)} cy={sy(0)} r={0.75} />
      <line x1={sx(-3)} y1={sy(-1.25)} x2={sx(3)} y2={sy(-1.25)} />
      <path d={arc(6, 0, Math.PI, 0, 13.75)} />
      <path d={arc(4, 0, Math.PI)} />
      <path d={THREE_PATH} />
    </g>
  );
}

/** The court drawing with an HTML layer on top (numerals, labels) that shares its coordinates. */
export function Court({ svg, overlay, label }: { svg?: ReactNode; overlay?: ReactNode; label: string }) {
  return (
    <div style={{ position: "relative", width: "100%", aspectRatio: `${VIEW_W} / ${VIEW_H}` }}>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} width="100%" height="100%" role="img" aria-label={label} style={{ display: "block" }}>
        <rect x={0} y={0} width={VIEW_W} height={VIEW_H} fill="var(--surface)" />
        {svg}
        <CourtLines />
      </svg>
      {overlay && <div style={{ position: "absolute", inset: 0 }}>{overlay}</div>}
    </div>
  );
}
