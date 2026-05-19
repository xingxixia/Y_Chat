from __future__ import annotations

import json
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
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                record_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                layer TEXT NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL,
                content_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                supersedes_record_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_audit_log (
                audit_id TEXT PRIMARY KEY,
                record_id TEXT,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
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


def memory_status_payload() -> dict[str, Any]:
    ensure_memory_db()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        manual_count = db.execute("SELECT COUNT(*) AS count FROM memory_items").fetchone()["count"]
        record_count = db.execute("SELECT COUNT(*) AS count FROM memory_records").fetchone()["count"]
        audit_count = db.execute("SELECT COUNT(*) AS count FROM memory_audit_log").fetchone()["count"]

    return {
        "manual_enabled": memory_enabled(),
        "automatic_writes_enabled": False,
        "manual_items_count": manual_count,
        "records_count": record_count,
        "audit_count": audit_count,
        "formal_tables_ready": True,
        "manual_notes_legacy": True,
    }


def list_memory_records(limit: int = 100) -> list[dict[str, Any]]:
    ensure_memory_db()
    safe_limit = max(1, min(limit, 200))
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT record_id, kind, layer, status, version, content_json,
                   evidence_json, supersedes_record_id, created_at, updated_at
            FROM memory_records
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [
        {
            **dict(row),
            "content": json.loads(row["content_json"]),
            "evidence": json.loads(row["evidence_json"]),
            "content_json": None,
            "evidence_json": None,
        }
        for row in rows
    ]


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
