"""Lineup feature engineering.

A lineup is represented as a set of player profiles with floor-time weights
that sum to 1. For a 5-man lineup every weight is 0.2; for a team-season the
weights are each player's share of the team's minutes. Because a team-season is
literally the minutes-weighted average of the lineups it played, the same
features describe both, and team-seasons become (noisy but real) training data
for lineup efficiency.

Features fall into three groups:
  * talent    - weighted box-score impact (BPM/OBPM/DBPM, TS%, ...)
  * fit       - how well skills complement: spacing, usage balance, creation,
                rim protection, rebounding, size balance
  * conflict  - non-linear penalties: too many ball-dominant players, no shooting,
                no big, two non-shooters clogging the paint, etc.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Skill thresholds (NBA per-100 / percentage scale).
SHOOTER_3PA100 = 5.5        # 3PA per 100 possessions
SHOOTER_3P = 0.355          # shrunk 3P%
CREATOR_AST = 20.0          # AST%
CREATOR_USG = 21.0
RIM_PROTECTOR_BLK = 3.0     # BLK%
NON_SHOOTER_3PAR = 0.15     # 3PA / FGA
BIG_POS = 4.25

TALENT = ["bpm", "obpm", "dbpm", "ts_pct", "off_rtg", "def_rtg", "ast_pct", "tov_pct",
          "stl_pct", "blk_pct", "orb_pct", "drb_pct", "usg_pct", "fta_rate"]

FEATURE_NAMES: list[str] = []  # filled on first call (stable ordering)


def _wmean(x: np.ndarray, w: np.ndarray) -> float:
    return float(np.sum(x * w))


def lineup_features(players: pd.DataFrame, weights: np.ndarray | None = None) -> dict[str, float]:
    p = players
    n = len(p)
    w = np.full(n, 1.0 / n) if weights is None else np.asarray(weights, dtype=float)
    w = w / w.sum()
    col = lambda c: p[c].to_numpy(dtype=float)  # noqa: E731

    f: dict[str, float] = {f"avg_{c}": _wmean(col(c), w) for c in TALENT}

    # Five-man-equivalent counts (share of floor time x 5).
    shooter = (col("fg3a_per_poss") >= SHOOTER_3PA100) & (col("fg3_pct_eb") >= SHOOTER_3P)
    creator = (col("ast_pct") >= CREATOR_AST) & (col("usg_pct") >= CREATOR_USG)
    protector = col("blk_pct") >= RIM_PROTECTOR_BLK
    non_shooter = col("fg3a_rate") < NON_SHOOTER_3PAR
    big = col("pos_num") >= BIG_POS
    f["n_shooters"] = 5 * _wmean(shooter, w)
    f["n_creators"] = 5 * _wmean(creator, w)
    f["n_rim_protectors"] = 5 * _wmean(protector, w)
    f["n_non_shooters"] = 5 * _wmean(non_shooter, w)
    f["n_bigs"] = 5 * _wmean(big, w)
    # Star power and weak links (basketball is a "strong-link" sport, but a
    # defensive liability gets hunted every possession).
    f["n_stars"] = 5 * _wmean(col("bpm") >= 4.0, w)
    f["n_weak_links"] = 5 * _wmean(col("bpm") <= -2.0, w)
    f["n_high_usage"] = 5 * _wmean(col("usg_pct") >= 27.0, w)

    # Spacing: volume x accuracy above a replacement-level 30% from three.
    f["spacing_index"] = 5 * _wmean(col("fg3a_per_poss") * (col("fg3_pct_eb") - 0.30), w)
    f["avg_fg3a_rate"] = _wmean(col("fg3a_rate"), w)
    f["avg_corner3_share"] = _wmean(col("corner3_share"), w)
    f["avg_rim_freq"] = _wmean(col("rim_freq"), w)
    f["avg_rim_fg"] = _wmean(col("rim_fg"), w)
    f["avg_mid_freq"] = _wmean(col("mid_freq"), w)

    # Usage balance: a lineup consumes exactly 100% of possessions.
    usage_total = 5 * f["avg_usg_pct"]
    f["usage_total"] = usage_total
    f["usage_overload"] = max(0.0, usage_total - 105.0)
    f["usage_vacuum"] = max(0.0, 95.0 - usage_total)
    # Dispersion of usage (one star vs. by-committee). A weighted SD is on the same
    # scale for a 5-man lineup and a 15-man team-season; a Herfindahl index is not.
    usg = col("usg_pct")
    f["usage_sd"] = float(np.sqrt(_wmean((usg - f["avg_usg_pct"]) ** 2, w)))
    u = usg * w
    f["usage_hhi"] = float(np.sum((u / u.sum()) ** 2)) if u.sum() > 0 else 0.2
    # Efficiency of who actually takes the shots.
    f["usage_weighted_ts"] = float(np.sum(col("ts_pct") * u) / u.sum()) if u.sum() > 0 else f["avg_ts_pct"]

    # Size / position balance.
    pos = col("pos_num")
    f["avg_pos"] = _wmean(pos, w)
    f["pos_spread"] = float(np.sqrt(_wmean((pos - f["avg_pos"]) ** 2, w)))
    f["avg_trb_pct"] = _wmean(col("trb_pct"), w)

    # Interactions / conflicts.
    f["creator_x_spacing"] = min(f["n_creators"], 2.0) * f["spacing_index"]
    f["no_creator"] = float(f["n_creators"] < 0.5)
    f["no_rim_protector"] = float(f["n_rim_protectors"] < 0.5)
    f["paint_clog"] = max(0.0, f["n_non_shooters"] - 1.5)
    f["too_small"] = float(f["avg_pos"] < 2.4)
    f["too_big"] = float(f["avg_pos"] > 3.6)
    f["def_anchor_x_perimeter"] = min(f["n_rim_protectors"], 1.5) * f["avg_stl_pct"]

    if not FEATURE_NAMES:
        FEATURE_NAMES.extend(f.keys())
    return f


def sampled_lineup_features(players: pd.DataFrame, minutes: np.ndarray, n_samples: int = 150,
                            rng: np.random.Generator | None = None) -> dict[str, float]:
    """Expected 5-man lineup features for a team-season, by Monte Carlo.

    Draws ``n_samples`` five-man lineups (players sampled without replacement,
    weighted by minutes) and averages their features. Unlike evaluating the
    features on the team's minutes-weighted average player, this keeps every
    non-linear feature (usage concentration, paint congestion, 'no creator')
    on exactly the scale it has for a real lineup, so a model trained on
    team-seasons can be applied to individual lineups without extrapolating.
    """
    rng = rng or np.random.default_rng(0)
    m = np.asarray(minutes, dtype=float)
    keep = m > 0
    players, m = players[keep].reset_index(drop=True), m[keep]
    if len(players) <= 5:
        return lineup_features(players)
    p = m / m.sum()
    rows = [lineup_features(players.iloc[rng.choice(len(players), 5, replace=False, p=p)])
            for _ in range(n_samples)]
    return pd.DataFrame(rows).mean().to_dict()


def feature_frame(rows: list[dict[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows)[FEATURE_NAMES]


def _init_feature_names() -> None:
    from rosterfit.features.players import PROFILE_COLS

    lineup_features(pd.DataFrame({c: [1.0] * 5 for c in PROFILE_COLS}))


_init_feature_names()
