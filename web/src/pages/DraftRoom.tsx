import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { get, post } from "../lib/api";
import { ORDINAL } from "../lib/color";
import { fixed, height, pct, signed } from "../lib/format";
import { useTeam } from "../lib/team";
import type { Board, DraftFit, Memo, ProspectReport } from "../lib/types";
import { DriverBars, ShareBars, ZoneChart } from "../components/Charts";
import { Button, Checks, PageHeader, Section, Slider, TextField } from "../components/Controls";
import { DataTable } from "../components/DataTable";
import { LineupPanel } from "../components/LineupPanel";
import { MemoText } from "../components/MemoText";
import { PersonPicker } from "../components/PersonPicker";
import { StatLine } from "../components/StatLine";
import { Empty, ErrorState, Note, Skeleton } from "../components/States";
import s from "./Page.module.css";

const CLASSES = ["Fr", "So", "Jr", "Sr"] as const;
type Cls = (typeof CLASSES)[number];

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function Bar({ value }: { value: number }) {
  return (
    <span className={s.inlineNums} style={{ gap: 8, justifyContent: "flex-end" }}>
      <span aria-hidden="true" style={{ width: 64, height: 8, background: "var(--surface-sunk)", borderRadius: 1, overflow: "hidden" }}>
        <span style={{ display: "block", width: `${Math.min(1, value) * 100}%`, height: "100%", background: "var(--slate)" }} />
      </span>
      {pct(value)}
    </span>
  );
}

export function DraftRoom() {
  const { team, teamInfo } = useTeam();
  const [minMin, setMinMin] = useState(250);
  const [minDraft, setMinDraft] = useState(0.5);
  const [classes, setClasses] = useState<Cls[]>([...CLASSES]);
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const board = useQuery({
    queryKey: ["board", minMin, minDraft, classes.join(","), dq],
    queryFn: () => get<Board>("/ui/prospects", { min_minutes: minMin, min_draft: minDraft, classes: classes.join(","), q: dq }),
    placeholderData: (prev) => prev,
  });
  const rows = board.data?.prospects ?? [];
  const [sel, setSel] = useState<number | null>(null);
  const selected = sel != null && rows.some((r) => r.torvik_id === sel) ? sel : rows[0]?.torvik_id ?? null;

  return (
    <>
      <PageHeader title={`Draft Room, ${teamInfo?.name ?? team}`} />
      <Section first title="Big board" description="Grade = percentile of expected 4-year VORP among college draftees since 2010, from college stats only (draft slot is not an input). Select a name for his report.">
        <div className={s.filters} role="group" aria-label="Board filters">
        <Slider label="Min. college minutes" value={minMin} min={0} max={1500} step={50} onChange={setMinMin} />
        <Slider label="Min. draftability" value={minDraft} min={0} max={1} step={0.05} onChange={setMinDraft} format={(v) => v.toFixed(2)} help="Probability of being drafted, from a model of every final college season since 2010." />
        <Checks<Cls> label="Class" options={[...CLASSES]} value={classes} onChange={setClasses} />
        <TextField label="Search name" value={q} onChange={setQ} placeholder="e.g. Bidunga" />
      </div>

        {board.error ? (
          <ErrorState error={board.error} onRetry={() => board.refetch()} />
        ) : !board.data ? (
          <Skeleton height={380} label="Grading prospects" />
        ) : rows.length === 0 ? (
          <Empty>
            {dq.trim() ? `No prospect matches "${dq}" with these filters.` : "No prospects pass these filters."} Lower the minimum minutes or draftability, or add class years.
          </Empty>
        ) : (
          <>
            <DataTable
              caption="Big board"
              maxHeight={440}
              rowKey={(r) => String(r.torvik_id)}
              selectedKey={selected != null ? String(selected) : null}
              rows={rows.slice(0, 60)}
              columns={[
                {
                  key: "player",
                  header: "Player",
                  align: "left",
                  sortValue: (r) => r.player,
                  render: (r) => (
                    <button type="button" className={s.linkBtn} onClick={() => setSel(r.torvik_id)} aria-pressed={selected === r.torvik_id}>
                      {r.player}
                    </button>
                  ),
                },
                { key: "school", header: "School", align: "left", sortValue: (r) => r.team, render: (r) => r.team },
                { key: "class", header: "Class", align: "left", render: (r) => r.class_yr },
                { key: "age", header: "Age", sortValue: (r) => r.age_at_draft, render: (r) => fixed(r.age_at_draft) },
                { key: "ht", header: "Height", sortValue: (r) => r.height_in, render: (r) => height(r.height_in) },
                { key: "bpm", header: "BPM", sortValue: (r) => r.bpm, render: (r) => fixed(r.bpm) },
                { key: "grade", header: "Grade", align: "left", render: (r) => <strong>{r.grade}</strong> },
                { key: "score", header: "Score", sortValue: (r) => r.grade_score, render: (r) => fixed(r.grade_score, 0), help: "Percentile among college draftees since 2010" },
                { key: "ev", header: "Exp. VORP (4 yr)", sortValue: (r) => r.expected_vorp_4yr, render: (r) => fixed(r.expected_vorp_4yr, 2) },
                { key: "hit", header: "P(hit)", sortValue: (r) => r.hit_prob, render: (r) => <Bar value={r.hit_prob} /> },
                { key: "bust", header: "P(bust)", sortValue: (r) => r.bust_prob, render: (r) => <Bar value={r.bust_prob} /> },
                { key: "path", header: "Likeliest path", align: "left", render: (r) => r.likeliest_path },
                { key: "arch", header: "NBA archetype", align: "left", render: (r) => r.archetype ?? "n/a" },
              ]}
            />
            <p className={s.hint}>
              Showing {Math.min(rows.length, 60)} of {board.data.count.toLocaleString()} prospects that pass the filters.
            </p>
          </>
        )}
      </Section>

      {selected != null && <ProspectReportView key={selected} id={selected} />}
      {rows.length > 0 && <TeamFit key={team} board={rows} />}
    </>
  );
}

