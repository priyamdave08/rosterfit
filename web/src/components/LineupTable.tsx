import { signed } from "../lib/format";
import type { LineupRow } from "../lib/types";
import { DataTable, type Column } from "./DataTable";
import { Twill } from "./Twill";
import s from "./LineupTable.module.css";

interface Props {
  rows: LineupRow[];
  caption: string;
  selected?: number | null;
  onSelect?: (row: LineupRow) => void;
  shooterHelp?: string;
  compact?: boolean;
  maxHeight?: number;
}

/** Ranked five-man units: each row shows the five players as their jersey numbers. */
export function LineupTable({ rows, caption, selected, onSelect, shooterHelp, compact, maxHeight }: Props) {
  const columns: Column<LineupRow>[] = [
    { key: "rank", header: "#", sortValue: (r) => r.rank, render: (r) => r.rank, width: "44px" },
    {
      key: "lineup",
      header: "Lineup",
      align: "left",
      render: (r) => {
        const names = r.players.map((p) => p.short).join(", ");
        const content = (
          <>
            {!compact && (
              <span className={s.nums}>
                {r.players.map((p) => (
                  <Twill key={p.id} person={p} />
                ))}
              </span>
            )}
            <span className={s.names}>{names}</span>
          </>
        );
        return onSelect ? (
          <button type="button" className={s.pick} onClick={() => onSelect(r)} aria-pressed={selected === r.rank} aria-label={`Inspect lineup ${r.rank}: ${names}`}>
            {content}
          </button>
        ) : (
          <span className={s.static}>{content}</span>
        );
      },
    },
    { key: "net", header: "Net", sortValue: (r) => r.net, render: (r) => <strong>{signed(r.net)}</strong> },
    { key: "off", header: "Off", sortValue: (r) => r.off, render: (r) => signed(r.off) },
    { key: "def", header: "Def", sortValue: (r) => r.def, render: (r) => signed(r.def) },
    { key: "shooters", header: "Shooters", sortValue: (r) => r.shooters, render: (r) => r.shooters.toFixed(0), help: shooterHelp },
    { key: "spacing", header: "Spacing", sortValue: (r) => r.spacing, render: (r) => r.spacing.toFixed(2), help: "Volume-weighted 3P% above 30%" },
    { key: "usage", header: "Usage", sortValue: (r) => r.usage_total, render: (r) => r.usage_total.toFixed(0), help: "Sum of the five usage rates (100 = balanced)" },
  ];
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(r) => String(r.rank)}
      caption={caption}
      selectedKey={selected != null ? String(selected) : null}
      maxHeight={maxHeight}
    />
  );
}
