"""League-average reference values (for shot charts and percentiles)."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from rosterfit import config
from rosterfit.db.warehouse import query

ZONE_FG = ["fg_pct_00_03", "fg_pct_03_10", "fg_pct_10_16", "fg_pct_16_xx", "fg_pct_fg3a", "fg_pct_corner3",
           "pct_fg3a_corner3"]


@lru_cache(maxsize=4)
def nba_zone_averages(season: int = config.LAST_FULL_SEASON) -> pd.Series:
    """Attempt-weighted league FG% by zone (weights = estimated FGA from that zone)."""
    df = query("""
        SELECT *, fga_per_poss * est_poss / 100.0 AS est_fga FROM mart_player_season
        WHERE season = ? AND mp >= 200
    """, [season])
    out = {}
    zone_share = {"fg_pct_00_03": "pct_fga_00_03", "fg_pct_03_10": "pct_fga_03_10",
                  "fg_pct_10_16": "pct_fga_10_16", "fg_pct_16_xx": "pct_fga_16_xx", "fg_pct_fg3a": "pct_fga_fg3a"}
    for fg, share in zone_share.items():
        w = (df["est_fga"] * df[share]).fillna(0)
        ok = df[fg].notna() & (w > 0)
        out[fg] = float((df.loc[ok, fg] * w[ok]).sum() / w[ok].sum())
    w3 = (df["est_fga"] * df["pct_fga_fg3a"] * df["pct_fg3a_corner3"]).fillna(0)
    ok = df["fg_pct_corner3"].notna() & (w3 > 0)
    out["fg_pct_corner3"] = float((df.loc[ok, "fg_pct_corner3"] * w3[ok]).sum() / w3[ok].sum())
    w = (df["est_fga"] * df["pct_fga_fg3a"]).fillna(0)
    out["pct_fg3a_corner3"] = float((df["pct_fg3a_corner3"].fillna(0) * w).sum() / w.sum())
    return pd.Series(out)


@lru_cache(maxsize=1)
def college_zone_averages() -> dict[str, float]:
    from rosterfit.features.college import shooting_priors

    p = shooting_priors()
    return {"rim": p["rim_eb"].mean, "mid": p["mid_eb"].mean, "three": p["fg3_eb"].mean}
