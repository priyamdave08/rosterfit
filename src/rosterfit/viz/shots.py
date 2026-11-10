"""Zone shot charts and lineup spacing maps.

Design follows the classic Goldsberry-style shot chart: **colour = efficiency
relative to league average** at that location, **size = shot volume**. Zones
are rasterised on a 0.5 ft grid so they render crisply as a heatmap.

Two zone schemes:
  nba     - Basketball-Reference distance zones: 0-3 ft, 3-10, 10-16, 16 ft-3P,
            corner 3 (L/R), above-the-break 3
  college - Torvik zones: at the rim, two-point jumpers, threes
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.optimize import linear_sum_assignment

from rosterfit.viz import palette
from rosterfit.viz.court import BASELINE_Y, CORNER_X, CORNER_Y, THREE_R, base_figure

GRID = 0.5
_xs = np.arange(-25, 25 + GRID, GRID)
_ys = np.arange(BASELINE_Y, 33 + GRID, GRID)
_X, _Y = np.meshgrid(_xs, _ys)
_R = np.hypot(_X, _Y)
_IS_THREE = (np.abs(_X) >= CORNER_X) & (_Y <= CORNER_Y) | (_R >= THREE_R) & (_Y > CORNER_Y)

NBA_ZONES = {
    "0-3 ft": (_R < 3) & ~_IS_THREE,
    "3-10 ft": (_R >= 3) & (_R < 10) & ~_IS_THREE,
    "10-16 ft": (_R >= 10) & (_R < 16) & ~_IS_THREE,
    "16 ft-3P": (_R >= 16) & ~_IS_THREE,
    "Left corner 3": _IS_THREE & (_Y <= CORNER_Y) & (_X < 0),
    "Right corner 3": _IS_THREE & (_Y <= CORNER_Y) & (_X > 0),
    "Above-break 3": _IS_THREE & (_Y > CORNER_Y) & (_R < 30),
}
# Labels fan out left/right inside their distance band so bubbles never stack on the centre line.
NBA_LABEL_POS = {"0-3 ft": (0, 0.6), "3-10 ft": (-5.2, 4.8), "10-16 ft": (8.6, 9.8), "16 ft-3P": (-13.5, 13.5),
                 "Left corner 3": (-23.5, 0), "Right corner 3": (23.5, 0), "Above-break 3": (9, 25.8)}

COLLEGE_ZONES = {
    "Rim": (_R < 4) & ~_IS_THREE,
    "2-pt jumper": (_R >= 4) & ~_IS_THREE,
    "Three": _IS_THREE & (_R < 30),
}
COLLEGE_LABEL_POS = {"Rim": (0, 0.8), "2-pt jumper": (-9, 11), "Three": (9, 25.8)}


@dataclass
class Zone:
    freq: float        # share of FGA from this zone (0-1)
    fg: float          # FG% from the zone
    lg_fg: float       # league FG% from the zone


def _safe(x, default=0.0) -> float:
    try:
        x = float(x)
        return default if np.isnan(x) else x
    except (TypeError, ValueError):
        return default


def nba_zones(row: pd.Series, league: pd.Series) -> dict[str, Zone]:
    """Zones for an NBA player from B-Ref shooting splits."""
    three = _safe(row.get("pct_fga_fg3a"))
    cs = _safe(row.get("pct_fg3a_corner3"))
    fg3 = _safe(row.get("fg_pct_fg3a"))
    c3 = _safe(row.get("fg_pct_corner3"), fg3)
    ab = (fg3 - cs * c3) / (1 - cs) if cs < 0.99 else fg3
    lg_c3, lg_fg3, lg_cs = league["fg_pct_corner3"], league["fg_pct_fg3a"], league["pct_fg3a_corner3"]
    lg_ab = (lg_fg3 - lg_cs * lg_c3) / (1 - lg_cs)
    z = {
        "0-3 ft": Zone(_safe(row.get("pct_fga_00_03")), _safe(row.get("fg_pct_00_03")), league["fg_pct_00_03"]),
        "3-10 ft": Zone(_safe(row.get("pct_fga_03_10")), _safe(row.get("fg_pct_03_10")), league["fg_pct_03_10"]),
        "10-16 ft": Zone(_safe(row.get("pct_fga_10_16")), _safe(row.get("fg_pct_10_16")), league["fg_pct_10_16"]),
        "16 ft-3P": Zone(_safe(row.get("pct_fga_16_xx")), _safe(row.get("fg_pct_16_xx")), league["fg_pct_16_xx"]),
        "Left corner 3": Zone(three * cs / 2, c3, lg_c3),
        "Right corner 3": Zone(three * cs / 2, c3, lg_c3),
        "Above-break 3": Zone(three * (1 - cs), ab, lg_ab),
    }
    return z


def college_zones(row: pd.Series, league: dict[str, float]) -> dict[str, Zone]:
    fga = _safe(row.get("fg2a")) + _safe(row.get("fg3a"))
    fga = fga or 1.0
    mid_a = max(_safe(row.get("fg2a")) - _safe(row.get("rim_a")), 0)
    return {
        "Rim": Zone(_safe(row.get("rim_a")) / fga, _safe(row.get("rim_eb")), league["rim"]),
        "2-pt jumper": Zone(mid_a / fga, _safe(row.get("mid_eb")), league["mid"]),
        "Three": Zone(_safe(row.get("fg3a")) / fga, _safe(row.get("fg3_eb")), league["three"]),
    }


def zone_chart(zones: dict[str, Zone], title: str = "", scheme: str = "nba", dark: bool = False,
               height: int = 440) -> go.Figure:
    masks = NBA_ZONES if scheme == "nba" else COLLEGE_ZONES
    labels = NBA_LABEL_POS if scheme == "nba" else COLLEGE_LABEL_POS
    diff = np.full(_X.shape, np.nan)
    hover = np.full(_X.shape, "", dtype=object)
    for name, mask in masks.items():
        z = zones[name]
        d = (z.fg - z.lg_fg) * 100 if z.freq > 0.005 else np.nan
        diff[mask] = d
        hover[mask] = f"{name}<br>{z.freq:.0%} of shots<br>FG {z.fg:.1%} (lg {z.lg_fg:.1%})"
    fig = base_figure(title, height=height, dark=dark)
    fig.add_trace(go.Heatmap(x=_xs, y=_ys, z=diff, zmin=-10, zmax=10, colorscale=palette.DIVERGING, opacity=0.8,
                             text=hover, hoverinfo="text",
                             colorbar={"orientation": "h", "y": -0.02, "yanchor": "top", "len": 0.8,
                                       "thickness": 10, "ticksuffix": " pts",
                                       "title": {"text": "FG% vs league average", "side": "top"}}))
    # Volume bubbles (size ~ share of attempts) with labels.
    xs, ys, sizes, texts = [], [], [], []
    for name, (x, y) in labels.items():
        z = zones[name]
        xs.append(x), ys.append(y)
        sizes.append(14 + 60 * np.sqrt(z.freq))
        texts.append(f"{z.freq:.0%}<br>{z.fg:.0%}" if z.freq > 0.005 else "")
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=texts, textfont={"size": 11, "color": palette.INK, "family": palette.MONO_FONT},
                             marker={"size": sizes, "color": palette.rgba("#FFFFFF", 0.82),
                                     "line": {"color": palette.rgba(palette.INK, 0.7), "width": 1}},
                             hoverinfo="skip"))
    fig.update_layout(margin={"l": 10, "r": 10, "t": 50 if title else 10, "b": 70})
    return fig


# --------------------------------------------------------------------------- spacing map
SPOTS = {  # name: (x, y, type)
    "Left corner": (-22.5, 0.5, "corner"), "Right corner": (22.5, 0.5, "corner"),
    "Left wing": (-17, 17, "wing"), "Right wing": (17, 17, "wing"),
    "Top of key": (0, 25.5, "top"),
    "Left dunker": (-6.5, 1.0, "dunker"), "Right dunker": (6.5, 1.0, "dunker"),
    "Elbow": (-6, 14, "elbow"),
}


def _spot_scores(p: pd.Series) -> dict[str, float]:
    shoot = max(_safe(p.fg3a_per_poss) * (_safe(p.fg3_pct_eb, 0.33) - 0.28), 0)
    return {
        "corner": 1.2 * shoot * (0.5 + _safe(p.corner3_share)) - 0.1 * _safe(p.ast_pct) / 10,
        "wing": shoot + 0.05 * _safe(p.usg_pct) / 10,
        "top": 0.06 * _safe(p.ast_pct) + 0.03 * _safe(p.usg_pct) + 0.4 * shoot,
        "dunker": 2.5 * _safe(p.rim_freq) * (1 - _safe(p.fg3a_rate)) + 0.12 * _safe(p.pos_num) - 1.2 * shoot,
        "elbow": 1.5 * _safe(p.mid_freq) + 0.15 * _safe(p.pos_num) + 0.005 * _safe(p.ast_pct) + 0.8 * shoot,
    }


def assign_spots(five: pd.DataFrame) -> list[tuple[str, str]]:
    """Optimal player->spot assignment (Hungarian algorithm, scipy)."""
    spot_names = list(SPOTS)
    cost = np.zeros((len(five), len(spot_names)))
    for i, (_, p) in enumerate(five.iterrows()):
        sc = _spot_scores(p)
        for j, s in enumerate(spot_names):
            cost[i, j] = -sc[SPOTS[s][2]]
    rows, cols = linear_sum_assignment(cost)
    return [(five.iloc[r]["player"], spot_names[c]) for r, c in zip(rows, cols, strict=False)]


def threat(p: pd.Series, spot_type: str) -> float:
    """How far the defence must stretch to respect this player (ft of 'gravity')."""
    if spot_type in ("corner", "wing", "top"):
        three = _safe(p.fg3a_per_poss) * max(_safe(p.fg3_pct_eb, 0.3) - 0.30, 0)
        return 2.0 + 9.0 * min(three / 0.8, 1.0)
    return 2.0 + 7.0 * min(_safe(p.rim_freq) * _safe(p.rim_fg, 0.6) / 0.35, 1.0)


def spacing_map(five: pd.DataFrame, title: str = "", dark: bool = False, height: int = 560,
                highlight: str | None = None) -> tuple[go.Figure, dict]:
    fig = base_figure(title, height=height, dark=dark)
    assigned = assign_spots(five)
    by_name = five.set_index("player")
    perimeter_threats = 0
    paint_bodies = 0
    for name, spot in assigned:
        p = by_name.loc[name]
        x, y, kind = SPOTS[spot]
        r = threat(p, kind)
        is_hl = highlight is not None and name == highlight
        color = palette.HIGHLIGHT if is_hl else (palette.PRIMARY if kind in ("corner", "wing", "top") else palette.BRAND)
        t = np.linspace(0, 2 * np.pi, 60)
        fig.add_trace(go.Scatter(x=x + r * np.cos(t), y=y + r * np.sin(t), fill="toself", mode="lines",
                                 line={"color": palette.rgba(color, 0.6), "width": 1},
                                 fillcolor=palette.rgba(color, 0.14), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers+text", text=[name.split(" ")[-1]],
                                 textposition="top center", textfont={"size": 12, "color": palette.INK},
                                 marker={"size": 16, "color": color, "line": {"color": "white", "width": 2}},
                                 hovertext=f"{name}<br>{spot}<br>gravity radius {r:.1f} ft", hoverinfo="text"))
        if kind in ("corner", "wing", "top") and r >= 6:
            perimeter_threats += 1
        if kind in ("dunker", "elbow") or _safe(p.fg3a_rate) < 0.15:
            paint_bodies += 1
    summary = {"assignment": assigned, "perimeter_threats": perimeter_threats,
               "paint_bodies": paint_bodies, "congested": paint_bodies >= 3}
    return fig, summary


def lineup_shot_diet(five: pd.DataFrame) -> pd.DataFrame:
    """Usage-weighted shot distribution of a lineup (where its shots come from)."""
    u = five["usg_pct"].to_numpy() / five["usg_pct"].sum()
    rim = float(np.sum(u * five["rim_freq"]))
    mid = float(np.sum(u * five["mid_freq"]))
    three = float(np.sum(u * five["fg3a_rate"]))
    short = max(1 - rim - mid - three, 0)
    return pd.DataFrame({"zone": ["Rim (0-3 ft)", "Short (3-10 ft)", "Mid-range (10 ft-3P)", "Three"],
                         "share": [rim, short, mid, three]})
