import { useMemo, useState, type ReactNode } from "react";
import { Help } from "./Help";
import s from "./DataTable.module.css";

export interface Column<T> {
  key: string;
  header: string;
  /** Raw value used for sorting; leave undefined to make the column unsortable. */
  sortValue?: (row: T) => number | string | null | undefined;
  render: (row: T) => ReactNode;
  align?: "left" | "right";
  help?: string;
  width?: string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  /** Initial sort: keeps the engine's own order when omitted. */
  initialSort?: { key: string; dir: "asc" | "desc" };
  maxHeight?: number;
  selectedKey?: string | null;
  empty?: ReactNode;
}

function SortGlyph({ dir }: { dir: "asc" | "desc" | null }) {
  return (
    <svg viewBox="0 0 10 12" width="9" height="11" aria-hidden="true" className={s.glyph}>
      <path d="M5 1 9 5H1Z" fill={dir === "asc" ? "currentColor" : "var(--rule)"} />
      <path d="M5 11 1 7h8Z" fill={dir === "desc" ? "currentColor" : "var(--rule)"} />
    </svg>
  );
}

export function DataTable<T>({ columns, rows, rowKey, caption, initialSort, maxHeight, selectedKey, empty }: Props<T>) {
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(initialSort ?? null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = col.sortValue!(a);
      const vb = col.sortValue!(b);
      if (va == null) return 1;
      if (vb == null) return -1;
      return (va < vb ? -1 : va > vb ? 1 : 0) * dir;
    });
  }, [rows, sort, columns]);

  if (!rows.length && empty) return <>{empty}</>;
  return (
    <div className={`${s.wrap} scroll-area`} style={maxHeight ? { maxHeight } : undefined} data-lenis-prevent>
      <table className={s.table}>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key ? sort.dir : null;
              return (
                <th
                  key={c.key}
                  scope="col"
                  className={c.align === "left" ? s.left : s.right}
                  style={c.width ? { width: c.width } : undefined}
                  aria-sort={active === "asc" ? "ascending" : active === "desc" ? "descending" : undefined}
                >
                  <span className={s.headCell}>
                  {c.sortValue ? (
                    <button
                      type="button"
                      className={s.sortBtn}
                      onClick={() =>
                        setSort((cur) =>
                          cur?.key === c.key ? { key: c.key, dir: cur.dir === "desc" ? "asc" : "desc" } : { key: c.key, dir: "desc" },
                        )
                      }
                    >
                      {c.header}
                      <SortGlyph dir={active} />
                    </button>
                  ) : (
                    c.header
                  )}
                  {c.help && <Help label={c.header} text={c.help} />}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const k = rowKey(r);
            return (
              <tr key={k} className={selectedKey === k ? s.selected : undefined}>
                {columns.map((c) => (
                  <td key={c.key} className={`${c.align === "left" ? s.left : s.right} num`}>
                    {c.render(r)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
