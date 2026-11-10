"""AWS data lake: publish the DuckDB marts to S3 as partitioned Parquet and query
them serverlessly with Amazon Athena (tables registered in the Glue Data Catalog).

    rosterfit export-s3 --bucket my-bucket          # write s3://my-bucket/rosterfit/marts/...
    rosterfit athena-ddl --bucket my-bucket         # print CREATE EXTERNAL TABLE statements
    rosterfit athena-query "SELECT ..." --bucket my-bucket

The same SQL that runs locally in DuckDB runs in Athena (both are ANSI SQL over
Parquet), so analysts can hit the lake from QuickSight, notebooks or the CLI
without the local database file.
"""
from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

import pandas as pd

from rosterfit import config
from rosterfit.db.warehouse import connect

log = logging.getLogger("rosterfit.cloud")

# mart -> partition column (None = unpartitioned)
LAKE_TABLES = {
    "mart_player_season": "season",
    "mart_team_season": "season",
    "mart_draft_outcomes": "draft_year",
    "mart_draft_college": "draft_year",
}
DEFAULT_PREFIX = "rosterfit/marts"
GLUE_DATABASE = "rosterfit"

_DUCK_TO_ATHENA = {
    "BIGINT": "bigint", "INTEGER": "int", "SMALLINT": "smallint", "TINYINT": "tinyint", "DOUBLE": "double",
    "FLOAT": "float", "BOOLEAN": "boolean", "VARCHAR": "string", "DATE": "date",
    "TIMESTAMP": "timestamp", "TIMESTAMP_NS": "timestamp", "TIMESTAMP WITH TIME ZONE": "timestamp",
}


def athena_type(duck_type: str) -> str:
    t = duck_type.upper()
    if t.startswith("DECIMAL"):
        return t.lower()
    return _DUCK_TO_ATHENA.get(t, "string")


def table_schema(table: str, db_path: Path | None = None) -> list[tuple[str, str]]:
    with connect(db_path, read_only=True) as con:
        rows = con.execute(f"DESCRIBE {table}").fetchall()
    return [(r[0], r[1]) for r in rows]


def write_partitioned(out_dir: Path, db_path: Path | None = None) -> list[Path]:
    """COPY each mart to Hive-partitioned Parquet under ``out_dir``."""
    written = []
    with connect(db_path, read_only=True) as con:
        for table, part in LAKE_TABLES.items():
            dest = out_dir / table
            opts = f"FORMAT PARQUET, PARTITION_BY ({part}), OVERWRITE_OR_IGNORE" if part else "FORMAT PARQUET"
            con.execute(f"COPY {table} TO '{dest}' ({opts})")
            written.extend(sorted(dest.rglob("*.parquet")))
    return written


def export_to_s3(bucket: str, prefix: str = DEFAULT_PREFIX, s3_client=None, db_path: Path | None = None) -> int:
    """Write every mart to s3://bucket/prefix/<table>/<partition>=<v>/*.parquet."""
    import boto3

    s3 = s3_client or boto3.client("s3")
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for path in write_partitioned(root, db_path):
            key = f"{prefix.rstrip('/')}/{path.relative_to(root).as_posix()}"
            s3.upload_file(str(path), bucket, key)
            n += 1
    log.info("uploaded %d parquet objects to s3://%s/%s", n, bucket, prefix)
    return n


def athena_ddl(bucket: str, prefix: str = DEFAULT_PREFIX, db_path: Path | None = None) -> list[str]:
    """CREATE DATABASE / EXTERNAL TABLE / partition-projection statements for Athena."""
    stmts = [f"CREATE DATABASE IF NOT EXISTS {GLUE_DATABASE}"]
    for table, part in LAKE_TABLES.items():
        cols = [(c, athena_type(t)) for c, t in table_schema(table, db_path) if c != part]
        col_sql = ",\n  ".join(f"`{c}` {t}" for c, t in cols)
        location = f"s3://{bucket}/{prefix.rstrip('/')}/{table}/"
        part_sql = f"\nPARTITIONED BY (`{part}` bigint)" if part else ""
        # Partition projection: Athena infers partitions from the path, no crawler or MSCK needed.
        props = ""
        if part:
            props = (f"\nTBLPROPERTIES ('projection.enabled'='true', 'projection.{part}.type'='integer', "
                     f"'projection.{part}.range'='2000,2100', "
                     f"'storage.location.template'='{location}{part}=${{{part}}}/')")
        stmts.append(f"CREATE EXTERNAL TABLE IF NOT EXISTS {GLUE_DATABASE}.{table} (\n  {col_sql}\n){part_sql}"
                     f"\nSTORED AS PARQUET\nLOCATION '{location}'{props}")
    return stmts


def athena_query(sql: str, output_location: str, workgroup: str = "primary", athena_client=None,
                 poll_seconds: float = 1.0, timeout_seconds: float = 300) -> pd.DataFrame:
    """Run a query in Athena and return the result set as a DataFrame."""
    import boto3

    ath = athena_client or boto3.client("athena")
    qid = ath.start_query_execution(QueryString=sql, WorkGroup=workgroup,
                                    QueryExecutionContext={"Database": GLUE_DATABASE},
                                    ResultConfiguration={"OutputLocation": output_location})["QueryExecutionId"]
    deadline = time.monotonic() + timeout_seconds
    while True:
        status = ath.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Athena query {state}: {status.get('StateChangeReason', '')}")
        if time.monotonic() > deadline:
            ath.stop_query_execution(QueryExecutionId=qid)
            raise TimeoutError(f"Athena query {qid} exceeded {timeout_seconds}s")
        time.sleep(poll_seconds)

    rows, header, token = [], None, None
    while True:
        kw = {"QueryExecutionId": qid, **({"NextToken": token} if token else {})}
        page = ath.get_query_results(**kw)
        data = [[c.get("VarCharValue") for c in r["Data"]] for r in page["ResultSet"]["Rows"]]
        if header is None:
            header, data = data[0], data[1:]
        rows.extend(data)
        token = page.get("NextToken")
        if not token:
            break
    df = pd.DataFrame(rows, columns=header)
    return df.apply(pd.to_numeric, errors="ignore") if len(df) else df


def default_bucket() -> str | None:
    import os

    return os.environ.get("ROSTERFIT_S3_BUCKET")


ARTIFACT_PREFIX = "rosterfit/artifacts"


def _artifact_files() -> list[Path]:
    files = [config.DB_PATH] + sorted(config.MODEL_DIR.glob("*.joblib"))
    return [f for f in files if f.exists()]


def push_artifacts(bucket: str, prefix: str = ARTIFACT_PREFIX, s3_client=None) -> int:
    """Upload the DuckDB warehouse and trained models so other services can pull them."""
    import boto3

    s3 = s3_client or boto3.client("s3")
    files = _artifact_files()
    for f in files:
        s3.upload_file(str(f), bucket, f"{prefix}/{f.relative_to(config.DATA_DIR).as_posix()}")
    log.info("pushed %d artifacts to s3://%s/%s", len(files), bucket, prefix)
    return len(files)


def pull_artifacts(bucket: str, prefix: str = ARTIFACT_PREFIX, s3_client=None) -> int:
    import boto3

    s3 = s3_client or boto3.client("s3")
    n = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix + "/"):
        for obj in page.get("Contents", []):
            rel = obj["Key"][len(prefix) + 1:]
            dest = config.DATA_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, obj["Key"], str(dest))
            n += 1
    log.info("pulled %d artifacts from s3://%s/%s", n, bucket, prefix)
    return n
