import { useMemo, useRef, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { get, post } from "../lib/api";
import { fixed, pct, signed } from "../lib/format";
import { scrollToElement } from "../lib/motion";
import { useTeam } from "../lib/team";
import type { CustomLineup, LineupDetail, LineupList, Person, RosterPlayer } from "../lib/types";
import { Button, PageHeader, Section, Segmented, TextField } from "../components/Controls";
import { DriverBars, ShareBars } from "../components/Charts";
import { DataTable } from "../components/DataTable";
import { LineupPanel } from "../components/LineupPanel";
import { LineupTable } from "../components/LineupTable";
import { PersonPicker } from "../components/PersonPicker";
import { SpacingMap } from "../components/SpacingMap";
import { StatLine } from "../components/StatLine";
import { Empty, ErrorState, Note, Skeleton } from "../components/States";
import { Twill } from "../components/Twill";
import s from "./Page.module.css";

type Pool = "roster" | "league" | "prospects";
interface Saved {
  name: string;
  team: string;
  ids: string[];
}
const SAVED_KEY = "rosterfit.savedLineups";

function loadSaved(): Saved[] {
  try {
    return JSON.parse(window.localStorage.getItem(SAVED_KEY) ?? "[]") as Saved[];
  } catch {
    return [];
  }
}
function storeSaved(v: Saved[]) {
  try {
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(v));
  } catch {
    /* storage blocked: the list still works for this visit */
  }
}

export function LineupLab() {
  const { team, teamInfo, meta } = useTeam();
  const lineups = useQuery({ queryKey: ["lineups", team], queryFn: () => get<LineupList>(`/ui/teams/${team}/lineups`, { top: 15 }) });
  const [inspect, setInspect] = useState(1); // page remounts per team (App keys it), so this starts at #1
  const courtRef = useRef<HTMLDivElement>(null);
  const select = (rank: number) => {
    setInspect(rank);
    if (courtRef.current && window.matchMedia("(max-width: 1080px)").matches) scrollToElement(courtRef.current);
  };
  const row = lineups.data?.lineups.find((l) => l.rank === inspect) ?? lineups.data?.lineups[0];
  const detail = useQuery({
    queryKey: ["lineup-detail", row?.ids.join(",")],
    queryFn: () => get<LineupDetail>("/ui/lineup-detail", { ids: row!.ids.join(",") }),
    enabled: !!row,
    placeholderData: (prev) => prev,
  });

  return (
    <>
      <PageHeader title={`Lineup Lab, ${teamInfo?.name ?? team}`} />
      <Section
        first
        title="Best five-man units"
        description={`${lineups.data ? lineups.data.count.toLocaleString() : "Every"} realistic units from the ${teamInfo?.name ?? team} top 11, ranked by projected net per 100 possessions. Off and Def are vs league average.`}
      >
        {lineups.isLoading ? (
          <Skeleton height={520} label="Scoring every five-man combination" />
        ) : lineups.error ? (
          <ErrorState error={lineups.error} onRetry={() => lineups.refetch()} />
        ) : (
          <div className={s.split}>
            <LineupTable rows={lineups.data!.lineups} caption="Best five-man units" selected={row?.rank} onSelect={(r) => select(r.rank)} shooterHelp={meta?.shooter_help} />
            <div className={s.stickyCol} ref={courtRef}>
              <p className="visually-hidden" aria-live="polite">
                {row ? `Showing unit ${row.rank}: ${row.players.map((p) => p.name).join(", ")}` : ""}
              </p>
              {detail.data ? (
                <>
                  <UnitStats detail={detail.data} />
                  <SpacingMap detail={detail.data} title={`Projected floor spacing, unit #${row?.rank}`} />
                </>
              ) : detail.error ? (
                <ErrorState error={detail.error} onRetry={() => detail.refetch()} />
              ) : (
                <Skeleton height={520} label="Placing the five on the floor" />
              )}
            </div>
          </div>
        )}
      </Section>
      {detail.data && (
        <div className={s.pair} id="drivers">
          <DriverBars title={`What drives unit #${row?.rank}'s rating`} axisLabel="Effect on net rating" rows={detail.data.drivers.map((d) => ({ label: d.label, value: d.net_impact ?? 0 }))} />
          <ShareBars title="Shot diet (usage-weighted)" rows={detail.data.shot_diet.map((d) => ({ label: d.zone, value: d.share }))} />
        </div>
      )}
      <Builder key={team} bestIds={lineups.data?.lineups[0]?.ids} />
      <RosterProfiles />
    </>
  );
}

