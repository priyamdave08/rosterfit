"""Plotly half-court with regulation NBA dimensions (feet, hoop at origin)."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

BASELINE_Y = -5.25          # baseline is 5.25 ft behind the hoop centre
HALFCOURT_Y = 41.75         # 47 ft from baseline
THREE_R = 23.75
CORNER_X = 22.0
CORNER_Y = np.sqrt(THREE_R**2 - CORNER_X**2)  # ~8.95 ft: where the arc meets the corner lines

LINE = "rgba(120,120,120,0.9)"


def _arc(r, start, end, n=80, cx=0.0, cy=0.0):
    t = np.linspace(start, end, n)
    return cx + r * np.cos(t), cy + r * np.sin(t)


def _path(xs, ys) -> str:
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in zip(xs, ys, strict=False))


def court_shapes(line_color: str = LINE) -> list[dict]:
    s = []
    line = {"color": line_color, "width": 1.6}

    def add(path):
        s.append({"type": "path", "path": path, "line": line, "layer": "above"})

    s.append({"type": "rect", "x0": -25, "y0": BASELINE_Y, "x1": 25, "y1": HALFCOURT_Y, "line": line,
              "layer": "above"})
    s.append({"type": "rect", "x0": -8, "y0": BASELINE_Y, "x1": 8, "y1": 13.75, "line": line, "layer": "above"})
    s.append({"type": "rect", "x0": -6, "y0": BASELINE_Y, "x1": 6, "y1": 13.75, "line": line, "layer": "above"})
    s.append({"type": "circle", "x0": -0.75, "y0": -0.75, "x1": 0.75, "y1": 0.75, "line": line, "layer": "above"})
    s.append({"type": "line", "x0": -3, "y0": -1.25, "x1": 3, "y1": -1.25, "line": line, "layer": "above"})
    add(_path(*_arc(6, 0, np.pi, cy=13.75)))                    # free-throw circle (top half)
    add(_path(*_arc(4, 0, np.pi)))                              # restricted area
    th = np.arcsin(CORNER_Y / THREE_R)
    xa, ya = _arc(THREE_R, th, np.pi - th)
    add(_path(np.r_[CORNER_X, xa, -CORNER_X], np.r_[BASELINE_Y, ya, BASELINE_Y]))
    add(_path(*_arc(6, np.pi, 2 * np.pi, cy=HALFCOURT_Y)))      # centre circle
    return s


def base_figure(title: str | None = None, height: int = 520, dark: bool = False) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        shapes=court_shapes("rgba(220,220,220,0.85)" if dark else LINE),
        xaxis={"range": [-25.5, 25.5], "visible": False, "fixedrange": True},
        yaxis={"range": [BASELINE_Y - 0.5, 33], "visible": False, "scaleanchor": "x", "fixedrange": True},
        height=height, margin={"l": 10, "r": 10, "t": 50 if title else 10, "b": 10},
        title=title, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
    )
    return fig
