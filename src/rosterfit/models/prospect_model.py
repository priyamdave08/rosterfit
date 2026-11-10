"""Prospect evaluation: will this college player pan out?

Trained on every drafted college player from 2010 through the last draft with
four completed NBA seasons.

1. **Outcome trajectories (latent classes).** Rather than hand-picking a "bust"
   threshold, a group-based finite mixture model is fit to each draftee's
   four-season trajectory of value (VORP) and playing time. The BIC-selected
   mixture recovers trajectory *shapes*: players who never stuck, players who
   got chances and flamed out, empty-minutes players, slow builders, starters
   and stars. Groups are named from their mean trajectories.

       bust = any group that is (on average) out of the league by year 4
       hit  = any group averaging >= 1.5 VORP over four seasons

2. **Outcome models (college stats only).** P(bust), P(hit), P(each trajectory)
   and expected 4-year VORP, each a blend of a regularised linear model and
   gradient boosting, blend weight chosen on held-out folds. Validation is
   leave-one-draft-class-out and is reported against (a) a draft-slot-only
   baseline and (b) stats + draft slot, to show what college stats add beyond
   the consensus.

3. **NBA translation.** College stats -> early-career NBA profile (the vector
   the lineup model uses), so a prospect can be dropped into any lineup.

Plus nearest-neighbour historical comps and SHAP explanations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from rosterfit import config
from rosterfit.db.warehouse import query
from rosterfit.features import college
from rosterfit.features.players import PROFILE_COLS
from rosterfit.models.registry import save, tracked_run

log = logging.getLogger("rosterfit.prospect")

GRADE_SCALE = [(97, "A+"), (92, "A"), (87, "A-"), (80, "B+"), (70, "B"), (60, "B-"),
               (50, "C+"), (40, "C"), (30, "C-"), (15, "D"), (0, "F")]
HIT_VORP = 1.5
OUT_OF_LEAGUE_MP = 300


def letter(pct: float) -> str:
    return next(g for cut, g in GRADE_SCALE if pct >= cut)


# --------------------------------------------------------------------------- trajectories
def trajectory_matrix(df: pd.DataFrame) -> np.ndarray:
    vorp = df[[f"vorp_{i}" for i in range(1, 5)]].fillna(0).to_numpy()
    mp = df[[f"mp_{i}" for i in range(1, 5)]].fillna(0).to_numpy() / 1000.0
    return np.hstack([vorp, mp])


def name_trajectory(vorp4: float, mp_total: float, mp_y4: float) -> str:
    if mp_y4 < OUT_OF_LEAGUE_MP:
        return "Washout" if mp_total < 1000 else "Flameout"
    if vorp4 >= 5:
        return "Star"
    if vorp4 >= HIT_VORP:
        return "Starter"
    if mp_total >= 4000 and vorp4 < 0:
        return "Empty Minutes"
    return "Slow Build" if mp_y4 > mp_total / 4 else "Rotation"


def fit_trajectories(df: pd.DataFrame, k_range=range(3, 8)) -> tuple[GaussianMixture, dict]:
    X = trajectory_matrix(df)
    fits = {k: GaussianMixture(k, covariance_type="full", n_init=8, reg_covar=1e-3,
                               random_state=config.RANDOM_STATE).fit(X) for k in k_range}
    bic = {k: m.bic(X) for k, m in fits.items()}
    k = min(bic, key=bic.get)
    gmm = fits[k]
    raw = gmm.predict(X)
    groups = []
    for c in range(k):
        m = df[raw == c]
        groups.append({"component": c, "n": len(m), "vorp4": m["vorp_4yr"].mean(), "mp": m["mp_4yr"].mean(),
                       "mp4": m["mp_4"].fillna(0).mean(),
                       "mean_vorp_path": m[[f"vorp_{i}" for i in range(1, 5)]].fillna(0).mean().tolist(),
                       "mean_mp_path": m[[f"mp_{i}" for i in range(1, 5)]].fillna(0).mean().tolist()})
    groups = sorted(groups, key=lambda g: g["vorp4"])
    seen: dict[str, int] = {}
    for g in groups:
        name = name_trajectory(g["vorp4"], g["mp"], g["mp4"])
        seen[name] = seen.get(name, 0) + 1
        g["name"] = name if seen[name] == 1 else f"{name} {seen[name]}"
        g["bust"] = g["mp4"] < OUT_OF_LEAGUE_MP
        g["hit"] = g["vorp4"] >= HIT_VORP
    order = [g["component"] for g in groups]
    return gmm, {"bic": bic, "k": k, "order": order, "groups": groups, "names": [g["name"] for g in groups]}


def tier_labels(gmm: GaussianMixture, meta: dict, df: pd.DataFrame) -> np.ndarray:
    rank = {c: i for i, c in enumerate(meta["order"])}
    return np.array([rank[int(c)] for c in gmm.predict(trajectory_matrix(df))])


# --------------------------------------------------------------------------- model bundle
@dataclass
class ProspectModel:
    features: list[str]
    tier_names: list[str]
    groups: list[dict]
    models: dict = field(default_factory=dict)      # task -> (linear, gbm, weight)
    ev_reference: np.ndarray | None = None
    translator: object = None
    translate_targets: list[str] = field(default_factory=list)
    comps_index: object = None
    comps_scaler: object = None
    comps_table: pd.DataFrame | None = None
    draft_model: object = None
    metrics: dict = field(default_factory=dict)
    background: pd.DataFrame | None = None

    def _blend(self, task: str, X: pd.DataFrame) -> np.ndarray:
        lin, gbm, w = self.models[task]
        if task == "ev":
            return (1 - w) * lin.predict(X) + w * gbm.predict(X)
        if task == "tiers":
            return (1 - w) * _proba(lin, X, len(self.tier_names)) + w * _proba(gbm, X, len(self.tier_names))
        return (1 - w) * lin.predict_proba(X)[:, 1] + w * gbm.predict_proba(X)[:, 1]

    def expected_value(self, X: pd.DataFrame) -> np.ndarray:
        return self._blend("ev", X[self.features])

    def grade(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df[self.features]
        ev = self._blend("ev", X)
        pct = np.searchsorted(np.sort(self.ev_reference), ev) / len(self.ev_reference) * 100
        out = pd.DataFrame(index=df.index)
        out["bust_prob"] = self._blend("bust", X)
        out["hit_prob"] = self._blend("hit", X)
        tiers = self._blend("tiers", X)
        for i, name in enumerate(self.tier_names):
            out[f"p_{name.lower().replace(' ', '_')}"] = tiers[:, i]
        out["likeliest_path"] = [self.tier_names[i] for i in tiers.argmax(1)]
        out["expected_vorp_4yr"] = ev
        out["grade_score"] = pct.round(1)
        out["grade"] = [letter(x) for x in pct]
        if self.draft_model is not None:
            out["draft_prob"] = self.draft_model.predict_proba(X)[:, 1]
        return out

    def translate(self, df: pd.DataFrame) -> pd.DataFrame:
        pred = self.translator.predict(df[self.features])
        out = pd.DataFrame(pred, columns=self.translate_targets, index=df.index)
        out["pos_num"] = out["pos_num"].clip(1, 5)
        for c in ("rim_freq", "mid_freq", "fg3a_rate", "corner3_share", "fg3_pct_eb", "ts_pct", "rim_fg"):
            out[c] = out[c].clip(0, 1)
        return out

    def comps(self, row: pd.DataFrame, k: int = 5) -> pd.DataFrame:
        z = self.comps_scaler.transform(row[self.features])
        dist, idx = self.comps_index.kneighbors(z, n_neighbors=k)
        out = self.comps_table.iloc[idx[0]].copy()
        out["similarity"] = (1 / (1 + dist[0] / np.sqrt(len(self.features)))).round(3)
        return out

    def explain(self, row: pd.DataFrame, top: int = 8) -> pd.DataFrame:
        """SHAP (permutation) attribution of expected 4-year VORP."""
        import shap

        f = lambda X: self.expected_value(pd.DataFrame(X, columns=self.features))  # noqa: E731
        explainer = shap.Explainer(f, self.background[self.features].to_numpy(), feature_names=self.features)
        sv = explainer(row[self.features].to_numpy(dtype=float), max_evals=2 * len(self.features) + 1)
        out = pd.DataFrame({"feature": self.features, "value": row[self.features].iloc[0].to_numpy(),
                            "impact_vorp": sv.values[0]})
        return out.reindex(out["impact_vorp"].abs().sort_values(ascending=False).index).head(top)


def _proba(model, X, k: int) -> np.ndarray:
    out = np.zeros((len(X), k))
    out[:, model.classes_] = model.predict_proba(X)
    return out


def _impute_scale(est):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), est)


def _gbm_clf():
    return make_pipeline(SimpleImputer(strategy="median"), HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.03, max_iter=250, min_samples_leaf=20, l2_regularization=2.0,
        random_state=config.RANDOM_STATE))


def _gbm_reg():
    return make_pipeline(SimpleImputer(strategy="median"), HistGradientBoostingRegressor(
        max_depth=3, learning_rate=0.03, max_iter=300, min_samples_leaf=20, l2_regularization=2.0,
        loss="absolute_error", random_state=config.RANDOM_STATE))


def _oof(model, X, y, groups, kind: str, k: int | None = None) -> np.ndarray:
    out = np.zeros((len(X), k)) if kind == "multi" else np.zeros(len(X))
    for tr, te in GroupKFold(n_splits=min(8, pd.Series(groups).nunique())).split(X, y, groups):
        m = clone(model).fit(X.iloc[tr], y.iloc[tr])
        if kind == "reg":
            out[te] = m.predict(X.iloc[te])
        elif kind == "bin":
            out[te] = m.predict_proba(X.iloc[te])[:, 1]
        else:
            out[te] = _proba(m, X.iloc[te], k)
    return out


def _best_weight(score_fn, a: np.ndarray, b: np.ndarray) -> float:
    grid = np.linspace(0, 1, 11)
    return float(grid[int(np.argmin([score_fn((1 - w) * a + w * b) for w in grid]))])


def _translation_targets() -> pd.DataFrame:
    """Minutes-weighted NBA profile over each draftee's first three seasons."""
    cols = ", ".join(f"sum({c} * mp) / sum(mp) AS {c}" for c in [
        "bpm", "obpm", "dbpm", "ts_pct", "usg_pct", "ast_pct", "tov_pct", "orb_pct", "drb_pct", "trb_pct",
        "stl_pct", "blk_pct", "fg3a_per_fga_pct", "fta_per_fga_pct", "fg3_pct", "fg3a_per_poss",
        "pct_fga_00_03", "fg_pct_00_03", "pct_fg3a_corner3", "off_rtg", "def_rtg", "pos_num"])
    df = query(f"""
        SELECT d.player_id, {cols},
               sum((coalesce(pct_fga_10_16,0) + coalesce(pct_fga_16_xx,0)) * mp) / sum(mp) AS mid_freq,
               sum(mp) AS nba_mp
        FROM stg_draft d JOIN mart_player_season ps
          ON ps.player_id = d.player_id AND ps.season BETWEEN d.draft_year + 1 AND d.draft_year + 3
        WHERE ps.mp > 0 GROUP BY d.player_id HAVING sum(mp) >= 500
    """)
    return df.rename(columns={"fg3a_per_fga_pct": "fg3a_rate", "fta_per_fga_pct": "fta_rate",
                              "fg3_pct": "fg3_pct_eb", "pct_fga_00_03": "rim_freq", "fg_pct_00_03": "rim_fg",
                              "pct_fg3a_corner3": "corner3_share"})