function UnitStats({ detail }: { detail: LineupDetail }) {
  const { meta } = useTeam();
  const m = detail.metrics;
  return (
    <StatLine
      stats={[
        { label: "Net rating", value: m.net, signed: true, help: "Projected points per 100 possessions vs opponents", evidence: { href: "#drivers", label: "What drives it" } },
        { label: "Offense vs avg", value: m.off, signed: true, help: "Positive = better than league-average offense" },
        { label: "Defense vs avg", value: m.def, signed: true, help: "Positive = better than league-average defense" },
        { label: "Volume shooters", value: m.shooters, decimals: 0, help: meta?.shooter_help },
      ]}
    />
  );
}

function Builder({ bestIds }: { bestIds?: string[] }) {
  const { team, teamInfo } = useTeam();
  const [pool, setPool] = useState<Pool>("roster");
  const [picked, setPicked] = useState<Record<Pool, string[] | null>>({ roster: null, league: null, prospects: null });
  const options = useQuery({ queryKey: ["pool", team, pool], queryFn: () => get<Person[]>(`/ui/teams/${team}/pool`, { kind: pool }), staleTime: 5 * 60_000 });
  const ids = picked[pool] ?? bestIds ?? [];
  const setIds = (v: string[]) => setPicked((p) => ({ ...p, [pool]: v }));
  const ready = ids.length === 5;
  const result = useQuery({
    queryKey: ["custom", team, ids.join(",")],
    queryFn: () => post<CustomLineup>("/ui/lineup", { team, ids }),
    enabled: ready,
    placeholderData: (prev) => prev,
  });
  const [saved, setSaved] = useState<Saved[]>(loadSaved);
  const [name, setName] = useState("");
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const opts = useMemo(() => (options.data ?? []).map((p) => ({ id: p.id, label: p.label, person: p })), [options.data]);

  const save = () => {
    const label = name.trim() || `Lineup ${saved.length + 1}`;
    if (saved.some((x) => x.team === team && x.ids.join() === ids.join())) {
      setSavedMsg("This exact lineup is already saved.");
      return;
    }
    const next = [...saved, { name: label, team, ids: [...ids] }];
    setSaved(next);
    storeSaved(next);
    setName("");
    setSavedMsg(`Saved "${label}".`);
  };

  const r = result.data;
  const need = 5 - ids.length;
  return (
    <Section
      title="Lineup builder"
      description="Put any five players on the floor and compare them with this roster's best unit. Mix in players from other teams, free agents or draft prospects to test hypotheticals."
    >
      <div className={s.controls}>
        <Segmented<Pool>
          label="Player pool"
          value={pool}
          onChange={setPool}
          options={[
            { value: "roster", label: "Roster" },
            { value: "league", label: "Whole league" },
            { value: "prospects", label: "League + draft prospects" },
          ]}
        />
      </div>
      <PersonPicker label="Pick exactly five" options={opts} value={ids} onChange={setIds} max={5} hint="Prospects use their projected early-career NBA profile." />
      {!ready ? (
        <Note>Pick {need} more player{need === 1 ? "" : "s"} to score the lineup.</Note>
      ) : result.error ? (
        <ErrorState error={result.error} onRetry={() => result.refetch()} />
      ) : !r ? (
        <Skeleton height={420} label="Scoring your lineup" />
      ) : (
        <>
          <p className={s.lead} aria-live="polite">
            Projected net <strong>{signed(r.metrics.net)}</strong>:{" "}
            {r.rank > r.of ? (
              <>
                would rank <strong>below all {r.of.toLocaleString()}</strong>
              </>
            ) : (
              <>
                would rank <strong>#{r.rank}</strong> of {r.of.toLocaleString()}
              </>
            )}{" "}
            {teamInfo?.name} lineups
            {r.outside.length ? `, using ${r.outside.length} player${r.outside.length === 1 ? "" : "s"} from outside the roster.` : "."}
          </p>
          {!r.realistic && (
            <Note tone="warn">Unusual construction (for example no ball handler or too many bigs). The model has seen few lineups like this, so treat the rating with caution.</Note>
          )}
          <CompareTable mine={r.metrics} best={r.best} />
          <LineupPanel detail={r} title="Your lineup" />
          <div className={s.saveRow}>
            <TextField label="Lineup name" value={name} onChange={setName} placeholder={`Lineup ${saved.length + 1}`} maxLength={40} />
            <Button onClick={save}>Save lineup</Button>
          </div>
          {savedMsg && <p className={s.hint} aria-live="polite">{savedMsg}</p>}
        </>
      )}
      <SavedLineups saved={saved} onRemove={(i) => {
        const next = saved.filter((_, j) => j !== i);
        setSaved(next);
        storeSaved(next);
        setSavedMsg(null);
      }} />
    </Section>
  );
}

