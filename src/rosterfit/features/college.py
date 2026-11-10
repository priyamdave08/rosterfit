"""College prospect feature engineering (Torvik player-seasons)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from rosterfit import config
from rosterfit.db.warehouse import query
from rosterfit.features.shrinkage import BetaPrior, fit_beta_prior

# (makes, attempts, output) for every percentage we regularise.
SHOOTING = [("fg3m", "fg3a", "fg3_eb"), ("ftm", "fta", "ft_eb"), ("rim_m", "rim_a", "rim_eb"),
            ("mid_m", "mid_a", "mid_eb"), ("fg2m", "fg2a", "fg2_eb")]

FEATURES = [
    # impact
    "bpm", "obpm", "dbpm", "porpag", "dporpag", "ortg", "drtg",
    # role / efficiency
    "usg", "ts", "ast_pct", "tov_pct", "ast_tov", "orb_pct", "drb_pct", "stl_pct", "blk_pct", "ftr",
    # shooting, Bayes-shrunk
    "fg3_eb", "ft_eb", "rim_eb", "mid_eb",
    # shot diet + volume
    "fg3a_rate", "rim_rate", "mid_rate", "dunk_rate", "fg3a_per40", "fta_per40", "stl_per40", "blk_per40",
    # context
    "age_at_draft", "height_in", "power_conf", "college_seasons", "recruit_rank", "has_recruit_rank",
    "min_pct", "mpg",
]

FEATURE_LABELS = {
    "bpm": "BPM", "obpm": "offensive BPM", "dbpm": "defensive BPM", "age_at_draft": "age at draft",
    "height_in": "height", "usg": "usage", "ts": "true shooting", "ast_pct": "assist rate",
    "tov_pct": "turnover rate", "stl_pct": "steal rate", "blk_pct": "block rate", "orb_pct": "offensive rebounding",
    "drb_pct": "defensive rebounding", "fg3_eb": "3P% (shrunk)", "ft_eb": "FT% (shrunk)", "rim_eb": "rim FG%",
    "mid_eb": "mid-range FG%", "fg3a_per40": "3PA per 40", "fta_per40": "FTA per 40", "stl_per40": "steals per 40",
    "blk_per40": "blocks per 40", "recruit_rank": "recruiting rank", "has_recruit_rank": "was a ranked recruit",
    "power_conf": "power conference", "college_seasons": "college seasons", "porpag": "PORPAG",
    "dporpag": "D-PORPAG", "ftr": "free-throw rate", "min_pct": "minutes share", "ortg": "offensive rating",
    "drtg": "defensive rating", "fg3a_rate": "3PA rate", "rim_rate": "rim attempt rate",
    "mid_rate": "mid-range rate", "dunk_rate": "dunk rate", "ast_tov": "assist/turnover", "mpg": "minutes per game",
}

_PRIORS: dict[str, BetaPrior] = {}
_GROUP_PRIORS: dict[str, pd.DataFrame] = {}

# Rate stats shrunk toward the (recruit tier x class) prior in small samples.
SHRINK_COLS = ["bpm", "obpm", "dbpm", "porpag", "dporpag", "ortg", "drtg", "usg", "ts", "ast_pct",
               "tov_pct", "ast_tov", "orb_pct", "drb_pct", "stl_pct", "blk_pct", "ftr", "fg3a_rate",
               "rim_rate", "mid_rate", "dunk_rate", "fg3a_per40", "fta_per40", "stl_per40", "blk_per40"]
PRIOR_MINUTES = 300.0


def recruit_tier(rr: pd.Series) -> pd.Series:
    rr = rr.fillna(0)
    return pd.cut(rr, [-1, 0.5, 90, 98, 101], labels=["unranked", "ranked", "top", "elite"]).astype(str)


def shooting_priors() -> dict[str, BetaPrior]:
    """Population priors fit once on every college player-season since 2010."""
    if not _PRIORS:
        df = query("SELECT fg3m, fg3a, ftm, fta, rim_m, rim_a, mid_m, mid_a, fg2m, fg2a "
                   "FROM stg_college WHERE gp >= 10 AND min_pct >= 20")
        for m, a, out in SHOOTING:
            _PRIORS[out] = fit_beta_prior(df[m], df[a], min_attempts=20)
    return _PRIORS


def _derive(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for m, a, out in SHOOTING:
        df[out] = shooting_priors()[out].posterior_mean(df[m], df[a])
    fga = (df["fg2a"].fillna(0) + df["fg3a"].fillna(0)).replace(0, np.nan)
    df["fg3a_rate"] = df["fg3a"] / fga
    df["rim_rate"] = df["rim_a"] / fga
    df["mid_rate"] = df["mid_a"] / fga
    df["dunk_rate"] = df["dunk_a"] / fga
    minutes = (df["mpg"] * df["gp"]).replace(0, np.nan)
    df["total_min"] = minutes
    df["fg3a_per40"] = df["fg3a"] / minutes * 40
    df["fta_per40"] = df["fta"] / minutes * 40
    df["stl_per40"] = df["stl_pg"] * df["gp"] / minutes * 40
    df["blk_per40"] = df["blk_pg"] * df["gp"] / minutes * 40
    df["has_recruit_rank"] = df["recruit_rank"].notna().astype(int)
    df["recruit_tier"] = recruit_tier(df["recruit_rank"])
    df["recruit_rank"] = df["recruit_rank"].fillna(0)
    df["class_yr"] = df["class_yr"].where(df["class_yr"].isin(["Fr", "So", "Jr", "Sr"]), "Sr")
    return df


def group_priors() -> dict[str, pd.DataFrame]:
    """Minutes-weighted mean of each rate stat by (recruit tier, class year), plus
    median age by class year - estimated from every college season on record."""
    if not _GROUP_PRIORS:
        pop = _derive(query("SELECT * FROM stg_college WHERE gp >= 8 AND min_pct >= 25 AND season < ?",
                            [config.CURRENT_SEASON]))
        pop["age_at_draft"] = pop["age_at_draft_day"]
        w = pop["total_min"].fillna(0)
        rows = {}
        for key, g in pop.groupby(["recruit_tier", "class_yr"]):
            gw = w.loc[g.index] + 1e-9
            rows[key] = {c: np.average(g[c].fillna(g[c].median()), weights=gw) for c in SHRINK_COLS}
        _GROUP_PRIORS["rates"] = pd.DataFrame(rows).T
        _GROUP_PRIORS["age"] = pop.groupby("class_yr")["age_at_draft"].median()
    return _GROUP_PRIORS


def engineer(df: pd.DataFrame, shrink: bool = True) -> pd.DataFrame:
    df = _derive(df)
    pri = group_priors()
    if "age_at_draft" in df:
        df["age_imputed"] = df["age_at_draft"].isna().astype(int)
        df["age_at_draft"] = df["age_at_draft"].fillna(df["class_yr"].map(pri["age"]))
    if shrink:
        rates = pri["rates"]
        keys = list(zip(df["recruit_tier"], df["class_yr"], strict=False))
        prior = rates.reindex(keys).set_axis(df.index)
        prior = prior.fillna(rates.mean())
        n = df["total_min"].fillna(0)
        for c in SHRINK_COLS:
            x = df[c].fillna(prior[c])
            df[c] = (n * x + PRIOR_MINUTES * prior[c]) / (n + PRIOR_MINUTES)
    return df


def training_frame() -> pd.DataFrame:
    """Drafted college players with their final college season + 4-year NBA outcome."""
    df = query("""
        SELECT dc.*, cc.college_seasons,
               o.vorp_4yr, o.mp_4yr, o.vorp_1, o.vorp_2, o.vorp_3, o.vorp_4,
               o.mp_1, o.mp_2, o.mp_3, o.mp_4, o.bpm_peak
        FROM mart_draft_college dc
        JOIN mart_college_career cc USING (torvik_id, season)
        JOIN (
            SELECT player_id, draft_year,
                   sum(vorp) AS vorp_4yr, sum(mp) AS mp_4yr, max(bpm) FILTER (WHERE mp >= 500) AS bpm_peak,
                   max(vorp) FILTER (WHERE yr = 1) AS vorp_1, max(vorp) FILTER (WHERE yr = 2) AS vorp_2,
                   max(vorp) FILTER (WHERE yr = 3) AS vorp_3, max(vorp) FILTER (WHERE yr = 4) AS vorp_4,
                   max(mp) FILTER (WHERE yr = 1) AS mp_1, max(mp) FILTER (WHERE yr = 2) AS mp_2,
                   max(mp) FILTER (WHERE yr = 3) AS mp_3, max(mp) FILTER (WHERE yr = 4) AS mp_4
            FROM mart_draft_outcomes GROUP BY ALL
        ) o USING (player_id, draft_year)
        WHERE dc.draft_year <= ?
    """, [config.LAST_LABELED_DRAFT])
    df["age_at_draft"] = df["age_at_draft_day"]
    return engineer(df)


def prospect_pool(min_minutes: float = 40) -> pd.DataFrame:
    """Players enrolled in the current college season, with last season blended in.

    Counting stats are summed across the two seasons; rate stats are averaged by
    minutes, so a returning junior's big 2025-26 sample still counts while a
    freshman is graded on (heavily shrunk) early-season numbers.
    """
    cur = config.CURRENT_SEASON
    raw = query("""
        SELECT c.*, cc.college_seasons
        FROM stg_college c JOIN mart_college_career cc USING (torvik_id, season)
        WHERE c.season IN (?, ?)
          AND c.torvik_id IN (SELECT torvik_id FROM stg_college WHERE season = ?)
          AND c.torvik_id NOT IN (SELECT torvik_id FROM stg_college WHERE pick IS NOT NULL AND season < ?)
    """, [cur - 1, cur, cur, cur])
    if raw.empty:
        return raw
    raw["minutes"] = (raw["mpg"] * raw["gp"]).fillna(0)
    counts = ["gp", "ftm", "fta", "fg2m", "fg2a", "fg3m", "fg3a", "rim_m", "rim_a", "mid_m", "mid_a",
              "dunk_m", "dunk_a"]
    per_game = ["mpg", "oreb_pg", "dreb_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg", "pts_pg"]
    rates = ["min_pct", "ortg", "usg", "efg", "ts", "orb_pct", "drb_pct", "ast_pct", "tov_pct", "blk_pct",
             "stl_pct", "ftr", "porpag", "adj_oe", "ast_tov", "drtg", "adj_drtg", "dporpag", "bpm", "obpm",
             "dbpm", "gbpm"]

    def blend(g: pd.DataFrame) -> pd.Series:
        latest = g.sort_values("season").iloc[-1]
        w = g["minutes"].to_numpy() + 1e-6
        out = latest.copy()
        for c in counts:
            out[c] = g[c].fillna(0).sum()
        tot_games = g["gp"].fillna(0).sum()
        for c in per_game:
            out[c] = np.average(g[c].fillna(0), weights=g["gp"].fillna(0) + 1e-6) if tot_games else latest[c]
        for c in rates:
            vals = g[c]
            out[c] = np.average(vals.fillna(vals.mean() if vals.notna().any() else 0), weights=w)
        out["seasons_blended"] = len(g)
        out["current_season_min"] = g.loc[g["season"] == cur, "minutes"].sum()
        return out

    pool = raw.groupby("torvik_id", group_keys=False).apply(blend, include_groups=False).reset_index()
    pool = pool[(pool["mpg"] * pool["gp"]) >= min_minutes]
    draft_day = pd.Timestamp(year=cur, month=6, day=25)
    pool["age_at_draft"] = (draft_day - pd.to_datetime(pool["birth_date"])).dt.days / 365.25
    return engineer(pool)


def final_seasons_for_draft_model() -> pd.DataFrame:
    """Every college player's last season (<= last completed draft), labelled drafted or not."""
    df = query("""
        SELECT c.*, cc.college_seasons, (c.pick IS NOT NULL) AS drafted
        FROM stg_college c JOIN mart_college_career cc USING (torvik_id, season)
        WHERE c.gp >= 10 AND c.min_pct >= 15 AND c.season < ?
          AND c.season = (SELECT max(season) FROM stg_college c2 WHERE c2.torvik_id = c.torvik_id)
    """, [config.CURRENT_SEASON])
    df["age_at_draft"] = df["age_at_draft_day"]
    return engineer(df)
