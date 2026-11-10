"""Player archetypes via Gaussian mixture models (BIC-selected).

Positions (PG..C) describe size, not role. A finite mixture over style
features (where a player shoots from, how much he creates, rebounds, protects
the rim) recovers roles like 'stretch big' or 'movement shooter' from data.
Number of components is chosen by BIC, the same model-selection criterion used
in group-based trajectory modelling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from rosterfit.config import RANDOM_STATE

STYLE_COLS = ["usg_pct", "ast_pct", "fg3a_rate", "rim_freq", "mid_freq", "corner3_share",
              "orb_pct", "drb_pct", "blk_pct", "stl_pct", "fta_rate", "pos_num"]


def fit_archetypes(profiles: pd.DataFrame, k_range=range(6, 11), min_minutes: float = 800) -> tuple[Pipeline, dict]:
    df = profiles[profiles["mp"] >= min_minutes]
    X = df[STYLE_COLS].to_numpy()
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    best, bics = None, {}
    for k in k_range:
        gm = GaussianMixture(k, covariance_type="full", n_init=4, random_state=RANDOM_STATE).fit(Xs)
        bics[k] = gm.bic(Xs)
        if best is None or bics[k] < bics[best.n_components]:
            best = gm
    pipe = Pipeline([("scale", scaler), ("gmm", best)])
    centroids = pd.DataFrame(scaler.inverse_transform(best.means_), columns=STYLE_COLS)
    names = name_clusters(centroids)
    return pipe, {"bic": bics, "k": best.n_components, "names": names, "centroids": centroids}


def name_clusters(c: pd.DataFrame) -> dict[int, str]:
    """Human-readable labels from centroid characteristics (z-scored vs. other centroids)."""
    z = (c - c.mean()) / c.std(ddof=0).replace(0, 1)
    names: dict[int, str] = {}
    for i, r in z.iterrows():
        raw = c.loc[i]
        if raw.pos_num >= 4.2:
            if r.fg3a_rate > 0.3:
                label = "Stretch Big"
            elif r.ast_pct > 0.3 or r.usg_pct > 0.5:
                label = "Playmaking Big"
            elif r.blk_pct > 0.5 and r.rim_freq > 0.3:
                label = "Rim-Running Anchor"
            else:
                label = "Interior Big"
        elif r.usg_pct > 0.8 and r.ast_pct > 0.5:
            label = "Primary Creator"
        elif r.ast_pct > 0.8:
            label = "Floor General"
        elif raw.pos_num <= 2.4:
            label = "Off-Ball Guard"
        elif r.usg_pct > 0.6:
            label = "Scoring Wing" if raw.pos_num >= 2.5 else "Scoring Guard"
        elif r.fg3a_rate > 0.6 and r.corner3_share > 0.2:
            label = "Spot-Up Shooter"
        elif r.fg3a_rate > 0.4:
            label = "3-and-D Wing" if r.stl_pct > 0 else "Movement Shooter"
        elif r.rim_freq > 0.4:
            label = "Slashing Wing"
        else:
            label = "Versatile Forward" if raw.pos_num >= 3 else "Combo Guard"
        names[int(i)] = label
    # De-duplicate (two clusters can earn the same label).
    seen: dict[str, int] = {}
    for i in sorted(names):
        base = names[i]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            names[i] = f"{base} ({'I' * seen[base]})"
    return names


def assign(pipe: Pipeline, names: dict[int, str], profiles: pd.DataFrame) -> pd.DataFrame:
    X = profiles[STYLE_COLS].to_numpy()
    proba = pipe.predict_proba(X)
    out = profiles[[]].copy()
    out["archetype_id"] = proba.argmax(1)
    out["archetype"] = out["archetype_id"].map(names)
    out["archetype_conf"] = proba.max(1)
    out["archetype_entropy"] = -(proba * np.log(proba + 1e-12)).sum(1)  # versatility
    return out


def assign_nearest(pipe: Pipeline, names: dict[int, str], profiles: pd.DataFrame) -> pd.DataFrame:
    """Nearest-centroid assignment in standardised space.

    Used for *projected* profiles (college prospects): model translations are
    shrunk toward the mean, so they often sit between clusters where a
    full-covariance likelihood is dominated by whichever component has the
    widest tails. Distance to the centroid is the more faithful read.
    """
    scaler, gmm = pipe[0], pipe[-1]
    z = scaler.transform(profiles[STYLE_COLS].to_numpy())
    d = ((z[:, None, :] - gmm.means_[None, :, :]) ** 2).sum(-1)
    out = profiles[[]].copy()
    out["archetype_id"] = d.argmin(1)
    out["archetype"] = out["archetype_id"].map(names)
    w = np.exp(-0.5 * (d - d.min(1, keepdims=True)))
    out["archetype_conf"] = (w.max(1) / w.sum(1))
    out["archetype_entropy"] = 0.0
    return out
