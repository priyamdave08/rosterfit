"""NBA player profiles: the per-player stat vector every model consumes.

Profiles are *regularised*: rate stats are shrunk toward the positional mean in
proportion to how few minutes a player has logged (pseudo-minute prior), and
3P% is shrunk with an empirical-Bayes beta prior on attempts. That keeps a
rookie who went 6-for-9 from three in October from looking like Klay Thompson.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from rosterfit import config
from rosterfit.db.warehouse import query
from rosterfit.features.shrinkage import fit_beta_prior

# The canonical profile vector, in order.
PROFILE_COLS = [
    "bpm", "obpm", "dbpm", "ts_pct", "usg_pct", "ast_pct", "tov_pct", "orb_pct", "drb_pct",
    "trb_pct", "stl_pct", "blk_pct", "fg3a_rate", "fta_rate", "fg3_pct_eb", "fg3a_per_poss",
    "rim_freq", "rim_fg", "mid_freq", "corner3_share", "off_rtg", "def_rtg", "pos_num",
]

PSEUDO_MINUTES = 400.0


def _raw(season_filter: str, params: list) -> pd.DataFrame:
    return query(f"""
        SELECT season, player_id, player, name_key, team_id, age, pos, pos_num, g, mp,
               bpm, obpm, dbpm, ts_pct, usg_pct, ast_pct, tov_pct, orb_pct, drb_pct, trb_pct,
               stl_pct, blk_pct, fg3a_per_fga_pct AS fg3a_rate, fta_per_fga_pct AS fta_rate,
               fg3_pct, est_fg3a, fg3a_per_poss, pct_fga_00_03 AS rim_freq, fg_pct_00_03 AS rim_fg,
               coalesce(pct_fga_10_16, 0) + coalesce(pct_fga_16_xx, 0) AS mid_freq,
               pct_fg3a_corner3 AS corner3_share, off_rtg, def_rtg, vorp, ws_per_48,
               pct_fga_00_03, pct_fga_03_10, pct_fga_10_16, pct_fga_16_xx, pct_fga_fg3a,
               fg_pct_00_03, fg_pct_03_10, fg_pct_10_16, fg_pct_16_xx, fg_pct_fg3a,
               fg_pct_corner3, pct_fga_dunk, avg_dist, fga_per_poss
        FROM mart_player_season WHERE {season_filter}
    """, params)


def regularise(df: pd.DataFrame, pseudo_minutes: float = PSEUDO_MINUTES) -> pd.DataFrame:
    """Shrink rate stats toward positional means, weighted by minutes played."""
    df = df.copy()
    df["pos_bucket"] = df["pos_num"].round().clip(1, 5)
    rate_cols = [c for c in PROFILE_COLS if c not in ("pos_num", "fg3_pct_eb")]

    # 3P% via beta-binomial on (estimated) attempts.
    makes = df["fg3_pct"].fillna(0) * df["est_fg3a"].fillna(0)
    prior = fit_beta_prior(makes, df["est_fg3a"].fillna(0), min_attempts=50)
    df["fg3_pct_eb"] = prior.posterior_mean(makes, df["est_fg3a"].fillna(0))

    w = df["mp"].fillna(0).to_numpy()
    for col in rate_cols:
        ok = df[col].notna()
        means = {b: np.average(g.loc[ok, col], weights=g.loc[ok, "mp"].fillna(0) + 1e-9)
                 for b, g in df[ok].groupby("pos_bucket")}
        fallback = np.average(df.loc[ok, col], weights=df.loc[ok, "mp"].fillna(0) + 1e-9)
        pos_mean = df["pos_bucket"].map(means).fillna(fallback).to_numpy()
        x = df[col].fillna(pd.Series(pos_mean, index=df.index)).to_numpy()
        df[col] = (w * x + pseudo_minutes * pos_mean) / (w + pseudo_minutes)
    return df.drop(columns="pos_bucket")


def season_profiles(season: int) -> pd.DataFrame:
    return regularise(_raw("season = ?", [season]))


def current_profiles(recent_weight: float = 1.5) -> pd.DataFrame:
    """Blend last full season with the in-progress season, minutes-weighted.

    The in-progress season gets ``recent_weight`` x credit per minute so that a
    player's current role and form count for more than last year's.
    """
    raw = _raw("season IN (?, ?)", [config.LAST_FULL_SEASON, config.CURRENT_SEASON])
    if raw.empty:
        raise RuntimeError("no player data for the current window")
    raw["w"] = raw["mp"].fillna(0) * np.where(raw["season"] == config.CURRENT_SEASON, recent_weight, 1.0)
    num_cols = [c for c in raw.columns if raw[c].dtype.kind in "fi"
                and c not in ("season", "w", "mp", "g", "age")]

    def blend(g: pd.DataFrame) -> pd.Series:
        wts = g["w"].to_numpy() + 1e-9
        out = {c: np.average(g[c].fillna(g[c].mean() if g[c].notna().any() else 0), weights=wts)
               for c in num_cols}
        latest = g.sort_values("season").iloc[-1]
        out["est_fg3a"] = g["est_fg3a"].fillna(0).sum()  # volumes add, rates average
        out.update(player=latest["player"], name_key=latest["name_key"], team_id=latest["team_id"],
                   pos=latest["pos"], age=latest["age"], mp=g["mp"].sum(),
                   mp_current=g.loc[g["season"] == config.CURRENT_SEASON, "mp"].sum(),
                   season=latest["season"])
        return pd.Series(out)

    blended = raw.groupby("player_id").apply(blend, include_groups=False).reset_index()
    return regularise(blended)
