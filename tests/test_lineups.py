import numpy as np
import pandas as pd
import pytest

from rosterfit.engine.optimizer import realistic, score_lineups
from rosterfit.features.lineups import FEATURE_NAMES, lineup_features, sampled_lineup_features
from rosterfit.features.players import PROFILE_COLS


def test_feature_names_are_stable(roster):
    f = lineup_features(roster.iloc[:5])
    assert list(f) == FEATURE_NAMES
    assert all(np.isfinite(v) for v in f.values())


def test_usage_total_is_five_times_mean(roster):
    five = roster.iloc[:5]
    f = lineup_features(five)
    assert f["usage_total"] == pytest.approx(5 * five["usg_pct"].mean())


def test_counts_are_five_man_equivalents(roster):
    five = roster.iloc[:5]
    f = lineup_features(five)
    assert f["n_rim_protectors"] == pytest.approx(1.0)   # only the Rim Anchor
    assert f["n_bigs"] == pytest.approx(1.0)             # threshold 4.25: the PF (4.0) is not a "big"
    assert 0 <= f["n_shooters"] <= 5


def test_sampled_features_equal_lineup_features_for_five_players(roster):
    five = roster.iloc[:5][PROFILE_COLS]
    direct = lineup_features(five)
    sampled = sampled_lineup_features(five, np.ones(5) * 1000, n_samples=20)
    for k in ("avg_bpm", "usage_hhi", "n_shooters", "paint_clog"):
        assert sampled[k] == pytest.approx(direct[k])


def test_sampled_features_stay_on_lineup_scale(roster):
    """Team-season features must look like 5-man lineups (the training/serving contract)."""
    sampled = sampled_lineup_features(roster[PROFILE_COLS], roster["minutes_proxy"].to_numpy(), n_samples=200)
    assert 0.18 <= sampled["usage_hhi"] <= 0.30              # 5-player HHI, not a 7-player one
    assert 0 <= sampled["n_rim_protectors"] <= 5


def test_realistic_rejects_all_bigs(roster):
    bigs = pd.DataFrame([roster.iloc[4]] * 5)
    assert not realistic(bigs)
    assert realistic(roster.iloc[:5])


class BpmModel:
    """Stand-in model: net rating = 5 x average BPM."""

    def predict_frame(self, X):
        net = 5 * X["avg_bpm"].to_numpy()
        return pd.DataFrame({"off_rtg_rel": net / 2, "def_rtg_rel": -net / 2, "net_rtg": net}, index=X.index)


def test_optimizer_finds_best_talent_lineup(roster):
    out = score_lineups(BpmModel(), roster, top=3)
    best = set(out.iloc[0]["player_ids"])
    assert {"p0", "p4"} <= best            # the two best players start
    assert out["net_rtg"].is_monotonic_decreasing


def test_optimizer_respects_must_include(roster):
    out = score_lineups(BpmModel(), roster, must_include=["p6"], top=None)
    assert all("p6" in ids for ids in out["player_ids"])


def test_batch_features_match_per_lineup_exactly(roster):
    """The vectorised optimiser path must give bit-identical features to lineup_features."""
    from itertools import combinations

    from rosterfit.features.lineups import lineup_features_batch

    prof = roster[PROFILE_COLS].astype(float).reset_index(drop=True)
    combos = list(combinations(range(len(prof)), 5))
    batch = lineup_features_batch(prof.to_numpy()[np.array(combos)], PROFILE_COLS)
    for i, c in enumerate(combos):
        single = lineup_features(prof.iloc[list(c)].reset_index(drop=True))
        assert batch.iloc[i].to_dict() == pytest.approx(single, rel=0, abs=0, nan_ok=True)


def test_batch_threshold_boundary_matches(roster):
    """avg_pos landing exactly on 3.6 must be classified the same way by both paths."""
    from rosterfit.features.lineups import lineup_features_batch

    five = roster.iloc[:5][PROFILE_COLS].astype(float).reset_index(drop=True)
    five["pos_num"] = [3.4, 3.6, 3.7, 3.5, 3.8]            # mean is 3.6 up to float rounding
    single = lineup_features(five)
    batch = lineup_features_batch(five.to_numpy()[None], PROFILE_COLS).iloc[0]
    assert batch["too_big"] == single["too_big"]
    assert batch["avg_pos"] == single["avg_pos"]
