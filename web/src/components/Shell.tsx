import { useEffect, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { scrollToTop } from "../lib/motion";
import { useTeam } from "../lib/team";
import s from "./Shell.module.css";

const TABS = [
  { to: "/", label: "Lineup Lab", end: true },
  { to: "/draft", label: "Draft Room" },
  { to: "/moves", label: "Signings and Trades" },
  { to: "/players", label: "Player Cards" },
  { to: "/model", label: "Model Card" },
];

export function Shell({ children }: { children: ReactNode }) {
  const { meta, team, setTeam, teamInfo } = useTeam();
  const location = useLocation();

  useEffect(() => {
    scrollToTop();
  }, [location.pathname]);

  useEffect(() => {
    const tab = TABS.find((t) => (t.end ? location.pathname === t.to : location.pathname.startsWith(t.to)));
    document.title = `${tab?.label ?? "RosterFit"}${teamInfo ? `, ${teamInfo.name}` : ""} | RosterFit`;
  }, [location.pathname, teamInfo]);

  return (
    <>
      <a className={s.skip} href="#main">
        Skip to content
      </a>
      <header className={s.bar}>
        <div className={s.inner}>
          <span className={s.mark}>RosterFit</span>
          <nav className={s.tabs} aria-label="Workspaces" data-lenis-prevent>
            {TABS.map((t) => (
              <NavLink
                key={t.to}
                to={{ pathname: t.to, search: location.search }}
                end={t.end}
                className={({ isActive }) => `${s.tab} ${isActive ? s.active : ""}`}
              >
                {t.label}
              </NavLink>
            ))}
          </nav>
          <label className={s.team}>
            <span className={s.teamLabel}>Your team</span>
            <select value={team} onChange={(e) => setTeam(e.target.value)} disabled={!meta}>
              {(meta?.teams ?? [{ abbr: team, name: team }]).map((t) => (
                <option key={t.abbr} value={t.abbr}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      <main id="main" className={s.main} tabIndex={-1}>
        {children}
      </main>
      <footer className={s.footer}>
        <p>
          Rosters: ESPN, {meta?.season ?? "current"} season. Stats: Basketball-Reference (NBA) and Bart Torvik (college).
          {meta?.warehouse_built ? ` Data last built ${meta.warehouse_built}.` : ""} Ratings are per 100 possessions vs league
          average.
        </p>
      </footer>
    </>
  );
}
