"""
Database Operations
---------------------
SQLite CRUD operations, statistics queries, and DB initialization.

Tables:
  users              - lightweight identity (name + email, no password)
  support_chats      - classified conversations / tickets
  expenses           - user-logged daily spending (Personal Finance Tracker)
  login_history       - one row per sign-in, powers the "Login History" panel
  notifications       - in-app notification center (poll-based)
  product_feedback    - general star-rating + comment feedback (not per-message)
  incident_updates    - user follow-up notes on escalated/critical tickets
  corrections          - admin re-labels of a ticket's intent, feeds retraining
"""

import csv
import io
import math
from collections import defaultdict, Counter
import os
import sqlite3
from datetime import datetime, timedelta

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(DB_DIR, "smartassist.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    is_blocked INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    user_name TEXT NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    intent TEXT NOT NULL,
    confidence REAL NOT NULL,
    sentiment TEXT NOT NULL,
    urgency_level TEXT NOT NULL,
    is_escalated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Resolved',
    rating INTEGER,
    assigned_agent TEXT,
    agent_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT,
    spent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    deleted_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS login_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS product_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS incident_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES support_chats(id)
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    query_text TEXT NOT NULL,
    original_intent TEXT NOT NULL,
    corrected_intent TEXT NOT NULL,
    corrected_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES support_chats(id)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_chats_intent ON support_chats(intent);",
    "CREATE INDEX IF NOT EXISTS idx_chats_urgency ON support_chats(urgency_level);",
    "CREATE INDEX IF NOT EXISTS idx_chats_status ON support_chats(status);",
    "CREATE INDEX IF NOT EXISTS idx_chats_user ON support_chats(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_expenses_user ON expenses(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_expenses_spent_at ON expenses(spent_at);",
    "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_login_history_user ON login_history(user_id);",
]

# Columns added to support_chats after the original schema shipped.
# Explicit migration list so upgrading an existing DB in place (without
# deleting data/smartassist.db) doesn't break.
MIGRATIONS = [
    ("support_chats", "user_id", "INTEGER"),
    ("support_chats", "rating", "INTEGER"),
    ("support_chats", "assigned_agent", "TEXT"),
    ("support_chats", "agent_notes", "TEXT"),
    ("expenses", "is_deleted", "INTEGER DEFAULT 0"),
    ("expenses", "deleted_at", "TIMESTAMP"),
]

AGENTS = ["Unassigned", "Aisha Verma", "Rohan Iyer", "Neha Kapoor", "Tier-2 Team"]
REAL_AGENTS = ["Aisha Verma", "Rohan Iyer", "Neha Kapoor"]

EXPENSE_CATEGORIES = [
    "Food & Dining", "Transport", "Shopping", "Bills & Utilities",
    "Entertainment", "Health", "Groceries", "Other",
]

TIME_BUCKETS = [
    ("Night (12am-5am)", 0, 5),
    ("Morning (5am-11am)", 5, 11),
    ("Afternoon (11am-5pm)", 11, 17),
    ("Evening (5pm-9pm)", 17, 21),
    ("Late Night (9pm-12am)", 21, 24),
]


def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _run_migrations(conn):
    cur = conn.cursor()
    for table, column, coltype in MIGRATIONS:
        cur.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cur.fetchall()}
        if column not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
    conn.commit()


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    conn.commit()
    # Migrations must run BEFORE indexes: an old database won't yet have
    # columns like user_id that a fresh-install index references.
    _run_migrations(conn)
    for stmt in INDEXES:
        cur.execute(stmt)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def get_or_create_user(name, email):
    name = (name or "Guest").strip()[:60]
    email = (email or "").strip().lower()[:120]
    if not email:
        email = f"guest+{datetime.utcnow().timestamp()}@local"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()

    if row:
        cur.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP, name = ? WHERE id = ?",
            (name, row["id"]),
        )
        conn.commit()
        user = dict(row)
        user["name"] = name
    else:
        cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,))
        user = dict(cur.fetchone())

    conn.close()
    return user


def update_user_name(user_id, name):
    name = (name or "").strip()[:60]
    if not name:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def set_user_blocked(user_id, blocked: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_blocked = ? WHERE id = ?", (int(blocked), user_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def is_user_blocked(user_id):
    if not user_id:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_blocked FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row["is_blocked"]) if row else False


