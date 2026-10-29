"""Create the MongoDB collection (validator + indexes) and load the raw CSV.

Usage:
    python database/load_mongodb.py

Also exports a few representative documents to
database/mongodb/sample_documents.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
from bson import json_util
from pymongo import ASCENDING, DESCENDING, MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.records import record_to_document  # noqa: E402

VALIDATOR_PATH = ROOT / "database" / "mongodb" / "validator.json"
SAMPLES_PATH = ROOT / "database" / "mongodb" / "sample_documents.json"


def raw_to_records(raw: pd.DataFrame) -> list[dict]:
    """Group the flat CSV into one record per hour with a list of conditions."""
    raw = raw.copy()
    raw["date_time"] = pd.to_datetime(raw["date_time"])
    raw["holiday"] = raw["holiday"].replace({"None": None})
    day = raw["date_time"].dt.date
    holiday_by_day = raw.dropna(subset=["holiday"]).groupby(day)["holiday"].first()
    raw["holiday"] = day.map(holiday_by_day)

    records = []
    for ts, g in raw.groupby("date_time", sort=True):
        first = g.iloc[0]
        conditions, seen = [], set()
        for m, d in zip(g.weather_main, g.weather_description):
            if (m, d) not in seen:
                seen.add((m, d))
                conditions.append({"main": m, "description": d})
        records.append({
            "date_time": ts.to_pydatetime(),
            "traffic_volume": int(first.traffic_volume),
            "temp": float(first.temp),
            "rain_1h": float(first.rain_1h),
            "snow_1h": float(first.snow_1h),
            "clouds_all": int(first.clouds_all),
            "holiday": None if pd.isna(first.holiday) else str(first.holiday),
            "weather": conditions,
        })
    return records


def setup_collection(db):
    name = config.MONGO_COLLECTION
    if name in db.list_collection_names():
        db.drop_collection(name)
    validator = json.loads(VALIDATOR_PATH.read_text(encoding="utf-8"))
    coll = db.create_collection(name, validator=validator, validationLevel="strict")
    coll.create_index([("timestamp", ASCENDING)], unique=True, name="uq_timestamp")
    coll.create_index([("calendar.day_of_week", ASCENDING), ("calendar.hour", ASCENDING)], name="idx_dow_hour")
    coll.create_index([("weather.conditions.main", ASCENDING)], name="idx_condition_main")
    coll.create_index([("holiday", ASCENDING)], name="idx_holiday",
                      partialFilterExpression={"holiday": {"$type": "string"}})
    return coll


def export_samples(coll) -> None:
    samples = [
        coll.find_one(sort=[("timestamp", DESCENDING)]),                         # latest reading
        coll.find_one({"weather.conditions.1": {"$exists": True}}),              # several conditions
        coll.find_one({"holiday": "Christmas Day", "calendar.hour": 8}),         # holiday hour
        coll.find_one({"weather.conditions.main": "Snow", "calendar.hour": 17}), # snowy rush hour
    ]
    SAMPLES_PATH.write_text(json_util.dumps(samples, indent=2, json_options=json_util.RELAXED_JSON_OPTIONS),
                            encoding="utf-8")
    print("Sample documents ->", SAMPLES_PATH.relative_to(ROOT))


def main() -> None:
    t0 = time.time()
    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[config.MONGO_DATABASE]
    coll = setup_collection(db)
    docs = [record_to_document(r) for r in raw_to_records(pd.read_csv(config.RAW_DATA_PATH))]
    coll.insert_many(docs, ordered=False)
    print(f"Inserted {coll.count_documents({}):,} documents into {db.name}.{coll.name}")
    print("Indexes:", [ix["name"] for ix in coll.list_indexes()])
    export_samples(coll)
    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
