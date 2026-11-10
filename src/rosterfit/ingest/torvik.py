"""College player-season stats from Bart Torvik's public CSV export.

The CSV has no header row; the column map below was verified against known
players (e.g. Cooper Flagg 2025: pick == 1, BPM == 14.16, rim 128/215).
"""
from __future__ import annotations

import io

import pandas as pd

from rosterfit.ingest.http import fetch

URL = "https://barttorvik.com/getadvstats.php?year={year}&csv=1"

COLUMNS = {
    0: "player", 1: "team", 2: "conf", 3: "gp", 4: "min_pct", 5: "ortg", 6: "usg",
    7: "efg", 8: "ts", 9: "orb_pct", 10: "drb_pct", 11: "ast_pct", 12: "tov_pct",
    13: "ftm", 14: "fta", 15: "ft_pct", 16: "fg2m", 17: "fg2a", 18: "fg2_pct",
    19: "fg3m", 20: "fg3a", 21: "fg3_pct", 22: "blk_pct", 23: "stl_pct", 24: "ftr",
    25: "class_yr", 26: "height", 27: "jersey", 28: "porpag", 29: "adj_oe", 30: "pf_rate",
    31: "season", 32: "torvik_id", 33: "hometown", 34: "recruit_rank", 35: "ast_tov",
    36: "rim_m", 37: "rim_a", 38: "mid_m", 39: "mid_a", 40: "rim_pct", 41: "mid_pct",
    42: "dunk_m", 43: "dunk_a", 44: "dunk_pct", 45: "pick", 46: "drtg", 47: "adj_drtg",
    48: "dporpag", 49: "stops", 50: "bpm", 51: "obpm", 52: "dbpm", 53: "gbpm", 54: "mpg",
    55: "ogbpm", 56: "dgbpm", 57: "oreb_pg", 58: "dreb_pg", 59: "reb_pg", 60: "ast_pg",
    61: "stl_pg", 62: "blk_pg", 63: "pts_pg", 64: "role", 66: "birth_date",
}
_TEXT = {"player", "team", "conf", "class_yr", "height", "hometown", "role", "birth_date"}

# Conferences whose players historically translate best (used as a strength feature).
POWER_CONFS = {"ACC", "B10", "B12", "SEC", "BE", "P12", "P10", "Amer", "MWC", "WCC", "A10"}


def height_to_inches(h: str | float) -> float:
    try:
        feet, inches = str(h).split("-")
        return int(feet) * 12 + int(inches)
    except (ValueError, AttributeError):
        return float("nan")


def season(year: int, refresh: bool = False) -> pd.DataFrame:
    text = fetch(URL.format(year=year), suffix=".csv", refresh=refresh)
    raw = pd.read_csv(io.StringIO(text), header=None, low_memory=False)
    df = raw[list(COLUMNS)].rename(columns=COLUMNS)
    for col in df.columns:
        if col not in _TEXT:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["season"] = year
    df["height_in"] = df["height"].map(height_to_inches)
    df["birth_date"] = pd.to_datetime(df["birth_date"], errors="coerce")
    df["power_conf"] = df["conf"].isin(POWER_CONFS).astype(int)
    return df
