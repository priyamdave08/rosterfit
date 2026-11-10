// Where the last-chosen team is remembered, readable before the app (and team metadata) loads.
export const KEY = "rosterfit.team";

export function readStored(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** The team a fresh page load will most likely show, before team metadata has loaded. */
export function initialTeam(): string {
  return new URLSearchParams(window.location.search).get("team")?.toUpperCase() ?? readStored() ?? "SAS";
}
