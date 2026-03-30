import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "squat_counter.db"


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                reps       INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS handstand_sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at   TEXT NOT NULL,
                duration   REAL NOT NULL
            )
        """)


def save_session(reps: int, started_at: datetime, ended_at: datetime) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (reps, started_at, ended_at) VALUES (?, ?, ?)",
            (reps, started_at.isoformat(), ended_at.isoformat()),
        )


def get_daily_totals(from_date: date, to_date: date) -> list[tuple[str, int]]:
    """Return [(date_str, total_reps), ...] grouped by day, inclusive range."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT date(started_at) AS day, SUM(reps)
            FROM sessions
            WHERE date(started_at) BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day
            """,
            (from_date.isoformat(), to_date.isoformat()),
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def get_all_sessions() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, reps, started_at, ended_at FROM sessions ORDER BY started_at DESC"
        ).fetchall()
    return [
        {"id": r[0], "reps": r[1], "started_at": r[2], "ended_at": r[3]}
        for r in rows
    ]


def save_handstand_session(started_at: datetime, ended_at: datetime, duration: float) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO handstand_sessions (started_at, ended_at, duration) VALUES (?, ?, ?)",
            (started_at.isoformat(), ended_at.isoformat(), duration),
        )


def get_all_handstand_sessions() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, started_at, ended_at, duration FROM handstand_sessions ORDER BY started_at DESC"
        ).fetchall()
    return [
        {"id": r[0], "started_at": r[1], "ended_at": r[2], "duration": r[3]}
        for r in rows
    ]


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)
