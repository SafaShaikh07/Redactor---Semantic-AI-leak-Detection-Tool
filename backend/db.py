import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "logs.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_length INTEGER NOT NULL,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            matched_doc TEXT,
            reason_detail TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("PRAGMA table_info(logs)")
    columns = [row[1] for row in cursor.fetchall()]
    if "reason_detail" not in columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN reason_detail TEXT")
    conn.commit()
    conn.close()

def log_check(input_length: int, action: str, reason: str, matched_doc: str = None, reason_detail: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO logs (input_length, action, reason, matched_doc, reason_detail, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (input_length, action, reason, matched_doc, reason_detail, timestamp))
    conn.commit()
    conn.close()

def get_recent_logs(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, input_length, action, reason, matched_doc, reason_detail, timestamp
        FROM logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Initialize DB on module import
init_db()
