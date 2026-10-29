"""Create the MySQL schema and load the raw Metro traffic CSV into it.

Usage:
    python database/load_mysql.py            # (re)creates all tables and loads data

Connection settings come from .env (see .env.example).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

SCHEMA_PATH = ROOT / "database" / "sql" / "schema.sql"
CHUNK = 5000


def connect(database: str | None = None) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=config.MYSQL_HOST, port=config.MYSQL_PORT,
        user=config.MYSQL_USER, password=config.MYSQL_PASSWORD,
        database=database, autocommit=False, charset="utf8mb4",
    )


def split_sql(script: str) -> list[str]:
    """Split a .sql file into statements (drops `--` comment lines)."""
    lines = [l for l in script.splitlines() if not l.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def create_schema() -> None:
    conn = connect()
    with conn.cursor() as cur:
        for stmt in split_sql(SCHEMA_PATH.read_text(encoding="utf-8")):
            cur.execute(stmt)
    conn.commit()
    conn.close()
    print("Schema created from", SCHEMA_PATH.relative_to(ROOT))


def build_tables(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Normalise the flat CSV into the four relational tables."""
    raw = raw.copy()
    raw["date_time"] = pd.to_datetime(raw["date_time"])
    raw["holiday"] = raw["holiday"].replace({"None": None})
    # keep the order in which conditions appear for the same hour
    raw["condition_rank"] = raw.groupby("date_time").cumcount() + 1

    # holidays: one row per date
    hol = (raw.dropna(subset=["holiday"])
              .assign(holiday_date=lambda d: d.date_time.dt.date)
              .drop_duplicates("holiday_date")[["holiday_date", "holiday"]]
              .rename(columns={"holiday": "holiday_name"})
              .sort_values("holiday_date").reset_index(drop=True))
    hol.insert(0, "holiday_id", range(1, len(hol) + 1))

    # weather_conditions lookup
    cond = (raw[["weather_main", "weather_description"]].drop_duplicates()
               .sort_values(["weather_main", "weather_description"]).reset_index(drop=True))
    cond.insert(0, "condition_id", range(1, len(cond) + 1))

    # traffic_observations: first row of every hour (numeric values are identical
    # or near-identical within an hour, see EDA A3)
    obs = raw.sort_values(["date_time", "condition_rank"]).drop_duplicates("date_time").reset_index(drop=True)
    obs.insert(0, "observation_id", range(1, len(obs) + 1))
    hol_by_date = dict(zip(hol.holiday_date, hol.holiday_id))
    obs["holiday_id"] = obs.date_time.dt.date.map(hol_by_date)
    obs = obs[["observation_id", "date_time", "traffic_volume", "temp", "rain_1h",
               "snow_1h", "clouds_all", "holiday_id"]]

    # observation_weather junction
    ow = (raw.merge(obs[["observation_id", "date_time"]], on="date_time")
             .merge(cond, on=["weather_main", "weather_description"])
             [["observation_id", "condition_id", "condition_rank"]]
             .drop_duplicates(["observation_id", "condition_id"]))
    return {"holidays": hol, "weather_conditions": cond,
            "traffic_observations": obs, "observation_weather": ow}


def _rows(df: pd.DataFrame) -> list[tuple]:
    clean = df.astype(object).where(pd.notna(df), None)
    out = []
    for row in clean.itertuples(index=False, name=None):
        out.append(tuple(v.to_pydatetime() if isinstance(v, pd.Timestamp) else v for v in row))
    return out


def insert(conn, table: str, df: pd.DataFrame) -> None:
    cols = ", ".join(df.columns)
    marks = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({marks})"
    rows = _rows(df)
    with conn.cursor() as cur:
        for i in range(0, len(rows), CHUNK):
            cur.executemany(sql, rows[i:i + CHUNK])
    conn.commit()
    print(f"  {table:<22} {len(rows):>7,} rows")


def main() -> None:
    t0 = time.time()
    create_schema()
    raw = pd.read_csv(config.RAW_DATA_PATH)
    tables = build_tables(raw)
    conn = connect(config.MYSQL_DATABASE)
    print("Loading:")
    for name in ["holidays", "weather_conditions", "traffic_observations", "observation_weather"]:
        insert(conn, name, tables[name])
    conn.close()
    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
