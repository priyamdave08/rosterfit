import numpy as np
import pytest

from rosterfit.features.shrinkage import BetaPrior, fit_beta_prior


def test_fit_recovers_population_mean():
    rng = np.random.default_rng(0)
    true_p = rng.beta(36, 64, size=3000)            # population mean 0.36
    attempts = rng.integers(20, 400, size=3000)
    makes = rng.binomial(attempts, true_p)
    prior = fit_beta_prior(makes, attempts)
    assert prior.mean == pytest.approx(0.36, abs=0.01)
    assert 40 < prior.strength < 200                # true strength is 100


def test_small_samples_shrink_more_than_large():
    prior = BetaPrior(36, 64)
    hot_small = prior.posterior_mean(9, 15)         # 60% on 15 attempts
    hot_large = prior.posterior_mean(240, 400)      # 60% on 400 attempts
    assert prior.mean < hot_small < hot_large < 0.6


def test_interval_narrows_with_volume():
    prior = BetaPrior(36, 64)
    lo1, hi1 = prior.posterior_interval(10, 25)
    lo2, hi2 = prior.posterior_interval(160, 400)
    assert (hi2 - lo2) < (hi1 - lo1)


def test_requires_enough_players():
    with pytest.raises(ValueError):
        fit_beta_prior([1, 2], [5, 5])
