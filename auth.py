"""Accounts + rate limits for DoubtSetu. SQLite store, bcrypt hashes, signed Flask session."""
import os
import sqlite3
import time
import uuid
from collections import defaultdict, deque

import bcrypt
from flask import g, jsonify, session

_DB_PATH = os.environ.get("DOUBTSETU_DB_PATH") or os.path.join("data", "doubtsetu.db")

def _conn():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    c = sqlite3.connect(_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
        pw_hash TEXT NOT NULL, created_at TEXT NOT NULL)""")
    return c

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def verify_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("utf-8"))
    except ValueError:
        return False

def create_user(email, name, password):
    email = (email or "").strip().lower()
    name = (name or "").strip() or email.split("@")[0]
    if "@" not in email or "." not in email.split("@")[-1]:
        return None, "Enter a valid email address."
    if len(password) < 8:
        return None, "Password must be at least 8 characters."
    if len(password) > 200 or len(email) > 254 or len(name) > 80:
        return None, "That value is too long."
    c = _conn()
    try:
        c.execute("INSERT INTO users VALUES (?,?,?,?,datetime('now'))",
                  (uuid.uuid4().hex, email, name, hash_password(password)))
        c.commit()
    except sqlite3.IntegrityError:
        return None, "An account with this email already exists."
    finally:
        c.close()
    return get_user_by_email(email), None

def get_user_by_email(email):
    c = _conn(); c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM users WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    c.close()
    return dict(row) if row else None

def get_user_by_id(uid):
    if not uid: return None
    c = _conn(); c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    c.close()
    return dict(row) if row else None

def delete_user(uid):
    c = _conn(); c.execute("DELETE FROM users WHERE id=?", (uid,)); c.commit(); c.close()

def current_user():
    if "uid" not in session: return None
    if not hasattr(g, "_user"): g._user = get_user_by_id(session["uid"])
    return g._user

def user_public(u):
    return {"id": u["id"], "email": u["email"], "name": u["name"], "created_at": u["created_at"]}

# --- in-memory rate limits (per instance; enough for a one-worker free deploy) ---
_buckets = defaultdict(deque)
def _hit(key, limit, window):
    now = time.time(); q = _buckets[key]
    while q and q[0] < now - window: q.popleft()
    if len(q) >= limit: return False
    q.append(now); return True

def limited(ip, kind):
    limits = {"register": (10, 3600), "auth": (30, 900), "solve_guest": (3, 86400), "solve_user": (20, 86400)}
    limit, window = limits[kind]
    return not _hit("%s:%s" % (kind, ip), limit, window)

def login_lockout_key(ip, email):
    return "lock:%s:%s" % (ip, (email or "").strip().lower())

_locks = defaultdict(deque)
def login_blocked(ip, email):
    k = login_lockout_key(ip, email); now = time.time(); q = _locks[k]
    while q and q[0] < now - 900: q.popleft()
    return len(q) >= 5

def login_fail(ip, email):
    _locks[login_lockout_key(ip, email)].append(time.time())

def too_many(kind="auth"):
    return jsonify({"error": {"auth": "Too many attempts. Please wait a bit and try again.",
                              "solve_guest": "Guest limit reached for today (3 doubts a day). Sign in for 20.",
                              "solve_user": "Daily limit reached (20 doubts). Back tomorrow.",
                              "register": "Too many sign-ups from this network. Try later."}[kind]}), 429
