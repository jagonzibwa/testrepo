"""Run every SQL and MongoDB query and save the queries + results as Markdown.

Usage:
    python database/run_queries.py

Writes:
    outputs/query_results/sql_query_results.md
    outputs/query_results/mongodb_query_results.md
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pymysql
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

SQL_FILE = ROOT / "database" / "sql" / "queries.sql"
OUT_DIR = config.QUERY_RESULTS_DIR


# --------------------------------------------------------------------------- #
# SQL
# --------------------------------------------------------------------------- #
def parse_sql_queries(text: str) -> list[tuple[str, str]]:
    """Return (title, sql) pairs using the `-- name:` markers."""
    blocks = re.split(r"^-- name:\s*", text, flags=re.M)[1:]
    out = []
    for block in blocks:
        title, _, body = block.partition("\n")
        sql = "\n".join(l for l in body.splitlines() if not l.strip().startswith("--")).strip().rstrip(";")
        out.append((title.strip(), sql))
    return out


def run_sql() -> str:
    conn = pymysql.connect(host=config.MYSQL_HOST, port=config.MYSQL_PORT, user=config.MYSQL_USER,
                           password=config.MYSQL_PASSWORD, database=config.MYSQL_DATABASE)
    parts = ["# SQL query results (MySQL)\n",
             f"_Generated {datetime.now():%Y-%m-%d %H:%M} by `database/run_queries.py` from `database/sql/queries.sql`._\n"]
    for title, sql in parse_sql_queries(SQL_FILE.read_text(encoding="utf-8")):
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [c[0] for c in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=cols)
        parts += [f"## {title}\n", "```sql", sql + ";", "```\n",
                  f"**Result ({len(df)} rows):**\n", df.to_markdown(index=False), "\n"]
        print(f"[SQL]   {title}: {len(df)} rows")
    conn.close()
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# MongoDB (same logic as database/mongodb/queries.js)
# --------------------------------------------------------------------------- #
def mongo_queries(coll):
    yield ("M1 Latest reading (find + sort + limit)",
           'db.traffic_readings.find({}, {_id: 0, timestamp: 1, traffic_volume: 1, "weather.conditions": 1, holiday: 1})\n'
           '  .sort({timestamp: -1}).limit(1)',
           list(coll.find({}, {"_id": 0, "timestamp": 1, "traffic_volume": 1, "weather.conditions": 1, "holiday": 1})
                .sort("timestamp", -1).limit(1)))

    start, end = datetime(2018, 9, 24, 6), datetime(2018, 9, 24, 10)
    yield ("M2 Records in a date range (Mon 24 Sep 2018, 06:00-10:00)",
           'db.traffic_readings.find(\n'
           '  {timestamp: {$gte: ISODate("2018-09-24T06:00:00Z"), $lte: ISODate("2018-09-24T10:00:00Z")}},\n'
           '  {_id: 0, timestamp: 1, traffic_volume: 1, "weather.temp_k": 1, "weather.conditions.main": 1}\n'
           ').sort({timestamp: 1})',
           list(coll.find({"timestamp": {"$gte": start, "$lte": end}},
                          {"_id": 0, "timestamp": 1, "traffic_volume": 1, "weather.temp_k": 1,
                           "weather.conditions.main": 1}).sort("timestamp", 1)))

    m3 = [
        {"$match": {"calendar.is_weekend": False, "calendar.hour": {"$in": [7, 8, 16, 17]}, "holiday": None}},
        {"$set": {"primary": {"$first": "$weather.conditions"}}},
        {"$group": {"_id": "$primary.main", "rush_hours": {"$sum": 1}, "avg_volume": {"$avg": "$traffic_volume"}}},
        {"$match": {"rush_hours": {"$gte": 30}}},
        {"$project": {"_id": 0, "weather_main": "$_id", "rush_hours": 1, "avg_volume": {"$round": ["$avg_volume", 0]}}},
        {"$sort": {"avg_volume": -1}},
    ]
    yield ("M3 Weekday rush-hour volume by primary weather condition (aggregation)",
           "db.traffic_readings.aggregate(" + json.dumps(m3, indent=2) + ")", list(coll.aggregate(m3)))

    m4 = [
        {"$match": {"timestamp": {"$gte": datetime(2016, 11, 24), "$lt": datetime(2017, 1, 1)}}},
        {"$group": {"_id": {"$dateTrunc": {"date": "$timestamp", "unit": "day"}},
                    "day_volume": {"$sum": "$traffic_volume"}, "hours": {"$sum": 1}}},
        {"$setWindowFields": {"sortBy": {"_id": 1}, "output": {
            "ma_7day": {"$avg": "$day_volume", "window": {"documents": [-6, 0]}},
            "prev_day": {"$shift": {"output": "$day_volume", "by": -1}}}}},
        {"$project": {"_id": 0, "day": {"$dateToString": {"date": "$_id", "format": "%Y-%m-%d"}}, "hours": 1,
                      "day_volume": 1, "ma_7day": {"$round": ["$ma_7day", 0]},
                      "change_vs_prev_day": {"$subtract": ["$day_volume", "$prev_day"]}}},
        {"$sort": {"day": -1}},
        {"$limit": 14},
    ]
    m4_text = json.dumps(m4, indent=2, default=lambda d: f'ISODate("{d:%Y-%m-%dT%H:%M:%S}Z")')
    yield ("M4 Daily totals with 7-day moving average, Dec 2016 ($setWindowFields)",
           "db.traffic_readings.aggregate(" + m4_text + ")", list(coll.aggregate(m4)))

    m5 = [
        {"$match": {"holiday": {"$type": "string"}}},
        {"$group": {"_id": "$holiday", "hours": {"$sum": 1}, "avg_volume": {"$avg": "$traffic_volume"},
                    "peak_volume": {"$max": "$traffic_volume"}}},
        {"$project": {"_id": 0, "holiday": "$_id", "hours": 1, "peak_volume": 1,
                      "avg_volume": {"$round": ["$avg_volume", 0]}}},
        {"$sort": {"avg_volume": 1}},
    ]
    yield ("M5 Holiday traffic summary (aggregation)",
           "db.traffic_readings.aggregate(" + json.dumps(m5, indent=2) + ")", list(coll.aggregate(m5)))


def _flatten(docs: list[dict]) -> pd.DataFrame:
    df = pd.json_normalize(docs)
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, list)).any():
            df[col] = df[col].map(lambda v: ", ".join(
                " / ".join(str(x) for x in i.values()) if isinstance(i, dict) else str(i) for i in v))
    return df


def run_mongo() -> str:
    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    coll = client[config.MONGO_DATABASE][config.MONGO_COLLECTION]
    parts = ["# MongoDB query results\n",
             f"_Generated {datetime.now():%Y-%m-%d %H:%M} by `database/run_queries.py`. "
             f"The same queries are in `database/mongodb/queries.js` for mongosh._\n"]
    for title, text, docs in mongo_queries(coll):
        parts += [f"## {title}\n", "```javascript", text, "```\n",
                  f"**Result ({len(docs)} documents):**\n", _flatten(docs).to_markdown(index=False), "\n"]
        print(f"[Mongo] {title}: {len(docs)} docs")
    return "\n".join(parts)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sql_query_results.md").write_text(run_sql(), encoding="utf-8")
    (OUT_DIR / "mongodb_query_results.md").write_text(run_mongo(), encoding="utf-8")
    print("Saved results to", OUT_DIR.relative_to(ROOT))


if __name__ == "__main__":
    main()