function CompareTable({ mine, best }: { mine: CustomLineup["metrics"]; best: CustomLineup["metrics"] }) {
  const rows: { k: keyof typeof mine; label: string; dp: number; signed?: boolean }[] = [
    { k: "net", label: "Net", dp: 2, signed: true },
    { k: "off", label: "Offense vs avg", dp: 2, signed: true },
    { k: "def", label: "Defense vs avg", dp: 2, signed: true },
    { k: "shooters", label: "Shooters", dp: 2 },
    { k: "creators", label: "Creators", dp: 2 },
    { k: "rim_protectors", label: "Rim protectors", dp: 2 },
    { k: "spacing", label: "Spacing", dp: 2 },
    { k: "usage_total", label: "Usage total", dp: 2 },
  ];
  return (
    <DataTable
      caption="Your lineup compared with the current best"
      rowKey={(r) => r.k}
      rows={rows}
      columns={[
        { key: "label", header: "", align: "left", render: (r) => r.label },
        { key: "mine", header: "Your lineup", render: (r) => (r.signed ? signed(mine[r.k], r.dp) : fixed(mine[r.k], r.dp)) },
        { key: "best", header: "Current best", render: (r) => (r.signed ? signed(best[r.k], r.dp) : fixed(best[r.k], r.dp)) },
        { key: "diff", header: "Difference", render: (r) => signed(mine[r.k] - best[r.k], 2) },
      ]}
    />
  );
}

