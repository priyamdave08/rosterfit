"""Central configuration: paths, seasons, and modeling constants."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("ROSTERFIT_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = DATA_DIR / "models"
DB_PATH = Path(os.environ.get("ROSTERFIT_DB", DATA_DIR / "rosterfit.duckdb"))
SQL_DIR = Path(__file__).resolve().parent / "db" / "sql"

for _d in (RAW_DIR, PROCESSED_DIR, MODEL_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Basketball-Reference labels a season by the year it ends: 2026 == 2025-26.
CURRENT_SEASON = int(os.environ.get("ROSTERFIT_SEASON", 2027))  # 2026-27 (in progress)
LAST_FULL_SEASON = CURRENT_SEASON - 1
FIRST_SEASON = 2011

# Draft classes used to train the prospect model. A draftee in year D plays
# his first NBA season in D+1, so a 4-year window needs D + 4 <= LAST_FULL_SEASON.
OUTCOME_YEARS = 4
FIRST_DRAFT = 2010
LAST_LABELED_DRAFT = LAST_FULL_SEASON - OUTCOME_YEARS

# Torvik labels college seasons by the year they end, same as B-Ref.
FIRST_COLLEGE_SEASON = 2010

# Politeness: Basketball-Reference asks for < 20 requests / minute.
BREF_DELAY_SECONDS = 3.6
USER_AGENT = "rosterfit/0.1 (open-source NBA research project)"

RANDOM_STATE = 42
