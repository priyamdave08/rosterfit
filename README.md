# RosterFit demo data

`rosterfit-demo.tar.gz` holds the built DuckDB warehouse and trained models that the hosted
RosterFit demo downloads on first boot (see `src/rosterfit/demo_data.py` on `main`). The app
checks its SHA-256 before unpacking.

Rebuild it from a local install with `python -m rosterfit.demo_data build rosterfit-demo.tar.gz`,
then update `BUNDLE_SHA256` on `main` in the same change.

Derived from Basketball-Reference, Bart Torvik and ESPN data for non-commercial demonstration.
