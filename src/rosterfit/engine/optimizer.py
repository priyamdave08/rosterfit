"""Lineup search: score every 5-man combination from a rotation pool."""
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from rosterfit.features.lineups import lineup_features_batch, realistic_mask
from rosterfit.features.players import PROFILE_COLS
from rosterfit.models.lineup_model import LineupModel


def realistic(players: pd.DataFrame) -> bool:
    """Basketball sanity: someone who can bring the ball up, someone with size."""
    pos = players["pos_num"].to_numpy(dtype=float)
    return bool(realistic_mask(pos[None, :])[0])


def score_lineups(model: LineupModel, pool: pd.DataFrame, must_include: list[str] | None = None,
                  pool_size: int = 11, top: int | None = 25, enforce_realism: bool = True) -> pd.DataFrame:
    """Enumerate C(pool_size, 5) lineups (always including ``must_include``) and rank by net rating."""
    must = [m for m in (must_include or []) if m in pool.index]
    rest = pool.drop(index=must).sort_values("minutes_proxy", ascending=False)
    rest = rest.head(max(0, pool_size - len(must)))
    candidates = list(rest.index)

    # All combinations as one (n_lineups, 5, n_stats) array: features and the realism
    # filter are computed in a few vectorised operations rather than one DataFrame each.
    order = must + candidates
    mat = pool.loc[order, PROFILE_COLS].to_numpy(dtype=float)
    k = len(must)
    combos = np.array([list(range(k)) + [k + i for i in c]
                       for c in combinations(range(len(candidates)), 5 - k)], dtype=int).reshape(-1, 5)
    if not len(combos):
        return pd.DataFrame()
    P = mat[combos]
    if enforce_realism:
        keep = realistic_mask(P[:, :, PROFILE_COLS.index("pos_num")])
        combos, P = combos[keep], P[keep]
    if not len(combos):
        return pd.DataFrame()
    members = [[order[i] for i in row] for row in combos]

    X = lineup_features_batch(P, PROFILE_COLS)
    pred = model.predict_frame(X)
    out = pd.concat([pred, X[["n_shooters", "n_creators", "n_rim_protectors", "spacing_index",
                              "usage_total", "avg_pos"]]], axis=1)
    out["player_ids"] = members
    names = pool["player"].astype(str).to_dict()
    out["players"] = [", ".join(names[pid] for pid in m) for m in members]
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
