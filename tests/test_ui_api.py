"""The React front end's API must show exactly what the Streamlit app shows.

Each test computes a value the way the Streamlit page does and checks the /ui endpoint
returns the same thing (to the API's 4-decimal JSON precision).
"""
import pytest
from fastapi.testclient import TestClient
from scipy import stats

from rosterfit.viz import shots
from tests.conftest import requires_data

pytestmark = requires_data


@pytest.fixture(scope="module")
def client():
    from rosterfit.api.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def ctx():
    from rosterfit.engine.context import get_context

    return get_context()


def test_lineups_match_engine(client, ctx):
    from rosterfit.engine.fit import best_lineups

    bl = best_lineups(ctx, "SAS", top=None)
    body = client.get("/ui/teams/SAS/lineups", params={"top": 15}).json()
    assert body["count"] == len(bl)
    for row, (rank, ref) in zip(body["lineups"], bl.head(15).iterrows(), strict=True):
        assert row["rank"] == rank and row["ids"] == list(ref["player_ids"])
        assert row["net"] == pytest.approx(ref["net_rtg"], abs=1e-4)
        assert row["def"] == pytest.approx(-ref["def_rtg_rel"], abs=1e-4)
        assert all(p["jersey"] for p in row["players"])           # every Spurs starter has a number


def test_custom_lineup_matches_streamlit_panel(client, ctx):
    from rosterfit.app import common

    ids = client.get("/ui/teams/SAS/lineups", params={"top": 1}).json()["lineups"][0]["ids"]
    body = client.post("/ui/lineup", json={"team": "SAS", "ids": ids}).json()
    ref = common.lineup_metrics(ids)
    assert body["metrics"]["net"] == pytest.approx(ref["Net"], abs=1e-4)
    assert body["metrics"]["def"] == pytest.approx(ref["Defense vs avg"], abs=1e-4)
    assert body["rank"] == 1 and body["of"] > 100
    five = common.five_frame(ids)
    _, summary = shots.spacing_map(five.assign(player=five["player"].astype(str)))
    assert body["spacing"]["perimeter_threats"] == summary["perimeter_threats"]
    assert body["spacing"]["paint_bodies"] == summary["paint_bodies"]


def test_lineup_rejects_duplicates(client):
    r = client.post("/ui/lineup", json={"team": "SAS", "ids": ["foxde01"] * 5})
    assert r.status_code == 400


def test_board_matches_draft_room_filters(client, ctx):
    p = ctx.prospects
    ref = p[(p["total_min"] >= 250) & (p["draft_prob"] >= 0.5) & p["class_yr"].isin(["Fr", "So", "Jr", "Sr"])]
    ref = ref.sort_values("grade_score", ascending=False)
    body = client.get("/ui/prospects").json()
    assert body["count"] == len(ref)
    assert [r["torvik_id"] for r in body["prospects"][:20]] == list(ref.index[:20])
    assert body["prospects"][0]["grade_score"] == pytest.approx(ref.iloc[0]["grade_score"], abs=1e-4)


def test_player_card_percentiles_match(client, ctx):
    body = client.get("/ui/players/wembavi01").json()
    pool = ctx.players[ctx.players["mp"] >= 500]
    r = ctx.players.loc["wembavi01"]
    bpm = next(x for x in body["percentiles"] if x["stat"] == "bpm")
    assert bpm["pct"] == pytest.approx(stats.percentileofscore(pool["bpm"].dropna(), r["bpm"]), abs=1e-4)
    tov = next(x for x in body["percentiles"] if x["stat"] == "tov_pct")
    assert tov["pct"] == pytest.approx(100 - stats.percentileofscore(pool["tov_pct"].dropna(), r["tov_pct"]), abs=1e-4)


def test_draft_fit_matches_compare_candidates(client, ctx):
    from rosterfit.engine.fit import compare_candidates

    ids = [r["torvik_id"] for r in client.get("/ui/prospects").json()["prospects"][:3]]
    body = client.post("/ui/draft-fit", json={"team": "SAS", "prospects": ids}).json()
    ref = compare_candidates(ctx, "SAS", [ctx.prospect_as_player(i) for i in ids], talent_weight=0.65)
    assert [r["player"] for r in body["rows"]] == list(ref["player"])
    assert body["rows"][0]["board_score"] == pytest.approx(ref.iloc[0]["board_score"], abs=1e-4)
    assert body["best_with_top"]["highlight"] == ref.iloc[0]["player_id"]


def test_move_matches_evaluate_move(client, ctx):
    from rosterfit.engine.fit import evaluate_move

    fa = client.get("/ui/teams/SAS/move-pool").json()["players"][0]["id"]
    body = client.post("/ui/move", json={"team": "SAS", "incoming": [fa]}).json()
    row = ctx.players.loc[fa].copy()
    row["player_id"] = fa
    ref = evaluate_move(ctx, "SAS", [row])
    assert body["after_best"] == pytest.approx(ref.after_best, abs=1e-4)
    assert body["players"][0]["fit_score"] == pytest.approx(ref.fit_score(fa), abs=1e-4)
    bad = client.post("/ui/move", json={"team": "SAS", "incoming": [fa], "outgoing": ["tatumja01"]})
    assert bad.status_code == 400


def test_player_search_and_meta(client):
    assert client.get("/ui/players", params={"q": "wemb"}).json()["players"][0]["id"] == "wembavi01"
    assert client.get("/ui/players", params={"q": "SAS"}).json()["count"] >= 13
    meta = client.get("/ui/meta").json()
    assert len(meta["teams"]) == 30 and all(t["color"].startswith("#") for t in meta["teams"])
    assert client.get("/ui/teams/XXX/lineups").status_code == 404
