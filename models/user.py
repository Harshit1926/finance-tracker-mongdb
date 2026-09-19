"""
User
----
email is the login identifier and OTP-delivery address.
phone is stored purely for reference -- never used for authentication.
"""

from datetime import datetime, timezone
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

from models.role import Role


class User:
    def __init__(self, db, email, role, name=None, phone=None, dob=None,
                 password_hash=None, is_verified=False, _id=None, created_at=None):
        self.db = db
        self.collection = db.get_collection("users")

        self._id = _id
        self.email = email.strip().lower()
        self.role = Role(role)
        self.name = name
        self.phone = phone
        self.dob = dob
        self.password_hash = password_hash
        self.is_verified = is_verified
        self.created_at = created_at or datetime.now(timezone.utc)

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "email": self.email,
            "role": self.role.name,
            "name": self.name,
            "phone": self.phone,
            "dob": self.dob,
            "password_hash": self.password_hash,
            "is_verified": self.is_verified,
            "created_at": self.created_at,
        }

    def save(self):
        doc = self.to_dict()
        if self._id:
            self.collection.update_one({"_id": self._id}, {"$set": doc})
        else:
            result = self.collection.insert_one(doc)
            self._id = result.inserted_id
        return self._id

    @classmethod
    def find_by_email(cls, db, email):
        doc = db.get_collection("users").find_one({"email": email.strip().lower()})
        return cls._from_doc(db, doc) if doc else None

    @classmethod
    def find_by_id(cls, db, user_id):
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        doc = db.get_collection("users").find_one({"_id": user_id})
        return cls._from_doc(db, doc) if doc else None

    @classmethod
    def find_all(cls, db, role=None):
        query = {"role": role} if role else {}
        docs = db.get_collection("users").find(query).sort("created_at", -1)
        return [cls._from_doc(db, d) for d in docs]

    @classmethod
    def _from_doc(cls, db, doc):
        return cls(
            db=db,
            email=doc["email"],
            role=doc["role"],
            name=doc.get("name"),
            phone=doc.get("phone"),
            dob=doc.get("dob"),
            password_hash=doc.get("password_hash"),
            is_verified=doc.get("is_verified", False),
            _id=doc.get("_id"),
            created_at=doc.get("created_at"),
        )

    @property
    def id_str(self):
        return str(self._id) if self._id else None
