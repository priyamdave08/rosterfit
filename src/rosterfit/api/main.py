"""REST API for front-office integrations.

    uvicorn rosterfit.api.main:app --reload      # docs at http://localhost:8000/docs
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from rosterfit.engine.context import Context, get_context
from rosterfit.engine.fit import best_lineups, compare_candidates, evaluate_move
from rosterfit.features.players import PROFILE_COLS

app = FastAPI(title="RosterFit API", version="0.1.0",
              description="NBA lineup optimisation and draft / free-agent / trade fit engine.")


def clean(obj: Any) -> Any:
    """Make pandas/numpy output JSON-safe (NaN -> null, numpy scalars -> python)."""
    if isinstance(obj, pd.DataFrame):
        return [clean(r) for r in obj.reset_index().to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return clean(obj.to_dict())
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if math.isnan(obj) or math.isinf(obj) else round(float(obj), 4)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def ctx() -> Context:
    return get_context()


def resolve(c: Context, pid: str) -> pd.Series:
    """'prospect:<torvik_id>' or a B-Ref player id -> profile row."""
    if pid.startswith("prospect:"):
        tid = int(pid.split(":", 1)[1])
        if tid not in c.prospects.index:
            raise HTTPException(404, f"unknown prospect {tid}")
        return c.prospect_as_player(tid)
    if pid not in c.players.index:
        raise HTTPException(404, f"unknown player {pid}")
    row = c.players.loc[pid].copy()
    row["player_id"] = pid
    return row


class LineupRequest(BaseModel):
    player_ids: list[str] = Field(..., min_length=5, max_length=5)


class MoveRequest(BaseModel):
    team: str
    incoming: list[str] = Field(..., description="B-Ref ids or 'prospect:<torvik_id>'")
    outgoing: list[str] = []


class BoardRequest(BaseModel):
    team: str
    candidates: list[str]
    talent_weight: float = Field(0.65, ge=0, le=1)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/teams")
def teams() -> list[dict]:
    return clean(ctx().teams)


@app.get("/teams/{team}/roster")
def roster(team: str) -> list[dict]:
    cols = ["player", "source", "pos", "age", "mp", "bpm", "obpm", "dbpm", "ts_pct", "usg_pct", "archetype"]
    df = ctx().team_roster(team.upper())
    if df.empty:
        raise HTTPException(404, f"no roster for {team}")
    return clean(df[[c for c in cols if c in df]])


@app.get("/teams/{team}/lineups")
def lineups(team: str, top: int = Query(10, le=100)) -> list[dict]:
    df = best_lineups(ctx(), team.upper(), top=top)
    return clean(df)


@app.post("/lineups/evaluate")
def evaluate_lineup(req: LineupRequest) -> dict:
    c = ctx()
    five = pd.DataFrame([resolve(c, p) for p in req.player_ids])
    pred = c.lineup_model.predict_lineup(five[PROFILE_COLS].astype(float))
    return clean({**{k: v for k, v in pred.items() if k != "features"}, "features": pred["features"],
                  "drivers": c.lineup_model.explain(five[PROFILE_COLS].astype(float))})


@app.get("/prospects")
def prospects(limit: int = Query(50, le=500), min_minutes: float = 150) -> list[dict]:
    p = ctx().prospects
    p = p[p["total_min"] >= min_minutes]
    cols = ["player", "team", "conf", "class_yr", "age_at_draft", "height_in", "total_min", "bpm", "grade",
            "grade_score", "expected_vorp_4yr", "bust_prob", "hit_prob", "draft_prob", "likeliest_path", "archetype"]
    return clean(p[[c for c in cols if c in p]].head(limit))


@app.get("/prospects/{torvik_id}")
def prospect(torvik_id: int, explain: bool = True) -> dict:
    c = ctx()
    if torvik_id not in c.prospects.index:
        raise HTTPException(404, "unknown prospect")
    row = c.prospects.loc[[torvik_id]]
    out = {"profile": c.prospects.loc[torvik_id], "comps": c.prospect_model.comps(row)}
    if explain:
        out["drivers"] = c.prospect_model.explain(row)
    return clean(out)


@app.get("/players/search")
def search(q: str, kind: str = Query("nba", pattern="^(nba|prospect)$")) -> list[dict]:
    c = ctx()
    df = c.search_players(q) if kind == "nba" else c.search_prospects(q)
    return clean(df[["player"] + [x for x in ("team_id", "current_team", "team", "source") if x in df]])


@app.get("/free-agents")
def free_agents(limit: int = 30) -> list[dict]:
    df = ctx().free_agents().head(limit)
    return clean(df[["player", "team_id", "mp", "bpm", "archetype"]])


@app.post("/moves/evaluate")
def move(req: MoveRequest) -> dict:
    c = ctx()
    incoming = [resolve(c, p) for p in req.incoming]
    try:
        res = evaluate_move(c, req.team.upper(), incoming, req.outgoing)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return clean({"team": res.team, "before_best": res.before_best, "after_best": res.after_best,
                  "ceiling_delta": res.ceiling_delta, "depth_delta": res.depth_delta,
                  "best_with": res.best_with, "displaces": res.displaces, "synergy": res.synergy,
                  "fit_score": {p: res.fit_score(p) for p in res.incoming},
                  "lineups_after": res.lineups_after.head(10)})


@app.post("/draft-board")
def draft_board(req: BoardRequest) -> list[dict]:
    c = ctx()
    cands = [resolve(c, p) for p in req.candidates]
    return clean(compare_candidates(c, req.team.upper(), cands, talent_weight=req.talent_weight))


@app.get("/model-card")
def model_card() -> dict:
    c = ctx()
    return clean({"lineup_model": c.lineup_model.metrics, "prospect_model": c.prospect_model.metrics,
                  "trajectory_groups": c.prospect_model.groups})
