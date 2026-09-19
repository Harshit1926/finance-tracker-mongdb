"""
OTPService
----------
- 1 minute validity.
- No resend until the previous OTP has expired (checked server-side --
  the frontend just shows a static message, no countdown needed).
- OTP is hashed at rest, never stored in plaintext.
- Failed verification attempts are capped to block brute-forcing.
"""

import os
import random
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash


class OTPStillActiveError(Exception):
    pass


class TooManyAttemptsError(Exception):
    pass


class OTPService:
    VALIDITY_SECONDS = int(os.getenv("OTP_VALIDITY_SECONDS", 60))
    MAX_ATTEMPTS = 5

    def __init__(self, db):
        self.collection = db.get_collection("otps")

    def generate(self, email):
        email = email.strip().lower()
        existing = self.collection.find_one({"email": email})

        if existing and datetime.now(timezone.utc) < existing["expires_at"]:
            remaining = int((existing["expires_at"] - datetime.now(timezone.utc)).total_seconds())
            raise OTPStillActiveError(f"Please wait {remaining}s before requesting a new OTP")

        code = f"{random.randint(100000, 999999)}"
        self.collection.update_one(
            {"email": email},
            {"$set": {
                "code_hash": generate_password_hash(code),
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self.VALIDITY_SECONDS),
                "attempts": 0,
            }},
            upsert=True,
        )
        return code

    def verify(self, email, code):
        email = email.strip().lower()
        record = self.collection.find_one({"email": email})
        if not record:
            return False

        if record.get("attempts", 0) >= self.MAX_ATTEMPTS:
            raise TooManyAttemptsError("Too many failed attempts. Request a new OTP.")

        if datetime.now(timezone.utc) > record["expires_at"]:
            return False

        if not check_password_hash(record["code_hash"], code):
            self.collection.update_one({"email": email}, {"$inc": {"attempts": 1}})
            return False

        self.collection.delete_one({"email": email})
        return True
