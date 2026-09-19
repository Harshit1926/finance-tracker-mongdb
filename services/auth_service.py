"""
AuthService
-----------
Single unified login path for every role, including Creator -- verification
status is just a field on the User doc, not a branch in login logic.
Signup only ever produces "user" role accounts and requires OTP verification.
"""

from models.user import User
from models.role import RoleType
from services.otp_service import OTPService
from services.email_notifier import EmailNotifier
from services.audit_logger import AuditLogger


class AuthService:
    def __init__(self, db):
        self.db = db
        self.otp_service = OTPService(db)
        self.notifier = EmailNotifier()
        self.audit = AuditLogger(db)

    def login(self, email, password):
        user = User.find_by_email(self.db, email)
        if not user or not user.password_hash or not user.check_password(password):
            return None, "Invalid email or password."
        if not user.is_verified:
            return None, "Account not verified. Please verify your email first."
        return user, None

    def start_signup(self, email, password, name=None, phone=None, dob=None):
        email = email.strip().lower()
        existing = User.find_by_email(self.db, email)

        if existing and existing.is_verified:
            return None, "An account with this email already exists."

        user = existing or User(self.db, email=email, role=RoleType.USER,
                                 name=name, phone=phone, dob=dob, is_verified=False)
        user.name = name or user.name
        user.phone = phone or user.phone
        user.dob = dob or user.dob
        user.set_password(password)
        user.save()

        code = self.otp_service.generate(email)
        self._send_otp_email(email, code)
        return user, None

    def verify_signup(self, email, code):
        if not self.otp_service.verify(email, code):
            return False, "Invalid or expired OTP."

        user = User.find_by_email(self.db, email)
        if not user:
            return False, "Account not found."

        user.is_verified = True
        user.save()
        self.audit.log(user.email, "USER_SELF_VERIFIED", "Signup OTP verified")

        self.notifier.notify_async(
            subject="Welcome to Finance Tracker",
            body=f"Hi {user.name or ''},\n\nThanks for creating this account! "
                 f"You can now log in with your email.",
            to=user.email,
        )
        return True, None

    def resend_otp(self, email):
        """
        BUGFIX: this previously only called otp_service.generate(email) and
        returned the code, without ever emailing it -- generate() creates
        and stores the new OTP but has no knowledge of email sending, so the
        caller is responsible for actually sending it. start_signup() did
        this correctly; resend_otp() did not, which is why "Resend code"
        showed a success flash message but no email ever arrived.
        """
        code = self.otp_service.generate(email)
        self._send_otp_email(email, code)
        return code

    def _send_otp_email(self, email, code):
        self.notifier.notify_async(
            subject="Your Verification Code",
            body=f"Your OTP is {code}. It is valid for {self.otp_service.VALIDITY_SECONDS} seconds.",
            to=email,
        )