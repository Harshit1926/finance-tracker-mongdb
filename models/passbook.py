"""
Passbook
--------
All read-only aggregation lives here: current balance, category totals,
monthly trend, and category-average (used by the FinanceAgent). MongoDB
does the summing; this class just shapes the result for templates/charts.
"""

from datetime import datetime, timedelta, timezone
from models.transaction import Category, TxnType


class Passbook:
    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        self.collection = db.get_collection("transactions")

    def summary(self):
        pipeline = [
            {"$match": {"user_id": self.user_id}},
            {"$group": {
                "_id": None,
                "total_income": {"$sum": {"$cond": [{"$eq": ["$type", TxnType.INCOME]}, "$amount", 0]}},
                "total_expense": {"$sum": {"$cond": [{"$eq": ["$type", TxnType.EXPENSE]}, "$amount", 0]}},
            }}
        ]
        result = list(self.collection.aggregate(pipeline))
        if not result:
            return {"total_income": 0, "total_expense": 0, "balance": 0}
        r = result[0]
        return {
            "total_income": r["total_income"],
            "total_expense": r["total_expense"],
            "balance": r["total_income"] - r["total_expense"],
        }

    def category_totals(self):
        pipeline = [
            {"$match": {"user_id": self.user_id}},
            {"$group": {
                "_id": {"category": "$category", "type": "$type"},
                "total": {"$sum": "$amount"},
            }}
        ]
        results = self.collection.aggregate(pipeline)
        totals = {cat: {"income": 0, "expense": 0} for cat in Category.ALL}
        for r in results:
            cat = r["_id"]["category"]
            txn_type = r["_id"]["type"]
            if cat in totals:
                totals[cat][txn_type] = r["total"]
        return totals

    def expense_breakdown(self):
        totals = self.category_totals()
        return {cat: v["expense"] for cat, v in totals.items() if v["expense"] > 0}

    def monthly_trend(self, months=6):
        pipeline = [
            {"$match": {"user_id": self.user_id}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m", "date": "$date"}},
                "income": {"$sum": {"$cond": [{"$eq": ["$type", TxnType.INCOME]}, "$amount", 0]}},
                "expense": {"$sum": {"$cond": [{"$eq": ["$type", TxnType.EXPENSE]}, "$amount", 0]}},
            }},
            {"$sort": {"_id": 1}},
            {"$limit": months},
        ]
        results = list(self.collection.aggregate(pipeline))
        return {
            "labels": [r["_id"] for r in results],
            "income": [r["income"] for r in results],
            "expense": [r["expense"] for r in results],
        }

    def category_average(self, category, days=30):
        pipeline = [
            {"$match": {
                "user_id": self.user_id,
                "category": category,
                "type": TxnType.EXPENSE,
                "date": {"$gte": datetime.now(timezone.utc) - timedelta(days=days)},
            }},
            {"$group": {"_id": None, "avg_amount": {"$avg": "$amount"}, "count": {"$sum": 1}}}
        ]
        result = list(self.collection.aggregate(pipeline))
        if not result or result[0]["count"] < 2:
            return None
        return result[0]["avg_amount"]
