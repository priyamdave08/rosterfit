"""Roster-move evaluation: drafts, free-agent signings and trades all reduce to
"add these players, remove those players, re-optimise the lineups".

Metrics returned for each move
------------------------------
ceiling_delta    change in the team's best-lineup net rating
depth_delta      change in the average of the top-10 lineups (rotation quality)
best_with        best net rating of any lineup that includes the candidate
displaces        who the candidate replaces in the best lineup
synergy          how much more the candidate helps THIS team than he helps the
                 median NBA team (fit, not just talent)
fit_score        0-100 logistic transform of (best_with - current best + synergy)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from rosterfit.engine.context import Context
from rosterfit.engine.optimizer import realistic, score_lineups
from rosterfit.features.lineups import lineup_features
from rosterfit.features.players import PROFILE_COLS

FIT_SCALE = 1.5  # net-rating points that move fit_score from 50 to ~73


@dataclass
class MoveResult:
    team: str
    incoming: list[str]
    outgoing: list[str]
    before_best: float
    after_best: float
    before_depth: float
    after_depth: float
    best_with: dict[str, float] = field(default_factory=dict)
    displaces: dict[str, str] = field(default_factory=dict)
    synergy: dict[str, float] = field(default_factory=dict)
    lineups_before: pd.DataFrame | None = None
    lineups_after: pd.DataFrame | None = None

    @property
    def ceiling_delta(self) -> float:
        return self.after_best - self.before_best

    @property
    def depth_delta(self) -> float:
        return self.after_depth - self.before_depth

    def fit_score(self, pid: str) -> float:
        x = (self.best_with.get(pid, self.before_best) - self.before_best) + self.synergy.get(pid, 0.0)
        return float(100 / (1 + np.exp(-x / FIT_SCALE)))


def _depth(lineups: pd.DataFrame, k: int = 10) -> float:
    return float(lineups["net_rtg"].head(k).mean()) if len(lineups) else float("nan")


def _with_candidates(ctx: Context, team: str, incoming: list[pd.Series], outgoing: list[str]) -> pd.DataFrame:
    roster = ctx.team_roster(team).drop(index=[o for o in outgoing if o], errors="ignore")
    add = pd.DataFrame(incoming).set_index("player_id") if incoming else pd.DataFrame()
    if len(add):
        add["minutes_proxy"] = 1e9  # always in the evaluation pool
    return pd.concat([roster, add]) if len(add) else roster


def league_replacement_gain(ctx: Context, cand: pd.Series, teams: list[str] | None = None) -> np.ndarray:
    """Net-rating gain from inserting ``cand`` into each team's current best lineup,
    replacing whichever starter it helps most to replace."""
    teams = teams or sorted(ctx.rosters["team_abbr"].unique())
    options, owner, base = [], [], {}
    cand_row = cand[PROFILE_COLS].astype(float).to_frame().T
    for t in teams:
        best = best_lineups(ctx, t, top=1)
        if best.empty:
            continue
        ids = best.iloc[0]["player_ids"]
        five = ctx.players.loc[ids, PROFILE_COLS].astype(float)
        base[t] = best.iloc[0]["net_rtg"]
        for out_id in ids:
            trial = pd.concat([five.drop(index=out_id), cand_row])
            if realistic(trial):
                options.append(lineup_features(trial.reset_index(drop=True)))
                owner.append(t)
    if not options:
        return np.array([])
    pred = ctx.lineup_model.predict_frame(pd.DataFrame(options))["net_rtg"]  # one batched call
    best_after = pred.groupby(np.array(owner)).max()
    return np.array([best_after[t] - base[t] for t in best_after.index])


_BEST_CACHE: dict[tuple, pd.DataFrame] = {}


def best_lineups(ctx: Context, team: str, top: int = 25) -> pd.DataFrame:
    key = (id(ctx), team)
    if key not in _BEST_CACHE:
        _BEST_CACHE[key] = score_lineups(ctx.lineup_model, ctx.team_roster(team), top=None)
    return _BEST_CACHE[key].head(top)


def evaluate_move(ctx: Context, team: str, incoming: list[pd.Series], outgoing: list[str] | None = None,
                  with_synergy: bool = True) -> MoveResult:
    outgoing = outgoing or []
    before = best_lineups(ctx, team, top=None)
    pool = _with_candidates(ctx, team, incoming, outgoing)
    after = score_lineups(ctx.lineup_model, pool, top=None, pool_size=11 + len(incoming))

    res = MoveResult(team=team, incoming=[c["player_id"] for c in incoming], outgoing=outgoing,
                     before_best=float(before["net_rtg"].iloc[0]), after_best=float(after["net_rtg"].iloc[0]),
                     before_depth=_depth(before), after_depth=_depth(after),
                     lineups_before=before.head(25), lineups_after=after.head(25))
    before_ids = set(before.iloc[0]["player_ids"])
    league_median = None
    for cand in incoming:
        pid = cand["player_id"]
        with_c = after[after["player_ids"].map(lambda ids, p=pid: p in ids)]
        if len(with_c):
            res.best_with[pid] = float(with_c["net_rtg"].iloc[0])
            gone = before_ids - set(with_c.iloc[0]["player_ids"])
            res.displaces[pid] = ", ".join(ctx.players.loc[list(gone), "player"]) if gone else "-"
        if with_synergy:
            team_gain = res.best_with.get(pid, res.before_best) - res.before_best
            league = league_replacement_gain(ctx, cand)
            league_median = float(np.median(league)) if len(league) else 0.0
            res.synergy[pid] = team_gain - league_median
    return res


def compare_candidates(ctx: Context, team: str, candidates: list[pd.Series], talent_weight: float = 0.65,
                       with_synergy: bool = True) -> pd.DataFrame:
    """Rank candidates (prospects, free agents, trade targets) for one team."""
    rows = []
    for cand in candidates:
        res = evaluate_move(ctx, team, [cand], with_synergy=with_synergy)
        pid = cand["player_id"]
        row = {"player": cand["player"], "player_id": pid, "source": cand.get("source"),
               "best_lineup_with": res.best_with.get(pid, np.nan),
               "gain_vs_current_best": res.best_with.get(pid, res.before_best) - res.before_best,
               "ceiling_delta": res.ceiling_delta, "depth_delta": res.depth_delta,
               "synergy": res.synergy.get(pid, np.nan), "displaces": res.displaces.get(pid, "-"),
               "fit_score": res.fit_score(pid)}
        if str(pid).startswith("prospect:"):
            p = ctx.prospects.loc[int(str(pid).split(":")[1])]
            row.update(grade=p["grade"], grade_score=p["grade_score"], bust_prob=p["bust_prob"],
                       hit_prob=p["hit_prob"], expected_vorp_4yr=p["expected_vorp_4yr"])
            row["board_score"] = talent_weight * p["grade_score"] + (1 - talent_weight) * row["fit_score"]
        else:
            row["board_score"] = row["fit_score"]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("board_score", ascending=False).reset_index(drop=True)
