"""Hugging Face Space entry point for the RosterFit API (free Gradio SDK tier).

Spaces on the free tier run `python app.py` and expect a web server on port 7860. This fetches
the RosterFit engine from GitHub (branch or commit in ROSTERFIT_REF, default main), points it at
a writable data folder, and serves the same FastAPI app the Dockerfile serves. The engine itself
is unchanged; on first boot its lifespan hook downloads and verifies the pinned demo bundle.
"""

import os
import subprocess
import sys
from pathlib import Path

try:  # present on Hugging Face Spaces; absent when this file is rehearsed locally
    import spaces
except ImportError:
    spaces = None

if spaces is not None:
    # Free Gradio Spaces run on ZeroGPU hardware, which refuses to start unless at least one
    # function is marked for the GPU. The engine runs entirely on CPU and never calls this.
    @spaces.GPU
    def gpu_probe() -> None:
        return None

REPO = "https://github.com/priyamdave08/rosterfit.git"
REF = os.environ.get("ROSTERFIT_REF", "main")
ENGINE = Path(__file__).resolve().parent / "engine"

if not (ENGINE / "src" / "rosterfit").is_dir():
    ENGINE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=ENGINE, check=True)
    subprocess.run(["git", "fetch", "-q", "--depth", "1", REPO, REF], cwd=ENGINE, check=True)
    subprocess.run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=ENGINE, check=True)

os.environ.setdefault("ROSTERFIT_ROOT", str(ENGINE))
sys.path.insert(0, str(ENGINE / "src"))

import uvicorn  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402

from rosterfit.api.main import app  # noqa: E402


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """The Space's landing page is the interactive API documentation."""
    return RedirectResponse("/docs")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
