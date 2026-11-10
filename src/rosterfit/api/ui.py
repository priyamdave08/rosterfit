"""Endpoints for the React front end.

Presentation only: every value comes from the same engine calls, filters and orderings
the Streamlit pages use (``rosterfit/app/views``), so the two front ends show identical
numbers. Nothing here re-models, re-ranks or re-rounds an engine output; ``clean`` only
makes it JSON-safe.
"""
from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from scipy import stats

from rosterfit import config
from rosterfit.cloud import scouting
from rosterfit.db.warehouse import query
from rosterfit.engine.context import Context, get_context, rank_search
from rosterfit.engine.fit import best_lineups, compare_candidates, evaluate_move
from rosterfit.engine.optimizer import realistic
from rosterfit.features.league import college_zone_averages, nba_zone_averages
from rosterfit.features.players import PROFILE_COLS
from rosterfit.labels import COLLEGE_LABELS, NAME_SUFFIXES, PROFILE_LABELS, SHOOTER_HELP, STAT_LABELS
from rosterfit.viz import shots

router = APIRouter(prefix="/ui", tags=["front end"])


def _clean(obj):
    from rosterfit.api.main import clean  # late import: main includes this router

    return clean(obj)


def ctx() -> Context:
    return get_context()


# --------------------------------------------------------------------------- identity helpers
def _team(c: Context, team: str) -> str:
    t = team.upper()
    if t not in set(c.teams["team_abbr"]):
        raise HTTPException(404, f"unknown team {team}")
    return t


def _prospect_id(pid: str) -> int | None:
    return int(pid.split(":", 1)[1]) if str(pid).startswith("prospect:") else None


def _jerseys(c: Context) -> dict[str, str]:
    j = c.rosters.dropna(subset=["player_id"]).set_index("player_id")["jersey"]
    return {k: str(v) for k, v in j.items() if pd.notna(v) and str(v) != ""}


def short_name(name: str) -> str:
    parts = name.split()
    if len(parts) >= 3 and parts[-1].lower() in NAME_SUFFIXES:
        return " ".join(parts[-2:])
    return parts[-1] if parts else name


def team_tag(c: Context, pid: str) -> str:
    t = c.players.loc[pid].get("current_team")
    return t if isinstance(t, str) and t else "FA"


def person(c: Context, pid: str, jerseys: dict[str, str] | None = None) -> dict:
    """Name, label and jersey for any id (B-Ref id or prospect:<torvik_id>)."""
    tid = _prospect_id(pid)
    if tid is not None:
        pr = c.prospects.loc[tid]
        return {"id": pid, "name": str(pr["player"]), "short": short_name(str(pr["player"])), "jersey": None,
                "team": str(pr["team"]), "label": f"{pr['player']} ({pr['team']}, prospect {pr['grade']})",
                "kind": "prospect"}
    name = str(c.players.loc[pid, "player"])
    tag = team_tag(c, pid)
    return {"id": pid, "name": name, "short": short_name(name), "jersey": (jerseys or _jerseys(c)).get(pid),
            "team": tag, "label": f"{name} ({tag})", "kind": "nba"}


def resolve(c: Context, pid: str) -> pd.Series:
    tid = _prospect_id(pid)
    if tid is not None:
        if tid not in c.prospects.index:
            raise HTTPException(404, f"unknown prospect {tid}")
        return c.prospect_as_player(tid)
    if pid not in c.players.index:
        raise HTTPException(404, f"unknown player {pid}")
    row = c.players.loc[pid].copy()
    row["player_id"] = pid
    return row


