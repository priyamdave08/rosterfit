"""AWS integrations, tested against moto (no real AWS calls) and a fake Claude client."""
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest

from rosterfit.cloud import lake, scouting

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")


@pytest.fixture
def tiny_db(tmp_path):
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE mart_player_season AS SELECT * FROM (VALUES (2025,'a',1.5::DOUBLE),(2026,'b',-0.5::DOUBLE)) t(season, player_id, bpm)")
    con.execute("CREATE TABLE mart_team_season AS SELECT * FROM (VALUES (2026,'SAS',8.2)) t(season, team_abbr, net_rtg)")
    con.execute("CREATE TABLE mart_draft_outcomes AS SELECT * FROM (VALUES (2020,'x',1,0.4)) t(draft_year, player_id, yr, vorp)")
    con.execute("CREATE TABLE mart_draft_college AS SELECT * FROM (VALUES (2020,'x','Duke')) t(draft_year, player_id, team)")
    con.close()
    return path


def test_export_to_s3_writes_hive_partitions(tiny_db, monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with moto.mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="lake")
        n = lake.export_to_s3("lake", s3_client=s3, db_path=tiny_db)
        keys = [o["Key"] for o in s3.list_objects_v2(Bucket="lake")["Contents"]]
    assert n == len(keys) >= 5
    assert any("mart_player_season/season=2025/" in k for k in keys)
    assert any("mart_draft_outcomes/draft_year=2020/" in k for k in keys)


def test_athena_ddl_uses_partition_projection(tiny_db):
    ddl = lake.athena_ddl("lake", db_path=tiny_db)
    player = next(s for s in ddl if "mart_player_season" in s)
    assert "PARTITIONED BY (`season` bigint)" in player
    assert "'projection.enabled'='true'" in player
    assert "`bpm` double" in player and "`season` bigint," not in player   # partition col not duplicated
    assert ddl[0].startswith("CREATE DATABASE")


def test_artifact_roundtrip(tmp_path, monkeypatch):
    from rosterfit import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "rosterfit.duckdb")
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "lineup_model.joblib").write_bytes(b"model")
    config.DB_PATH.write_bytes(b"db")
    with moto.mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="art")
        assert lake.push_artifacts("art", s3_client=s3) == 2
        config.DB_PATH.unlink()
        assert lake.pull_artifacts("art", s3_client=s3) == 2
    assert config.DB_PATH.read_bytes() == b"db"


# ----------------------------------------------------------------- scouting reports
@pytest.fixture
def packet():
    prospect = pd.Series({"player": "Test Prospect", "team": "State", "class_yr": "So", "grade": "B+",
                          "grade_score": 82.0, "expected_vorp_4yr": 1.7, "hit_prob": 0.31, "bust_prob": 0.22,
                          "likeliest_path": "Starter", "archetype": "Rim-Running Anchor", "bpm": 9.1})
    drivers = pd.DataFrame({"feature": ["blk_per40", "age_at_draft"], "value": [3.1, 22.4],
                            "impact_vorp": [0.4, -0.3]})
    return scouting.build_packet(prospect, drivers, None, {"fit_score": 61.0, "synergy": 0.4, "displaces": "X"}, "SAS")


def test_packet_is_json_safe(packet):
    import json

    json.dumps(packet)
    assert packet["model_drivers"][0]["label"] == "blocks per 40"


def test_template_report_without_llm(packet):
    rep = scouting.generate(packet, provider="none")
    assert rep.provider == "template"
    assert "blocks per 40" in rep.text and "age at draft" in rep.text
    assert "\u2014" not in rep.text                     # house style: no em dashes


class FakeClient:
    def __init__(self, stop_reason="end_turn"):
        self.calls = []
        self.stop_reason = stop_reason
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self.stop_reason, model=kw["model"],
                               content=[SimpleNamespace(type="text", text="Bottom line: draft him.")])


def test_generate_calls_claude_with_packet(packet):
    fake = FakeClient()
    rep = scouting.generate(packet, provider="anthropic", client=fake, model="claude-opus-5-5")
    assert rep.text == "Bottom line: draft him." and rep.model == "claude-opus-5-5"
    call = fake.calls[0]
    assert "Test Prospect" in call["messages"][0]["content"]
    assert call["output_config"] == {"effort": "medium"}
    assert "thinking" not in call                       # Opus 5.5: adaptive thinking is the default


def test_refusal_falls_back_to_template(packet):
    rep = scouting.generate(packet, provider="anthropic", client=FakeClient("refusal"), model="m")
    assert rep.provider.startswith("template")
