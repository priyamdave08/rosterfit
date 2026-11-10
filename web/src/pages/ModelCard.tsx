import { useQuery } from "@tanstack/react-query";
import { get } from "../lib/api";
import { ORDINAL } from "../lib/color";
import { useTeam } from "../lib/team";
import type { ModelCard } from "../lib/types";
import { Legend, LineChart } from "../components/Charts";
import { PageHeader, Section } from "../components/Controls";
import { DataTable } from "../components/DataTable";
import { StatLine } from "../components/StatLine";
import { ErrorState, Skeleton } from "../components/States";
import s from "./Page.module.css";

const n = (x: unknown) => (typeof x === "number" ? x : NaN);

export function ModelCardPage() {
  const { meta } = useTeam();
  const card = useQuery({ queryKey: ["model-card"], queryFn: () => get<ModelCard>("/model-card"), staleTime: Infinity });
  if (card.error) return <ErrorState error={card.error} onRetry={() => card.refetch()} />;
  if (!card.data) return <Skeleton height={600} label="Loading model card" />;
  const lm = card.data.lineup_model;
  const pm = card.data.prospect_model;
  // Trajectory groups, worst to best, coloured on the same cold-to-warm scale as career paths.
  const tierNames = (pm.tier_names as string[] | undefined) ?? card.data.trajectory_groups.map((g) => g.name);
  const groups = [...card.data.trajectory_groups].sort((a, b) => tierNames.indexOf(a.name) - tierNames.indexOf(b.name));
  const color = (name: string) => ORDINAL[Math.max(0, tierNames.indexOf(name))] ?? "var(--slate)";
  const legend = [...groups].reverse().map((g) => ({ name: g.name, color: color(g.name) }));
  const translate = Object.entries(pm)
    .filter(([k]) => k.startsWith("translate_r_"))
    .map(([k, v]) => ({ stat: meta?.labels.profile[k.replace("translate_r_", "")] ?? k.replace("translate_r_", ""), r: n(v) }))
    .sort((a, b) => b.r - a.r);
  const comp = [
    { metric: "P(hit) AUC", stats: pm.hit_auc_stats, slot: pm.hit_auc_pick },
    { metric: "P(hit) AUC, 1st round only", stats: pm.hit_auc_stats_round1, slot: pm.hit_auc_pick_round1 },
    { metric: "P(bust) AUC", stats: pm.bust_auc_stats, slot: pm.bust_auc_pick },
    { metric: "Expected-value Spearman ρ", stats: pm.ev_spearman_stats, slot: pm.ev_spearman_pick },
  ];
  return (
    <>
      <PageHeader title="Model Card" />
      <Section first title="Lineup efficiency model" description="How the two models are trained, and how well they predict on seasons and draft classes they never saw.">
        <div className={s.prose}>
          <p>
            Predicts a lineup's offensive and defensive rating (per 100 possessions, vs league average) from the five players' <strong>prior-season</strong> profiles. Trained on every
            team-season since 2011-12 (a team-season is the minutes-weighted average of the lineups it played). Ridge + gradient boosting blend, validated{" "}
            <strong>leave-one-season-out</strong>.
          </p>
        </div>
        <StatLine
          stats={[
            { label: "Net rating R²", value: lm.net_r2, decimals: 2, delta: `${(lm.net_r2 - lm.net_r2_bpm_baseline >= 0 ? "+" : "")}${(lm.net_r2 - lm.net_r2_bpm_baseline).toFixed(2)} vs BPM-only`, help: "Out of sample. Baseline: average player BPM alone." },
            { label: "Offense R²", value: lm.off_rtg_rel_r2_blend, decimals: 2, delta: `${(lm.off_rtg_rel_r2_blend - lm.off_rtg_rel_r2_bpm_baseline >= 0 ? "+" : "")}${(lm.off_rtg_rel_r2_blend - lm.off_rtg_rel_r2_bpm_baseline).toFixed(2)} vs BPM-only` },
            { label: "Defense R²", value: lm.def_rtg_rel_r2_blend, decimals: 2, delta: `${(lm.def_rtg_rel_r2_blend - lm.def_rtg_rel_r2_bpm_baseline >= 0 ? "+" : "")}${(lm.def_rtg_rel_r2_blend - lm.def_rtg_rel_r2_bpm_baseline).toFixed(2)} vs BPM-only` },
          ]}
        />
      </Section>
      <Section title="Prospect outcome model">
        <div className={s.prose}>
          <p>
            <strong>Outcome definition (latent trajectories).</strong> A group-based finite mixture model is fit to every draftee's four-season path of VORP and minutes. BIC picks the
            number of groups; each group is named from its mean path. <em>Bust</em> = groups out of the league by year 4. <em>Hit</em> = groups averaging 1.5 or more VORP over four seasons.
          </p>
        </div>
        <div className={s.pair} style={{ marginTop: 0 }}>
          <LineChart title="Mean minutes by NBA season" yLabel="Minutes" xLabels={["1", "2", "3", "4"]} series={groups.map((g) => ({ name: g.name, color: color(g.name), values: g.mean_mp_path }))} />
          <LineChart title="Mean VORP by NBA season" yLabel="VORP" xLabels={["1", "2", "3", "4"]} series={groups.map((g) => ({ name: g.name, color: color(g.name), values: g.mean_vorp_path }))} />
        </div>
        <Legend items={legend} />
        <p className={s.hint}>Groups are coloured from best (warm) to worst (cool).</p>
        <DataTable
          caption="Prospect model accuracy vs draft slot"
          rowKey={(r) => r.metric}
          rows={comp}
          columns={[
            { key: "m", header: "Metric", align: "left", render: (r) => r.metric },
            { key: "s", header: "College stats only", render: (r) => n(r.stats).toFixed(3) },
            { key: "d", header: "Draft slot only", render: (r) => n(r.slot).toFixed(3) },
          ]}
        />
        <div className={s.prose}>
          <p>
            <strong>How to read this.</strong> Draft slot is a strong signal because it encodes scouting, medicals and interviews, and because teams give high picks more minutes. College
            stats alone <strong>rank first-round outcomes better than the actual draft order did</strong> and predict 4-year value better than slot, but slot is still better at predicting
            who washes out of the league (second-round contracts are non-guaranteed).
          </p>
        </div>
      </Section>
      <Section title="College to NBA translation" description="Out-of-sample correlation between each projected stat and the player's actual early-career NBA number.">
        <DataTable
          caption="Translation accuracy by stat"
          rowKey={(r) => r.stat}
          rows={translate}
          columns={[
            { key: "s", header: "Stat", align: "left", render: (r) => r.stat },
            {
              key: "r",
              header: "Correlation (r)",
              sortValue: (r) => r.r,
              render: (r) => (
                <span className={s.inlineNums} style={{ gap: 10, justifyContent: "flex-end" }}>
                  <span aria-hidden="true" style={{ width: 160, height: 8, background: "var(--surface-sunk)", borderRadius: 1, overflow: "hidden" }}>
                    <span style={{ display: "block", width: `${Math.max(0, r.r) * 100}%`, height: "100%", background: "var(--slate)" }} />
                  </span>
                  {r.r.toFixed(2)}
                </span>
              ),
            },
          ]}
        />
      </Section>
      <details className={s.details}>
        <summary>All metrics (raw)</summary>
        <pre className={`${s.raw} scroll-area`} data-lenis-prevent>
          {JSON.stringify({ lineup: lm, prospect: pm }, null, 2)}
        </pre>
      </details>
    </>
  );
}
