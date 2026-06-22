"""
MongoDB data access layer using PyMongo.
Replaces the previous SQLAlchemy-based schema.py.
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
mongo_uri = os.environ.get("MONGODB_URI") or os.environ.get("URL")
if not mongo_uri:
    raise RuntimeError("Set MONGODB_URI or URL to your MongoDB connection string.")

_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
_db = _client[os.environ.get("DB_NAME", "quiz")]

# Collection references
subjects_col = _db.subjects
users_col = _db.users
questions_col = _db.questions
attempts_col = _db.quiz_attempts
answers_col = _db.attempt_answers


# ---------------------------------------------------------------------------
# Lightweight document wrapper – lets Jinja2 templates keep using dot-access
# (e.g.  {{ attempt.subject }})  without any template changes.
# ---------------------------------------------------------------------------
class Doc:
    """Wrap a MongoDB document dict for convenient attribute access."""

    def __init__(self, data: dict | None = None):
        data = data or {}
        for key, value in data.items():
            if key != "_id":
                setattr(self, key, value)
        # Expose _id as .id (string) for URL generation & session storage
        if "_id" in data:
            self.id = str(data["_id"])

    def __repr__(self):
        return f"<Doc id={getattr(self, 'id', '?')}>"


def to_doc(data):
    """Convert a raw dict (or None) into a Doc."""
    return Doc(data) if data else None


def to_docs(cursor):
    """Convert a pymongo cursor into a list of Doc objects."""
    return [Doc(d) for d in cursor]


# ---------------------------------------------------------------------------
# Create indexes (idempotent – safe to call on every startup)
# ---------------------------------------------------------------------------
def ensure_indexes():
    users_col.create_index("username", unique=True)
    users_col.create_index("email", unique=True)
    questions_col.create_index("subject")
    attempts_col.create_index("user_id")
    answers_col.create_index("attempt_id")
