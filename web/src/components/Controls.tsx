import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
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

type InputAttrs = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "id" | "className">;

/** Labelled text input. Extra input attributes (name, type, autoComplete, spellCheck) pass through. */
export function TextField({ label, value, onChange, help, ...input }: { label: string; value: string; onChange: (v: string) => void; help?: string } & InputAttrs) {
  const id = useId();
  return (
    <div className={s.field}>
      <label htmlFor={id} className={s.fieldLabel}>
        {label}
      </label>
      <input autoComplete="off" {...input} id={id} className={s.text} value={value} onChange={(e) => onChange(e.target.value)} aria-describedby={help ? `${id}-help` : undefined} />
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

interface SectionProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  id?: string;
}

function SectionFrame({ title, description, actions, children, id, className }: SectionProps & { className: string }) {
  return (
    <section className={className} id={id}>
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

/** A titled section below the first one: separated from the content above by a hairline. */
export function Section(props: SectionProps) {
  return <SectionFrame {...props} className={s.section} />;
}

/** The page's first section: owns the first viewport, so it has no rule above it. */
export function LeadSection(props: SectionProps) {
  return <SectionFrame {...props} className={`${s.section} ${s.first}`} />;
}

/** The page's H1 for assistive tech; the active tab already shows the name, so it isn't repeated visually. */
export function PageHeader({ title }: { title: string }) {
  return <h1 className="visually-hidden">{title}</h1>;
}
