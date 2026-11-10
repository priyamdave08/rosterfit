"""Live NBA rosters from ESPN's public site API (always the current season)."""
from __future__ import annotations

import json

import pandas as pd

from rosterfit.ingest.http import fetch

TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{tid}/roster"

# ESPN -> Basketball-Reference abbreviations where they differ.
ESPN_TO_BREF = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA",
                "WSH": "WAS", "PHX": "PHO", "BKN": "BRK", "CHA": "CHO"}


def teams(refresh: bool = True) -> pd.DataFrame:
    data = json.loads(fetch(TEAMS_URL, suffix=".json", refresh=refresh))
    out = []
    for t in data["sports"][0]["leagues"][0]["teams"]:
        t = t["team"]
        abbr = t["abbreviation"]
        out.append({"espn_id": int(t["id"]), "espn_abbr": abbr,
                    "team_abbr": ESPN_TO_BREF.get(abbr, abbr), "team_name": t["displayName"],
                    "color": "#" + t.get("color", "333333"),
                    "alt_color": "#" + t.get("alternateColor", "999999")})
    return pd.DataFrame(out)


def rosters(refresh: bool = True) -> pd.DataFrame:
    """One row per rostered player on every team, as of today."""
    rows = []
    for team in teams(refresh=refresh).itertuples():
        data = json.loads(fetch(ROSTER_URL.format(tid=team.espn_id), suffix=".json", refresh=refresh))
        for a in data.get("athletes", []):
            rows.append({
                "team_abbr": team.team_abbr, "espn_player_id": int(a["id"]),
                "player": a["fullName"], "position": (a.get("position") or {}).get("abbreviation"),
                "height_in": a.get("height"), "weight_lb": a.get("weight"), "age": a.get("age"),
                "experience": (a.get("experience") or {}).get("years"),
                "jersey": a.get("jersey"),
                "headshot": (a.get("headshot") or {}).get("href"),
                "season_label": data.get("season", {}).get("displayName"),
            })
    return pd.DataFrame(rows)
