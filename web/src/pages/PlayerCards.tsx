import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "../lib/api";
import { fixed, pct } from "../lib/format";
import { useTeam } from "../lib/team";
import type { Person, PlayerCard } from "../lib/types";
import { Radar, ZoneChart } from "../components/Charts";
import { PageHeader, Section, TextField } from "../components/Controls";
import { DataTable } from "../components/DataTable";
import { StatLine } from "../components/StatLine";
import { Empty, ErrorState, Skeleton } from "../components/States";
import { Twill } from "../components/Twill";
import s from "./Page.module.css";

const season = (y: number) => `${y - 1}-${String(y).slice(-2)}`;
const SOURCE_HELP: Record<string, string> = {
  nba: "Regularised NBA stats",
  "nba+college": "Young player: NBA stats blended with his college projection",
  college: "Rookie with no NBA minutes: college projection",
};

export function PlayerCards() {
  const { meta } = useTeam();
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDq(q), 250);
    return () => clearTimeout(t);
  }, [q]);
  const search = useQuery({ queryKey: ["players", dq], queryFn: () => get<{ count: number; players: Person[] }>("/ui/players", { q: dq, limit: 60 }), placeholderData: (prev) => prev });
  const [pid, setPid] = useState<string | null>(null);
  const list = search.data?.players ?? [];
  const current = pid && list.some((p) => p.id === pid) ? pid : list[0]?.id ?? null;

  return (
    <>
      <PageHeader title="Player Cards" />
      <div className={s.cardsLayout}>
        <aside className={s.searchCol}>
          <TextField label="Search players" value={q} onChange={setQ} placeholder="Name or team code, e.g. wemb, Doncic, SAS" help="Matches any part of a name, ignores accents and tolerates typos. A team code lists that roster." />
          {search.error ? (
            <ErrorState error={search.error} onRetry={() => search.refetch()} />
          ) : !search.data ? (
            <Skeleton height={300} label="Searching" />
          ) : list.length === 0 ? (
            <Empty>No players match "{dq}". Try part of a first or last name, or a team code such as BOS.</Empty>
          ) : (
            <>
              <p className={s.hint} aria-live="polite">
                {dq ? `${search.data.count} match${search.data.count === 1 ? "" : "es"}` : "Players by minutes"}
                {search.data.count > list.length ? `, showing ${list.length}` : ""}
              </p>
              <ul className={`${s.resultList} scroll-area`} data-lenis-prevent aria-label="Players">
                {list.map((p) => (
                  <li key={p.id}>
                    <button type="button" className={`${s.result} ${p.id === current ? s.resultOn : ""}`} aria-pressed={p.id === current} onClick={() => setPid(p.id)}>
                      <Twill person={p} />
                      <span>{p.name}</span>
                      <span className={s.resultTeam}>{p.team}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>
        <div>{current ? <Card key={current} id={current} labels={meta?.nba_label_pos} /> : null}</div>
      </div>
    </>
  );
}

function Card({ id, labels }: { id: string; labels?: Record<string, [number, number]> }) {
  const card = useQuery({ queryKey: ["card", id], queryFn: () => get<PlayerCard>(`/ui/players/${encodeURIComponent(id)}`) });
  const seasons = card.data?.seasons ?? [];
  const [sea, setSea] = useState<number | null>(null);
  const chosen = sea ?? seasons[0]?.season ?? null;
  if (card.error) return <ErrorState error={card.error} onRetry={() => card.refetch()} />;
  if (!card.data) return <Skeleton height={600} label="Loading player card" />;
  const c = card.data;
  return (
    <div style={{ display: "grid", gap: "var(--s-5)" }}>
      <div className={s.cardHead}>
        <Twill person={c} size="lg" />
        <div>
          <h2>{c.name}</h2>
          <p className={s.hint}>{c.team === "FA" ? "Free agent" : c.team}</p>
        </div>
      </div>
      <StatLine
        stats={[
          { label: "Archetype", value: c.archetype ?? "n/a" },
          { label: "BPM (regularised)", value: c.bpm, signed: true, help: "Box plus/minus, shrunk toward his position's average when minutes are limited" },
          { label: "True shooting", value: c.ts_pct * 100, decimals: 0, suffix: "%" },
          { label: "Profile source", value: c.source, help: SOURCE_HELP[c.source] },
        ]}
      />
      <div className={s.pair} style={{ marginTop: 0 }}>
        <div style={{ display: "grid", gap: "var(--s-3)" }}>
          {seasons.length && chosen != null && labels ? (
            <>
              <label className={s.selectField}>
                <span>Season</span>
                <select value={chosen} onChange={(e) => setSea(Number(e.target.value))}>
                  {seasons.map((x) => (
                    <option key={x.season} value={x.season}>
                      {season(x.season)}
                    </option>
                  ))}
                </select>
              </label>
              <ZoneChart title={`Shot zones, ${season(chosen)}`} scheme="nba" zones={c.zones[String(chosen)]} labels={labels} />
            </>
          ) : (
            <Empty>No NBA shooting data yet. This player's profile is a projection from college stats.</Empty>
          )}
        </div>
        <Radar title="League percentiles (500+ min)" items={c.percentiles.map((p) => ({ label: p.label, pct: p.pct }))} />
      </div>
      {seasons.length > 0 && (
        <Section title="Season by season">
          <DataTable
            caption="Season by season"
            rowKey={(x) => String(x.season)}
            rows={seasons}
            columns={[
              { key: "s", header: "Season", align: "left", render: (x) => season(x.season) },
              { key: "t", header: "Team", align: "left", render: (x) => x.team_id },
              { key: "a", header: "Age", render: (x) => fixed(x.age, 0) },
              { key: "g", header: "G", render: (x) => fixed(x.g, 0) },
              { key: "mp", header: "MP", render: (x) => fixed(x.mp, 0) },
              { key: "per", header: "PER", render: (x) => fixed(x.per) },
              { key: "ts", header: "TS%", render: (x) => pct(x.ts_pct, 1) },
              { key: "usg", header: "USG%", render: (x) => fixed(x.usg_pct) },
              { key: "bpm", header: "BPM", render: (x) => fixed(x.bpm) },
              { key: "vorp", header: "VORP", render: (x) => fixed(x.vorp) },
              { key: "ws", header: "WS/48", render: (x) => fixed(x.ws_per_48, 3) },
              { key: "o", header: "ORtg", render: (x) => fixed(x.off_rtg, 0) },
              { key: "d", header: "DRtg", render: (x) => fixed(x.def_rtg, 0) },
            ]}
          />
        </Section>
      )}
    </div>
  );
}
