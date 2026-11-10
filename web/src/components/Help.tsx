import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import s from "./Help.module.css";

const TIP_W = 280;
const GUTTER = 16;

/**
 * A keyboard-reachable explanation: click to show, Escape or blur to hide. The tip is positioned
 * against the viewport (so scrolling tables can't clip it) and clamped inside it.
 */
export function Help({ label, text }: { label: string; text: string }) {
  const [pos, setPos] = useState<CSSProperties | null>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const id = useId();
  const open = pos !== null;

  const show = () => {
    const r = btn.current?.getBoundingClientRect();
    if (!r) return;
    const width = Math.min(TIP_W, window.innerWidth - GUTTER * 2);
    const left = Math.min(Math.max(GUTTER, r.left + r.width / 2 - width / 2), window.innerWidth - GUTTER - width);
    setPos({ top: r.bottom + 6, left, maxWidth: width, transformOrigin: `${r.left + r.width / 2 - left}px 0` });
  };

  useEffect(() => {
    if (!open) return;
    const close = () => setPos(null);
    window.addEventListener("scroll", close, { passive: true, capture: true });
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, { capture: true });
      window.removeEventListener("resize", close);
    };
  }, [open]);

  return (
    <span className={s.wrap}>
      <button
        ref={btn}
        type="button"
        className={s.button}
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => (open ? setPos(null) : show())}
        onBlur={() => setPos(null)}
        onKeyDown={(e) => e.key === "Escape" && setPos(null)}
      >
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          <circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
          <path d="M6.3 6.2a1.8 1.8 0 1 1 2.5 1.7c-.5.2-.8.6-.8 1.1v.4" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          <circle cx="8" cy="11.6" r=".8" fill="currentColor" />
        </svg>
      </button>
      {open && (
        <span role="tooltip" id={id} className={s.tip} style={pos}>
          {text}
        </span>
      )}
    </span>
  );
}
