import { diverging } from "../lib/color";
import { signed } from "../lib/format";
import type { Zone } from "../lib/types";
import { BASELINE_Y, CORNER_X, CORNER_Y, Court, THREE_PATH, THREE_R, VIEW_TOP, pctX, pctY, sx, sy } from "./Court";

const VIEW_TOP_FT = VIEW_TOP;
import s from "./Charts.module.css";

/* ------------------------------------------------------------------ signed driver bars */
export function DriverBars({
  rows,
  title,
  axisLabel,
  domain = 8,
}: {
  rows: { label: string; value: number }[];
  title: string;
  axisLabel: string;
  /** Fixed half-range so two panels compare at one scale; longer bars are clipped and marked. */
  domain?: number;
}) {
  const ordered = [...rows];
  return (
    <figure className={s.figure}>
      <figcaption className={s.title}>{title}</figcaption>
      <ul className={s.drivers} aria-label={title}>
        {ordered.map((r) => {
          const w = Math.min(Math.abs(r.value) / domain, 1) * 50;
          const clipped = Math.abs(r.value) > domain;
          return (
            <li key={r.label} className={s.driverRow}>
              <span className={s.driverLabel}>{r.label}</span>
              <span className={s.track} aria-hidden="true">
                <span className={s.axis} />
                <span
                  className={`${s.bar} ${r.value >= 0 ? s.helps : s.hurts}`}
                  style={r.value >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
                  data-clipped={clipped || undefined}
                />
              </span>
              <span className={`${s.driverValue} num`}>{signed(r.value, 2)}</span>
            </li>
          );
        })}
      </ul>
      <p className={s.axisNote}>
        {axisLabel}. Warm bars raise it, cool bars lower it.
      </p>
    </figure>
  );
}

/* ------------------------------------------------------------------ share bars (0 to 100%) */
export function ShareBars({
  rows,
  title,
  colors,
  note,
}: {
  rows: { label: string; value: number }[];
  title: string;
  colors?: string[];
  note?: string;
}) {
  return (
    <figure className={s.figure}>
      <figcaption className={s.title}>{title}</figcaption>
      <ul className={s.shares} aria-label={title}>
        {rows.map((r, i) => (
          <li key={r.label} className={s.shareRow}>
            <span className={s.shareLabel}>{r.label}</span>
            <span className={s.shareTrack} aria-hidden="true">
              <span className={s.shareBar} style={{ width: `${Math.max(0, Math.min(1, r.value)) * 100}%`, background: colors?.[i] ?? "var(--slate)" }} />
            </span>
            <span className={`${s.shareValue} num`}>{(r.value * 100).toFixed(0)}%</span>
          </li>
        ))}
      </ul>
      {note && <p className={s.axisNote}>{note}</p>}
    </figure>
  );
}

/* ------------------------------------------------------------------ zone shot chart */
function ringPath(r0: number, r1: number): string {
  // A distance band clipped to inside the three-point line, drawn with even-odd fill.
  const circle = (r: number) =>
    r <= 0 ? "" : `M ${sx(-r)},${sy(0)} A ${r} ${r} 0 1 0 ${sx(r)},${sy(0)} A ${r} ${r} 0 1 0 ${sx(-r)},${sy(0)} Z`;
  return `${circle(r1)} ${circle(r0)}`;
}

export function ZoneChart({
  zones,
  labels,
  scheme,
  title,
}: {
  zones: Record<string, Zone>;
  labels: Record<string, [number, number]>;
  scheme: "nba" | "college";
  title: string;
}) {
  const fill = (name: string) => {
    const z = zones[name];
    if (!z || z.freq <= 0.005) return "var(--surface-sunk)";
    return diverging(((z.fg - z.lg_fg) * 100) / 10);
  };
  const inside = "inside3";
  const bands = scheme === "nba"
    ? [["0-3 ft", 0, 3], ["3-10 ft", 3, 10], ["10-16 ft", 10, 16], ["16 ft-3P", 16, 40]] as const
    : [["Rim", 0, 4], ["2-pt jumper", 4, 40]] as const;
  return (
    <figure className={s.figure}>
      <figcaption className={s.title}>{title}</figcaption>
      <Court
        label={`${title}: ${Object.entries(zones).map(([k, z]) => `${k} ${(z.freq * 100).toFixed(0)}% of shots at ${(z.fg * 100).toFixed(0)}%`).join("; ")}`}
        svg={
          <>
            <defs>
              {/* inside the three-point line (zones measured by distance from the hoop) */}
              <clipPath id={`${inside}-${scheme}`}>
                <path d={`${THREE_PATH} Z`} />
              </clipPath>
              {/* above the break: between the arc and 30 ft, above where the corner line ends */}
              <clipPath id={`break-${scheme}`}>
                <rect x={sx(-25)} y={sy(VIEW_TOP_FT)} width={50} height={VIEW_TOP_FT - CORNER_Y} />
              </clipPath>
            </defs>
            <g clipPath={`url(#${inside}-${scheme})`}>
              {bands.map(([name, r0, r1]) => (
                <path key={name} d={ringPath(r0, r1)} fillRule="evenodd" fill={fill(name)} />
              ))}
            </g>
            <g clipPath={`url(#break-${scheme})`}>
              <path d={ringPath(THREE_R, 30)} fillRule="evenodd" fill={fill(scheme === "nba" ? "Above-break 3" : "Three")} />
            </g>
            <rect x={sx(-25)} y={sy(CORNER_Y)} width={25 - CORNER_X} height={CORNER_Y - BASELINE_Y} fill={fill(scheme === "nba" ? "Left corner 3" : "Three")} />
            <rect x={sx(CORNER_X)} y={sy(CORNER_Y)} width={25 - CORNER_X} height={CORNER_Y - BASELINE_Y} fill={fill(scheme === "nba" ? "Right corner 3" : "Three")} />
          </>
        }
        overlay={Object.entries(labels).map(([name, [x, y]]) => {
          const z = zones[name];
          if (!z || z.freq <= 0.005) return null;
          return (
            <span key={name} className={s.zoneLabel} style={{ left: `${pctX(x)}%`, top: `${pctY(y)}%` }}>
              <b className="num">{(z.freq * 100).toFixed(0)}%</b>
              <span className="num">{(z.fg * 100).toFixed(0)}%</span>
            </span>
          );
        })}
      />
      <div className={s.scale} aria-hidden="true">
        <span>-10 pts</span>
        <span className={s.ramp} />
        <span>+10 pts</span>
      </div>
      <p className={s.axisNote}>
        Top number: share of shots. Bottom number: FG%. Color: FG% relative to {scheme === "nba" ? "league" : "the Division I"} average
        {scheme === "college" ? ", shrunk for small samples" : ""}.
      </p>
    </figure>
  );
}
/* ------------------------------------------------------------------ percentile radar */
export function Radar({ items, title }: { items: { label: string; pct: number }[]; title: string }) {
  const n = items.length;
  const cx = 230;
  const cy = 160;
  const rad = 112;
  const pt = (i: number, v: number) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
    return [cx + Math.cos(a) * rad * (v / 100), cy + Math.sin(a) * rad * (v / 100)] as const;
  };
  const poly = items.map((it, i) => pt(i, it.pct).join(",")).join(" ");
  return (
    <figure className={s.figure}>
      <figcaption className={s.title}>{title}</figcaption>
      <svg viewBox="0 0 460 320" width="100%" role="img" aria-label={`${title}: ${items.map((i) => `${i.label} ${i.pct.toFixed(0)}th`).join(", ")}`}>
        {[50, 100].map((r) => (
          <polygon key={r} points={items.map((_, i) => pt(i, r).join(",")).join(" ")} fill="none" stroke="var(--rule)" strokeWidth={r === 100 ? 1.2 : 0.8} />
        ))}
        {items.map((_, i) => {
          const [x, y] = pt(i, 100);
          return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--rule-soft)" strokeWidth={0.8} />;
        })}
        <polygon points={poly} fill="color-mix(in srgb, var(--slate) 20%, transparent)" stroke="var(--slate)" strokeWidth={1.6} />
        {items.map((it, i) => {
          const [x, y] = pt(i, 122);
          const anchor = Math.abs(x - cx) < 8 ? "middle" : x > cx ? "start" : "end";
          return (
            <text key={it.label} x={x} y={y} textAnchor={anchor} dominantBaseline="middle" className={s.radarLabel}>
              {it.label}
            </text>
          );
        })}
      </svg>
      <p className={s.axisNote}>Inner ring = league median, outer ring = best in the league (500+ minutes). Ball security is inverted turnover rate.</p>
    </figure>
  );
}

