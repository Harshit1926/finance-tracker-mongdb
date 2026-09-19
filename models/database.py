"""
DatabaseManager
---------------
Single wrapper around the MongoDB Atlas connection. Every other class asks
this object for a collection instead of importing pymongo directly.
"""

import os
from datetime import timezone
from pymongo import MongoClient, ASCENDING, DESCENDING


class DatabaseManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, uri=None, db_name=None):
        if self._initialized:
            return

        uri = uri or os.getenv("MONGO_URI")
        db_name = db_name or os.getenv("MONGO_DB_NAME", "finance_tracker")

        if not uri:
            raise ValueError("MONGO_URI is not set. Add it to your .env file.")

        # tz_aware=True makes pymongo return timezone-aware datetimes on reads
        # (UTC), matching the timezone-aware datetimes we write throughout
        # the app (datetime.now(timezone.utc)). Without this, reads come
        # back naive and comparisons like "now > expires_at" raise
        # TypeError: can't compare offset-naive and offset-aware datetimes.
        self.client = MongoClient(uri, tz_aware=True, tzinfo=timezone.utc)
        self.db = self.client[db_name]
        self._initialized = True
        self._ensure_indexes()

    def get_collection(self, name):
        return self.db[name]

    def _ensure_indexes(self):
        users = self.db["users"]
        users.create_index([("email", ASCENDING)], unique=True)
        users.create_index(
            [("role", ASCENDING)],
            unique=True,
            partialFilterExpression={"role": "creator"},
            name="unique_creator_role",
        )

        txns = self.db["transactions"]
        txns.create_index([("user_id", ASCENDING), ("category", ASCENDING), ("date", DESCENDING)])
        txns.create_index([("user_id", ASCENDING), ("date", DESCENDING)])

        otps = self.db["otps"]
        otps.create_index("expires_at", expireAfterSeconds=0)

        audit = self.db["audit_logs"]
        audit.create_index([("timestamp", DESCENDING)])