import { useId, useState } from "react";
import s from "./Help.module.css";

/** A keyboard-reachable explanation: click or focus to show, Escape to hide. */
export function Help({ label, text }: { label: string; text: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className={s.wrap} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className={s.button}
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
      >
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
          <path d="M6.3 6.2a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          <circle cx="8" cy="11.6" r=".8" fill="currentColor" />
        </svg>
      </button>
      {open && (
        <span role="tooltip" id={id} className={s.tip}>
          {text}
        </span>
      )}
    </span>
  );
}
