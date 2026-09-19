"""
TransactionManager
------------------
Orchestrates: save transaction -> audit log -> email -> (on create only)
hand off to the FinanceAgent for anomaly reasoning.
"""

from models.transaction import Transaction
from services.email_notifier import EmailNotifier
from services.audit_logger import AuditLogger


class TransactionManager:
    def __init__(self, db, finance_agent=None):
        self.db = db
        self.notifier = EmailNotifier()
        self.audit = AuditLogger(db)
        self.finance_agent = finance_agent

    def add(self, user, amount, category, txn_type, date, note="", custom_category=None):
        txn = Transaction(
            db=self.db, user_id=user._id, amount=amount, category=category,
            txn_type=txn_type, date=date, note=note,
            custom_category=custom_category, user_email=user.email,
        )
        txn.save()
        self.audit.log(user.email, "TRANSACTION_ADDED",
                        f"{txn_type} of {txn.amount} in {txn.display_category()}")

        agent_handled = False
        if self.finance_agent and txn.type == "expense":
            agent_handled = self.finance_agent.observe_transaction(txn)

        if not agent_handled:
            self.notifier.notify_async(
                subject=f"Transaction Added: {txn.type.title()} of Rs. {txn.amount:,.2f}",
                body=f"Category: {txn.display_category()}\n"
                     f"Note: {txn.note or '-'}\nDate: {txn.date}",
                to=user.email,
            )
        return txn

    def delete(self, user, txn_id):
        txn = Transaction.find_by_id(self.db, txn_id, user_id=user._id)
        if not txn:
            return False

        self.db.get_collection("transactions").delete_one({"_id": txn._id})
        self.audit.log(user.email, "TRANSACTION_DELETED",
                        f"Removed {txn.type} of {txn.amount} in {txn.display_category()}")

        self.notifier.notify_async(
            subject=f"Transaction Deleted: {txn.type.title()} of Rs. {txn.amount:,.2f}",
            body=f"Category: {txn.display_category()}\nDate: {txn.date}",
            to=user.email,
        )
        return True
