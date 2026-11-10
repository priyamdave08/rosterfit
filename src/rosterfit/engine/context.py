"""Front-office context: every player the engine can reason about, in one place.

Sources, in priority order, for a player's profile:
  nba          - regularised NBA profile (last full season blended with current)
  nba+college  - young NBA player (< 1500 min): Bayesian blend of his NBA sample
                 with the college-translation prior
  college      - rostered rookie with no NBA minutes yet: college translation
  replacement  - nothing known: typical end-of-bench profile
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from rosterfit import config
from rosterfit.db.warehouse import query
from rosterfit.features import archetypes, college
from rosterfit.features.players import PROFILE_COLS, current_profiles
from rosterfit.models.lineup_model import LineupModel, replacement_profile
from rosterfit.models.prospect_model import ProspectModel
from rosterfit.models.registry import load

log = logging.getLogger("rosterfit.engine")

ROOKIE_PRIOR_MINUTES = 600.0
YOUNG_PLAYER_MINUTES = 1500.0


def _norm(s: pd.Series) -> pd.Series:
    return (s.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii").str.lower()
            .str.replace(r"\b(jr|sr|ii|iii|iv)\b\.?", "", regex=True).str.replace(r"[^a-z ]", "", regex=True)
            .str.strip())


@dataclass
class Context:
    lineup_model: LineupModel
    prospect_model: ProspectModel
    players: pd.DataFrame          # every NBA player, indexed by player_id
    rosters: pd.DataFrame          # current ESPN rosters joined to player_id
    teams: pd.DataFrame
    prospects: pd.DataFrame        # graded college prospects, indexed by torvik_id
    replacement: pd.Series
    archetype_model: tuple | None = None

    # ------------------------------------------------------------------ lookups
    def team_roster(self, team: str) -> pd.DataFrame:
        ids = self.rosters.loc[self.rosters["team_abbr"] == team, "player_id"]
        df = self.players.loc[self.players.index.intersection(ids)].copy()
        return df.sort_values("minutes_proxy", ascending=False)

    def free_agents(self, min_minutes: float = 300) -> pd.DataFrame:
        """NBA players with recent minutes who are not on any current roster."""
        rostered = set(self.rosters["player_id"].dropna())
        fa = self.players[~self.players.index.isin(rostered) & (self.players["mp"] >= min_minutes)
                          & (self.players["source"] == "nba")]
        return fa.sort_values("bpm", ascending=False)

    def search_players(self, text: str, limit: int = 10) -> pd.DataFrame:
        hits = process.extract(text, self.players["player"].to_dict(), scorer=fuzz.WRatio, limit=limit)
        return self.players.loc[[h[2] for h in hits]]

    def search_prospects(self, text: str, limit: int = 10) -> pd.DataFrame:
        hits = process.extract(text, self.prospects["player"].to_dict(), scorer=fuzz.WRatio, limit=limit)
        return self.prospects.loc[[h[2] for h in hits]]

    def prospect_as_player(self, torvik_id: int) -> pd.Series:
        """A prospect's translated NBA profile, ready to drop into a lineup."""
        p = self.prospects.loc[torvik_id]
        s = nba_profile(p.to_frame().T).iloc[0].astype(float).copy()
        s["player"] = p["player"]
        s["player_id"] = f"prospect:{torvik_id}"
        s["source"] = "college"
        s["team_id"] = p["team"]
        return s


def nba_profile(prospects: pd.DataFrame) -> pd.DataFrame:
    """The translated NBA profile of prospects, under the standard PROFILE_COLS names."""
    cols = [f"nba_{c}" for c in PROFILE_COLS]
    return prospects[cols].set_axis(PROFILE_COLS, axis=1)


def _match_rosters(rosters: pd.DataFrame, players: pd.DataFrame) -> pd.Series:
    """ESPN name -> B-Ref player_id (exact normalised key, then fuzzy fallback)."""
    key_to_id = dict(zip(players["name_key"], players.index, strict=False))
    keys = _norm(rosters["player"])
    ids = keys.map(key_to_id)
    choices = players["name_key"].to_dict()
    for i in ids[ids.isna()].index:
        hit = process.extractOne(keys[i], choices, scorer=fuzz.ratio, score_cutoff=88)
        if hit:
            ids[i] = hit[2]
    return ids


def _college_rows_for_nba_players(pm: ProspectModel) -> pd.DataFrame:
    """Final college season (engineered) for every drafted NBA player we can link."""
    df = query("""
        SELECT dc.*, cc.college_seasons FROM mart_draft_college dc
        JOIN mart_college_career cc USING (torvik_id, season)
        WHERE dc.draft_year >= ?
    """, [config.CURRENT_SEASON - 6])
    if df.empty:
        return df
    df["age_at_draft"] = df["age_at_draft_day"]
    df = college.engineer(df)
    trans = pm.translate(df)
    trans["player_id"] = df["player_id"].to_numpy()
    trans["college_name"] = df["player"].to_numpy()
    return trans.set_index("player_id")


