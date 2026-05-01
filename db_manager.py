import sqlite3
from datetime import datetime

DB_PATH = "flyobj_bot.sqlite3"


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_counter (
            month TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            limit_val INTEGER DEFAULT 350
        )
    """)
    conn.commit()
    return conn


class DbManager:
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

    @staticmethod
    def _current_month() -> str:
        now = datetime.now()
        return f"{now.month}-{now.year}"