/* ------------------------------------------------------------------ small multi-line chart */
export function LineChart({
  series,
  title,
  yLabel,
  xLabels,
}: {
  series: { name: string; color: string; values: number[] }[];
  title: string;
  yLabel: string;
  xLabels: string[];
}) {
  const all = series.flatMap((s2) => s2.values);
  const lo = Math.min(0, ...all);
  const hi = Math.max(...all);
  const W = 460;
  const H = 240;
  const L = 48;
  const B = 28;
  const x = (i: number) => L + ((W - L - 12) * i) / (xLabels.length - 1);
  const y = (v: number) => 12 + (H - B - 12) * (1 - (v - lo) / (hi - lo || 1));
  const ticks = [lo, (lo + hi) / 2, hi];
  return (
    <figure className={s.figure}>
      <figcaption className={s.title}>{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`${title}. ${series.map((s2) => `${s2.name}: ${s2.values.map((v) => v.toFixed(1)).join(", ")}`).join("; ")}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - 12} y1={y(t)} y2={y(t)} stroke="var(--rule-soft)" />
            <text x={L - 6} y={y(t)} textAnchor="end" dominantBaseline="middle" className={s.tick}>
              {Math.abs(hi - lo) > 50 ? t.toFixed(0) : t.toFixed(1)}
            </text>
          </g>
        ))}
        {xLabels.map((lab, i) => (
          <text key={lab} x={x(i)} y={H - 8} textAnchor="middle" className={s.tick}>
            {lab}
          </text>
        ))}
        {series.map((s2) => (
          <g key={s2.name}>
            <polyline points={s2.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} fill="none" stroke={s2.color} strokeWidth={2} />
            {s2.values.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r={3} fill={s2.color} />)}
          </g>
        ))}
        <text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle" className={s.tick}>
          {yLabel}
        </text>
      </svg>
    </figure>
  );
}

export function Legend({ items }: { items: { name: string; color: string }[] }) {
  return (
    <ul className={s.legend}>
      {items.map((i) => (
        <li key={i.name}>
          <span style={{ background: i.color }} aria-hidden="true" /> {i.name}
        </li>
      ))}
    </ul>
  );
}
