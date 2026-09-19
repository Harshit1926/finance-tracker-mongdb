"""
check_mongo_connection.py
--------------------------
Standalone diagnostic script -- checks MONGO_URI step by step so you know
exactly which layer failed (network reachability, auth, or permissions)
instead of a single opaque error.

Usage:
    python check_mongo_connection.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 60)
    print("MongoDB Atlas Connection Check")
    print("=" * 60)

    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB_NAME", "finance_tracker")

    # ---------- Step 1: is MONGO_URI even set? ----------
    if not uri:
        print("\n[FAIL] MONGO_URI is not set in your .env file.")
        print("       Add a line like:")
        print('       MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>/?retryWrites=true&w=majority')
        sys.exit(1)

    if "<username>" in uri or "<password>" in uri or "<cluster-url>" in uri:
        print("\n[FAIL] MONGO_URI still contains placeholder text.")
        print("       Replace <username>, <password>, and <cluster-url> with your real values.")
        sys.exit(1)

    print(f"\n[OK] MONGO_URI is set (showing masked): {_mask(uri)}")
    print(f"[OK] Target database name: {db_name}")

    # ---------- Step 2: can we import pymongo? ----------
    try:
        from pymongo import MongoClient
        from pymongo.errors import (
            ConfigurationError,
            ServerSelectionTimeoutError,
            OperationFailure,
        )
    except ImportError:
        print("\n[FAIL] pymongo is not installed.")
        print("       Run: pip install pymongo")
        sys.exit(1)

    # ---------- Step 3: attempt connection ----------
    print("\nConnecting to MongoDB Atlas ...")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        print("[OK] Connected successfully -- server responded to ping.")
    except ConfigurationError as e:
        print(f"\n[FAIL] URI is malformed: {e}")
        print("       Check for typos, or special characters in your password that")
        print("       need URL-encoding (@, #, %, etc.).")
        sys.exit(1)
    except ServerSelectionTimeoutError as e:
        print(f"\n[FAIL] Could not reach the cluster within the timeout: {e}")
        print("       Likely causes:")
        print("       - Your current IP is not whitelisted in Atlas Network Access")
        print("         (Atlas -> Network Access -> Add IP Address -> Allow Access From Anywhere for testing)")
        print("       - The cluster URL in MONGO_URI is wrong")
        print("       - No internet connection / firewall blocking outbound traffic")
        sys.exit(1)
    except OperationFailure as e:
        print(f"\n[FAIL] Authentication failed: {e}")
        print("       Likely causes:")
        print("       - Wrong username or password in MONGO_URI")
        print("       - The DB user doesn't exist (Atlas -> Database Access)")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error while connecting: {e}")
        sys.exit(1)

    # ---------- Step 4: check read/write permissions ----------
    print("\nChecking read/write permissions on the target database ...")
    try:
        db = client[db_name]
        test_collection = db["_connection_test"]
        result = test_collection.insert_one({"check": "ok"})
        test_collection.delete_one({"_id": result.inserted_id})
        print("[OK] Write permission confirmed (test document inserted and deleted).")
    except OperationFailure as e:
        print(f"\n[FAIL] Connected, but this DB user lacks write permission: {e}")
        print("       Fix in Atlas -> Database Access -> edit user -> grant")
        print("       'readWrite' on this database.")
        sys.exit(1)

    # ---------- Step 5: list existing collections (sanity check) ----------
    try:
        collections = db.list_collection_names()
        print(f"\n[OK] Existing collections in '{db_name}': {collections or '(none yet -- fresh database)'}")
    except Exception as e:
        print(f"\n[WARN] Could not list collections: {e}")

    print("\n" + "=" * 60)
    print("All checks passed. Your MONGO_URI is working correctly.")
    print("=" * 60)
    client.close()


def _mask(uri):
    """Hide the password portion of the URI when printing it back."""
    if "://" not in uri or "@" not in uri:
        return uri
    scheme, rest = uri.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:****@{host}"
    return uri


if __name__ == "__main__":
    main()
