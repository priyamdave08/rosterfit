// Team colorway resolution with WCAG contrast guarantees. A team's ESPN colors drive the
// shell and the twill numerals, but text on them always clears AA, whatever the team.

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const INK = "#121212";
const WHITE = "#ffffff";

export function textOn(fill: string): string {
  return contrast(WHITE, fill) >= contrast(INK, fill) ? WHITE : INK;
}

function mix(hex: string, toward: string, amount: number): string {
  const a = hex.replace("#", "");
  const b = toward.replace("#", "");
  const out = [0, 2, 4].map((i) => {
    const x = parseInt(a.slice(i, i + 2), 16);
    const y = parseInt(b.slice(i, i + 2), 16);
    return Math.round(x + (y - x) * amount)
      .toString(16)
      .padStart(2, "0");
  });
  return `#${out.join("")}`;
}

export interface Colorway {
  team: string;
  team2: string;
  onTeam: string;
  onTeamMuted: string;
  twillFill: string;
  twillEdge: string;
}

/** Shell = primary; stitching = secondary; numerals = the secondary (or white/ink) on primary. */
export function colorway(primary: string, secondary: string): Colorway {
  let team = primary.toLowerCase();
  // A very light primary (rare) can't carry white type or read as a shell; deepen it.
  if (contrast(team, WHITE) < 3 && contrast(team, INK) < 7) team = mix(team, INK, 0.55);
  const onTeam = textOn(team);
  const onTeamMuted = mix(onTeam, team, 0.25);
  const sec = secondary.toLowerCase();
  const twillFill = contrast(sec, team) >= 3 ? sec : onTeam;
  return { team, team2: sec, onTeam, onTeamMuted, twillFill, twillEdge: team };
}

export function applyColorway(c: Colorway, el: HTMLElement = document.documentElement): void {
  el.style.setProperty("--team", c.team);
  el.style.setProperty("--team-2", c.team2);
  el.style.setProperty("--on-team", c.onTeam);
  el.style.setProperty("--on-team-muted", c.onTeamMuted);
  el.style.setProperty("--twill-fill", c.twillFill);
  el.style.setProperty("--twill-edge", c.twillEdge);
}

/** Diverging cold to hot for "vs league average" (shot zones, FG% diff in points). */
export function diverging(t: number): string {
  const clamp = Math.max(-1, Math.min(1, t));
  const mid = "#efebe3";
  return clamp >= 0 ? mix(mid, "#b03a28", clamp) : mix(mid, "#285f9a", -clamp);
}

/** Worst-to-best ordinal steps (career paths), same scale as the Streamlit palette. */
export const ORDINAL = ["#2a6496", "#5e86aa", "#9aa7b2", "#c9a27e", "#c26a45", "#b83c2a"];
