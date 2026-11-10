"""Design tokens: text colours must meet WCAG 2.2 AA, and the theme must use the tokens."""
from pathlib import Path

import pytest
import tomllib

from rosterfit.viz import palette


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("name", ["INK", "INK_2", "MUTED", "PRIMARY", "BRAND", "HOT", "COLD", "DATA",
                                  "SUCCESS", "WARNING", "ERROR"])
def test_text_colours_meet_aa_on_paper(name):
    assert contrast(getattr(palette, name), palette.PAPER) >= 4.5


@pytest.mark.parametrize("name", ["PRIMARY", "DATA", "HOT", "COLD"])
def test_white_text_on_filled_colours_meets_aa(name):
    assert contrast("#FFFFFF", getattr(palette, name)) >= 4.5


def test_streamlit_theme_uses_the_tokens():
    theme = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit/config.toml").read_text())["theme"]
    assert theme["primaryColor"] == palette.PRIMARY
    assert theme["backgroundColor"] == palette.PAPER
    assert theme["textColor"] == palette.INK
    assert palette.HEADING_FONT in theme["headingFont"]
    assert "Inter" not in theme["font"]
