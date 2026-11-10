---
title: RosterFit API
emoji: 🏀
colorFrom: gray
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Engine API behind the RosterFit React front end
---

The Python engine behind [RosterFit](https://github.com/priyamdave08/rosterfit). On first boot it
downloads the verified demo bundle (warehouse and trained models) and serves the FastAPI app.
Interactive docs are at `/docs`.

Set `ROSTERFIT_CORS_ORIGINS` in the Space settings to the React app's origin (for example the
Vercel URL) so browsers can call it.
