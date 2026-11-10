import { get } from "./api";
import type { LineupList } from "./types";

/** Shared query definition so the startup prefetch and the Lineup Lab hit the same cache entry. */
export const lineupsQuery = (team: string) => ({
  queryKey: ["lineups", team] as const,
  queryFn: () => get<LineupList>(`/ui/teams/${team}/lineups`, { top: 15 }),
});
