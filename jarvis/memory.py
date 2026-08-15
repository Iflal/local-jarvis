"""Local SQLite storage for conversations, notes, and reminders."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class MemoryStore:
    def __init__(self, database_path: str) -> None:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    due_at REAL NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def add_message(self, role: str, content: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO messages(role, content, created_at) VALUES (?, ?, ?)",
                (role, content, time.time()),
            )

    def recent_messages(self, limit: int) -> list[dict[str, str]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def last_user_message(self) -> str | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT content FROM messages WHERE role = 'user' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return str(row["content"]) if row else None

    def add_note(self, content: str) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO notes(content, created_at) VALUES (?, ?)",
                (content, time.time()),
            )
            return int(cursor.lastrowid)

    def list_notes(self, limit: int = 10) -> list[tuple[int, str]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, content FROM notes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [(int(row["id"]), str(row["content"])) for row in rows]

    def add_reminder(self, content: str, due_at: float) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO reminders(content, due_at) VALUES (?, ?)",
                (content, due_at),
            )
            return int(cursor.lastrowid)

    def pop_due_reminders(self, now: float | None = None) -> list[str]:
        current = time.time() if now is None else now
        with self._lock, self._connection:
            rows = self._connection.execute(
                "SELECT id, content FROM reminders WHERE delivered = 0 AND due_at <= ? ORDER BY due_at",
                (current,),
            ).fetchall()
            if rows:
                self._connection.executemany(
                    "UPDATE reminders SET delivered = 1 WHERE id = ?",
                    [(int(row["id"]),) for row in rows],
                )
        return [str(row["content"]) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()
