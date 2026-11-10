"""DuckDB warehouse: registers raw parquet extracts and builds SQL marts."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

from rosterfit import config

log = logging.getLogger("rosterfit.db")

RAW_TABLES = {
    "raw_advanced": "nba_advanced.parquet",
    "raw_per_poss": "nba_per_poss.parquet",
    "raw_shooting": "nba_shooting.parquet",
    "raw_team_ratings": "nba_team_ratings.parquet",
    "raw_drafts": "nba_drafts.parquet",
    "raw_college": "college_players.parquet",
    "raw_rosters": "rosters.parquet",
    "raw_teams": "teams.parquet",
}


@contextmanager
def connect(path: Path | str | None = None, read_only: bool = False):
    con = duckdb.connect(str(path or config.DB_PATH), read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def build(path: Path | str | None = None) -> None:
    """(Re)create raw tables from parquet and run every SQL file in order."""
    with connect(path) as con:
        for table, fname in RAW_TABLES.items():
            src = config.PROCESSED_DIR / fname
            if not src.exists():
                raise FileNotFoundError(f"{src} missing - run `rosterfit ingest` first")
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet(?)", [str(src)])
        for sql_file in sorted(config.SQL_DIR.glob("*.sql")):
            log.info("running %s", sql_file.name)
            con.execute(sql_file.read_text())
        for (t,) in con.execute("SELECT table_name FROM information_schema.tables "
                                "WHERE table_name LIKE 'mart_%' ORDER BY 1").fetchall():
            n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            log.info("%-28s %8d rows", t, n)


def query(sql: str, params: list | None = None, path: Path | str | None = None) -> pd.DataFrame:
    with connect(path, read_only=True) as con:
        return con.execute(sql, params or []).df()
