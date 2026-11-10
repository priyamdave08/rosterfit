import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { get, post } from "../lib/api";
import { signed } from "../lib/format";
import { useTeam } from "../lib/team";
import type { MovePool, MoveResult } from "../lib/types";
import { Button, PageHeader, Section, Segmented } from "../components/Controls";
import { DataTable } from "../components/DataTable";
import { LineupPanel } from "../components/LineupPanel";
import { LineupTable } from "../components/LineupTable";
import { PersonPicker } from "../components/PersonPicker";
import { StatLine } from "../components/StatLine";
import { ErrorState, Note, Skeleton } from "../components/States";
import { Twill } from "../components/Twill";
import s from "./Page.module.css";

type Mode = "signing" | "trade";

export function Moves() {
  const { team, teamInfo, meta } = useTeam();
  const [mode, setMode] = useState<Mode>("signing");
  const [incoming, setIncoming] = useState<Record<Mode, string[]>>({ signing: [], trade: [] });
  const [outgoing, setOutgoing] = useState<string[]>([]);
  const pool = useQuery({ queryKey: ["move-pool", team, mode], queryFn: () => get<MovePool>(`/ui/teams/${team}/move-pool`, { mode }) });
  const inc = incoming[mode];
  const out = mode === "trade" ? outgoing : [];
  const move = useMutation({ mutationFn: () => post<MoveResult>("/ui/move", { team, incoming: inc, outgoing: out }) });
  const [ranKey, setRanKey] = useState("");
  const key = `${team}|${mode}|${inc.join(",")}|${out.join(",")}`;

  const incOpts = useMemo(() => (pool.data?.players ?? []).map((p) => ({ id: p.id, label: p.label, person: p })), [pool.data]);
  const outOpts = useMemo(() => (pool.data?.roster ?? []).map((p) => ({ id: p.id, label: p.name, person: p })), [pool.data]);
  const r = move.data;

  return (
    <>
      <PageHeader
        title="Signings and Trades"
        purpose="Add or remove players and re-score every lineup with the same model the Draft Room uses. Fit is measured against this roster, not in a vacuum."
      />
      <div className={s.controls}>
        <Segmented<Mode>
          label="Move type"
          value={mode}
          onChange={(m) => {
            setMode(m);
            move.reset();
          }}
          options={[
            { value: "signing", label: "Free-agent signing" },
            { value: "trade", label: "Trade" },
          ]}
        />
      </div>
      {pool.error ? (
        <ErrorState error={pool.error} onRetry={() => pool.refetch()} />
      ) : !pool.data ? (
        <Skeleton height={120} label="Loading available players" />
      ) : (
        <div style={{ display: "grid", gap: "var(--s-4)", marginTop: "var(--s-4)" }}>
          {mode === "signing" && <p className={s.hint}>{pool.data.count} unsigned players with 300+ recent NBA minutes are available.</p>}
          <div className={mode === "trade" ? s.pair : undefined} style={{ marginTop: 0 }}>
            <PersonPicker
              label="Incoming"
              options={incOpts}
              value={inc}
              onChange={(v) => setIncoming((x) => ({ ...x, [mode]: v }))}
              max={3}
              hint={mode === "signing" ? "Up to three free agents." : "Up to three players from other teams."}
            />
            {mode === "trade" && (
              <PersonPicker label="Outgoing" options={outOpts} value={outgoing} onChange={setOutgoing} max={4} placeholder={`Players leaving the ${teamInfo?.name ?? team}`} hint="Up to four of your players." />
            )}
          </div>
          <div className={s.controls}>
            <Button
              variant="primary"
              disabled={!inc.length}
              busy={move.isPending}
              onClick={() => {
                setRanKey(key);
                move.mutate();
              }}
            >
              {move.isPending ? `Re-scoring every ${teamInfo?.name ?? team} lineup` : "Evaluate move"}
            </Button>
          </div>
          {!inc.length && <Note>Choose at least one incoming player to evaluate the move.</Note>}
          {move.error && <ErrorState error={move.error} onRetry={() => move.mutate()} />}
        </div>
      )}

      {r && (
        <Section title="Result">
          {ranKey !== key && <Note tone="warn">The move changed since this evaluation. Click Evaluate move to update.</Note>}
          <StatLine
            stats={[
              { label: "Best lineup net", value: r.after_best, signed: true, delta: `${signed(r.ceiling_delta, 2)} vs now`, help: "Projected net rating of the best five-man unit after the move" },
              { label: "Top-10 lineup depth", value: r.after_depth, signed: true, delta: `${signed(r.depth_delta, 2)} vs now`, help: "Average net rating of the ten best units after the move" },
              { label: "Fit score", value: r.players.map((p) => p.fit_score.toFixed(0)).join(" / "), help: "0 to 100, 50 = neutral. One score per incoming player." },
            ]}
          />
          <DataTable
            caption="Incoming players"
            rowKey={(p) => p.id}
            rows={r.players}
            columns={[
              { key: "p", header: "Player", align: "left", render: (p) => <span className={s.inlineNums}><Twill person={p} incoming />{p.name}</span> },
              { key: "b", header: "Best lineup with him", render: (p) => signed(p.best_with) },
              { key: "r", header: "Replaces", align: "left", render: (p) => p.displaces ?? "n/a" },
              { key: "s", header: "Synergy", render: (p) => signed(p.synergy, 2), help: "How much more he helps this team than the median NBA team" },
            ]}
          />
          <div className={s.pair}>
            <div className={s.subsection} style={{ marginTop: 0 }}>
              <h3>Before</h3>
              <LineupTable rows={r.before} caption="Best lineups before the move" shooterHelp={meta?.shooter_help} compact />
            </div>
            <div className={s.subsection} style={{ marginTop: 0 }}>
              <h3>After</h3>
              <LineupTable rows={r.after} caption="Best lineups after the move" shooterHelp={meta?.shooter_help} compact />
            </div>
          </div>
          <LineupPanel detail={r.best_after} title="New best lineup" />
        </Section>
      )}
    </>
  );
}
