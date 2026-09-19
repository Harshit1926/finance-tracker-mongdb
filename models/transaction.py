"""
Transaction
-----------
Fixed category list keeps analytics and anomaly-detection aggregation
reliable. "Other" accepts a free-text custom_category for display only --
never used for grouping.
"""

from datetime import datetime, timezone
from bson import ObjectId


class TxnType:
    INCOME = "income"
    EXPENSE = "expense"
    ALL = [INCOME, EXPENSE]


class Category:
    FOOD = "Food"
    TRAVEL = "Travel"
    RENT = "Rent"
    SALARY = "Salary"
    UTILITIES = "Utilities"
    SHOPPING = "Shopping"
    HEALTHCARE = "Healthcare"
    ENTERTAINMENT = "Entertainment"
    OTHER = "Other"

    PRESET = [FOOD, TRAVEL, RENT, SALARY, UTILITIES, SHOPPING, HEALTHCARE, ENTERTAINMENT]
    ALL = PRESET + [OTHER]

    ICONS = {
        FOOD: "food", TRAVEL: "travel", RENT: "rent", SALARY: "salary",
        UTILITIES: "utilities", SHOPPING: "shopping", HEALTHCARE: "healthcare",
        ENTERTAINMENT: "entertainment", OTHER: "other",
    }

    COLORS = {
        FOOD: "#e07a5f", TRAVEL: "#81b29a", RENT: "#f2cc8f", SALARY: "#3fa796",
        UTILITIES: "#9b8cf2", SHOPPING: "#f28482", HEALTHCARE: "#5fa8d3",
        ENTERTAINMENT: "#f4a261", OTHER: "#8d99ae",
    }


class Transaction:
    def __init__(self, db, user_id, amount, category, txn_type, date,
                 note="", custom_category=None, user_email=None,
                 _id=None, created_at=None):
        if category not in Category.ALL:
            raise ValueError(f"Invalid category: {category}")
        if txn_type not in TxnType.ALL:
            raise ValueError(f"Invalid transaction type: {txn_type}")

        self.db = db
        self.collection = db.get_collection("transactions")

        self._id = _id
        self.user_id = user_id
        self.amount = abs(float(amount))
        self.category = category
        self.custom_category = custom_category if category == Category.OTHER else None
        self.type = txn_type
        self.date = date
        self.note = note
        self.user_email = user_email
        self.created_at = created_at or datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "amount": self.amount,
            "category": self.category,
            "custom_category": self.custom_category,
            "type": self.type,
            "date": self.date,
            "note": self.note,
            "user_email": self.user_email,
            "created_at": self.created_at,
        }

    def save(self):
        result = self.collection.insert_one(self.to_dict())
        self._id = result.inserted_id
        return self._id

    def display_category(self):
        if self.category == Category.OTHER and self.custom_category:
            return f"Other - {self.custom_category}"
        return self.category

    @classmethod
    def find_by_id(cls, db, txn_id, user_id=None):
        if isinstance(txn_id, str):
            txn_id = ObjectId(txn_id)
        query = {"_id": txn_id}
        if user_id:
            query["user_id"] = user_id
        doc = db.get_collection("transactions").find_one(query)
        return cls._from_doc(db, doc) if doc else None

    @classmethod
    def find_by_user(cls, db, user_id, limit=None):
        cursor = db.get_collection("transactions").find({"user_id": user_id}).sort("date", -1)
        if limit:
            cursor = cursor.limit(limit)
        return [cls._from_doc(db, d) for d in cursor]

    @classmethod
    def _from_doc(cls, db, doc):
        return cls(
            db=db,
            user_id=doc["user_id"],
            amount=doc["amount"],
            category=doc["category"],
            txn_type=doc["type"],
            date=doc["date"],
            note=doc.get("note", ""),
            custom_category=doc.get("custom_category"),
            user_email=doc.get("user_email"),
            _id=doc.get("_id"),
            created_at=doc.get("created_at"),
        )

    @property
    def id_str(self):
        return str(self._id) if self._id else None
