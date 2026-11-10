"""End-to-end checks against the real warehouse and trained models (skipped in CI
unless `rosterfit all` has been run)."""
import pytest
from fastapi.testclient import TestClient

from tests.conftest import requires_data

pytestmark = requires_data


@pytest.fixture(scope="module")
def client():
    from rosterfit.api.main import app

    return TestClient(app)


def test_sql_marts_are_consistent():
    from rosterfit.db.warehouse import query

    teams = query("SELECT season, count(*) n FROM mart_team_season GROUP BY 1")
    assert (teams["n"] == 30).all()
    dupes = query("SELECT count(*) - count(DISTINCT (season, player_id)) d FROM mart_player_season")["d"][0]
    assert dupes == 0
    links = query("SELECT avg(name_sim) s FROM mart_draft_college")["s"][0]
    assert links > 0.95


def test_name_key_macro():
    from rosterfit.db.warehouse import query

    k = query("SELECT name_key('Nikola Jokić') a, name_key('Jaren Jackson Jr.') b")
    assert k["a"][0] == "nikola jokic" and k["b"][0] == "jaren jackson"


def test_api_lineups(client):
    r = client.get("/teams/SAS/lineups", params={"top": 3})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3 and body[0]["net_rtg"] >= body[1]["net_rtg"]


def test_api_prospects_and_detail(client):
    board = client.get("/prospects", params={"limit": 5}).json()
    assert len(board) == 5 and {"grade", "bust_prob", "hit_prob"} <= set(board[0])
    detail = client.get(f"/prospects/{board[0]['torvik_id']}", params={"explain": False}).json()
    assert len(detail["comps"]) >= 5


def test_api_trade_evaluation(client):
    roster = client.get("/teams/SAS/roster").json()
    fa = client.get("/free-agents", params={"limit": 1}).json()
    if not fa:
        pytest.skip("no unsigned players right now")
    r = client.post("/moves/evaluate", json={"team": "SAS", "incoming": [fa[0]["player_id"]],
                                             "outgoing": [roster[-1]["player_id"]]})
    assert r.status_code == 200
    assert 0 <= list(r.json()["fit_score"].values())[0] <= 100


def test_model_card_beats_baselines(client):
    card = client.get("/model-card").json()
    lm, pm = card["lineup_model"], card["prospect_model"]
    assert lm["net_mae"] <= lm["net_mae_bpm_baseline"]
    assert pm["ev_spearman_stats"] > pm["ev_spearman_pick"]


def test_api_rejects_impossible_moves(client):
    roster = client.get("/teams/SAS/roster").json()
    own = roster[0]["player_id"]
    other = client.get("/teams/BOS/roster").json()[0]["player_id"]
    r = client.post("/moves/evaluate", json={"team": "SAS", "incoming": [other], "outgoing": [other]})
    assert r.status_code == 400 and "not on SAS" in r.json()["detail"]
    r = client.post("/moves/evaluate", json={"team": "SAS", "incoming": [own]})
    assert r.status_code == 400 and "already on SAS" in r.json()["detail"]


def test_api_search_ranks_prefix_first(client):
    hits = client.get("/players/search", params={"q": "wemb"}).json()
    assert hits[0]["player"] == "Victor Wembanyama"
