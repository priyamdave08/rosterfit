"""Pull every raw source and write tidy parquet files to data/processed.

    python -m rosterfit.ingest.pipeline            # everything (cached pages are reused)
    python -m rosterfit.ingest.pipeline --refresh  # re-download in-progress season + rosters
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd

from rosterfit import config
from rosterfit.ingest import bref, espn, torvik

log = logging.getLogger("rosterfit.ingest")


def _concat(frames: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat([f for f in frames if f is not None and len(f)], ignore_index=True)


def run(refresh_current: bool = False) -> None:
    out = config.PROCESSED_DIR
    seasons = range(config.FIRST_SEASON, config.CURRENT_SEASON + 1)

    for kind in ("advanced", "per_poss", "shooting"):
        frames = []
        for s in seasons:
            if refresh_current and s == config.CURRENT_SEASON:
                bref.fetch(f"{bref.BASE}/leagues/NBA_{s}_{kind}.html", refresh=True)
            try:
                frames.append(bref.player_table(s, kind))
                log.info("bref %s %s: %d rows", kind, s, len(frames[-1]))
            except Exception as exc:  # noqa: BLE001 - keep the pipeline going, log the gap
                log.warning("bref %s %s failed: %s", kind, s, exc)
        _concat(frames).to_parquet(out / f"nba_{kind}.parquet", index=False)

    ratings = []
    for s in seasons:
        try:
            ratings.append(bref.team_ratings(s))
        except Exception as exc:  # noqa: BLE001
            log.warning("bref ratings %s failed: %s", s, exc)
    _concat(ratings).to_parquet(out / "nba_team_ratings.parquet", index=False)

    drafts = []
    for y in range(config.FIRST_DRAFT, config.CURRENT_SEASON):
        try:
            drafts.append(bref.draft_class(y))
        except Exception as exc:  # noqa: BLE001
            log.warning("bref draft %s failed: %s", y, exc)
    _concat(drafts).to_parquet(out / "nba_drafts.parquet", index=False)

    college = []
    for y in range(config.FIRST_COLLEGE_SEASON, config.CURRENT_SEASON + 1):
        try:
            college.append(torvik.season(y, refresh=refresh_current and y == config.CURRENT_SEASON))
            log.info("torvik %s: %d rows", y, len(college[-1]))
        except Exception as exc:  # noqa: BLE001
            log.warning("torvik %s failed: %s", y, exc)
    _concat(college).to_parquet(out / "college_players.parquet", index=False)

    espn.teams().to_parquet(out / "teams.parquet", index=False)
    espn.rosters().to_parquet(out / "rosters.parquet", index=False)
    log.info("ingest complete -> %s", out)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true", help="re-download the in-progress season")
    run(refresh_current=p.parse_args().refresh)
