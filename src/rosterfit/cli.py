"""Command-line entry point.

    rosterfit ingest [--refresh]   pull Basketball-Reference, Torvik, ESPN
    rosterfit build-db             build DuckDB staging views + marts (SQL)
    rosterfit train                train archetype, lineup and prospect models
    rosterfit all                  ingest + build-db + train
    rosterfit lineups SAS          print the best lineups for a team
    rosterfit board SAS            draft board for a team
    rosterfit api | app            serve FastAPI / Streamlit
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

import pandas as pd

from rosterfit import config


def _train() -> None:
    from rosterfit.features import archetypes
    from rosterfit.features.players import season_profiles
    from rosterfit.models import lineup_model, prospect_model
    from rosterfit.models.registry import save

    profiles = pd.concat([season_profiles(s) for s in range(config.LAST_FULL_SEASON - 2, config.LAST_FULL_SEASON + 1)])
    pipe, meta = archetypes.fit_archetypes(profiles)
    save("archetypes", (pipe, meta))
    logging.info("archetypes: k=%d %s", meta["k"], sorted(meta["names"].values()))
    lineup_model.train()
    prospect_model.train()


def _lineups(team: str) -> None:
    from rosterfit.engine.context import get_context
    from rosterfit.engine.fit import best_lineups

    ctx = get_context()
    print(ctx.team_roster(team)[["player", "source", "mp", "bpm", "archetype"]].head(15).to_string())
    print(best_lineups(ctx, team, top=10)[["players", "off_rtg_rel", "def_rtg_rel", "net_rtg"]].round(2).to_string())


def _board(team: str, n: int = 12) -> None:
    from rosterfit.engine.context import get_context
    from rosterfit.engine.fit import compare_candidates

    ctx = get_context()
    top = ctx.prospects.head(n)
    cands = [ctx.prospect_as_player(i) for i in top.index]
    board = compare_candidates(ctx, team, cands)
    cols = ["player", "grade", "grade_score", "bust_prob", "fit_score", "gain_vs_current_best", "synergy",
            "displaces", "board_score"]
    print(board[cols].round(2).to_string())


def _scout(name: str, team: str | None) -> None:
    from rosterfit.cloud import scouting
    from rosterfit.engine.context import get_context
    from rosterfit.engine.fit import evaluate_move

    ctx = get_context()
    hit = ctx.search_prospects(name, limit=1)
    tid = hit.index[0]
    row = ctx.prospects.loc[[tid]]
    fit = None
    if team:
        cand = ctx.prospect_as_player(tid)
        res = evaluate_move(ctx, team, [cand])
        pid = cand["player_id"]
        fit = {"fit_score": res.fit_score(pid), "synergy": res.synergy.get(pid),
               "best_lineup_net_with_him": res.best_with.get(pid), "current_best_net": res.before_best,
               "displaces": res.displaces.get(pid)}
    packet = scouting.build_packet(ctx.prospects.loc[tid], ctx.prospect_model.explain(row),
                                   ctx.prospect_model.comps(row), fit, team)
    report = scouting.generate(packet)
    print(f"[{report.provider}{' / ' + report.model if report.model else ''}]\n")
    print(report.text)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    p = argparse.ArgumentParser(prog="rosterfit")
    sub = p.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest")
    ing.add_argument("--refresh", action="store_true")
    sub.add_parser("build-db")
    sub.add_parser("train")
    al = sub.add_parser("all")
    al.add_argument("--refresh", action="store_true", help="re-download the in-progress season + rosters")
    for name in ("lineups", "board"):
        sp = sub.add_parser(name)
        sp.add_argument("team")
    sub.add_parser("api")
    sub.add_parser("app")
    # AWS
    for name in ("export-s3", "athena-ddl"):
        sp = sub.add_parser(name)
        sp.add_argument("--bucket", default=os.environ.get("ROSTERFIT_S3_BUCKET"), required=False)
        sp.add_argument("--prefix", default="rosterfit/marts")
    aq = sub.add_parser("athena-query")
    aq.add_argument("sql")
    aq.add_argument("--bucket", default=os.environ.get("ROSTERFIT_S3_BUCKET"))
    aq.add_argument("--workgroup", default="rosterfit")
    sy = sub.add_parser("sync")
    sy.add_argument("direction", choices=["push", "pull"])
    sy.add_argument("--bucket", default=os.environ.get("ROSTERFIT_S3_BUCKET"))
    sc = sub.add_parser("scout", help="AI scouting report for a prospect")
    sc.add_argument("name")
    sc.add_argument("--team", default=None)
    args = p.parse_args(argv)
    if args.cmd in ("export-s3", "athena-ddl", "athena-query", "sync") and not args.bucket:
        p.error("--bucket (or ROSTERFIT_S3_BUCKET) is required")

    if args.cmd in ("ingest", "all"):
        from rosterfit.ingest import pipeline
        pipeline.run(refresh_current=getattr(args, "refresh", False))
    if args.cmd in ("build-db", "all"):
        from rosterfit.db import warehouse
        warehouse.build()
    if args.cmd in ("train", "all"):
        _train()
    if args.cmd == "lineups":
        _lineups(args.team.upper())
    if args.cmd == "board":
        _board(args.team.upper())
    if args.cmd == "export-s3":
        from rosterfit.cloud import lake
        lake.export_to_s3(args.bucket, args.prefix)
    if args.cmd == "athena-ddl":
        from rosterfit.cloud import lake
        print(";\n\n".join(lake.athena_ddl(args.bucket, args.prefix)) + ";")
    if args.cmd == "athena-query":
        from rosterfit.cloud import lake
        print(lake.athena_query(args.sql, f"s3://{args.bucket}/athena-results/", args.workgroup).to_string())
    if args.cmd == "sync":
        from rosterfit.cloud import lake
        (lake.push_artifacts if args.direction == "push" else lake.pull_artifacts)(args.bucket)
    if args.cmd == "scout":
        _scout(args.name, args.team.upper() if args.team else None)
    if args.cmd == "api":
        subprocess.run([sys.executable, "-m", "uvicorn", "rosterfit.api.main:app", "--port", "8000"], check=True)
    if args.cmd == "app":
        app = config.ROOT / "src" / "rosterfit" / "app" / "streamlit_app.py"
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app)], check=True)


if __name__ == "__main__":
    main()
