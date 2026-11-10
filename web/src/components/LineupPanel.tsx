import { useTeam } from "../lib/team";
import type { LineupDetail } from "../lib/types";
import { DriverBars, ShareBars } from "./Charts";
import { SpacingMap } from "./SpacingMap";
import { StatLine } from "./StatLine";
import s from "./LineupPanel.module.css";

/** Stat line, spacing map, rating drivers and shot diet for one five-man unit (Streamlit's lineup_panel). */
export function LineupPanel({ detail, title }: { detail: LineupDetail; title: string }) {
  const { meta } = useTeam();
  const m = detail.metrics;
  return (
    <div className={s.panel}>
      <StatLine
        stats={[
          { label: "Net rating", value: m.net, signed: true, help: "Projected points per 100 possessions vs opponents" },
          { label: "Offense vs avg", value: m.off, signed: true, help: "Positive = better than league-average offense" },
          { label: "Defense vs avg", value: m.def, signed: true, help: "Positive = better than league-average defense" },
          { label: "Volume shooters", value: m.shooters, decimals: 0, help: meta?.shooter_help },
        ]}
      />
      <div className={s.grid}>
        <SpacingMap detail={detail} title={title} />
        <div className={s.side}>
          <DriverBars
            title="What drives the rating"
            axisLabel="Effect on net rating"
            rows={detail.drivers.map((d) => ({ label: d.label, value: d.net_impact ?? 0 }))}
          />
          <ShareBars title="Shot diet (usage-weighted)" rows={detail.shot_diet.map((d) => ({ label: d.zone, value: d.share }))} />
        </div>
      </div>
    </div>
  );
}
