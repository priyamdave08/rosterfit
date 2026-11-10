import Counter from "../vendor/react-bits/Counter/Counter";
import { Help } from "./Help";
import s from "./StatLine.module.css";

export interface Stat {
  label: string;
  /** Numeric stats roll to their new value (React Bits Counter); text stats render as words. */
  value: number | string | null | undefined;
  decimals?: number;
  signed?: boolean;
  suffix?: string;
  help?: string;
  delta?: string;
  /** Where the evidence for this number lives on the page (one click away). */
  evidence?: { href: string; label: string };
}

function textValue(st: Stat): string {
  if (st.value == null) return "n/a";
  if (typeof st.value === "string") return st.value;
  const v = st.value.toFixed(st.decimals ?? 1);
  return `${st.signed && st.value >= 0 ? "+" : ""}${v}${st.suffix ?? ""}`;
}

/** Box-score stat line: heavy rule over each figure, uppercase label, tabular numbers. */
export function StatLine({ stats }: { stats: Stat[] }) {
  return (
    <dl className={s.line} style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}>
      {stats.map((st) => (
        <div key={st.label} className={s.cell}>
          <dt className={s.label}>
            {st.label}
            {st.help && <Help label={st.label} text={st.help} />}
          </dt>
          <dd className={s.value}>
            {typeof st.value === "number" ? (
              <>
                <span className="visually-hidden">{textValue(st)}</span>
                <span aria-hidden="true" className={s.counter}>
                  <Counter
                    value={st.value}
                    decimals={st.decimals ?? 1}
                    prefix={st.signed && st.value >= 0 ? "+" : undefined}
                    suffix={st.suffix}
                    fontSize="inherit"
                    fontWeight={600}
                    textColor="currentColor"
                    tabular
                    intro={false}
                    duration={0.3}
                  />
                </span>
              </>
            ) : (
              <span className={s.word}>{textValue(st)}</span>
            )}
            {st.delta && <span className={s.delta}>{st.delta}</span>}
          </dd>
          {st.evidence && (
            <a className={s.evidence} href={st.evidence.href}>
              {st.evidence.label}
            </a>
          )}
        </div>
      ))}
    </dl>
  );
}
