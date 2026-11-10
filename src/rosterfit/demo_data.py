"""Fetch the prebuilt demo bundle (warehouse + trained models) for hosted deployments.

A hosted demo has no time to scrape and train on boot, so it downloads a bundle
built by ``python -m rosterfit.demo_data build`` and published on the repository's
``demo-data`` branch. The download is verified against a pinned SHA-256 before
anything is extracted, and extraction only accepts the expected file names.

Local installs are unaffected: if the warehouse already exists, nothing happens.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from rosterfit import config

log = logging.getLogger("rosterfit.demo")

BUNDLE_NAME = "rosterfit-demo.tar.gz"
DEFAULT_URL = f"https://raw.githubusercontent.com/priyamdave08/rosterfit/demo-data/{BUNDLE_NAME}"
# Update together with the bundle on the demo-data branch.
BUNDLE_SHA256 = "2366913491b6b21bf440340280c82e3e6f49fef5d2a760f87fdca6ec0f8598c2"
MODEL_FILES = ("archetypes.joblib", "lineup_model.joblib", "prospect_model.joblib", "trajectory_gmm.joblib")
ALLOWED = {"rosterfit.duckdb", *(f"models/{m}" for m in MODEL_FILES)}


class DemoDataError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(bundle: Path, expected_sha: str, dest: Path = config.DATA_DIR) -> None:
    """Verify ``bundle`` and unpack only the allowed files into ``dest``."""
    actual = _sha256(bundle)
    if actual != expected_sha:
        raise DemoDataError(f"demo bundle checksum mismatch (expected {expected_sha[:12]}…, got {actual[:12]}…)")
    with tarfile.open(bundle, "r:gz") as tar:
        members = tar.getmembers()
        names = {m.name for m in members}
        unexpected = names - ALLOWED - {"models"}
        if unexpected or not {"rosterfit.duckdb"} <= names:
            raise DemoDataError(f"unexpected demo bundle contents: {sorted(unexpected) or sorted(names)}")
        (dest / "models").mkdir(parents=True, exist_ok=True)
        tar.extractall(dest, members=[m for m in members if m.isfile()], filter="data")


def ensure_demo_data() -> bool:
    """Download and unpack the demo bundle if the warehouse is missing. Returns True if it did."""
    if config.DB_PATH.exists():
        return False
    url = os.environ.get("ROSTERFIT_DEMO_BUNDLE_URL", DEFAULT_URL)
    sha = os.environ.get("ROSTERFIT_DEMO_BUNDLE_SHA256", BUNDLE_SHA256)
    log.info("warehouse missing; downloading demo bundle from %s", url)
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / BUNDLE_NAME
        try:
            with urllib.request.urlopen(url, timeout=120) as resp, target.open("wb") as out:
                while chunk := resp.read(1 << 20):
                    out.write(chunk)
        except OSError as exc:
            raise DemoDataError(f"could not download the demo bundle from {url}: {exc}") from exc
        extract(target, sha)
    return True


def build(out: Path) -> str:
    """Pack the local warehouse and models into ``out``; returns its SHA-256."""
    missing = [p for p in [config.DB_PATH, *(config.MODEL_DIR / m for m in MODEL_FILES)] if not p.exists()]
    if missing:
        raise DemoDataError(f"build the warehouse and train first (missing: {', '.join(map(str, missing))})")
    with tarfile.open(out, "w:gz") as tar:
        tar.add(config.DB_PATH, arcname="rosterfit.duckdb")
        for m in MODEL_FILES:
            tar.add(config.MODEL_DIR / m, arcname=f"models/{m}")
    return _sha256(out)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        print(build(Path(sys.argv[2])))
    else:
        sys.exit("usage: python -m rosterfit.demo_data build <output.tar.gz>")
