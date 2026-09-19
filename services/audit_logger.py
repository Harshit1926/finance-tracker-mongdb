"""
AuditLogger
-----------
Immutable trail of every meaningful action in the system -- only ever
appended to, never updated or deleted.
"""

from datetime import datetime, timezone


class AuditLogger:
    def __init__(self, db):
        self.collection = db.get_collection("audit_logs")

    def log(self, actor_email, action, details=""):
        self.collection.insert_one({
            "actor_email": actor_email,
            "action": action,
            "details": str(details),
            "timestamp": datetime.now(timezone.utc),
        })

    def recent(self, limit=50):
        return list(self.collection.find().sort("timestamp", -1).limit(limit))
