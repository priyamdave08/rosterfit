"""Shared data access and lineup components for the dashboard pages."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from rosterfit import demo_data
from rosterfit.engine.context import Context, get_context
from rosterfit.features.college import FEATURE_LABELS
from rosterfit.features.league import college_zone_averages, nba_zone_averages
from rosterfit.features.players import PROFILE_COLS
from rosterfit.viz import palette as P
from rosterfit.viz import shots

# --------------------------------------------------------------------------- labels
STAT_LABELS = {
    "avg_bpm": "Talent (BPM)", "avg_obpm": "Offensive BPM", "avg_dbpm": "Defensive BPM",
    "avg_ts_pct": "True shooting", "spacing_index": "Spacing", "n_shooters": "# shooters",
    "n_creators": "# creators", "n_rim_protectors": "# rim protectors", "usage_overload": "Usage overload",
    "usage_vacuum": "Usage vacuum", "usage_sd": "Usage spread (star vs committee)", "usage_weighted_ts": "Shot-taker TS%",
    "paint_clog": "Paint congestion", "avg_trb_pct": "Rebounding", "creator_x_spacing": "Creation × spacing",
    "def_anchor_x_perimeter": "Rim protection × ball pressure", "avg_off_rtg": "Offensive rating",
    "avg_def_rtg": "Defensive rating", "avg_tov_pct": "Turnovers", "avg_stl_pct": "Steals",
    "avg_blk_pct": "Blocks", "no_creator": "No creator", "no_rim_protector": "No rim protector",
    "avg_pos": "Size", "pos_spread": "Positional spread", "avg_ast_pct": "Assist rate",
    "avg_drb_pct": "Defensive rebounding", "avg_orb_pct": "Offensive rebounding", "avg_usg_pct": "Usage",
    "avg_fta_rate": "Free-throw rate", "avg_fg3a_rate": "3PA rate", "avg_corner3_share": "Corner-3 share",
    "avg_rim_freq": "Rim frequency", "avg_rim_fg": "Rim FG%", "avg_mid_freq": "Mid-range frequency",
    "usage_total": "Usage total", "too_small": "Too small", "too_big": "Too big",
    "n_non_shooters": "# non-shooters", "n_bigs": "# bigs",
}
COLLEGE_LABELS = FEATURE_LABELS
PROFILE_LABELS = {
    "bpm": "BPM", "obpm": "Offensive BPM", "dbpm": "Defensive BPM", "ts_pct": "True shooting", "usg_pct": "Usage",
    "ast_pct": "Assist rate", "tov_pct": "Turnover rate", "orb_pct": "Off. rebound rate", "drb_pct": "Def. rebound rate",
    "trb_pct": "Rebound rate", "stl_pct": "Steal rate", "blk_pct": "Block rate", "fg3a_rate": "3PA rate",
    "fta_rate": "Free-throw rate", "fg3_pct_eb": "3P% (shrunk)", "fg3a_per_poss": "3PA per 100", "rim_freq": "Rim frequency",
    "rim_fg": "Rim FG%", "mid_freq": "Mid-range frequency", "corner3_share": "Corner-3 share",
    "off_rtg": "Offensive rating", "def_rtg": "Defensive rating", "pos_num": "Position",
}
SHOOTER_HELP = ("Players taking 5.5+ threes per 100 possessions at a Bayes-shrunk 35.5% or better (above league "
                "average). A 34% shooter on volume counts as zero.")
NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
CHART_MARGIN = {"l": 8, "r": 8, "t": 44, "b": 8}


# --------------------------------------------------------------------------- data
@st.cache_resource(show_spinner="Downloading the demo data (first visit only)…")
def _demo_bundle() -> bool:
    return demo_data.ensure_demo_data()


@st.cache_resource(show_spinner="Loading models and rosters (first load takes about 30 seconds)…")
def _load_context() -> Context:
    return get_context()


def context() -> Context:
    """The shared engine context; on a fresh hosted deploy, fetches the demo bundle first."""
    try:
        _demo_bundle()
    except demo_data.DemoDataError as err:
        st.error(f"The demo data couldn't be loaded: {err}. Reload the page to try again.")
        st.stop()
    return _load_context()


@st.cache_resource(show_spinner=False)
def league_shooting() -> tuple[pd.Series, dict]:
    return nba_zone_averages(), college_zone_averages()


def team_names() -> dict[str, str]:
    return context().teams.set_index("team_abbr")["team_name"].to_dict()


def team_colors() -> dict[str, str]:
    t = context().teams.set_index("team_abbr")["color"].dropna()
    return {k: v if str(v).startswith("#") else f"#{v}" for k, v in t.items()}


# --------------------------------------------------------------------------- names and labels
def team_tag(pid: str) -> str:
    """Current team code, or FA for unsigned players."""
    t = context().players.loc[pid].get("current_team")
    return t if isinstance(t, str) and t else "FA"


def pct(x: float) -> str:
    return f"{x:.0%}" if pd.notna(x) else "n/a"


def plural(n: int, word: str) -> str:
    return f"**{n}** {word}{'' if n == 1 else 's'}"


def _prospect_id(pid: str) -> int | None:
    return int(str(pid).split(":")[1]) if str(pid).startswith("prospect:") else None


def name_of(pid: str) -> str:
    tid = _prospect_id(pid)
    ctx = context()
    return str(ctx.prospects.loc[tid, "player"] if tid is not None else ctx.players.loc[pid, "player"])


def short_name(name: str) -> str:
    """Last name, keeping a suffix: 'Kevin Porter Jr.' -> 'Porter Jr.'."""
    parts = name.split()
    if len(parts) >= 3 and parts[-1].lower() in NAME_SUFFIXES:
        return " ".join(parts[-2:])
    return parts[-1] if parts else name


def lineup_names(ids: list[str]) -> str:
    return ", ".join(short_name(name_of(i)) for i in ids)


def player_label(pid: str) -> str:
    tid = _prospect_id(pid)
    if tid is not None:
        pr = context().prospects.loc[tid]
        return f"{pr['player']} ({pr['team']}, prospect {pr['grade']})"
    return f"{context().players.loc[pid, 'player']} ({team_tag(pid)})"


# --------------------------------------------------------------------------- lineups
def five_frame(ids: list[str]) -> pd.DataFrame:
    ctx = context()
    rows = []
    for pid in ids:
        tid = _prospect_id(pid)
        if tid is not None:
            rows.append(ctx.prospect_as_player(tid))
        else:
            r = ctx.players.loc[pid].copy()
            r["player_id"] = pid
            rows.append(r)
    return pd.DataFrame(rows)


def builder_pool(kind: str, roster: pd.DataFrame) -> list[str]:
    """Players selectable in the lineup builder: this roster first, then the league, then prospects."""
    ctx = context()
    ids = list(roster.index)
    if kind != "Roster":
        league = ctx.players[(ctx.players["source"] != "replacement") & ~ctx.players.index.isin(ids)]
        ids += list(league.sort_values("minutes_proxy", ascending=False).index)
    if kind == "League + draft prospects":
        top = ctx.prospects[ctx.prospects["draft_prob"] >= 0.3].sort_values("grade_score", ascending=False)
        ids += [f"prospect:{i}" for i in top.index[:300]]
    return ids


def lineup_metrics(ids: list[str]) -> dict:
    """Headline numbers for one lineup, as a row for comparison tables."""
    prof = five_frame(ids)[PROFILE_COLS].astype(float)
    pred = context().lineup_model.predict_lineup(prof)
    f = pred["features"]
    return {"Players": lineup_names(ids),
            "Net": pred["net_rtg"], "Offense vs avg": pred["off_rtg_rel"], "Defense vs avg": -pred["def_rtg_rel"],
            "Shooters": f["n_shooters"], "Creators": f["n_creators"], "Rim protectors": f["n_rim_protectors"],
            "Spacing": f["spacing_index"], "Usage total": f["usage_total"]}


LINEUP_COLUMNS = {
    "Lineup": st.column_config.TextColumn("Lineup", width=322),
    "Net": st.column_config.NumberColumn("Net", width=56, format="%+.1f", help="Projected net rating per 100 possessions"),
    "Off": st.column_config.NumberColumn("Off", width=56, format="%+.1f", help="Offense vs league average (positive = better)"),
    "Def": st.column_config.NumberColumn("Def", width=56, format="%+.1f", help="Defense vs league average (positive = better)"),
    "Shooters": st.column_config.NumberColumn("Shooters", width=66, format="%.0f", help=SHOOTER_HELP),
    "Spacing": st.column_config.NumberColumn("Spacing", width=66, format="%.2f", help="Volume-weighted 3P% above 30%"),
    "Usage": st.column_config.NumberColumn("Usage", width=58, format="%.0f", help="Sum of the five usage rates (100 = balanced)"),
}


def lineup_table(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({"Lineup": df["player_ids"].map(lineup_names), "Net": df["net_rtg"],
                        "Off": df["off_rtg_rel"], "Def": -df["def_rtg_rel"], "Shooters": df["n_shooters"],
                        "Spacing": df["spacing_index"], "Usage": df["usage_total"]}, index=df.index)
    out.index.name = "#"
    return out


def show_lineups(df: pd.DataFrame, where=st, **kw) -> None:
    where.dataframe(lineup_table(df), width="stretch", column_config=LINEUP_COLUMNS, **kw)


# --------------------------------------------------------------------------- charts
def drivers_chart(df: pd.DataFrame, value_col: str, labels: dict, title: str) -> go.Figure:
    """Signed contributions: warm bars help, cool bars hurt (same scale as the shot charts)."""
    d = df.copy()
    d["label"] = d["feature"].map(labels).fillna(d["feature"])
    d = d.iloc[::-1]
    fig = go.Figure(go.Bar(x=d[value_col], y=d["label"], orientation="h",
                           marker_color=P.sign_colors(d[value_col]),
                           hovertext=[f"value = {v:.3g}" for v in d["value"]], hoverinfo="text+x"))
    fig.update_layout(title=title, height=330, margin=CHART_MARGIN, xaxis_title="Effect on net rating" if
                      value_col == "net_impact" else "Effect on expected VORP")
    return fig


def share_bars(df: pd.DataFrame, value: str, label: str, title: str, colors: list[str] | None = None,
               height: int = 250) -> go.Figure:
    """Horizontal percentage bars with the value printed inside each bar."""
    fill = colors if colors is not None else [P.DATA] * len(df)
    fig = go.Figure(go.Bar(x=df[value], y=df[label], orientation="h", marker_color=fill,
                           text=df[value].map(lambda v: f"{v:.0%}"), textposition="inside",
                           insidetextanchor="end", textfont={"color": [P.text_on(c) for c in fill]},
                           hovertemplate="%{y}: %{x:.0%}<extra></extra>"))
    fig.update_layout(title=title)
    fig.update_layout(height=height, margin=CHART_MARGIN, xaxis_tickformat=".0%", xaxis_title="", yaxis_title="")
    return fig


def lineup_panel(ids: list[str], title: str, key: str, highlight: str | None = None) -> None:
    """Stat line, spacing map, rating drivers and shot diet for one five-man unit."""
    ctx = context()
    five = five_frame(ids)
    prof = five[PROFILE_COLS].astype(float)
    pred = ctx.lineup_model.predict_lineup(prof)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net rating", f"{pred['net_rtg']:+.1f}", help="Projected points per 100 possessions vs opponents")
    c2.metric("Offense vs avg", f"{pred['off_rtg_rel']:+.1f}", help="Positive = better than league-average offense")
    c3.metric("Defense vs avg", f"{-pred['def_rtg_rel']:+.1f}", help="Positive = better than league-average defense")
    c4.metric("Volume shooters", f"{pred['features']['n_shooters']:.0f}", help=SHOOTER_HELP)
    left, right = st.columns([1.15, 1])
    with left:
        fig, summary = shots.spacing_map(five.assign(player=five["player"].astype(str)), title=title,
                                         highlight=highlight)
        st.plotly_chart(fig, width="stretch", key=f"{key}_spacing")
        msg = (f"{plural(summary['perimeter_threats'], 'perimeter threat')} the defense must respect. "
               f"{plural(summary['paint_bodies'], 'player')} living in the paint.")
        legend = (f"Blue = perimeter spot, orange = paint spot{', green = incoming player' if highlight else ''}. "
                  "Circle size = how far the defense must stretch to guard him.")
        if summary["congested"]:
            st.warning(msg + " The paint is congested.")
        else:
            st.markdown(msg)
        st.caption(legend)
    with right:
        st.plotly_chart(drivers_chart(ctx.lineup_model.explain(prof), "net_impact", STAT_LABELS,
                                      "What drives the rating"), width="stretch", key=f"{key}_drivers")
        st.plotly_chart(share_bars(shots.lineup_shot_diet(prof), "share", "zone", "Shot diet (usage-weighted)"),
                        width="stretch", key=f"{key}_diet")
