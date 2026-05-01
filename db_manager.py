import sqlite3
from datetime import datetime
from typing import Optional, Tuple

DB_PATH = "flyobj_bot.sqlite3"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_counter (
            month TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            limit_val INTEGER DEFAULT 350
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_state (
            chat_id INTEGER PRIMARY KEY,
            last_lat REAL,
            last_lon REAL,
            waiting_address INTEGER DEFAULT 0,
            pending_track TEXT
        )
    """)
    conn.commit()
    return conn


def _ensure_user(conn: sqlite3.Connection, chat_id: int):
    conn.execute("INSERT OR IGNORE INTO user_state (chat_id) VALUES (?)", (chat_id,))


class DbManager:
    # --- quota API ---

    def has_quota_available(self) -> bool:
        month = self._current_month()
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT count, limit_val FROM api_counter WHERE month = ?", (month,)
            ).fetchone()
            if row is None:
                conn.execute("INSERT INTO api_counter (month) VALUES (?)", (month,))
                conn.commit()
                return True
            return row[0] < row[1]

    def increase_counter(self):
        month = self._current_month()
        with _get_conn() as conn:
            conn.execute(
                "UPDATE api_counter SET count = count + 1 WHERE month = ?", (month,)
            )
            conn.commit()

    # --- stato conversazionale ---

    def save_coords(self, chat_id: int, lat: float, lon: float):
        with _get_conn() as conn:
            _ensure_user(conn, chat_id)
            conn.execute(
                "UPDATE user_state SET last_lat=?, last_lon=? WHERE chat_id=?",
                (lat, lon, chat_id)
            )
            conn.commit()

    def get_coords(self, chat_id: int) -> Optional[Tuple[float, float]]:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT last_lat, last_lon FROM user_state WHERE chat_id=?", (chat_id,)
            ).fetchone()
        if row and row[0] is not None and row[1] is not None:
            return (row[0], row[1])
        return None

    def set_waiting_address(self, chat_id: int, waiting: bool):
        with _get_conn() as conn:
            _ensure_user(conn, chat_id)
            conn.execute(
                "UPDATE user_state SET waiting_address=? WHERE chat_id=?",
                (1 if waiting else 0, chat_id)
            )
            conn.commit()

    def is_waiting_address(self, chat_id: int) -> bool:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT waiting_address FROM user_state WHERE chat_id=?", (chat_id,)
            ).fetchone()
        return bool(row and row[0])

    def set_pending_track(self, chat_id: int, path: Optional[str]):
        with _get_conn() as conn:
            _ensure_user(conn, chat_id)
            conn.execute(
                "UPDATE user_state SET pending_track=? WHERE chat_id=?",
                (path, chat_id)
            )
            conn.commit()

    def get_pending_track(self, chat_id: int) -> Optional[str]:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT pending_track FROM user_state WHERE chat_id=?", (chat_id,)
            ).fetchone()
        return row[0] if row else None

    @staticmethod
    def _current_month() -> str:
        now = datetime.now()
        return f"{now.month}-{now.year}"


db = DbManager()
