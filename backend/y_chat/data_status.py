from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import CONFIG_PATH, RUNTIME_DIR, runtime_sqlite_path
from .data.sqlite_store import table_names
from .memory import ensure_memory_db
from .shared.contracts import SchemaVersion


TABLES: dict[str, list[str]] = {
    "memory": [
        "memory_items",
        "memory_records",
        "memory_audit_log",
        "memory_observations",
        "memory_entities",
        "memory_features",
        "memory_links",
        "memory_review_queue",
        "memory_consolidation_buffer",
        "raw_backups",
        "memory_visual_evidence",
        "memory_text_evidence",
        "memory_audio_evidence",
    ],
    "reasoning": [
        "reasoning_runs",
        "reasoning_steps",
        "reasoning_context_snapshots",
        "reasoning_schema_failures",
        "reasoning_action_proposals",
        "pending_actions",
        "memory_write_candidates",
        "memory_write_audit",
    ],
    "provider": ["provider_config_audit"],
}


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def _table_count(db: sqlite3.Connection, table: str) -> int | None:
    try:
        return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return None


def data_status_payload() -> dict[str, Any]:
    ensure_memory_db()
    sqlite_path = runtime_sqlite_path()
    table_status: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(sqlite_path) as db:
        existing = table_names(db)
        for group, tables in TABLES.items():
            table_status[group] = {
                table: {
                    "exists": table in existing,
                    "rows": _table_count(db, table) if table in existing else None,
                }
                for table in tables
            }

    runtime_files = {
        "config": CONFIG_PATH,
        "sqlite": sqlite_path,
        "events": RUNTIME_DIR / "events.jsonl",
    }
    runtime_file_status = {
        name: {
            "path": str(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
        }
        for name, path in runtime_files.items()
    }
    blob_root = RUNTIME_DIR / "memory_blobs"
    screenshot_root = blob_root / "vision" / "screenshots"
    return {
        "schema_version": SchemaVersion.DATA_STATUS,
        "runtime_dir": str(RUNTIME_DIR),
        "runtime_files": runtime_file_status,
        "tables": table_status,
        "blob_storage": {
            "root": str(blob_root),
            "exists": blob_root.exists(),
            "bytes": _dir_size(blob_root),
            "vision_screenshots": {
                "path": str(screenshot_root),
                "exists": screenshot_root.exists(),
                "bytes": _dir_size(screenshot_root),
            },
        },
        "raw_payload_returned": False,
    }
