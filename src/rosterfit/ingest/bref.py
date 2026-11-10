"""Basketball-Reference ingestion: player advanced / per-100 / shooting tables,
team ratings and draft classes.

Tables are parsed by their ``data-stat`` attributes rather than header text,
which is far more stable across seasons. Some B-Ref tables ship inside HTML
comments; those are uncommented before parsing.
"""
from __future__ import annotations

import re

import pandas as pd
from bs4 import BeautifulSoup

from rosterfit.ingest.http import fetch

BASE = "https://www.basketball-reference.com"


def _parse_table(html: str, table_id: str) -> pd.DataFrame:
    html = re.sub(r"<!--|-->", "", html)
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id=table_id)
    if table is None:
        raise ValueError(f"table #{table_id} not found")
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        if "thead" in (tr.get("class") or []):
            continue
        cells = tr.find_all(["th", "td"])
        rec = {}
        for c in cells:
            stat = c.get("data-stat")
            if not stat:
                continue
            rec[stat] = c.get_text(strip=True)
            if stat in ("player", "name_display", "team_name", "team"):
                a = c.find("a")
                if a and a.get("href"):
                    rec[f"{stat}_href"] = a["href"]
            if c.get("data-append-csv"):
                rec["player_id"] = c["data-append-csv"]
        if rec:
            rows.append(rec)
    df = pd.DataFrame(rows)
    # Normalise column names that changed in B-Ref's 2024 redesign.
    df = df.rename(columns={"name_display": "player", "team_name_abbr": "team_id", "pos": "pos",
                            "age": "age", "games": "g", "games_started": "gs"})
    if "player_id" not in df.columns and "player_href" in df.columns:
        df["player_id"] = df["player_href"].str.extract(r"/players/\w/(\w+)\.html")[0]
    return df.replace({"": None})


def _numeric(df: pd.DataFrame, keep: tuple[str, ...]) -> pd.DataFrame:
    for col in df.columns:
        if col in keep or col.endswith("_href"):
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


_TEXT_COLS = ("player", "player_id", "team_id", "pos", "awards", "college_name", "team", "team_name")


def player_table(season: int, kind: str) -> pd.DataFrame:
    """kind in {'advanced', 'per_poss', 'shooting'}; one row per player-team stint."""
    html = fetch(f"{BASE}/leagues/NBA_{season}_{kind}.html")
    table_id = {"advanced": "advanced", "per_poss": "per_poss", "shooting": "shooting"}[kind]
    df = _parse_table(html, table_id)
    df = df[df["player"].notna() & (df["player"] != "League Average")]
    df = _numeric(df, _TEXT_COLS)
    df["season"] = season
    return df.reset_index(drop=True)


def team_ratings(season: int) -> pd.DataFrame:
    html = fetch(f"{BASE}/leagues/NBA_{season}_ratings.html")
    df = _parse_table(html, "ratings")
    df = df[df["team_name"].notna()].copy()
    df["team_abbr"] = df["team_name_href"].str.extract(r"/teams/(\w+)/")[0]
    df = _numeric(df, _TEXT_COLS + ("team_abbr", "conf_id", "division_id"))
    df["season"] = season
    return df.reset_index(drop=True)


def draft_class(year: int) -> pd.DataFrame:
    html = fetch(f"{BASE}/draft/NBA_{year}.html")
    df = _parse_table(html, "stats")
    df = df[df["player"].notna() & df["pick_overall"].notna()].copy()
    df = _numeric(df, _TEXT_COLS)
    df["draft_year"] = year
    return df.reset_index(drop=True)
