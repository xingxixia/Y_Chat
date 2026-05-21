from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from .memory_store import db_path, ensure_memory_db, now_iso


def list_memory_items() -> list[dict[str, Any]]:
    ensure_memory_db()
    with sqlite3.connect(db_path()) as db:
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
    ensure_memory_db()
    item = {
        "id": str(uuid4()),
        "kind": kind,
        "text": text,
        "created_at": now_iso(),
    }
    with sqlite3.connect(db_path()) as db:
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
    with sqlite3.connect(db_path()) as db:
        cursor = db.execute("DELETE FROM memory_items WHERE id = ?", (item_id,))
    return cursor.rowcount > 0
