"""Lineup efficiency model: predict offensive and defensive rating vs. league
average from the five players' *prior-season* profiles.

Training data
-------------
Public 5-man lineup data is paywalled, but a team-season is exactly the
minutes-weighted average of the lineups it played. So every team-season since
2011-12 becomes one training row: features = lineup_features(players, minutes
share), target = team ORtg / DRtg relative to league average that season.

Player features come from the PREVIOUS season, so the model is genuinely
predictive ("given what we know about these players, how will this group
perform?") rather than re-deriving a team's rating from its own box score.

Validation is leave-one-season-out (GroupKFold on season), so no season's
information leaks into its own prediction.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from rosterfit import config
from rosterfit.db.warehouse import query
from rosterfit.features.lineups import FEATURE_NAMES, lineup_features, sampled_lineup_features
from rosterfit.features.players import PROFILE_COLS, season_profiles
from rosterfit.models.registry import save, tracked_run

log = logging.getLogger("rosterfit.lineup")

TARGETS = ("off_rtg_rel", "def_rtg_rel")


def gradient_booster():
    """XGBoost when its native lib loads (Linux / brew libomp), else sklearn's HGB."""
    try:
        from xgboost import XGBRegressor

        return XGBRegressor(n_estimators=400, max_depth=3, learning_rate=0.03, subsample=0.8,
                            colsample_bytree=0.7, min_child_weight=5, reg_lambda=5.0,
                            random_state=config.RANDOM_STATE, n_jobs=2)
    except Exception:  # noqa: BLE001 - xgboost raises XGBoostError if libomp is missing
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.04, max_iter=400,
                                             min_samples_leaf=12, l2_regularization=2.0,
                                             random_state=config.RANDOM_STATE)


def replacement_profile(profiles: pd.DataFrame) -> pd.Series:
    """Fallback for players with no prior NBA season: a typical end-of-bench player."""
    bench = profiles[(profiles["mp"] > 150) & (profiles["mp"] < 900)]
    return bench[PROFILE_COLS].median()


def build_training_set() -> pd.DataFrame:
    stints = query("SELECT season, team_id, player_id, mp, pos_num FROM mart_player_team_season WHERE mp > 0")
    teams = query("SELECT season, team_abbr, off_rtg_rel, def_rtg_rel, net_rtg FROM mart_team_season")
    rows = []
    rng = np.random.default_rng(config.RANDOM_STATE)
    for season in range(config.FIRST_SEASON + 1, config.LAST_FULL_SEASON + 1):
        prior = season_profiles(season - 1).set_index("player_id")
        repl = replacement_profile(prior.reset_index())
        cur = stints[stints["season"] == season]
        for team, g in cur.groupby("team_id"):
            prof = prior.reindex(g["player_id"])[PROFILE_COLS]
            missing = prof.isna().all(axis=1).to_numpy()
            prof = prof.fillna(repl)
            # Position is a current-season fact; take it from this season's stint.
            prof["pos_num"] = g["pos_num"].to_numpy()
            feats = sampled_lineup_features(prof.reset_index(drop=True), g["mp"].to_numpy(), rng=rng)
            feats["avg_bpm_minutes_weighted"] = lineup_features(prof.reset_index(drop=True),
                                                                g["mp"].to_numpy())["avg_bpm"]
            feats.update(season=season, team=team, new_player_share=float(
                np.sum(g["mp"].to_numpy() * missing) / g["mp"].sum()))
            rows.append(feats)
    df = pd.DataFrame(rows).merge(teams, left_on=["season", "team"], right_on=["season", "team_abbr"])
    return df.drop(columns="team_abbr")


