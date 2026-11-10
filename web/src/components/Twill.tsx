import { initials } from "../lib/format";
import type { Person } from "../lib/types";
import s from "./Twill.module.css";

interface Props {
  person: Pick<Person, "name" | "jersey">;
  size?: "sm" | "md" | "lg";
  /** The player a roster move is adding: marked by a ring and a text label, not color alone. */
  incoming?: boolean;
}

const HEIGHT = { sm: 26, md: 36, lg: 52 } as const;

/**
 * A player's real jersey number as layered tackle twill: the glyph itself is the patch, with a
 * fill, an inner outline in the team color and an outer outline in the secondary, the way the
 * numbers are cut and sewn on a game uniform. Players without a number show initials.
 */
export function Twill({ person, size = "sm", incoming = false }: Props) {
  const hasNumber = !!person.jersey;
  const label = person.jersey ?? initials(person.name);
  const h = HEIGHT[size];
  const glyph = hasNumber ? h * 0.58 : h * 0.4; // advance width per character
  const w = Math.max(h * 0.82, label.length * glyph + h * 0.42);
  const fontSize = hasNumber ? h * 0.84 : h * 0.5;
  const y = hasNumber ? h * 0.8 : h * 0.66;
  const text = {
    x: w / 2,
    y,
    textAnchor: "middle" as const,
    fontSize,
    className: hasNumber ? s.numeral : s.initials,
    strokeLinejoin: "round" as const,
    paintOrder: "stroke" as const,
  };
  return (
    <svg
      className={`${s.twill} ${incoming ? s.incoming : ""}`}
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      aria-hidden="true"
      data-twill
    >
      {/* outer twill layer (secondary), the one an incoming player's re-stitch draws in */}
      <text {...text} data-stitch fill="var(--twill-outer)" stroke="var(--twill-outer)" strokeWidth={fontSize * 0.2}>
        {label}
      </text>
      {/* inner layer: fill with the team-color outline */}
      <text {...text} fill="var(--twill-fill)" stroke="var(--twill-inner)" strokeWidth={fontSize * 0.1}>
        {label}
      </text>
    </svg>
  );
}
