import numpy as np
import pandas as pd

from rosterfit.models.prospect_model import fit_trajectories, letter, name_trajectory, tier_labels


def test_grade_scale_is_monotone():
    grades = [letter(x) for x in (99, 93, 88, 81, 71, 61, 51, 41, 31, 16, 5)]
    assert grades == ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]


def test_trajectory_naming_rules():
    assert name_trajectory(vorp4=-0.1, mp_total=200, mp_y4=0) == "Washout"
    assert name_trajectory(vorp4=-0.4, mp_total=1500, mp_y4=50) == "Flameout"
    assert name_trajectory(vorp4=7.0, mp_total=8000, mp_y4=2200) == "Star"
    assert name_trajectory(vorp4=2.5, mp_total=6000, mp_y4=1700) == "Starter"
    assert name_trajectory(vorp4=-0.5, mp_total=5000, mp_y4=1100) == "Empty Minutes"


def _synthetic_draft(n=120, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        kind = i % 3
        if kind == 0:     # washouts
            vorp, mp = [0.0, 0.0, 0.0, 0.0], [100, 20, 0, 0]
        elif kind == 1:   # starters
            vorp, mp = [0.5, 1.0, 1.2, 1.5], [1200, 1700, 1900, 2000]
        else:             # stars
            vorp, mp = [1.5, 2.5, 3.0, 3.5], [2000, 2500, 2600, 2700]
        vorp = list(np.array(vorp) + rng.normal(0, 0.15, 4))
        mp = list(np.clip(np.array(mp) + rng.normal(0, 60, 4), 0, None))
        rows.append({**{f"vorp_{k + 1}": vorp[k] for k in range(4)}, **{f"mp_{k + 1}": mp[k] for k in range(4)},
                     "vorp_4yr": sum(vorp), "mp_4yr": sum(mp)})
    return pd.DataFrame(rows)


def test_trajectory_mixture_recovers_ordered_groups():
    df = _synthetic_draft()
    gmm, meta = fit_trajectories(df, k_range=range(2, 5))
    assert meta["k"] == 3
    labels = tier_labels(gmm, meta, df)
    by_kind = pd.Series(labels).groupby(np.arange(len(df)) % 3).agg(lambda s: s.mode()[0])
    assert by_kind[0] < by_kind[1] < by_kind[2]          # washout < starter < star
    names = meta["names"]
    assert names[0] == "Washout" and names[-1] == "Star"
    assert meta["groups"][0]["bust"] and meta["groups"][-1]["hit"]
