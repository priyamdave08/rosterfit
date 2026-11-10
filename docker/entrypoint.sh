#!/bin/sh
# Container entrypoint.
#   app      Streamlit dashboard on :8501
#   api      FastAPI on :8000
#   refresh  full pipeline (ingest -> SQL marts -> train), then publish to S3
#   <other>  passed straight to the rosterfit CLI
set -e

pull_if_configured() {
  if [ -n "$ROSTERFIT_S3_BUCKET" ]; then
    rosterfit sync pull --bucket "$ROSTERFIT_S3_BUCKET" || echo "no artifacts in S3 yet"
  fi
}

case "$1" in
  app)
    pull_if_configured
    exec streamlit run src/rosterfit/app/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
    ;;
  api)
    pull_if_configured
    exec uvicorn rosterfit.api.main:app --host 0.0.0.0 --port 8000
    ;;
  refresh)
    pull_if_configured
    rosterfit all --refresh
    if [ -n "$ROSTERFIT_S3_BUCKET" ]; then
      rosterfit export-s3 --bucket "$ROSTERFIT_S3_BUCKET"
      rosterfit sync push --bucket "$ROSTERFIT_S3_BUCKET"
    fi
    ;;
  *)
    exec rosterfit "$@"
    ;;
esac