function ProspectReportView({ id }: { id: number }) {
  const { team, teamInfo, meta } = useTeam();
  const report = useQuery({ queryKey: ["prospect", id], queryFn: () => get<ProspectReport>(`/ui/prospects/${id}`) });
  const memo = useMutation({ mutationFn: () => post<Memo>(`/ui/prospects/${id}/memo`, { team }) });
  const writer = meta?.memo_writer === "bedrock" ? "Claude on Amazon Bedrock" : meta?.memo_writer === "anthropic" ? "the Claude API" : "the built-in template (no Claude API key configured)";
  useEffect(() => memo.reset(), [team]); // eslint-disable-line react-hooks/exhaustive-deps
  if (report.error) return <Section title="Prospect report"><ErrorState error={report.error} onRetry={() => report.refetch()} /></Section>;
  if (!report.data) return <Section title="Prospect report"><Skeleton height={520} label="Computing his report" /></Section>;
  const r = report.data;
  const p = r.profile;
  return (
    <Section title={`${p.player}, ${p.team}`} description="Probabilities, the college stats behind the grade, his college shot profile and the most similar past draftees.">
      <StatLine
        stats={[
          { label: "Grade", value: `${p.grade} (${p.grade_score.toFixed(0)})`, help: "Letter grade and percentile" },
          { label: "P(hit)", value: p.hit_prob * 100, decimals: 0, suffix: "%", help: "Probability of averaging 1.5+ VORP over his first four seasons" },
          { label: "P(bust)", value: p.bust_prob * 100, decimals: 0, suffix: "%", help: "Probability of being out of the league by year 4" },
          { label: "Exp. VORP (4 yrs)", value: p.expected_vorp_4yr, decimals: 2 },
          { label: "NBA archetype", value: p.archetype ?? "n/a" },
        ]}
      />
      <div className={s.pair}>
        <div style={{ display: "grid", gap: "var(--s-4)" }}>
          <ShareBars
            title="Career-path probabilities"
            rows={[...r.tiers].reverse().map((t) => ({ label: t.path, value: t.prob }))}
            colors={[...ORDINAL].reverse()}
            note="Paths run from best (warm, top) to worst (cool), named from the first four NBA seasons of past draftees."
          />
          <DriverBars title="What drives his grade" axisLabel="Effect on expected VORP" domain={1.2} rows={r.drivers.map((d) => ({ label: d.label, value: d.impact_vorp ?? 0 }))} />
        </div>
        {meta && <ZoneChart title="College shot profile" scheme="college" zones={r.zones} labels={meta.college_label_pos} />}
      </div>
      <div className={s.subsection}>
        <h3>Historical comps</h3>
        <p className={s.hint}>Nearest college profiles among past draftees, and how their first four NBA seasons went.</p>
        <DataTable
          caption="Historical comps"
          rowKey={(c) => `${c.nba_name}-${c.draft_year}`}
          rows={r.comps}
          columns={[
            { key: "n", header: "Player", align: "left", render: (c) => c.nba_name },
            { key: "t", header: "School", align: "left", render: (c) => c.team },
            { key: "d", header: "Draft", render: (c) => c.draft_year },
            { key: "p", header: "Pick", render: (c) => (c.pick == null ? "n/a" : c.pick.toFixed(0)) },
            { key: "o", header: "Outcome", align: "left", render: (c) => c.outcome },
            { key: "v", header: "VORP (4 yr)", sortValue: (c) => c.vorp_4yr, render: (c) => fixed(c.vorp_4yr) },
            { key: "m", header: "Minutes (4 yr)", sortValue: (c) => c.mp_4yr, render: (c) => fixed(c.mp_4yr, 0) },
            { key: "s", header: "Similarity", sortValue: (c) => c.similarity, render: (c) => fixed(c.similarity, 2) },
          ]}
        />
      </div>
      <div className={s.subsection}>
        <div className={s.controls}>
          <Button onClick={() => memo.mutate()} busy={memo.isPending} title={`Written by ${writer}`}>
            {memo.isPending ? "Evaluating team fit and writing the memo" : `Write scouting memo for the ${teamInfo?.name ?? team}`}
          </Button>
          <span className={s.hint}>Written by {writer}.</span>
        </div>
        {memo.error && <ErrorState error={memo.error} onRetry={() => memo.mutate()} />}
        {memo.data && (
          <article className={s.memo} aria-live="polite">
            <MemoText text={memo.data.text} />
            <p className={s.hint} style={{ marginTop: 16 }}>
              Written by: {memo.data.provider}
              {memo.data.model ? ` / ${memo.data.model}` : ""}. Every figure comes from RosterFit's models.
            </p>
          </article>
        )}
      </div>
    </Section>
  );
}