def list_users(search=None, limit=200):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT u.*,
               COUNT(c.id) AS ticket_count,
               SUM(CASE WHEN c.is_escalated = 1 THEN 1 ELSE 0 END) AS escalated_count,
               SUM(CASE WHEN c.status = 'Open' THEN 1 ELSE 0 END) AS open_count,
               MAX(c.created_at) AS last_message_at
        FROM users u
        LEFT JOIN support_chats c ON c.user_id = u.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (u.name LIKE ? OR u.email LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])

    query += " GROUP BY u.id ORDER BY u.last_active DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_user_with_tickets(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_row = cur.fetchone()
    if not user_row:
        conn.close()
        return None

    cur.execute(
        "SELECT * FROM support_chats WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    tickets = [dict(r) for r in cur.fetchall()]
    conn.close()

    user = dict(user_row)
    user["tickets"] = tickets
    return user


def get_user_profile(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    cur.execute("SELECT COUNT(*) AS c FROM support_chats WHERE user_id = ?", (user_id,))
    ticket_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM support_chats WHERE user_id = ? AND is_escalated = 1", (user_id,))
    escalated_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM login_history WHERE user_id = ?", (user_id,))
    login_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,))
    expense_count = cur.fetchone()["c"]

    conn.close()

    profile = dict(row)
    profile.update({
        "ticket_count": ticket_count,
        "escalated_count": escalated_count,
        "login_count": login_count,
        "expense_count": expense_count,
    })
    return profile


