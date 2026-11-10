"""Model persistence (joblib) + experiment tracking (MLflow, local SQLite store).

Browse runs with:  mlflow ui --backend-store-uri sqlite:///data/mlflow.db
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

import joblib

from rosterfit import config

log = logging.getLogger("rosterfit.models")
MLFLOW_URI = f"sqlite:///{config.DATA_DIR / 'mlflow.db'}"


def save(name: str, obj: Any) -> None:
    joblib.dump(obj, config.MODEL_DIR / f"{name}.joblib")


def load(name: str) -> Any:
    path = config.MODEL_DIR / f"{name}.joblib"
    if not path.exists():
        raise FileNotFoundError(f"model '{name}' not trained - run `rosterfit train`")
    return joblib.load(path)


def _noop(params: dict | None = None, metrics: dict | None = None) -> None:
    log.info("params=%s metrics=%s", params, metrics)


@contextmanager
def tracked_run(name: str):
    """Yield log_fn(params, metrics). Tracking problems never break training."""
    try:
        import mlflow

        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment("rosterfit")
        run = mlflow.start_run(run_name=name)
    except Exception as exc:  # noqa: BLE001
        log.warning("MLflow unavailable (%s); logging to stdout", exc)
        yield _noop
        return

    def log_fn(params: dict | None = None, metrics: dict | None = None) -> None:
        if params:
            mlflow.log_params({k: str(v)[:250] for k, v in params.items()})
        if metrics:
            mlflow.log_metrics({k.replace("+", "plus"): float(v) for k, v in metrics.items()})

    try:
        yield log_fn
    finally:
        mlflow.end_run()
        del run