function TeamFit({ board }: { board: Board["prospects"] }) {
  const { team, teamInfo } = useTeam();
  const options = useMemo(() => board.slice(0, 200).map((p) => ({ id: String(p.torvik_id), label: `${p.player} (${p.team})` })), [board]);
  const [chosen, setChosen] = useState<string[] | null>(null);
  const ids = chosen ?? options.slice(0, 6).map((o) => o.id);
  const [weight, setWeight] = useState(0.65);
  const fit = useMutation({ mutationFn: () => post<DraftFit>("/ui/draft-fit", { team, prospects: ids.map(Number), talent_weight: weight }) });
  const [ranIds, setRanIds] = useState<string>("");
  const stale = fit.data && (ranIds !== ids.join(",") || fit.data.talent_weight !== weight);

  return (
    <Section
      title={`Fit with the ${teamInfo?.name ?? team}`}
      description="Each prospect is dropped into the roster as a rookie and every lineup is re-scored. The board score blends his standalone grade with that fit."
    >
      <PersonPicker label="Prospects to compare" options={options} value={ids} onChange={setChosen} max={12} placeholder="Add a prospect" hint="Up to 12 prospects from the board above." />
      <div className={s.saveRow} style={{ maxWidth: 640 }}>
        <Slider label="Weight on standalone talent vs. team fit" value={weight} min={0} max={1} step={0.05} onChange={setWeight} format={(v) => v.toFixed(2)} help="1.00 ranks by grade only; 0.00 ranks by fit with this roster only." />
        <Button
          variant="primary"
          disabled={!ids.length}
          busy={fit.isPending}
          onClick={() => {
            setRanIds(ids.join(","));
            fit.mutate();
          }}
        >
          {fit.isPending ? `Re-scoring with ${ids.length} prospects` : "Run fit analysis"}
        </Button>
      </div>
      {!ids.length && <Note>Choose at least one prospect to compare.</Note>}
      {fit.error && <ErrorState error={fit.error} onRetry={() => fit.mutate()} />}
      {fit.data && (
        <>
          {stale && <Note tone="warn">The prospects or the talent weight changed since this run. Run the analysis again to update.</Note>}
          <DataTable
            caption="Team fit comparison"
            rowKey={(r) => r.player_id}
            rows={fit.data.rows}
            columns={[
              { key: "p", header: "Player", align: "left", render: (r) => r.player },
              { key: "g", header: "Grade", align: "left", render: (r) => r.grade },
              { key: "sc", header: "Score", sortValue: (r) => r.grade_score, render: (r) => fixed(r.grade_score, 0) },
              { key: "fit", header: "Fit", sortValue: (r) => r.fit_score, render: (r) => <Bar value={r.fit_score / 100} />, help: "0 to 100, 50 = neutral" },
              { key: "board", header: "Board score", sortValue: (r) => r.board_score, render: (r) => <strong>{fixed(r.board_score, 0)}</strong> },
              { key: "gain", header: "Net gain", sortValue: (r) => r.gain_vs_current_best, render: (r) => signed(r.gain_vs_current_best, 2) },
              { key: "syn", header: "Synergy", sortValue: (r) => r.synergy, render: (r) => signed(r.synergy, 2) },
              { key: "dis", header: "Displaces", align: "left", render: (r) => r.displaces },
              { key: "bust", header: "P(bust)", sortValue: (r) => r.bust_prob, render: (r) => pct(r.bust_prob) },
              { key: "hit", header: "P(hit)", sortValue: (r) => r.hit_prob, render: (r) => pct(r.hit_prob) },
            ]}
          />
          <p className={s.hint}>Net gain: change in best-lineup net rating with the prospect as a rookie. Synergy: how much more he helps this team than the median NBA team.</p>
          {fit.data.best_with_top && (
            <div className={s.subsection}>
              <h3>Best lineup with {fit.data.rows[0].player}</h3>
              <LineupPanel detail={fit.data.best_with_top} title={`Spacing with ${fit.data.rows[0].player}`} />
            </div>
          )}
        </>
      )}
    </Section>
  );
}