# ---------------------------------------------------------------------------
# Login history
# ---------------------------------------------------------------------------
def record_login(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO login_history (user_id) VALUES (?)", (user_id,))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_login_history(user_id, limit=20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM login_history WHERE user_id = ? ORDER BY login_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
def create_notification(user_id, title, message, ntype="info"):
    if not user_id:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notifications (user_id, title, message, type) VALUES (?, ?, ?, ?)",
        (user_id, title, message, ntype),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_notifications(user_id, unread_only=False, limit=30):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM notifications WHERE user_id = ?"
    params = [user_id]
    if unread_only:
        query += " AND is_read = 0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def unread_notification_count(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
    count = cur.fetchone()["c"]
    conn.close()
    return count


def mark_notification_read(notification_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def mark_all_notifications_read(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Chats / Tickets
# ---------------------------------------------------------------------------
def _auto_assign_agent(urgency_level, query_text):
    """Lightweight rules-based routing: critical issues go straight to the
    Tier-2 team, high-urgency issues round-robin across agents so response
    load is spread automatically, everything else stays Unassigned for a
    human to triage."""
    if urgency_level == "Critical":
        return "Tier-2 Team"
    if urgency_level == "High":
        idx = abs(hash(query_text)) % len(REAL_AGENTS)
        return REAL_AGENTS[idx]
    return "Unassigned"


def insert_chat(user_name, query_text, response_text, intent, confidence,
                 sentiment, urgency_level, is_escalated, user_id=None):
    conn = get_connection()
    cur = conn.cursor()
    status = "Open" if is_escalated else "Resolved"
    agent = _auto_assign_agent(urgency_level, query_text)
    cur.execute(
        """INSERT INTO support_chats
           (user_id, user_name, query_text, response_text, intent, confidence,
            sentiment, urgency_level, is_escalated, status, assigned_agent)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, user_name, query_text, response_text, intent, confidence,
         sentiment, urgency_level, int(is_escalated), status, agent),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    if is_escalated and user_id:
        agent_note = f" and routed to {agent}" if agent != "Unassigned" else ""
        create_notification(
            user_id,
            "Your issue was escalated",
            f"Ticket #{new_id} needed extra attention{agent_note}. A human agent will follow up shortly.",
            "warning",
        )

    return new_id


def get_user_ticket_history(user_id, limit=50):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM support_chats WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_user_incidents(user_id):
    """Escalated or high/critical urgency tickets — the user's 'incidents'."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM support_chats
           WHERE user_id = ? AND (is_escalated = 1 OR urgency_level IN ('Critical', 'High'))
           ORDER BY created_at DESC""",
        (user_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    for r in rows:
        r["updates"] = get_incident_updates(r["id"])
    return rows


def add_incident_update(chat_id, user_id, message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO incident_updates (chat_id, user_id, message) VALUES (?, ?, ?)",
        (chat_id, user_id, message),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_incident_updates(chat_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM incident_updates WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def set_chat_rating(chat_id, rating):
    """rating: 1 (helpful) or -1 (not helpful)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE support_chats SET rating = ? WHERE id = ?", (rating, chat_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def get_tickets(status=None, urgency=None, intent=None, search=None, agent=None, limit=200):
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT * FROM support_chats WHERE 1=1"
    params = []

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    if urgency and urgency != "All":
        query += " AND urgency_level = ?"
        params.append(urgency)
    if intent and intent != "All":
        query += " AND intent = ?"
        params.append(intent)
    if agent and agent != "All":
        query += " AND assigned_agent = ?"
        params.append(agent)
    if search:
        query += " AND (query_text LIKE ? OR user_name LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_chat_by_id(chat_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM support_chats WHERE id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_ticket_status(ticket_id, new_status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM support_chats WHERE id = ?", (ticket_id,))
    row = cur.fetchone()

    cur.execute("UPDATE support_chats SET status = ? WHERE id = ?", (new_status, ticket_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()

    if affected and row and row["user_id"] and new_status == "Resolved":
        create_notification(
            row["user_id"],
            "Ticket resolved",
            f"Ticket #{ticket_id} has been marked Resolved by our support team.",
            "success",
        )

    return affected > 0


def assign_ticket_agent(ticket_id, agent_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE support_chats SET assigned_agent = ? WHERE id = ?", (agent_name, ticket_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def update_ticket_notes(ticket_id, notes):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE support_chats SET agent_notes = ? WHERE id = ?", (notes, ticket_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def export_tickets_csv():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM support_chats ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()

    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Corrections (admin re-labeling -> feeds smarter retraining)
# ---------------------------------------------------------------------------
def add_correction(chat_id, corrected_intent, corrected_by="Admin"):
    chat = get_chat_by_id(chat_id)
    if not chat:
        return None

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO corrections (chat_id, query_text, original_intent, corrected_intent, corrected_by)
           VALUES (?, ?, ?, ?, ?)""",
        (chat_id, chat["query_text"], chat["intent"], corrected_intent, corrected_by),
    )
    cur.execute("UPDATE support_chats SET intent = ? WHERE id = ?", (corrected_intent, chat_id))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_corrections(limit=100):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM corrections ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_correction_training_pairs():
    """Return [(query_text, corrected_intent), ...] for retraining — every
    admin correction becomes a labeled training example, so the classifier
    literally learns from its own past mistakes."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT query_text, corrected_intent FROM corrections")
    pairs = [(r["query_text"], r["corrected_intent"]) for r in cur.fetchall()]
    conn.close()
    return pairs


# ---------------------------------------------------------------------------
# Product feedback (general star rating + comment)
# ---------------------------------------------------------------------------
def add_feedback(user_id, rating, comment):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO product_feedback (user_id, rating, comment) VALUES (?, ?, ?)",
        (user_id, rating, comment),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def get_feedback(limit=100):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT f.*, u.name AS user_name, u.email AS user_email
           FROM product_feedback f
           LEFT JOIN users u ON u.id = f.user_id
           ORDER BY f.created_at DESC LIMIT ?""",
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_feedback_stats():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c, AVG(rating) AS avg FROM product_feedback")
    row = cur.fetchone()
    cur.execute("SELECT rating, COUNT(*) AS c FROM product_feedback GROUP BY rating")
    dist = {str(r["rating"]): r["c"] for r in cur.fetchall()}
    conn.close()
    return {
        "count": row["c"] or 0,
        "average": round(row["avg"], 2) if row["avg"] else 0,
        "distribution": dist,
    }


# ---------------------------------------------------------------------------
# Expenses (Personal Daily Expenditure Tracker)
# ---------------------------------------------------------------------------
def add_expense(user_id, category, amount, note=None, spent_at=None):
    conn = get_connection()
    cur = conn.cursor()
    if spent_at:
        cur.execute(
            """INSERT INTO expenses (user_id, category, amount, note, spent_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, category, amount, note, spent_at),
        )
    else:
        cur.execute(
            "INSERT INTO expenses (user_id, category, amount, note) VALUES (?, ?, ?, ?)",
            (user_id, category, amount, note),
        )
    conn.commit()
    new_id = cur.lastrowid
    cur.execute("SELECT * FROM expenses WHERE id = ?", (new_id,))
    row = dict(cur.fetchone())
    conn.close()
    return row


def get_user_expenses(user_id, days=90, limit=500):
    conn = get_connection()
    cur = conn.cursor()
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    cur.execute(
        """SELECT * FROM expenses WHERE user_id = ? AND spent_at >= ? AND is_deleted = 0
           ORDER BY spent_at DESC LIMIT ?""",
        (user_id, since, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_expenses_in_range(user_id, start_dt, end_dt):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM expenses WHERE user_id = ? AND is_deleted = 0
           AND spent_at >= ? AND spent_at < ? ORDER BY spent_at ASC""",
        (user_id, start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_expense(expense_id, user_id):
    """Soft delete — moves the expense to the user's Recycle Bin instead
    of destroying it, so it can be restored later."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE expenses SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ? AND is_deleted = 0",
        (expense_id, user_id),
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def get_deleted_expenses(user_id, limit=100):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM expenses WHERE user_id = ? AND is_deleted = 1 ORDER BY deleted_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def restore_expense(expense_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE expenses SET is_deleted = 0, deleted_at = NULL WHERE id = ? AND user_id = ? AND is_deleted = 1",
        (expense_id, user_id),
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def permanently_delete_expense(expense_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ? AND user_id = ? AND is_deleted = 1", (expense_id, user_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def get_admin_expense_overview():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c, COALESCE(SUM(amount), 0) AS total FROM expenses WHERE is_deleted = 0")
    row = cur.fetchone()

    cur.execute("SELECT category, COALESCE(SUM(amount), 0) AS total FROM expenses WHERE is_deleted = 0 GROUP BY category ORDER BY total DESC")
    category_totals = {r["category"]: round(r["total"], 2) for r in cur.fetchall()}

    cur.execute(
        """SELECT u.name AS name, COALESCE(SUM(e.amount), 0) AS total
           FROM expenses e JOIN users u ON u.id = e.user_id
           WHERE e.is_deleted = 0
           GROUP BY e.user_id ORDER BY total DESC LIMIT 8"""
    )
    top_spenders = [{"name": r["name"], "total": round(r["total"], 2)} for r in cur.fetchall()]

    since = (datetime.utcnow() - timedelta(days=13)).strftime("%Y-%m-%d")
    cur.execute(
        """SELECT DATE(spent_at) AS day, COALESCE(SUM(amount), 0) AS total
           FROM expenses WHERE is_deleted = 0 AND DATE(spent_at) >= ?
           GROUP BY DATE(spent_at) ORDER BY day""",
        (since,),
    )
    trend = {r["day"]: round(r["total"], 2) for r in cur.fetchall()}

    conn.close()
    return {
        "total_entries": row["c"],
        "total_spent": round(row["total"], 2),
        "category_totals": category_totals,
        "top_spenders": top_spenders,
        "trend_14d": trend,
    }


# ---------------------------------------------------------------------------
# Statistics (admin overview)
# ---------------------------------------------------------------------------
def get_stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM support_chats")
    total = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM support_chats WHERE is_escalated = 1")
    escalated = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM support_chats WHERE status = 'Open'")
    open_tickets = cur.fetchone()["c"]

    cur.execute("SELECT AVG(confidence) AS a FROM support_chats")
    avg_conf_row = cur.fetchone()["a"]
    avg_confidence = round(avg_conf_row, 4) if avg_conf_row else 0

    cur.execute("SELECT COUNT(*) AS c FROM users")
    total_users = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM users WHERE is_blocked = 1")
    blocked_users = cur.fetchone()["c"]

    cur.execute("SELECT intent, COUNT(*) AS c FROM support_chats GROUP BY intent")
    intent_dist = {r["intent"]: r["c"] for r in cur.fetchall()}

    cur.execute("SELECT urgency_level, COUNT(*) AS c FROM support_chats GROUP BY urgency_level")
    urgency_dist = {r["urgency_level"]: r["c"] for r in cur.fetchall()}

    cur.execute("SELECT sentiment, COUNT(*) AS c FROM support_chats GROUP BY sentiment")
    sentiment_dist = {r["sentiment"]: r["c"] for r in cur.fetchall()}

    cur.execute("SELECT status, COUNT(*) AS c FROM support_chats GROUP BY status")
    status_dist = {r["status"]: r["c"] for r in cur.fetchall()}

    cur.execute("SELECT COUNT(*) AS c FROM support_chats WHERE rating = 1")
    helpful = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM support_chats WHERE rating = -1")
    not_helpful = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM corrections")
    correction_count = cur.fetchone()["c"]

    since = (datetime.utcnow() - timedelta(days=6)).strftime("%Y-%m-%d")
    cur.execute(
        """SELECT DATE(created_at) AS day, COUNT(*) AS c
           FROM support_chats
           WHERE DATE(created_at) >= ?
           GROUP BY DATE(created_at)
           ORDER BY day""",
        (since,),
    )
    volume_trend = {r["day"]: r["c"] for r in cur.fetchall()}

    conn.close()

    return {
        "total_chats": total,
        "escalated": escalated,
        "open_tickets": open_tickets,
        "avg_confidence": avg_confidence,
        "total_users": total_users,
        "blocked_users": blocked_users,
        "intent_distribution": intent_dist,
        "urgency_distribution": urgency_dist,
        "sentiment_distribution": sentiment_dist,
        "status_distribution": status_dist,
        "feedback": {"helpful": helpful, "not_helpful": not_helpful},
        "correction_count": correction_count,
        "volume_trend": volume_trend,
    }


def seed_demo_data():
    """Populate a handful of realistic demo users + tickets + expenses so
    the dashboard isn't empty on first run. Safe to call multiple times
    (only seeds when the table is empty)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM support_chats")
    if cur.fetchone()["c"] > 0:
        conn.close()
        return
    conn.close()

    from ml.classifier import classify_message

    demo_messages = [
        ("Aditi R.", "aditi.r@example.com", "I was charged twice this month, please refund the extra amount"),
        ("Rahul K.", "rahul.k@example.com", "The app crashes every time I try to open my dashboard"),
        ("Meera S.", "meera.s@example.com", "Where is my order? It's been 6 days and tracking hasn't updated"),
        ("Store Admin", "admin@example.com", "How do I reset a customer's two factor authentication"),
        ("Priya N.", "priya.n@example.com", "What are your support hours on weekends"),
        ("Karan V.", "karan.v@example.com", "This is unacceptable, my account got suspended with no explanation"),
        ("Sana T.", "sana.t@example.com", "Thanks, my issue about the coupon code is now resolved"),
        ("Vikram J.", "vikram.j@example.com", "I need to change the email address linked to my account"),
        ("Divya P.", "divya.p@example.com", "The export button on the reports page does nothing"),
        ("Arjun M.", "arjun.m@example.com", "Can I get an invoice copy for last month's payment"),
    ]

    demo_users = {}
    for name, email, msg in demo_messages:
        user = get_or_create_user(name, email)
        demo_users[name] = user
        record_login(user["id"])
        result = classify_message(msg)
        insert_chat(
            user_name=name,
            query_text=msg,
            response_text=result["response"],
            intent=result["intent"],
            confidence=result["confidence"],
            sentiment=result["sentiment"],
            urgency_level=result["urgency"],
            is_escalated=result["escalated"],
            user_id=user["id"],
        )

    # A few sample expenses for the demo user "Aditi R." so the expense
    # tracker / analytics aren't empty on first look.
    aditi = demo_users.get("Aditi R.")
    if aditi:
        now = datetime.utcnow()
        demo_expenses = [
            ("Food & Dining", 450, "Dinner with friends", now.replace(hour=20, minute=15)),
            ("Transport", 180, "Cab to office", now.replace(hour=9, minute=5)),
            ("Groceries", 1200, "Weekly groceries", (now - timedelta(days=1)).replace(hour=18, minute=30)),
            ("Food & Dining", 220, "Coffee + snacks", (now - timedelta(days=1)).replace(hour=16, minute=0)),
            ("Entertainment", 600, "Movie tickets", (now - timedelta(days=2)).replace(hour=21, minute=0)),
            ("Bills & Utilities", 1500, "Electricity bill", (now - timedelta(days=3)).replace(hour=11, minute=0)),
            ("Shopping", 2200, "New shoes", (now - timedelta(days=4)).replace(hour=17, minute=45)),
            ("Food & Dining", 380, "Lunch order", (now - timedelta(days=5)).replace(hour=13, minute=20)),
        ]
        for category, amount, note, when in demo_expenses:
            add_expense(aditi["id"], category, amount, note, when.strftime("%Y-%m-%d %H:%M:%S"))

        create_notification(
            aditi["id"], "Welcome to SmartAssist AI",
            "Your account is set up. Explore My Space to track expenses, view incidents, and manage your profile.",
            "info",
        )
