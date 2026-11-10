"""RosterFit design tokens: colour, type and the Plotly chart template.

Identity: a printed scouting report. Warm paper and ink for surfaces, condensed
box-score headings, monospaced figures. Each colour has one job:

  PRIMARY  navy      anything the user can act on (buttons, selections, focus)
  BRAND    hardwood  the wordmark and the painted area on court diagrams only
  HOT/COLD           above / below league average, and helps / hurts. The same
                     scale is used by shot charts, driver charts and outcome tiers,
                     so "warm = good" reads the same everywhere.
  DATA     slate     single-series bars where no judgement is implied

All text colours pass WCAG 2.2 AA (4.5:1) on PAPER; see tests/test_palette.py.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# --------------------------------------------------------------------------- colour
INK = "#16191D"          # body text, court lines
INK_2 = "#4A4F57"        # secondary text, axis labels
MUTED = "#62666E"        # captions, metadata
RULE = "#D9D4C9"         # hairlines and table borders
PAPER = "#FBFAF7"        # page
PAPER_2 = "#F1EEE6"      # inputs, table headers
NEUTRAL_MID = "#EFEBE3"  # midpoint of the diverging scale

PRIMARY = "#1F3A5F"
BRAND = "#B5501A"
HOT = "#B83C2A"
COLD = "#2A6496"
DATA = "#3E5770"
HIGHLIGHT = "#2A7A5E"    # the player being added in a roster move

SUCCESS = "#2A7A5E"
WARNING = "#8A5F00"
ERROR = "#B23A2E"

# Cold -> neutral -> hot, for anything measured against league average.
DIVERGING = [[0.0, COLD], [0.5, NEUTRAL_MID], [1.0, HOT]]
# Six ordered steps, worst to best (career-path tiers, etc.).
ORDINAL = ["#2A6496", "#5E86AA", "#9AA7B2", "#C9A27E", "#C26A45", "#B83C2A"]
CATEGORICAL = [PRIMARY, BRAND, HIGHLIGHT, "#8C6D1F", "#6A5D86", "#5E6B73"]


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    hi, lo = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def text_on(fill: str) -> str:
    """White or ink, whichever reads better on ``fill``."""
    return "#FFFFFF" if contrast("#FFFFFF", fill) >= contrast(INK, fill) else INK


def sign_colors(values) -> list[str]:
    """Hot for helps / above average, cold for hurts / below."""
    return [HOT if v >= 0 else COLD for v in values]


# --------------------------------------------------------------------------- type
BODY_FONT = "IBM Plex Sans"
HEADING_FONT = "Barlow Condensed"
MONO_FONT = "IBM Plex Mono"
FONT_STACK = f"{BODY_FONT}, -apple-system, Segoe UI, sans-serif"
HEADING_STACK = f"{HEADING_FONT}, {BODY_FONT}, sans-serif"

# --------------------------------------------------------------------------- spacing (px)
SPACE = {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 40}
RADIUS = {"sm": 3, "md": 4}

# --------------------------------------------------------------------------- Plotly template
TEMPLATE = go.layout.Template(
    layout={
        "font": {"family": FONT_STACK, "size": 12, "color": INK_2},
        "title": {"font": {"family": HEADING_STACK, "size": 18, "color": INK}, "x": 0, "xanchor": "left",
                  "pad": {"l": 4}},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": CATEGORICAL,
        "xaxis": {"gridcolor": RULE, "zerolinecolor": INK_2, "zerolinewidth": 1, "linecolor": RULE,
                  "tickfont": {"color": INK_2}, "title": {"font": {"color": INK_2}}},
        "yaxis": {"gridcolor": RULE, "zerolinecolor": INK_2, "zerolinewidth": 1, "linecolor": RULE,
                  "tickfont": {"color": INK_2}, "title": {"font": {"color": INK_2}}},
        "polar": {"bgcolor": "rgba(0,0,0,0)", "radialaxis": {"gridcolor": RULE, "linecolor": RULE},
                  "angularaxis": {"gridcolor": RULE, "linecolor": INK_2, "tickfont": {"color": INK_2}}},
        "legend": {"font": {"color": INK_2}, "title": {"font": {"color": INK}}},
        "hoverlabel": {"bgcolor": "#FFFFFF", "bordercolor": RULE, "font": {"family": FONT_STACK, "color": INK}},
        "bargap": 0.28,
    },
    data={"bar": [go.Bar(marker={"color": DATA}, textfont={"color": "#FFFFFF"})]},
)
pio.templates["rosterfit"] = TEMPLATE
pio.templates.default = "rosterfit"
