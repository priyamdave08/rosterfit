FROM python:3.12-slim

# libgomp: OpenMP runtime for XGBoost / scikit-learn on Linux.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 ROSTERFIT_ROOT=/app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[xgb,aws,api,train]"

COPY .streamlit ./.streamlit
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /app/data

EXPOSE 8501 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["app"]
