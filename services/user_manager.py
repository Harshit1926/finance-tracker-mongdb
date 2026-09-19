"""
UserManager
-----------
All account lifecycle actions performed by Admin/Creator on other accounts.
Every action is permission-checked through Role.can_manage(), logged, and
triggers an email to the affected user.
"""

from models.user import User
from models.role import Role, RoleType
from services.email_notifier import EmailNotifier
from services.audit_logger import AuditLogger


class UserManager:
    EDITABLE_FIELDS = {"name", "phone", "dob", "role"}

    def __init__(self, db):
        self.db = db
        self.collection = db.get_collection("users")
        self.notifier = EmailNotifier()
        self.audit = AuditLogger(db)

    def create(self, actor: User, email, password, role, name=None, phone=None, dob=None):
        if not actor.role.can_assign(role):
            raise PermissionError("You are not authorized to create an account with this role.")

        email = email.strip().lower()
        if User.find_by_email(self.db, email):
            raise ValueError("A user with this email already exists.")

        new_user = User(self.db, email=email, role=role, name=name, phone=phone,
                         dob=dob, is_verified=True)
        new_user.set_password(password)
        new_user.save()

        self.audit.log(actor.email, "USER_CREATED", f"{email} ({role})")
        self.notifier.notify_async(
            subject="Your Account Has Been Created",
            body=f"Hi {name or ''},\n\nThanks for creating this account. "
                 f"Your role: {RoleType.LABELS.get(role, role)}.\n"
                 f"You can log in now using this email address.",
            to=email,
        )
        return new_user

    def update(self, actor: User, target_email, field, new_value):
        if field not in self.EDITABLE_FIELDS:
            raise ValueError(f"Field '{field}' is not editable.")

        target = User.find_by_email(self.db, target_email)
        if not target:
            raise ValueError("User not found.")

        if not actor.role.can_manage(target.role):
            raise PermissionError("You are not authorized to update this account.")

        if field == "role":
            if new_value == RoleType.CREATOR:
                raise PermissionError("The Creator role cannot be assigned.")
            if not actor.role.can_assign(new_value):
                raise PermissionError("You cannot promote a user beyond your own authority.")
            target.role = Role(new_value)
        else:
            setattr(target, field, new_value)

        target.save()
        self.audit.log(actor.email, "USER_UPDATED", f"{target_email}: {field} -> {new_value}")

        self.notifier.notify_async(
            subject="Your Account Details Were Updated",
            body=f"Your {field} was changed to: {new_value}.\n"
                 f"If you didn't expect this change, please contact support.",
            to=target_email,
        )
        return target

    def delete(self, actor: User, target_email):
        target = User.find_by_email(self.db, target_email)
        if not target:
            raise ValueError("User not found.")

        if not actor.role.can_manage(target.role):
            raise PermissionError("You are not authorized to delete this account.")

        email_for_notice = target.email

        self.collection.delete_one({"email": target_email})
        self.db.get_collection("transactions").delete_many({"user_id": target._id})

        self.audit.log(actor.email, "USER_DELETED", email_for_notice)
        self.notifier.notify_async(
            subject="Your Account Has Been Deleted",
            body="Your account has been removed by an administrator. "
                 "Contact support if you believe this was a mistake.",
            to=email_for_notice,
        )
        return True