function SavedLineups({ saved, onRemove }: { saved: Saved[]; onRemove: (i: number) => void }) {
  const results = useQueries({
    queries: saved.map((sv) => ({ queryKey: ["custom", sv.team, sv.ids.join(",")], queryFn: () => post<CustomLineup>("/ui/lineup", { team: sv.team, ids: sv.ids }) })),
  });
  if (!saved.length) return null;
  const rows = saved
    .map((sv, i) => ({ sv, i, r: results[i]?.data }))
    .sort((a, b) => (b.r?.metrics.net ?? -99) - (a.r?.metrics.net ?? -99));
  return (
    <div className={s.subsection}>
      <h3>Saved lineups</h3>
      <p className={s.hint}>Kept in this browser. Ratings are recomputed each time.</p>
      <DataTable
        caption="Saved lineups"
        rowKey={(x) => String(x.i)}
        rows={rows}
        columns={[
          { key: "name", header: "Name", align: "left", render: (x) => x.sv.name },
          { key: "team", header: "Team", align: "left", render: (x) => x.sv.team },
          {
            key: "players",
            header: "Players",
            align: "left",
            render: (x) =>
              x.r ? (
                <span className={s.inlineNums}>
                  {x.r.players.map((p) => (
                    <Twill key={p.id} person={p} />
                  ))}
                  <span>{x.r.players.map((p) => p.short).join(", ")}</span>
                </span>
              ) : (
                "Loading"
              ),
          },
          { key: "net", header: "Net", render: (x) => (x.r ? signed(x.r.metrics.net) : "") },
          { key: "off", header: "Off", render: (x) => (x.r ? signed(x.r.metrics.off) : "") },
          { key: "def", header: "Def", render: (x) => (x.r ? signed(x.r.metrics.def) : "") },
          {
            key: "remove",
            header: "",
            render: (x) => (
              <Button onClick={() => onRemove(x.i)} aria-label={`Remove ${x.sv.name}`}>
                Remove lineup
              </Button>
            ),
          },
        ]}
      />
    </div>
  );
}

function RosterProfiles() {
  const { team, teamInfo } = useTeam();
  const roster = useQuery({ queryKey: ["roster", team], queryFn: () => get<RosterPlayer[]>(`/ui/teams/${team}/roster`) });
  return (
    <details className={s.details}>
      <summary>
        {teamInfo?.name ?? team} player profiles{roster.data ? ` (${roster.data.length} players)` : ""}
      </summary>
      {roster.error ? (
        <ErrorState error={roster.error} onRetry={() => roster.refetch()} />
      ) : !roster.data ? (
        <Skeleton height={240} label="Loading roster" />
      ) : roster.data.length === 0 ? (
        <Empty>No roster found for this team.</Empty>
      ) : (
        <>
          <DataTable
            caption="Roster profiles"
            rowKey={(p) => p.id}
            rows={roster.data}
            columns={[
              { key: "player", header: "Player", align: "left", sortValue: (p) => p.name, render: (p) => <span className={s.inlineNums}><Twill person={p} />{p.name}</span> },
              { key: "source", header: "Profile source", align: "left", render: (p) => p.source },
              { key: "arch", header: "Archetype", align: "left", render: (p) => p.archetype ?? "n/a" },
              { key: "mp", header: "Minutes", sortValue: (p) => p.mp, render: (p) => fixed(p.mp, 0) },
              { key: "bpm", header: "BPM", sortValue: (p) => p.bpm, render: (p) => fixed(p.bpm) },
              { key: "obpm", header: "OBPM", sortValue: (p) => p.obpm, render: (p) => fixed(p.obpm) },
              { key: "dbpm", header: "DBPM", sortValue: (p) => p.dbpm, render: (p) => fixed(p.dbpm) },
              { key: "ts", header: "TS%", sortValue: (p) => p.ts_pct, render: (p) => pct(p.ts_pct, 1) },
              { key: "usg", header: "USG%", sortValue: (p) => p.usg_pct, render: (p) => fixed(p.usg_pct) },
              { key: "fg3", header: "3P% (shrunk)", sortValue: (p) => p.fg3_pct_eb, render: (p) => pct(p.fg3_pct_eb, 1) },
              { key: "fg3a", header: "3PA/100", sortValue: (p) => p.fg3a_per_poss, render: (p) => fixed(p.fg3a_per_poss) },
              { key: "ast", header: "AST%", sortValue: (p) => p.ast_pct, render: (p) => fixed(p.ast_pct) },
              { key: "blk", header: "BLK%", sortValue: (p) => p.blk_pct, render: (p) => fixed(p.blk_pct) },
            ]}
          />
          <p className={s.hint}>
            Profile source: nba = regularised NBA stats; nba+college = young player blended with his college projection; college = rookie with no NBA minutes yet.
          </p>
        </>
      )}
    </details>
  );
}
