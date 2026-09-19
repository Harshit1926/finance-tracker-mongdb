"""
seed_creator.py
----------------
Run this ONCE, manually, to create the Creator (superadmin) account.
It is never wired into any Flask route -- the only way to create a Creator
is by running this script directly with credentials from .env.

Usage:
    python seed_creator.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

from models.database import DatabaseManager
from models.user import User
from models.role import RoleType


def seed():
    username = os.getenv("CREATOR_EMAIL")
    password = os.getenv("CREATOR_PASSWORD")
    name = os.getenv("CREATOR_NAME", "Creator")

    if not username or not password:
        raise SystemExit("CREATOR_EMAIL and CREATOR_PASSWORD must be set in .env")

    db = DatabaseManager()
    existing = db.get_collection("users").find_one({"role": RoleType.CREATOR})

    if existing:
        print(f"Creator account already exists ({existing['email']}). Skipping.")
        return

    creator = User(db, email=username, role=RoleType.CREATOR, name=name, is_verified=True)
    creator.set_password(password)
    creator.save()
    print(f"Creator account seeded: {username}")


if __name__ == "__main__":
    seed()
