"""The hosted-demo bundle: checksum and file-name checks before anything is unpacked."""
import hashlib
import io
import tarfile

import pytest

from rosterfit import demo_data


def _bundle(tmp_path, files: dict[str, bytes]):
    path = tmp_path / "b.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


GOOD = {"rosterfit.duckdb": b"db", **{f"models/{m}": b"m" for m in demo_data.MODEL_FILES}}


def test_extracts_expected_files(tmp_path):
    path, sha = _bundle(tmp_path, GOOD)
    dest = tmp_path / "data"
    dest.mkdir()
    demo_data.extract(path, sha, dest)
    assert (dest / "rosterfit.duckdb").read_bytes() == b"db"
    assert all((dest / "models" / m).exists() for m in demo_data.MODEL_FILES)


def test_rejects_checksum_mismatch(tmp_path):
    path, _ = _bundle(tmp_path, GOOD)
    with pytest.raises(demo_data.DemoDataError, match="checksum"):
        demo_data.extract(path, "0" * 64, tmp_path)


def test_rejects_unexpected_or_traversal_paths(tmp_path):
    path, sha = _bundle(tmp_path, {**GOOD, "../evil.py": b"x"})
    with pytest.raises(demo_data.DemoDataError, match="unexpected"):
        demo_data.extract(path, sha, tmp_path)
    assert not (tmp_path.parent / "evil.py").exists()


def test_noop_when_warehouse_exists(monkeypatch, tmp_path):
    db = tmp_path / "rosterfit.duckdb"
    db.write_bytes(b"x")
    monkeypatch.setattr(demo_data.config, "DB_PATH", db)
    assert demo_data.ensure_demo_data() is False
