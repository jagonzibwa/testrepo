"""Database connections (created once, reused by every request)."""
from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src import config


@lru_cache
def sql_engine() -> Engine:
    return create_engine(config.mysql_url(), pool_pre_ping=True, pool_recycle=1800)


@lru_cache
def mongo_client() -> MongoClient:
    return MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=3000)


def mongo_collection() -> Collection:
    return mongo_client()[config.MONGO_DATABASE][config.MONGO_COLLECTION]
