import { useId, useMemo, useRef, useState } from "react";
import type { Person } from "../lib/types";
import { Twill } from "./Twill";
import s from "./PersonPicker.module.css";

interface Option {
  id: string;
  label: string;
  person?: Pick<Person, "name" | "jersey">;
}

interface Props {
  label: string;
  options: Option[];
  value: string[];
  onChange: (ids: string[]) => void;
  max?: number;
  placeholder?: string;
  hint?: string;
}

const norm = (t: string) =>
  t
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "");

/** Accessible multi-select combobox: type to filter, arrows to move, Enter to add, Backspace to remove. */
export function PersonPicker({ label, options, value, onChange, max, placeholder = "Type a name to search…", hint }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const byId = useMemo(() => new Map(options.map((o) => [o.id, o])), [options]);
  const full = max != null && value.length >= max;

  const matches = useMemo(() => {
    const n = norm(q);
    const pool = options.filter((o) => !value.includes(o.id));
    if (!n) return pool.slice(0, 40);
    const scored = pool
      .map((o) => {
        const l = norm(o.label);
        const words = l.split(" ");
        const score = l.startsWith(n) ? 3 : words.some((w) => w.startsWith(n)) ? 2 : l.includes(n) ? 1 : 0;
        return { o, score };
      })
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score);
    return scored.slice(0, 40).map((x) => x.o);
  }, [q, options, value]);

  const add = (o: Option) => {
    if (full) return;
    onChange([...value, o.id]);
    setQ("");
    setActive(0);
    setOpen(false); // close so the list never covers the controls below; typing reopens it
    input.current?.focus();
  };

  return (
    <div className={s.root}>
      <label className={s.label} htmlFor={`${id}-input`}>
        {label}
      </label>
      <div className={s.field} onClick={() => input.current?.focus()}>
        <ul className={s.chips} aria-label={`${label}: selected`}>
          {value.map((v) => {
            const o = byId.get(v);
            return (
              <li key={v} className={s.chip}>
                {o?.person && <Twill person={o.person} />}
                <span>{o?.label ?? v}</span>
                <button type="button" className={s.remove} aria-label={`Remove ${o?.label ?? v}`} onClick={() => onChange(value.filter((x) => x !== v))}>
                  <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true">
                    <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                </button>
              </li>
            );
          })}
        </ul>
        <input
          ref={input}
          id={`${id}-input`}
          className={s.input}
          role="combobox"
          aria-expanded={open && !full && matches.length > 0}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={open && matches[active] ? `${id}-opt-${active}` : undefined}
          aria-describedby={hint ? `${id}-hint` : undefined}
          autoComplete="off"
          spellCheck={false}
          name={`${id}-search`}
          placeholder={full ? "Limit reached: remove one to add another" : placeholder}
          disabled={full}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onFocus={() => setOpen(!!q)}
          onClick={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setOpen(true);
              setActive((a) => Math.min(a + 1, matches.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && open && matches[active]) {
              e.preventDefault();
              add(matches[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            } else if (e.key === "Backspace" && !q && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
        />
      </div>
      {hint && (
        <p id={`${id}-hint`} className={s.hint}>
          {hint}
        </p>
      )}
      {open && !full && (
        <ul id={`${id}-list`} role="listbox" className={`${s.list} scroll-area`} data-lenis-prevent aria-label={label}>
          {matches.length === 0 ? (
            <li className={s.none}>No matches for “{q}”.</li>
          ) : (
            matches.map((o, i) => (
              <li
                key={o.id}
                id={`${id}-opt-${i}`}
                role="option"
                aria-selected={i === active}
                className={`${s.option} ${i === active ? s.activeOpt : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  add(o);
                }}
                onMouseEnter={() => setActive(i)}
              >
                {o.person && <Twill person={o.person} />}
                <span>{o.label}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