@dataclass
class LineupModel:
    models: dict[str, object] = field(default_factory=dict)
    feature_names: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    blend: dict[str, float] = field(default_factory=dict)  # weight on the GBM per target
    background: pd.DataFrame | None = None

    def _predict_target(self, t: str, X: pd.DataFrame) -> np.ndarray:
        ridge, gbm = self.models[t]
        w = self.blend[t]
        return (1 - w) * ridge.predict(X) + w * gbm.predict(X)

    def predict_frame(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X[self.feature_names]
        off = self._predict_target("off_rtg_rel", X)
        dfn = self._predict_target("def_rtg_rel", X)
        return pd.DataFrame({"off_rtg_rel": off, "def_rtg_rel": dfn, "net_rtg": off - dfn}, index=X.index)

    def predict_lineup(self, players: pd.DataFrame) -> dict[str, float]:
        f = lineup_features(players[PROFILE_COLS].reset_index(drop=True))
        X = pd.DataFrame([f])
        return {**self.predict_frame(X).iloc[0].to_dict(), "features": f}

    def explain(self, players: pd.DataFrame, top: int = 8) -> pd.DataFrame:
        """Ridge-component attribution of the net rating, per feature (exact for the
        linear part; it's what a coach can actually read)."""
        f = pd.DataFrame([lineup_features(players[PROFILE_COLS].reset_index(drop=True))])[self.feature_names]
        contrib = np.zeros(len(self.feature_names))
        for t, sign in (("off_rtg_rel", 1), ("def_rtg_rel", -1)):
            ridge = self.models[t][0]
            scaler, reg = ridge[0], ridge[-1]
            z = (f.to_numpy()[0] - scaler.mean_) / scaler.scale_
            contrib += sign * reg.coef_ * z
        out = pd.DataFrame({"feature": self.feature_names, "value": f.iloc[0].to_numpy(),
                            "net_impact": contrib})
        return out.reindex(out["net_impact"].abs().sort_values(ascending=False).index).head(top)


def _cv_predictions(model, X, y, groups) -> np.ndarray:
    pred = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=min(10, len(np.unique(groups)))).split(X, y, groups):
        m = clone(model).fit(X.iloc[tr], y.iloc[tr])
        pred[te] = m.predict(X.iloc[te])
    return pred


def train(df: pd.DataFrame | None = None) -> LineupModel:
    df = build_training_set() if df is None else df
    df.to_parquet(config.PROCESSED_DIR / "lineup_training.parquet", index=False)
    feats = [c for c in FEATURE_NAMES if c in df.columns]
    X, groups = df[feats], df["season"]
    lm = LineupModel(feature_names=feats, background=X.sample(min(100, len(X)), random_state=0))

    ridge_proto = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 3, 30)))
    gbm_proto = gradient_booster()
    with tracked_run("lineup_model") as log_run:
        metrics: dict[str, float] = {"n_team_seasons": len(df)}
        net_preds = {}
        for t in TARGETS:
            y = df[t]
            p_ridge = _cv_predictions(ridge_proto, X, y, groups)
            p_gbm = _cv_predictions(gbm_proto, X, y, groups)
            p_base = _cv_predictions(LinearRegression(), X[["avg_bpm"]], y, groups)
            # Choose blend weight on held-out predictions (grid search, 0 = pure ridge).
            grid = np.linspace(0, 1, 11)
            maes = [mean_absolute_error(y, (1 - w) * p_ridge + w * p_gbm) for w in grid]
            w = float(grid[int(np.argmin(maes))])
            lm.blend[t] = w
            blend_pred = (1 - w) * p_ridge + w * p_gbm
            net_preds[t] = (blend_pred, p_base)
            metrics.update({
                f"{t}_r2_blend": r2_score(y, blend_pred), f"{t}_mae_blend": mean_absolute_error(y, blend_pred),
                f"{t}_r2_ridge": r2_score(y, p_ridge), f"{t}_r2_gbm": r2_score(y, p_gbm),
                f"{t}_r2_bpm_baseline": r2_score(y, p_base), f"{t}_gbm_weight": w,
            })
            lm.models[t] = (clone(ridge_proto).fit(X, y), clone(gbm_proto).fit(X, y))

        net_true = df["off_rtg_rel"] - df["def_rtg_rel"]
        net_pred = net_preds["off_rtg_rel"][0] - net_preds["def_rtg_rel"][0]
        net_base = net_preds["off_rtg_rel"][1] - net_preds["def_rtg_rel"][1]
        metrics.update(net_r2=r2_score(net_true, net_pred), net_mae=mean_absolute_error(net_true, net_pred),
                       net_r2_bpm_baseline=r2_score(net_true, net_base),
                       net_mae_bpm_baseline=mean_absolute_error(net_true, net_base))
        lm.metrics = metrics
        log_run(params={"features": len(feats), "gbm": type(gbm_proto).__name__,
                        "validation": "leave-season-out GroupKFold"}, metrics=metrics)
    log.info("lineup model: %s", {k: round(v, 3) for k, v in metrics.items()})
    save("lineup_model", lm)
    return lm
