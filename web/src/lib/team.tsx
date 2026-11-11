import { createContext, use, useEffect, useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { get } from "./api";
import { applyColorway, colorway } from "./color";
import { KEY, readStored } from "./teamStorage";
import type { Meta, Team } from "./types";

interface TeamState {
  meta: Meta | undefined;
  team: string;
  teamInfo: Team | undefined;
  setTeam: (abbr: string) => void;
  isLoading: boolean;
  /** True while the first request keeps failing because the free API is still starting. */
  waking: boolean;
  error: Error | null;
}

const TeamContext = createContext<TeamState | null>(null);
/** The selected team lives in the URL (?team=SAS) so links and reloads keep it. */
export function TeamProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => get<Meta>("/ui/meta"), staleTime: Infinity });
  const valid = new Set(meta.data?.teams.map((t) => t.abbr) ?? []);
  const fromUrl = params.get("team")?.toUpperCase() ?? null;
  const stored = readStored();
  const team = (fromUrl && (valid.size === 0 || valid.has(fromUrl)) ? fromUrl : null) ?? (stored && valid.has(stored) ? stored : "SAS");
  const teamInfo = meta.data?.teams.find((t) => t.abbr === team);

  useEffect(() => {
    if (teamInfo) applyColorway(colorway(teamInfo.color, teamInfo.alt_color));
  }, [teamInfo]);

  const value = useMemo<TeamState>(
    () => ({
      meta: meta.data,
      team,
      teamInfo,
      isLoading: meta.isLoading,
      waking: meta.isLoading && meta.failureCount > 0,
      error: meta.error,
      setTeam: (abbr: string) => {
        try {
          window.localStorage.setItem(KEY, abbr);
        } catch {
          /* private mode: the URL still carries the team */
        }
        const next = new URLSearchParams(params);
        next.set("team", abbr);
        next.delete("unit"); // unit ranks belong to the previous team's list
        setParams(next, { replace: true });
      },
    }),
    [meta.data, meta.isLoading, meta.failureCount, meta.error, team, teamInfo, params, setParams],
  );
  return <TeamContext.Provider value={value}>{children}</TeamContext.Provider>;
}

export function useTeam(): TeamState {
  const ctx = use(TeamContext);
  if (!ctx) throw new Error("useTeam must be used inside TeamProvider");
  return ctx;
}
