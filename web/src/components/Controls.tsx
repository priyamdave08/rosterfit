import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";
import s from "./Controls.module.css";

export function Button({ variant = "secondary", busy, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary"; busy?: boolean }) {
  return (
    <button {...rest} className={`${s.btn} ${variant === "primary" ? s.primary : s.secondary} ${rest.className ?? ""}`} aria-busy={busy || undefined} disabled={rest.disabled || busy}>
      {busy && <span className={s.spinner} aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Segmented<T extends string>({ label, options, value, onChange }: { label: string; options: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  const name = useId();
  return (
    <fieldset className={s.segmented}>
      <legend className={s.fieldLabel}>{label}</legend>
      <div className={s.segRow}>
        {options.map((o) => (
          <label key={o.value} className={`${s.seg} ${o.value === value ? s.segOn : ""}`}>
            <input type="radio" name={name} value={o.value} checked={o.value === value} onChange={() => onChange(o.value)} />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function Slider({ label, value, min, max, step, onChange, format, help }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format?: (v: number) => string; help?: string }) {
  const id = useId();
  return (
    <div className={s.field}>
      <div className={s.sliderHead}>
        <label htmlFor={id} className={s.fieldLabel}>
          {label}
        </label>
        <output htmlFor={id} className={`${s.sliderValue} num`}>
          {format ? format(value) : value}
        </output>
      </div>
      <input id={id} type="range" className={s.range} min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} aria-describedby={help ? `${id}-help` : undefined} />
      {help && (
        <p id={`${id}-help`} className={s.help}>
          {help}
        </p>
      )}
    </div>
  );
}

export function TextField({ label, value, onChange, placeholder, maxLength, help }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; maxLength?: number; help?: string }) {
  const id = useId();
  return (
    <div className={s.field}>
      <label htmlFor={id} className={s.fieldLabel}>
        {label}
      </label>
      <input id={id} className={s.text} value={value} placeholder={placeholder} maxLength={maxLength} onChange={(e) => onChange(e.target.value)} aria-describedby={help ? `${id}-help` : undefined} />
      {help && (
        <p id={`${id}-help`} className={s.help}>
          {help}
        </p>
      )}
    </div>
  );
}

export function Checks<T extends string>({ label, options, value, onChange }: { label: string; options: T[]; value: T[]; onChange: (v: T[]) => void }) {
  return (
    <fieldset className={s.segmented}>
      <legend className={s.fieldLabel}>{label}</legend>
      <div className={s.segRow}>
        {options.map((o) => {
          const on = value.includes(o);
          return (
            <label key={o} className={`${s.seg} ${on ? s.segOn : ""}`}>
              <input type="checkbox" checked={on} onChange={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])} />
              {o}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function Section({ title, description, actions, children, first }: { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode; first?: boolean }) {
  return (
    <section className={`${s.section} ${first ? s.first : ""}`}>
      <div className={s.sectionHead}>
        <div>
          <h2>{title}</h2>
          {description && <p className={s.sectionDesc}>{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

/** The page's H1 for assistive tech; the active tab already shows the name, so it isn't repeated visually. */
export function PageHeader({ title }: { title: string }) {
  return <h1 className="visually-hidden">{title}</h1>;
}
