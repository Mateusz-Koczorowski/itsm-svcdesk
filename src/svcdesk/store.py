# ai-generated: 100% - Claude wrote the SQLite store; reviewed by me
"""Ticket persistence: one SQLite file in the named volume (API.md section 10, R-23)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path


class Store:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS tickets ("
            " seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, data TEXT NOT NULL)"
        )
        self._db.commit()

    def insert(self, ticket: dict) -> None:
        with self._lock:
            self._db.execute("INSERT INTO tickets (id, data) VALUES (?, ?)", (ticket["id"], json.dumps(ticket)))
            self._db.commit()

    def update(self, ticket: dict) -> None:
        with self._lock:
            self._db.execute("UPDATE tickets SET data = ? WHERE id = ?", (json.dumps(ticket), ticket["id"]))
            self._db.commit()

    def get(self, ticket_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT data FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM tickets ORDER BY seq").fetchall()
        return [json.loads(r[0]) for r in rows]


def default_store() -> Store:
    return Store(os.environ.get("SVCDESK_DB", "/data/svcdesk.db"))