def train() -> ProspectModel:
    df = college.training_frame()
    feats = college.FEATURES
    gmm, meta = fit_trajectories(df)
    df["tier"] = tier_labels(gmm, meta, df)
    k = meta["k"]
    bust_tiers = [i for i, g in enumerate(meta["groups"]) if g["bust"]]
    hit_tiers = [i for i, g in enumerate(meta["groups"]) if g["hit"]]
    df["bust"] = df["tier"].isin(bust_tiers).astype(int)
    df["hit"] = df["tier"].isin(hit_tiers).astype(int)
    df.to_parquet(config.PROCESSED_DIR / "prospect_training.parquet", index=False)

    X, groups = df[feats], df["draft_year"]
    Xp = np.log(df[["pick"]]).rename(columns={"pick": "log_pick"})
    Xsp = pd.concat([X, Xp], axis=1)
    lin_clf = _impute_scale(LogisticRegression(C=0.1, max_iter=5000))
    lin_reg = _impute_scale(RidgeCV(alphas=np.logspace(0, 3.5, 25)))

    pm = ProspectModel(features=feats, tier_names=meta["names"], groups=meta["groups"])
    metrics: dict = {"n_draftees": len(df), "n_tiers": k, "bust_rate": df["bust"].mean(),
                     "hit_rate": df["hit"].mean()}

    for task in ("bust", "hit"):
        y = df[task]
        a = _oof(lin_clf, X, y, groups, "bin")
        b = _oof(_gbm_clf(), X, y, groups, "bin")
        w = _best_weight(lambda p, _y=y: brier_score_loss(_y, p), a, b)
        p = (1 - w) * a + w * b
        p_pick = _oof(_impute_scale(LogisticRegression()), Xp, y, groups, "bin")
        p_both = _oof(lin_clf, Xsp, y, groups, "bin")
        metrics.update({f"{task}_auc_stats": roc_auc_score(y, p), f"{task}_auc_pick": roc_auc_score(y, p_pick),
                        f"{task}_auc_stats_plus_pick": roc_auc_score(y, p_both),
                        f"{task}_brier_stats": brier_score_loss(y, p),
                        f"{task}_brier_pick": brier_score_loss(y, p_pick), f"{task}_gbm_w": w})
        # Within the first round, does the model order players better than the draft did?
        r1 = df["pick"] <= 30
        metrics[f"{task}_auc_stats_round1"] = roc_auc_score(y[r1], p[r1])
        metrics[f"{task}_auc_pick_round1"] = roc_auc_score(y[r1], p_pick[r1])
        pm.models[task] = (clone(lin_clf).fit(X, y), clone(_gbm_clf()).fit(X, y), w)

    y = df["vorp_4yr"]
    a, b = _oof(lin_reg, X, y, groups, "reg"), _oof(_gbm_reg(), X, y, groups, "reg")
    w = _best_weight(lambda p: -pd.Series(p).corr(y, method="spearman"), a, b)
    ev = (1 - w) * a + w * b
    ev_pick = _oof(RidgeCV(), Xp, y, groups, "reg")
    metrics.update(ev_spearman_stats=pd.Series(ev).corr(y, method="spearman"),
                   ev_spearman_pick=pd.Series(ev_pick).corr(y, method="spearman"),
                   ev_mae_stats=mean_absolute_error(y, ev), ev_gbm_w=w)
    pm.models["ev"] = (clone(lin_reg).fit(X, y), clone(_gbm_reg()).fit(X, y), w)
    pm.ev_reference = ev  # out-of-fold, so grade percentiles are honest

    yt = df["tier"]
    a = _oof(lin_clf, X, yt, groups, "multi", k)
    b = _oof(_gbm_clf(), X, yt, groups, "multi", k)
    pm.models["tiers"] = (clone(lin_clf).fit(X, yt), clone(_gbm_clf()).fit(X, yt), 0.5)
    metrics["tier_top1_acc"] = float((((a + b) / 2).argmax(1) == yt).mean())
    for i, g in enumerate(meta["groups"]):
        metrics[f"group_{i}_{g['name'].replace(' ', '_')}_share"] = g["n"] / len(df)
        metrics[f"group_{i}_{g['name'].replace(' ', '_')}_vorp4"] = g["vorp4"]

    pm.background = X.sample(min(80, len(X)), random_state=0).fillna(X.median())

    # Draftability: P(drafted | final college season), context for undrafted-calibre players.
    fs = college.final_seasons_for_draft_model()
    pm.draft_model = _impute_scale(LogisticRegression(C=0.5, max_iter=5000, class_weight="balanced"))
    pm.draft_model.fit(fs[feats], fs["drafted"].astype(int))

    # Translation: college -> early-career NBA profile.
    tgt = _translation_targets()
    tr_df = df.merge(tgt, on="player_id", how="inner", suffixes=("", "_nba"))
    targets = list(PROFILE_COLS)
    Yf = tr_df[[f"{c}_nba" if f"{c}_nba" in tr_df else c for c in targets]]
    Y = Yf.fillna(Yf.median()).to_numpy()
    pm.translator = _impute_scale(RidgeCV(alphas=np.logspace(-1, 3, 25))).fit(tr_df[feats], Y)
    pm.translate_targets = targets
    tr_pred = np.zeros_like(Y)
    for tr, te in GroupKFold(n_splits=6).split(tr_df, groups=tr_df["draft_year"]):
        tr_pred[te] = clone(pm.translator).fit(tr_df[feats].iloc[tr], Y[tr]).predict(tr_df[feats].iloc[te])
    for j, c in enumerate(targets):
        metrics[f"translate_r_{c}"] = float(np.corrcoef(tr_pred[:, j], Y[:, j])[0, 1])
    metrics["n_translation"] = len(tr_df)

    # Historical comps.
    comp_cols = ["player", "nba_name", "team", "season", "draft_year", "pick", "vorp_4yr", "mp_4yr", "tier"]
    pm.comps_scaler = make_pipeline(SimpleImputer(strategy="median"), StandardScaler()).fit(X)
    pm.comps_index = NearestNeighbors(n_neighbors=10).fit(pm.comps_scaler.transform(X))
    pm.comps_table = df[comp_cols].assign(outcome=df["tier"].map(dict(enumerate(meta["names"])))).reset_index(drop=True)

    pm.metrics = metrics
    with tracked_run("prospect_model") as log_run:
        log_run(params={"features": len(feats), "tiers": k, "validation": "leave-draft-class-out"},
                metrics={k_: v for k_, v in metrics.items() if isinstance(v, (int, float))})
    log.info("prospect model: %s", {k_: round(v, 3) for k_, v in metrics.items()})
    save("prospect_model", pm)
    save("trajectory_gmm", (gmm, meta))
    return pm
