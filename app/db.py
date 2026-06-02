"""
MongoDB access helpers for OmniFarm Hub.
All application code imports from here rather than touching pymongo directly.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from math import ceil
from bson import ObjectId


# ── Collection accessor ──────────────────────────────────────────────────────

def get_col(name: str):
    """Return a pymongo Collection by name.

    Flask-PyMongo exposes:
      mongo.db   — the Database object  (bound to MONGO_URI's database name)
      mongo.cx   — the MongoClient       (use for admin commands, RS status, etc.)
    Both are app-context-aware; safe to call from any request or CLI context.
    """
    from app.extensions import mongo
    return mongo.db[name]


# ── ObjectId helpers ─────────────────────────────────────────────────────────

def oid(id_str) -> ObjectId | None:
    """Safely convert a string (URL param, form value) to ObjectId."""
    if isinstance(id_str, ObjectId):
        return id_str
    try:
        return ObjectId(str(id_str))
    except Exception:
        return None


# ── Date / datetime converters ───────────────────────────────────────────────

def date_to_dt(d) -> datetime | None:
    """Convert Python date → UTC midnight datetime for MongoDB storage."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def dt_to_date(v) -> date | None:
    """Convert datetime (from MongoDB) → Python date."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return v


# ── Pagination ───────────────────────────────────────────────────────────────

class Pagination:
    """Drop-in replacement for Flask-SQLAlchemy's paginate() result."""

    def __init__(self, items: list, total: int, page: int, per_page: int):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = ceil(total / per_page) if per_page and total > 0 else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1 if self.has_prev else None
        self.next_num = page + 1 if self.has_next else None

    def iter_pages(self, left_edge: int = 2, right_edge: int = 2,
                   left_current: int = 2, right_current: int = 5):
        last = 0
        for num in range(1, self.pages + 1):
            if (num <= left_edge
                    or self.page - left_current - 1 < num < self.page + right_current
                    or num > self.pages - right_edge):
                if last + 1 != num:
                    yield None
                yield num
                last = num
