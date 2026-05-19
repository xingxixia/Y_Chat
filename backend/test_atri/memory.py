from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import RUNTIME_DIR, load_config


DB_PATH = RUNTIME_DIR / "test_atri.sqlite3"


def memory_enabled() -> bool:
    config = load_config()
    return bool(config.get("permissions", {}).get("memory.write", False))


def ensure_memory_db() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def list_memory_items() -> list[dict[str, Any]]:
    ensure_memory_db()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT id, kind, text, created_at
            FROM memory_items
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
    return [dict(row) for row in rows]


def add_memory_item(kind: str, text: str) -> dict[str, Any]:
    if not memory_enabled():
        raise PermissionError("memory.write is disabled")

    ensure_memory_db()
    item = {
        "id": str(uuid4()),
        "kind": kind,
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            INSERT INTO memory_items (id, kind, text, created_at)
            VALUES (:id, :kind, :text, :created_at)
            """,
            item,
        )
    return item


def delete_memory_item(item_id: str) -> bool:
    ensure_memory_db()
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("DELETE FROM memory_items WHERE id = ?", (item_id,))
    return cursor.rowcount > 0
