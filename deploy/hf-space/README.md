---
title: RosterFit API
emoji: 🏀
colorFrom: gray
colorTo: gray
sdk: gradio
sdk_version: 6.31.0
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
short_description: Engine API behind the RosterFit React front end
---

The Python engine behind [RosterFit](https://github.com/priyamdave08/rosterfit). `app.py` fetches
the engine from GitHub, and on first boot it downloads the verified demo bundle (warehouse and
trained models) and serves the FastAPI app on the free tier (ZeroGPU hardware; the engine itself
runs on CPU). Interactive docs are at `/docs`.

The `Dockerfile` here serves the same app on any Docker host (or a Docker Space on a paid plan).

Set `ROSTERFIT_CORS_ORIGINS` in the Space settings to the React app's origin (for example the
Vercel URL) so browsers can call it.
