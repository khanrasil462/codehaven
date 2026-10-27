from __future__ import annotations

import sqlite3
from datetime import datetime

from app.core.database import DB_PATH

_ready = False


def _connect() -> sqlite3.Connection:
    global _ready
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    if not _ready:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                day TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL
            )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_usage_day ON token_usage(day)")
        _ready = True
    return conn


def record_usage(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return
    now = datetime.now()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO token_usage (ts, day, model, prompt_tokens, completion_tokens) VALUES (?,?,?,?,?)",
                (now.isoformat(timespec="seconds"), now.strftime("%Y-%m-%d"), model, prompt_tokens, completion_tokens),
            )
    except sqlite3.Error:
        pass  # usage tracking must never break a generation


def month_usage(month: str) -> dict:
    """Aggregate usage for a 'YYYY-MM' month."""
    like = f"{month}-%"
    with _connect() as conn:
        days = conn.execute(
            """SELECT day, SUM(prompt_tokens), SUM(completion_tokens), COUNT(*)
               FROM token_usage WHERE day LIKE ? GROUP BY day ORDER BY day""",
            (like,),
        ).fetchall()
        models = conn.execute(
            """SELECT model, SUM(prompt_tokens), SUM(completion_tokens), COUNT(*)
               FROM token_usage WHERE day LIKE ? GROUP BY model ORDER BY SUM(prompt_tokens + completion_tokens) DESC""",
            (like,),
        ).fetchall()
        today = conn.execute(
            "SELECT COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0) FROM token_usage WHERE day = ?",
            (datetime.now().strftime("%Y-%m-%d"),),
        ).fetchone()
        all_time = conn.execute(
            "SELECT COALESCE(SUM(prompt_tokens + completion_tokens),0) FROM token_usage"
        ).fetchone()

    def row(r, key):
        return {key: r[0], "prompt_tokens": r[1], "completion_tokens": r[2], "requests": r[3]}

    daily = [row(r, "day") for r in days]
    return {
        "month": month,
        "prompt_tokens": sum(d["prompt_tokens"] for d in daily),
        "completion_tokens": sum(d["completion_tokens"] for d in daily),
        "requests": sum(d["requests"] for d in daily),
        "daily": daily,
        "models": [row(r, "model") for r in models],
        "today_tokens": today[0] + today[1],
        "all_time_tokens": all_time[0],
    }
