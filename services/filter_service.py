"""
FilterService
-------------
Powers the Analyst dashboard: filter a chosen user's transactions by date
range, category, and type, then summarize the filtered set.
"""

from datetime import datetime
from models.transaction import TxnType


class FilterService:
    def __init__(self, db):
        self.collection = db.get_collection("transactions")

    def filter_transactions(self, user_id, start_date=None, end_date=None,
                             category=None, txn_type=None):
        query = {"user_id": user_id}

        date_filter = {}
        if start_date:
            date_filter["$gte"] = self._to_date(start_date)
        if end_date:
            date_filter["$lte"] = self._to_date(end_date)
        if date_filter:
            query["date"] = date_filter

        if category and category.strip():
            query["category"] = category.strip()

        if txn_type and txn_type.strip():
            query["type"] = txn_type.strip().lower()

        return list(self.collection.find(query).sort("date", -1))

    @staticmethod
    def summarize(transactions):
        income = sum(t["amount"] for t in transactions if t["type"] == TxnType.INCOME)
        expense = sum(t["amount"] for t in transactions if t["type"] == TxnType.EXPENSE)
        return {"total_income": income, "total_expense": expense, "balance": income - expense}

    @staticmethod
    def _to_date(value):
        if isinstance(value, datetime):
            return value
        return datetime.strptime(value, "%Y-%m-%d")
