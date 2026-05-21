from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import RUNTIME_DIR, runtime_sqlite_path
from ..data.sqlite_store import ensure_column


def db_path() -> Path:
    return runtime_sqlite_path()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def ensure_memory_db() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path()) as db:
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
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_observations (
                observation_id TEXT PRIMARY KEY,
                source_event_id TEXT,
                modality TEXT NOT NULL,
                source TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                feature_refs_json TEXT NOT NULL,
                raw_ref TEXT,
                confidence REAL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entities (
                entity_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                label TEXT,
                status TEXT NOT NULL,
                confidence REAL,
                summary_json TEXT NOT NULL,
                feature_refs_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_features (
                feature_id TEXT PRIMARY KEY,
                modality TEXT NOT NULL,
                feature_kind TEXT NOT NULL,
                owner_entity_id TEXT,
                source_observation_id TEXT,
                storage_ref TEXT,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_links (
                link_id TEXT PRIMARY KEY,
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                confidence REAL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_review_queue (
                review_id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_consolidation_buffer (
                buffer_id TEXT PRIMARY KEY,
                target_layer TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                source_refs_json TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL,
                feature_refs_json TEXT NOT NULL,
                entity_candidate_refs_json TEXT NOT NULL,
                confidence REAL,
                importance REAL,
                review_required INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_backups (
                backup_id TEXT PRIMARY KEY,
                modality TEXT NOT NULL,
                storage_ref TEXT NOT NULL,
                size_bytes INTEGER,
                expires_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_visual_evidence (
                evidence_id TEXT PRIMARY KEY,
                source_event_id TEXT,
                attachment_id TEXT,
                source TEXT NOT NULL,
                raw_ref TEXT,
                backup_id TEXT,
                observation_id TEXT,
                feature_refs_json TEXT NOT NULL,
                entity_candidate_refs_json TEXT NOT NULL,
                mime TEXT,
                sha256 TEXT,
                width INTEGER,
                height INTEGER,
                source_display_width INTEGER,
                source_display_height INTEGER,
                thumbnail_max_width INTEGER,
                raw_available INTEGER NOT NULL,
                vision_reader_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        ensure_column(db, "memory_visual_evidence", "source_display_width", "INTEGER")
        ensure_column(db, "memory_visual_evidence", "source_display_height", "INTEGER")
        ensure_column(db, "memory_visual_evidence", "thumbnail_max_width", "INTEGER")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_text_evidence (
                evidence_id TEXT PRIMARY KEY,
                source_event_id TEXT,
                source TEXT NOT NULL,
                observation_id TEXT,
                feature_refs_json TEXT NOT NULL,
                text_chars INTEGER,
                text_hash TEXT,
                language TEXT,
                text_reader_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_audio_evidence (
                evidence_id TEXT PRIMARY KEY,
                source_event_id TEXT,
                attachment_id TEXT,
                source TEXT NOT NULL,
                raw_ref TEXT,
                backup_id TEXT,
                observation_id TEXT,
                feature_refs_json TEXT NOT NULL,
                transcript_observation_id TEXT,
                mime TEXT,
                sha256 TEXT,
                duration_ms INTEGER,
                size_bytes INTEGER,
                raw_available INTEGER NOT NULL,
                audio_reader_status TEXT NOT NULL,
                transcript_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def list_table_rows(table: str, order_column: str = "created_at", limit: int = 100) -> list[dict[str, Any]]:
    ensure_memory_db()
    safe_limit = max(1, min(limit, 200))
    with sqlite3.connect(db_path()) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            f"""
            SELECT *
            FROM {table}
            ORDER BY {order_column} DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def parse_json_field(value: Any, fallback: Any) -> Any:
    if not isinstance(value, str) or not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
