"""Empirical-Bayes shrinkage of shooting percentages.

A college player who shoots 45% on 40 threes and one who shoots 38% on 250 are
not equally convincing. We fit a beta-binomial prior to the population by
maximum likelihood (scipy), then report each player's posterior mean:

    posterior = (makes + alpha) / (attempts + alpha + beta)

Small samples are pulled toward the population mean; large samples barely move.
This is the same idea as the Bayesian hierarchical models used in front-office
work, in its simplest closed form.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize, stats


@dataclass(frozen=True)
class BetaPrior:
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def strength(self) -> float:
        """Prior 'pseudo-attempts' - how many shots it takes to move off the mean."""
        return self.alpha + self.beta

    def posterior_mean(self, makes, attempts):
        makes = np.nan_to_num(np.asarray(makes, dtype=float))
        attempts = np.nan_to_num(np.asarray(attempts, dtype=float))
        return (makes + self.alpha) / (attempts + self.alpha + self.beta)

    def posterior_interval(self, makes, attempts, level: float = 0.8):
        makes = np.nan_to_num(np.asarray(makes, dtype=float))
        attempts = np.nan_to_num(np.asarray(attempts, dtype=float))
        a, b = makes + self.alpha, attempts - makes + self.beta
        lo, hi = (1 - level) / 2, 1 - (1 - level) / 2
        return stats.beta.ppf(lo, a, b), stats.beta.ppf(hi, a, b)


def fit_beta_prior(makes, attempts, min_attempts: int = 1) -> BetaPrior:
    """MLE of a beta-binomial prior over (makes, attempts) pairs."""
    m = np.asarray(makes, dtype=float)
    n = np.asarray(attempts, dtype=float)
    ok = np.isfinite(m) & np.isfinite(n) & (n >= min_attempts) & (m <= n)
    m, n = m[ok].round(), n[ok].round()
    if len(m) < 10:
        raise ValueError("need at least 10 players to fit a prior")

    p = m.sum() / n.sum()  # method-of-moments start

    def nll(log_params):
        a, b = np.exp(log_params)
        return -stats.betabinom.logpmf(m, n, a, b).sum()

    res = optimize.minimize(nll, x0=np.log([p * 20, (1 - p) * 20]), method="Nelder-Mead")
    a, b = np.exp(res.x)
    return BetaPrior(float(a), float(b))


def shrink(df: pd.DataFrame, makes: str, attempts: str, out: str, prior: BetaPrior | None = None,
           min_attempts: int = 10) -> tuple[pd.DataFrame, BetaPrior]:
    prior = prior or fit_beta_prior(df[makes], df[attempts], min_attempts=min_attempts)
    df = df.copy()
    df[out] = prior.posterior_mean(df[makes], df[attempts])
    return df, prior
