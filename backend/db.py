import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "logs.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS logs")
    cursor.execute("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_length INTEGER NOT NULL,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            matched_doc TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def log_check(input_length: int, action: str, reason: str, matched_doc: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO logs (input_length, action, reason, matched_doc, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (input_length, action, reason, matched_doc, timestamp))
    conn.commit()
    conn.close()

def get_recent_logs(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, input_length, action, reason, matched_doc, timestamp
        FROM logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Initialize DB on module import
init_db()
