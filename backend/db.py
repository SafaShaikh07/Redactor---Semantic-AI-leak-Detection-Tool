import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

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
            latency_ms REAL,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("PRAGMA table_info(logs)")
    columns = [row[1] for row in cursor.fetchall()]
    if "reason_detail" not in columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN reason_detail TEXT")
    if "latency_ms" not in columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN latency_ms REAL")
    conn.commit()
    conn.close()

def log_check(input_length: int, action: str, reason: str, matched_doc: str = None, reason_detail: str = None, latency_ms: float = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO logs (input_length, action, reason, matched_doc, reason_detail, latency_ms, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (input_length, action, reason, matched_doc, reason_detail, latency_ms, timestamp))
    conn.commit()
    conn.close()

def get_recent_logs(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, input_length, action, reason, matched_doc, reason_detail, latency_ms, timestamp
        FROM logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_metrics() -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM logs")
    total_checks = cursor.fetchone()["total"]

    cursor.execute("SELECT action, COUNT(*) as cnt FROM logs GROUP BY action")
    actions = {"allow": 0, "redact": 0, "block": 0}
    for row in cursor.fetchall():
        act = row["action"].lower()
        if act in actions:
            actions[act] = row["cnt"]

    cursor.execute("SELECT latency_ms FROM logs WHERE latency_ms IS NOT NULL ORDER BY latency_ms ASC")
    latencies = [row["latency_ms"] for row in cursor.fetchall()]

    if latencies:
        avg_ms = round(sum(latencies) / len(latencies), 2)
        p95_idx = int(len(latencies) * 0.95)
        p95_idx = min(p95_idx, len(latencies) - 1)
        p95_ms = round(latencies[p95_idx], 2)
    else:
        avg_ms = 0.0
        p95_ms = 0.0

    cursor.execute("SELECT reason FROM logs WHERE reason != 'no match'")
    category_counts = {}
    for row in cursor.fetchall():
        reason_str = row["reason"]
        parts = [p.strip() for p in reason_str.replace("&", ",").split(",")]
        for p in parts:
            if not p:
                continue
            category_counts[p] = category_counts.get(p, 0) + 1

    conn.close()

    block_rate = round((actions["block"] / total_checks * 100), 1) if total_checks > 0 else 0.0
    redact_rate = round((actions["redact"] / total_checks * 100), 1) if total_checks > 0 else 0.0

    return {
        "total_checks": total_checks,
        "actions": actions,
        "rates": {
            "block_rate_pct": block_rate,
            "redact_rate_pct": redact_rate,
            "allow_rate_pct": round((actions["allow"] / total_checks * 100), 1) if total_checks > 0 else 0.0
        },
        "latency": {
            "avg_ms": avg_ms,
            "p95_ms": p95_ms
        },
        "category_counts": category_counts
    }

# Initialize DB on module import
init_db()
