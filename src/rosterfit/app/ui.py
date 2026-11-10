"""Page chrome for the RosterFit dashboard: global CSS, page headers, section headers.

Visual rules live in ``rosterfit.viz.palette`` and ``.streamlit/config.toml``; this
module only adds what the theme cannot express (metric styling, focus rings,
reduced motion, the header breadcrumb).
"""
from __future__ import annotations

from html import escape

import streamlit as st

from rosterfit import config
from rosterfit.viz import palette as P

_CSS = f"""
<style>
:root {{
  --rf-ink: {P.INK}; --rf-ink-2: {P.INK_2}; --rf-muted: {P.MUTED}; --rf-rule: {P.RULE};
  --rf-primary: {P.PRIMARY}; --rf-brand: {P.BRAND};
  --rf-space-xs: {P.SPACE['xs']}px; --rf-space-sm: {P.SPACE['sm']}px; --rf-space-md: {P.SPACE['md']}px;
  --rf-space-lg: {P.SPACE['lg']}px; --rf-space-xl: {P.SPACE['xl']}px;
}}
.block-container {{ max-width: 1240px; padding-top: 4.75rem; padding-bottom: var(--rf-space-xl); }}
h1 {{ line-height: 1.05; letter-spacing: 0.005em; }}
h2 {{ border-top: 1px solid var(--rf-rule); padding-top: var(--rf-space-md) !important;
      margin-top: var(--rf-space-lg) !important; }}
[data-testid="stCaptionContainer"] {{ color: var(--rf-muted); opacity: 1 !important; }}

/* Box-score stat line: a heavy rule over each figure, uppercase label, tabular mono numbers. */
[data-testid="stMetric"] {{ border-top: 2px solid var(--rf-ink); padding-top: var(--rf-space-sm); }}
[data-testid="stMetricLabel"] p {{ text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.72rem;
                                   font-weight: 600; color: var(--rf-ink-2); }}
[data-testid="stMetricValue"] {{ font-family: '{P.MONO_FONT}', monospace; font-variant-numeric: tabular-nums; }}
[data-testid="stMetricValue"] > div {{ white-space: normal; overflow: visible; text-overflow: clip; line-height: 1.15; }}

.rf-textstat {{ border-top: 2px solid var(--rf-ink); padding-top: var(--rf-space-sm); }}
.rf-textstat-label {{ text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.72rem; font-weight: 600;
                      color: var(--rf-ink-2); margin-bottom: var(--rf-space-xs); }}
.rf-textstat-value {{ font-size: 1.3rem; font-weight: 600; line-height: 1.2; color: var(--rf-ink); }}

/* Header breadcrumb and purpose line. */
.rf-crumb {{ font-size: 0.85rem; color: var(--rf-ink-2); margin-bottom: var(--rf-space-xs); }}
.rf-crumb .rf-mark {{ color: var(--rf-brand); font-family: '{P.HEADING_FONT}', sans-serif; font-weight: 700;
                      font-size: 1.05rem; letter-spacing: 0.06em; text-transform: uppercase; }}
.rf-crumb .rf-sep {{ color: var(--rf-muted); padding: 0 var(--rf-space-xs); }}
.rf-swatch {{ display: inline-block; width: 0.7rem; height: 0.7rem; border-radius: 2px; margin-right: 0.35rem;
              vertical-align: -1px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.15); }}
.rf-nowrap {{ white-space: nowrap; }}
.rf-purpose {{ color: var(--rf-ink-2); font-size: 1.02rem; max-width: 64ch; margin: 0 0 var(--rf-space-sm); }}

/* Keyboard focus is always visible. */
:focus-visible {{ outline: 2px solid var(--rf-primary) !important; outline-offset: 2px; }}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation-duration: 0.01ms !important; animation-iteration-count: 1 !important;
                            transition-duration: 0.01ms !important; scroll-behavior: auto !important; }}
}}
@media (max-width: 640px) {{
  .block-container {{ padding-left: var(--rf-space-md); padding-right: var(--rf-space-md); }}
  h1 {{ font-size: 2rem !important; }}
}}
</style>
"""


def inject_css() -> None:
    st.html(_CSS)


def season_label(season: int = config.CURRENT_SEASON) -> str:
    return f"{season - 1}-{str(season)[-2:]}"


def team_picker(team_names: dict[str, str], where=st) -> str:
    """'Your team' selector that keeps its value across pages.

    Widget state is dropped on pages that don't render the widget, so the choice is
    mirrored into ``st.session_state["team"]`` and re-seeded from there.
    """
    teams = sorted(team_names)
    if "team_widget" not in st.session_state:
        st.session_state["team_widget"] = st.session_state.get("team", "SAS" if "SAS" in teams else teams[0])
    where.selectbox("Your team", teams, key="team_widget", format_func=lambda t: team_names[t],
                    help="Every page analyses this team's current roster.")
    st.session_state["team"] = st.session_state["team_widget"]
    return st.session_state["team"]


def page_header(title: str, purpose: str, team_names: dict[str, str] | None = None,
                team_colors: dict[str, str] | None = None) -> str | None:
    """Breadcrumb, page title, one-line purpose and (for team pages) the team picker.

    Returns the selected team, or None for league-wide pages.
    """
    if team_names is None:
        st.html('<div class="rf-crumb"><span class="rf-mark">RosterFit</span>'
                '<span class="rf-sep">/</span>League-wide</div>')
        st.title(title, anchor=False)
        st.html(f'<p class="rf-purpose">{escape(purpose)}</p>')
        return None
    left, right = st.columns([2.6, 1.2], vertical_alignment="center")
    with right:
        team = team_picker(team_names)
    color = (team_colors or {}).get(team, P.INK)
    with left:
        st.html(f'<div class="rf-crumb"><span class="rf-mark">RosterFit</span><span class="rf-sep">/</span>'
                f'<span class="rf-swatch" style="background:{escape(color)}" aria-hidden="true"></span>'
                f'{escape(team_names[team])} front office, <span class="rf-nowrap">{season_label()} season</span></div>')
        st.title(title, anchor=False)
        st.html(f'<p class="rf-purpose">{escape(purpose)}</p>')
    return team


def text_stat(label: str, value: str, where=st) -> None:
    """A stat-line cell for word values (archetype, source); numbers use st.metric."""
    where.html(f'<div class="rf-textstat"><div class="rf-textstat-label">{escape(label)}</div>'
               f'<div class="rf-textstat-value">{escape(value)}</div></div>')


def section(title: str, description: str | None = None) -> None:
    st.header(title, anchor=False)
    if description:
        st.caption(description)


def footer() -> None:
    """Where the numbers come from and how fresh they are (read from the warehouse file itself)."""
    import datetime as dt

    built = (dt.datetime.fromtimestamp(config.DB_PATH.stat().st_mtime).strftime("%b %d, %Y")
             if config.DB_PATH.exists() else "not built yet")
    st.divider()
    st.caption(f"Rosters: ESPN, {season_label()} season. Stats: Basketball-Reference (NBA) and Bart Torvik "
               f"(college). Data warehouse last built {built}. Ratings are per 100 possessions vs league average.")
