"""OPTIONAL: individual shot locations (x, y) from stats.nba.com via `nba_api`.

stats.nba.com frequently blocks or times out requests from cloud / CI hosts, so
the core pipeline does not depend on it. When it is reachable, this powers the
hexbin shot charts in the app; otherwise the app falls back to zone charts
built from Basketball-Reference shooting splits.

    pip install "rosterfit[shots]"
"""
from __future__ import annotations

import json
import logging

import pandas as pd

from rosterfit import config

log = logging.getLogger("rosterfit.shots")
CACHE = config.RAW_DIR / "nba_shots"


def season_string(bref_season: int) -> str:
    return f"{bref_season - 1}-{str(bref_season)[-2:]}"


def shot_locations(player_name: str, season: int = config.LAST_FULL_SEASON, timeout: int = 20) -> pd.DataFrame | None:
    """Return one row per FGA with LOC_X/LOC_Y in feet (hoop at origin), or None."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{player_name.replace(' ', '_')}_{season}.json"
    if path.exists():
        return pd.DataFrame(json.loads(path.read_text()))
    try:
        from nba_api.stats.endpoints import shotchartdetail
        from nba_api.stats.static import players
    except ImportError:
        return None
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        return None
    try:
        resp = shotchartdetail.ShotChartDetail(
            team_id=0, player_id=matches[0]["id"], season_nullable=season_string(season),
            context_measure_simple="FGA", timeout=timeout)
        df = resp.get_data_frames()[0]
    except Exception as exc:  # noqa: BLE001 - network / blocking errors are expected
        log.warning("stats.nba.com unavailable for %s: %s", player_name, exc)
        return None
    df = df.assign(x=-df["LOC_X"] / 10.0, y=df["LOC_Y"] / 10.0, made=df["SHOT_MADE_FLAG"])[["x", "y", "made"]]
    path.write_text(df.to_json(orient="records"))
    return df


def hexbin_chart(shots: pd.DataFrame, title: str = "", dark: bool = False):
    """Hexagonal-ish binned shot chart (2D histogram), size ~ volume, colour ~ FG%."""
    import numpy as np
    import plotly.graph_objects as go

    from rosterfit.viz.court import base_figure

    shots = shots[(shots["y"] < 33) & (shots["x"].abs() <= 25)]
    bx = np.round(shots["x"] / 1.5) * 1.5
    by = np.round(shots["y"] / 1.5) * 1.5
    g = shots.assign(bx=bx, by=by).groupby(["bx", "by"]).agg(n=("made", "size"), fg=("made", "mean")).reset_index()
    fig = base_figure(title, dark=dark)
    fig.add_trace(go.Scatter(
        x=g["bx"], y=g["by"], mode="markers", hovertext=[f"{n} FGA, {fg:.0%}" for n, fg in zip(g["n"], g["fg"], strict=False)],
        hoverinfo="text", marker={"symbol": "hexagon", "size": 4 + 14 * np.sqrt(g["n"] / g["n"].max()),
                                  "color": g["fg"], "colorscale": "RdBu_r", "cmin": 0.2, "cmax": 0.7,
                                  "colorbar": {"title": "FG%"}}))
    return fig
