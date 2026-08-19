import sqlite3

DB_PATH = "runs.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            idempotency_key TEXT UNIQUE,
            goal TEXT NOT NULL,
            status TEXT NOT NULL,
            credits_spent INTEGER NOT NULL DEFAULT 0,
            steps_json TEXT NOT NULL DEFAULT '[]',
            result TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()