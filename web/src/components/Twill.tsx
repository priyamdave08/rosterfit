import { initials } from "../lib/format";
import type { Person } from "../lib/types";
import s from "./Twill.module.css";

interface Props {
  person: Pick<Person, "name" | "jersey">;
  size?: "sm" | "md" | "lg";
  /** The player a roster move is adding: marked by a ring and a text label, not color alone. */
  incoming?: boolean;
}

/** A player's real jersey number as layered tackle twill in the team colorway. */
export function Twill({ person, size = "sm", incoming = false }: Props) {
  const label = person.jersey ?? initials(person.name);
  return (
    <span
      className={`${s.twill} ${s[size]} ${person.jersey ? "" : s.initials} ${incoming ? s.incoming : ""}`}
      aria-hidden="true"
      data-twill
    >
      <span className={s.num}>{label}</span>
    </span>
  );
}
