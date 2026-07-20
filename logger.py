import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "concurrency_lab.db")


def init_db():
    """Creates the database file and 'runs' table if they don't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            demo_type TEXT NOT NULL,       -- 'producer_consumer' or 'dining_philosophers'
            mode TEXT NOT NULL,            -- 'safe' or 'unsafe'
            duration_seconds REAL NOT NULL,
            violation_count INTEGER DEFAULT 0,
            deadlock_detected INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def log_run(demo_type, mode, duration_seconds, violation_count=0, deadlock_detected=0):
    """Saves one completed demo run's stats into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO runs (demo_type, mode, duration_seconds, violation_count, deadlock_detected)
        VALUES (?, ?, ?, ?, ?)
    """, (demo_type, mode, duration_seconds, violation_count, deadlock_detected))
    conn.commit()
    conn.close()


def get_all_runs():
    """Fetches every logged run — used later by stats.py to build graphs."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT demo_type, mode, duration_seconds, violation_count, deadlock_detected, timestamp FROM runs")
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_all_runs():
    """Wipes all logged run data. Use before a final demo for a clean dataset."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM runs")
    conn.commit()
    conn.close()