def build_context() -> Context:
    lm: LineupModel = load("lineup_model")
    pm: ProspectModel = load("prospect_model")

    players = current_profiles().set_index("player_id")
    players["source"] = "nba"
    repl = replacement_profile(players.reset_index())

    # Young players: blend NBA sample with college prior (precision-weighted by minutes).
    prior = _college_rows_for_nba_players(pm)
    young = players.index.intersection(prior.index)
    young = young[players.loc[young, "mp"] < YOUNG_PLAYER_MINUTES]
    for pid in young:
        w = players.at[pid, "mp"]
        for c in PROFILE_COLS:
            players.at[pid, c] = (w * players.at[pid, c] + ROOKIE_PRIOR_MINUTES * prior.at[pid, c]) / (
                w + ROOKIE_PRIOR_MINUTES)
        players.at[pid, "source"] = "nba+college"

    rosters = query("SELECT * FROM raw_rosters")
    teams = query("SELECT * FROM raw_teams")
    rosters["player_id"] = _match_rosters(rosters, players)

    # Rostered players with no NBA profile (e.g. this year's rookies before their debut).
    new_rows = []
    draft = query("SELECT player_id, name_key FROM stg_draft WHERE draft_year >= ?", [config.CURRENT_SEASON - 2])
    draft_key = dict(zip(draft["name_key"], draft["player_id"], strict=False))
    for i, r in rosters[rosters["player_id"].isna()].iterrows():
        pid = draft_key.get(_norm(pd.Series([r["player"]]))[0])
        if pid is not None and pid in prior.index:
            row = prior.loc[pid, PROFILE_COLS].copy()
            source = "college"
        else:
            pid = f"espn:{r['espn_player_id']}"
            row = repl.copy()
            source = "replacement"
        row["player"], row["source"], row["mp"], row["team_id"] = r["player"], source, 0.0, r["team_abbr"]
        row["player_id"] = pid
        new_rows.append(row)
        rosters.at[i, "player_id"] = pid
    if new_rows:
        players = pd.concat([players, pd.DataFrame(new_rows).set_index("player_id")])

    # Minutes proxy for "who's in the rotation": recency-weighted minutes,
    # with rookies credited a bench role until they log real minutes.
    players["minutes_proxy"] = players.get("mp_current", 0).fillna(0) * 3 + players["mp"].fillna(0)
    players.loc[players["source"] == "college", "minutes_proxy"] = 900.0
    # Rostered players carry the ESPN team + bio.
    bio = rosters.dropna(subset=["player_id"]).drop_duplicates("player_id").set_index("player_id")
    players["current_team"] = bio["team_abbr"].reindex(players.index)
    players["height_in"] = bio["height_in"].reindex(players.index)
    players["headshot"] = bio["headshot"].reindex(players.index)

    # Archetypes.
    try:
        arche_pipe, arche_meta = load("archetypes")
        observed = players["source"].isin(["nba", "nba+college"])
        players = players.join(pd.concat([
            archetypes.assign(arche_pipe, arche_meta["names"], players[observed].fillna(0)),
            archetypes.assign_nearest(arche_pipe, arche_meta["names"], players[~observed].fillna(0)),
        ]))
        arche = (arche_pipe, arche_meta)
    except FileNotFoundError:
        arche = None

    # Prospect board.
    pool = college.prospect_pool()
    if len(pool):
        graded = pm.grade(pool)
        trans = pm.translate(pool)
        # College stats keep their own names; the NBA projection lives in nba_* columns
        # (several names overlap, e.g. blk_pct, and must not overwrite each other).
        prospects = pd.concat([pool, graded, trans.add_prefix("nba_")], axis=1).set_index("torvik_id")
        if arche:
            nba_view = nba_profile(prospects)
            prospects = prospects.join(archetypes.assign_nearest(arche[0], arche[1]["names"], nba_view.fillna(0)))
        prospects = prospects.sort_values("expected_vorp_4yr", ascending=False)
    else:
        prospects = pd.DataFrame()

    log.info("context: %d players, %d rostered, %d prospects", len(players), rosters["player_id"].notna().sum(),
             len(prospects))
    return Context(lm, pm, players, rosters, teams, prospects, repl, arche)


SNAPSHOT = config.MODEL_DIR / "context_snapshot.joblib"


def _snapshot_is_fresh() -> bool:
    if not SNAPSHOT.exists():
        return False
    pkg = Path(__file__).resolve().parents[1]
    code = [f for d in ("engine", "features", "models") for f in (pkg / d).glob("*.py")]
    deps = [config.DB_PATH, *config.MODEL_DIR.glob("*_model.joblib"), config.MODEL_DIR / "archetypes.joblib", *code]
    return all(SNAPSHOT.stat().st_mtime >= d.stat().st_mtime for d in deps if d.exists())


@lru_cache(maxsize=1)
def get_context() -> Context:
    """Load the context snapshot if it is newer than the DB and models, else rebuild it."""
    import joblib

    if _snapshot_is_fresh():
        return joblib.load(SNAPSHOT)
    ctx = build_context()
    joblib.dump(ctx, SNAPSHOT)
    return ctx