def five_frame(c: Context, ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame([resolve(c, p) for p in ids])


# --------------------------------------------------------------------------- lineups
def lineup_metrics(c: Context, ids: list[str]) -> dict:
    """Same fields as the Streamlit lineup builder's comparison table."""
    prof = five_frame(c, ids)[PROFILE_COLS].astype(float)
    pred = c.lineup_model.predict_lineup(prof)
    f = pred["features"]
    return {"net": pred["net_rtg"], "off": pred["off_rtg_rel"], "def": -pred["def_rtg_rel"],
            "shooters": f["n_shooters"], "creators": f["n_creators"], "rim_protectors": f["n_rim_protectors"],
            "spacing": f["spacing_index"], "usage_total": f["usage_total"]}


def lineup_detail(c: Context, ids: list[str], highlight: str | None = None) -> dict:
    """Everything the Streamlit lineup panel shows for one five-man unit."""
    five = five_frame(c, ids)
    prof = five[PROFILE_COLS].astype(float)
    jerseys = _jerseys(c)
    layout = shots.spacing_layout(five.assign(player=five["player"].astype(str)))
    by_name = {person(c, p, jerseys)["name"]: p for p in ids}
    for spot in layout["players"]:
        spot["id"] = by_name.get(spot["player"])
    drivers = c.lineup_model.explain(prof)
    drivers["label"] = drivers["feature"].map(STAT_LABELS).fillna(drivers["feature"])
    return {"players": [person(c, p, jerseys) for p in ids], "metrics": lineup_metrics(c, ids),
            "realistic": bool(realistic(prof)), "highlight": highlight,
            "spacing": {k: layout[k] for k in ("players", "perimeter_threats", "paint_bodies", "congested")},
            "drivers": drivers[["feature", "label", "value", "net_impact"]],
            "shot_diet": shots.lineup_shot_diet(prof)}


def _lineup_rows(c: Context, df: pd.DataFrame) -> list[dict]:
    jerseys = _jerseys(c)
    out = []
    for rank, r in df.iterrows():
        out.append({"rank": int(rank), "ids": list(r["player_ids"]),
                    "players": [person(c, p, jerseys) for p in r["player_ids"]],
                    "net": r["net_rtg"], "off": r["off_rtg_rel"], "def": -r["def_rtg_rel"],
                    "shooters": r["n_shooters"], "spacing": r["spacing_index"], "usage_total": r["usage_total"]})
    return out


@router.get("/meta")
def meta() -> dict:
    c = ctx()
    built = pd.Timestamp(config.DB_PATH.stat().st_mtime, unit="s").strftime("%b %d, %Y") if config.DB_PATH.exists() else None
    teams = c.teams.sort_values("team_abbr")
    return _clean({"season": f"{config.CURRENT_SEASON - 1}-{str(config.CURRENT_SEASON)[-2:]}", "warehouse_built": built,
                   "teams": [{"abbr": t.team_abbr, "name": t.team_name,
                              "color": t.color if str(t.color).startswith("#") else f"#{t.color}",
                              "alt_color": t.alt_color if str(t.alt_color).startswith("#") else f"#{t.alt_color}"}
                             for t in teams.itertuples()],
                   "labels": {"stats": STAT_LABELS, "college": COLLEGE_LABELS, "profile": PROFILE_LABELS},
                   "shooter_help": SHOOTER_HELP, "memo_writer": scouting.resolve_provider(),
                   "spots": shots.SPOTS, "nba_label_pos": shots.NBA_LABEL_POS,
                   "college_label_pos": shots.COLLEGE_LABEL_POS})


@router.get("/teams/{team}/lineups")
def team_lineups(team: str, top: int = Query(15, ge=1, le=500)) -> dict:
    c = ctx()
    t = _team(c, team)
    bl = best_lineups(c, t, top=None)
    return _clean({"count": len(bl), "lineups": _lineup_rows(c, bl.head(top))})


@router.get("/teams/{team}/roster")
def team_roster(team: str) -> list[dict]:
    c = ctx()
    t = _team(c, team)
    roster = c.team_roster(t)
    jerseys = _jerseys(c)
    cols = ["source", "archetype", "mp", "bpm", "obpm", "dbpm", "ts_pct", "usg_pct", "fg3_pct_eb", "fg3a_per_poss",
            "ast_pct", "blk_pct"]
    return _clean([{**person(c, pid, jerseys), **{k: roster.loc[pid].get(k) for k in cols}} for pid in roster.index])


class LineupBody(BaseModel):
    team: str
    ids: list[str] = Field(..., min_length=5, max_length=5)


@router.post("/lineup")
def lineup(body: LineupBody) -> dict:
    """A custom five: the panel plus its rank against the team's realistic lineups."""
    c = ctx()
    t = _team(c, body.team)
    if len(set(body.ids)) != 5:
        raise HTTPException(400, "pick five different players")
    bl = best_lineups(c, t, top=None)
    detail = lineup_detail(c, body.ids)
    roster_ids = set(c.team_roster(t).index)
    detail["rank"] = int((bl["net_rtg"] > detail["metrics"]["net"]).sum()) + 1
    detail["of"] = len(bl)
    detail["outside"] = [p for p in body.ids if p not in roster_ids]
    detail["best"] = lineup_metrics(c, bl.iloc[0]["player_ids"])
    return _clean(detail)


@router.get("/lineup-detail")
def lineup_detail_route(ids: str, highlight: str | None = None) -> dict:
    parts = [p for p in ids.split(",") if p]
    if len(parts) != 5:
        raise HTTPException(400, "five ids, comma separated")
    return _clean(lineup_detail(ctx(), parts, highlight))


@router.get("/teams/{team}/pool")
def builder_pool(team: str, kind: Literal["roster", "league", "prospects"] = "roster") -> list[dict]:
    """Players selectable in the lineup builder, in the Streamlit order."""
    c = ctx()
    t = _team(c, team)
    ids = list(c.team_roster(t).index)
    if kind != "roster":
        league = c.players[(c.players["source"] != "replacement") & ~c.players.index.isin(ids)]
        ids += list(league.sort_values("minutes_proxy", ascending=False).index)
    if kind == "prospects":
        top = c.prospects[c.prospects["draft_prob"] >= 0.3].sort_values("grade_score", ascending=False)
        ids += [f"prospect:{i}" for i in top.index[:300]]
    jerseys = _jerseys(c)
    return _clean([person(c, p, jerseys) for p in ids])


# --------------------------------------------------------------------------- draft room
BOARD_COLS = ["player", "team", "class_yr", "age_at_draft", "height_in", "bpm", "grade", "grade_score",
              "expected_vorp_4yr", "hit_prob", "bust_prob", "likeliest_path", "archetype", "total_min", "draft_prob"]


@router.get("/prospects")
def board(min_minutes: float = 250, min_draft: float = 0.5, classes: str = "Fr,So,Jr,Sr", q: str = "") -> dict:
    p = ctx().prospects
    cls = [x for x in classes.split(",") if x]
    b = p[(p["total_min"] >= min_minutes) & (p["draft_prob"] >= min_draft) & p["class_yr"].isin(cls)]
    b = b.sort_values("grade_score", ascending=False)
    if q.strip():
        b = b.loc[rank_search(b["player"], q, limit=None)]
    rows = b[BOARD_COLS].head(200).reset_index().rename(columns={"index": "torvik_id"})
    return _clean({"count": len(b), "prospects": rows})


@router.get("/prospects/{torvik_id}")
def prospect_report(torvik_id: int) -> dict:
    c = ctx()
    if torvik_id not in c.prospects.index:
        raise HTTPException(404, "unknown prospect")
    r = c.prospects.loc[torvik_id]
    expl = c.prospect_model.explain(c.prospects.loc[[torvik_id]])
    expl["label"] = expl["feature"].map(COLLEGE_LABELS).fillna(expl["feature"])
    tiers = [{"path": n, "prob": r[f"p_{n.lower().replace(' ', '_')}"]} for n in c.prospect_model.tier_names]
    zones = shots.college_zones(r, college_zone_averages())
    comps = c.prospect_model.comps(c.prospects.loc[[torvik_id]], k=6)
    return _clean({"torvik_id": torvik_id, "profile": r[BOARD_COLS], "tiers": tiers,
                   "drivers": expl[["feature", "label", "value", "impact_vorp"]],
                   "zones": {k: {"freq": z.freq, "fg": z.fg, "lg_fg": z.lg_fg} for k, z in zones.items()},
                   "comps": comps[["nba_name", "team", "draft_year", "pick", "outcome", "vorp_4yr", "mp_4yr",
                                   "similarity"]]})


class MemoBody(BaseModel):
    team: str


@router.post("/prospects/{torvik_id}/memo")
def memo(torvik_id: int, body: MemoBody) -> dict:
    c = ctx()
    t = _team(c, body.team)
    if torvik_id not in c.prospects.index:
        raise HTTPException(404, "unknown prospect")
    names = c.teams.set_index("team_abbr")["team_name"].to_dict()
    r = c.prospects.loc[torvik_id]
    expl = c.prospect_model.explain(c.prospects.loc[[torvik_id]])
    comps = c.prospect_model.comps(c.prospects.loc[[torvik_id]], k=6)
    cand = c.prospect_as_player(torvik_id)
    res = evaluate_move(c, t, [cand])
    pid = cand["player_id"]
    fit = {"fit_score": res.fit_score(pid), "synergy": res.synergy.get(pid),
           "best_lineup_net_with_him": res.best_with.get(pid), "current_best_net": res.before_best,
           "displaces": res.displaces.get(pid)}
    out = scouting.generate(scouting.build_packet(r, expl, comps, fit, names[t]))
    return _clean({"text": out.text, "provider": out.provider, "model": out.model})


class FitBody(BaseModel):
    team: str
    prospects: list[int] = Field(..., min_length=1, max_length=12)
    talent_weight: float = Field(0.65, ge=0, le=1)


@router.post("/draft-fit")
def draft_fit(body: FitBody) -> dict:
    c = ctx()
    t = _team(c, body.team)
    missing = [i for i in body.prospects if i not in c.prospects.index]
    if missing:
        raise HTTPException(404, f"unknown prospects {missing}")
    cmp = compare_candidates(c, t, [c.prospect_as_player(i) for i in body.prospects], talent_weight=body.talent_weight)
    top = cmp.iloc[0]
    res = evaluate_move(c, t, [c.prospect_as_player(int(top["player_id"].split(":")[1]))], with_synergy=False)
    with_him = res.lineups_after[res.lineups_after["player_ids"].map(lambda ids: top["player_id"] in ids)]
    best = lineup_detail(c, list(with_him.iloc[0]["player_ids"]), highlight=top["player_id"]) if len(with_him) else None
    cols = ["player_id", "player", "grade", "grade_score", "fit_score", "board_score", "gain_vs_current_best",
            "synergy", "displaces", "bust_prob", "hit_prob"]
    return _clean({"team": t, "talent_weight": body.talent_weight, "rows": cmp[cols], "best_with_top": best})


# --------------------------------------------------------------------------- signings and trades
@router.get("/teams/{team}/move-pool")
def move_pool(team: str, mode: Literal["signing", "trade"] = "signing") -> dict:
    c = ctx()
    t = _team(c, team)
    if mode == "signing":
        fa = c.free_agents()
        ids = list(fa.index)
    else:
        rostered = c.players[(c.players["source"] != "replacement") & c.players["current_team"].notna()
                             & (c.players["current_team"] != t)]
        ids = list(rostered.sort_values("minutes_proxy", ascending=False).index)
    jerseys = _jerseys(c)
    return _clean({"mode": mode, "count": len(ids), "players": [person(c, p, jerseys) for p in ids],
                   "roster": [person(c, p, jerseys) for p in c.team_roster(t).index]})


class MoveBody(BaseModel):
    team: str
    incoming: list[str] = Field(..., min_length=1, max_length=3)
    outgoing: list[str] = Field(default_factory=list, max_length=4)


@router.post("/move")
def move(body: MoveBody) -> dict:
    c = ctx()
    t = _team(c, body.team)
    cands = [resolve(c, p) for p in body.incoming]
    try:
        res = evaluate_move(c, t, cands, body.outgoing)
    except ValueError as err:
        raise HTTPException(400, str(err)) from err
    jerseys = _jerseys(c)
    return _clean({
        "team": t, "after_best": res.after_best, "ceiling_delta": res.ceiling_delta,
        "after_depth": res.after_depth, "depth_delta": res.depth_delta,
        "players": [{**person(c, p, jerseys), "fit_score": res.fit_score(p), "best_with": res.best_with.get(p),
                     "displaces": res.displaces.get(p), "synergy": res.synergy.get(p)} for p in res.incoming],
        "before": _lineup_rows(c, res.lineups_before.head(5)),
        "after": _lineup_rows(c, res.lineups_after.head(5)),
        "best_after": lineup_detail(c, list(res.lineups_after.iloc[0]["player_ids"]), highlight=res.incoming[0]),
    })


# --------------------------------------------------------------------------- player cards
def _card_pool(c: Context) -> pd.DataFrame:
    return c.players[c.players["source"] != "replacement"].sort_values("minutes_proxy", ascending=False)


@router.get("/players")
def players(q: str = "", limit: int = Query(60, ge=1, le=700)) -> dict:
    """Player Cards search: a team code lists that roster, otherwise ranked name matches."""
    c = ctx()
    pool = _card_pool(c)
    code = q.strip().upper()
    if code in set(c.teams["team_abbr"]):
        matches = list(pool.index[pool["current_team"] == code])
    else:
        matches = rank_search(pool["player"], q, limit=None)
    jerseys = _jerseys(c)
    return _clean({"count": len(matches), "players": [person(c, p, jerseys) for p in matches[:limit]]})


RADAR = ["bpm", "obpm", "dbpm", "ts_pct", "usg_pct", "ast_pct", "tov_pct", "trb_pct", "stl_pct", "blk_pct",
         "fg3_pct_eb", "fg3a_per_poss", "rim_freq"]
RADAR_LABELS = {"bpm": "BPM", "obpm": "Off. BPM", "dbpm": "Def. BPM", "ts_pct": "True shooting", "usg_pct": "Usage",
                "ast_pct": "Assists", "tov_pct": "Ball security", "trb_pct": "Rebounding", "stl_pct": "Steals",
                "blk_pct": "Blocks", "fg3_pct_eb": "3P% (shrunk)", "fg3a_per_poss": "3PA volume",
                "rim_freq": "Rim pressure"}
SEASON_COLS = ["season", "team_id", "age", "g", "mp", "per", "ts_pct", "usg_pct", "bpm", "vorp", "ws_per_48",
               "off_rtg", "def_rtg"]


@router.get("/players/{pid}")
def player_card(pid: str) -> dict:
    c = ctx()
    if pid not in c.players.index or c.players.loc[pid, "source"] == "replacement":
        raise HTTPException(404, f"unknown player {pid}")
    r = c.players.loc[pid]
    pool = c.players[c.players["mp"] >= 500]
    pct = [stats.percentileofscore(pool[s].dropna(), r[s]) for s in RADAR]
    pct = [100 - x if s == "tov_pct" else x for s, x in zip(RADAR, pct, strict=False)]
    seasons = query("SELECT * FROM mart_player_season WHERE player_id = ? ORDER BY season DESC", [pid])
    league_now = nba_zone_averages()
    zones = {}
    for _, row in seasons.iterrows():
        sea = int(row["season"])
        zc = shots.nba_zones(row, nba_zone_averages(sea) if sea < config.CURRENT_SEASON else league_now)
        zones[str(sea)] = {k: {"freq": z.freq, "fg": z.fg, "lg_fg": z.lg_fg} for k, z in zc.items()}
    return _clean({**person(c, pid), "archetype": r.get("archetype"), "bpm": r["bpm"], "ts_pct": r["ts_pct"],
                   "source": r["source"],
                   "percentiles": [{"stat": s, "label": RADAR_LABELS[s], "pct": v} for s, v in zip(RADAR, pct, strict=False)],
                   "seasons": seasons[SEASON_COLS] if len(seasons) else [], "zones": zones})
