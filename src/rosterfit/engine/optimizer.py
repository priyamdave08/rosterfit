"""Lineup search: score every 5-man combination from a rotation pool."""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from rosterfit.features.lineups import lineup_features
from rosterfit.features.players import PROFILE_COLS
from rosterfit.models.lineup_model import LineupModel


def realistic(players: pd.DataFrame) -> bool:
    """Basketball sanity: someone who can bring the ball up, someone with size."""
    pos = players["pos_num"].to_numpy()
    return pos.min() <= 2.6 and pos.max() >= 3.9 and 2.2 <= pos.mean() <= 3.8


def score_lineups(model: LineupModel, pool: pd.DataFrame, must_include: list[str] | None = None,
                  pool_size: int = 11, top: int | None = 25, enforce_realism: bool = True) -> pd.DataFrame:
    """Enumerate C(pool_size, 5) lineups (always including ``must_include``) and rank by net rating."""
    must = [m for m in (must_include or []) if m in pool.index]
    rest = pool.drop(index=must).sort_values("minutes_proxy", ascending=False)
    rest = rest.head(max(0, pool_size - len(must)))
    candidates = list(rest.index)

    rows, members = [], []
    for combo in combinations(candidates, 5 - len(must)):
        ids = must + list(combo)
        five = pool.loc[ids]
        if enforce_realism and not realistic(five):
            continue
        rows.append(lineup_features(five[PROFILE_COLS].reset_index(drop=True)))
        members.append(ids)
    if not rows:
        return pd.DataFrame()

    X = pd.DataFrame(rows)
    pred = model.predict_frame(X)
    out = pd.concat([pred, X[["n_shooters", "n_creators", "n_rim_protectors", "spacing_index",
                              "usage_total", "avg_pos"]]], axis=1)
    out["player_ids"] = members
    out["players"] = [", ".join(pool.loc[m, "player"]) for m in members]
    out = out.sort_values("net_rtg", ascending=False).reset_index(drop=True)
    out.index += 1
    out.index.name = "rank"
    return out.head(top) if top else out


def lineup_breakdown(model: LineupModel, five: pd.DataFrame) -> dict:
    pred = model.predict_lineup(five)
    pred["explain"] = model.explain(five)
    return pred


def percentile_vs_league(net: float, league_best: np.ndarray) -> float:
    return float((league_best < net).mean() * 100)
