from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..config import RUNTIME_DIR, runtime_sqlite_path
from ..data.sqlite_store import connect as connect_sqlite, table_columns


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_reasoning_db() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS reasoning_runs (
                run_id TEXT PRIMARY KEY,
                source_event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                depth TEXT NOT NULL,
                provider TEXT NOT NULL,
                primary_modality TEXT,
                modalities_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                reply_text TEXT,
                failure_summary TEXT
            )
            """
        )
        columns = table_columns(db, "reasoning_runs")
        if "primary_modality" not in columns:
            db.execute("ALTER TABLE reasoning_runs ADD COLUMN primary_modality TEXT")
        if "modalities_json" not in columns:
            db.execute("ALTER TABLE reasoning_runs ADD COLUMN modalities_json TEXT")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS reasoning_steps (
                step_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                step_type TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS reasoning_context_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS reasoning_schema_failures (
                failure_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                error TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS action_audit (
                audit_id TEXT PRIMARY KEY,
                run_id TEXT,
                action_id TEXT,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_actions (
                pending_id TEXT PRIMARY KEY,
                run_id TEXT,
                action_id TEXT,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS permission_audit (
                audit_id TEXT PRIMARY KEY,
                run_id TEXT,
                capability TEXT,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_write_candidates (
                candidate_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                target_layer TEXT NOT NULL,
                kind TEXT NOT NULL,
                confidence REAL NOT NULL,
                accepted INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_write_audit (
                audit_id TEXT PRIMARY KEY,
                run_id TEXT,
                candidate_id TEXT,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_config_audit (
                audit_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def connect() -> sqlite3.Connection:
    ensure_reasoning_db()
    return connect_sqlite(row_factory=True)


def insert_run(
    db: sqlite3.Connection,
    *,
    run_id: str,
    source_event_id: str,
    event_type: str,
    depth: str,
    provider: str,
    primary_modality: str,
    modalities: list[str],
    created_at: str,
) -> None:
    db.execute(
        """
        INSERT INTO reasoning_runs (
            run_id, source_event_id, event_type, status, depth, provider,
            primary_modality, modalities_json,
            created_at, updated_at, reply_text, failure_summary
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            source_event_id,
            event_type,
            "created",
            depth,
            provider,
            primary_modality,
            json.dumps(modalities, ensure_ascii=True),
            created_at,
            created_at,
            None,
            None,
        ),
    )


def insert_step(
    db: sqlite3.Connection,
    run_id: str,
    step_index: int,
    step_type: str,
    status: str,
    summary: str,
) -> str:
    step_id = str(uuid4())
    db.execute(
        """
        INSERT INTO reasoning_steps (
            step_id, run_id, step_index, step_type, status, summary, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (step_id, run_id, step_index, step_type, status, summary, now_iso()),
    )
    return step_id


def record_context_snapshot(
    db: sqlite3.Connection,
    run_id: str,
    snapshot: dict[str, Any],
) -> str:
    snapshot_id = str(uuid4())
    db.execute(
        """
        INSERT INTO reasoning_context_snapshots (
            snapshot_id, run_id, schema_version, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            run_id,
            snapshot["schema_version"],
            json.dumps(snapshot, ensure_ascii=True),
            now_iso(),
        ),
    )
    return snapshot_id


def insert_memory_candidate(
    db: sqlite3.Connection,
    run_id: str,
    candidate: dict[str, Any],
) -> str:
    candidate_id = str(candidate["candidate_id"])
    payload = {**candidate, "accepted": False}
    db.execute(
        """
        INSERT INTO memory_write_candidates (
            candidate_id, run_id, target_layer, kind, confidence, accepted,
            payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            run_id,
            payload["target_layer"],
            payload["kind"],
            float(payload["confidence"]),
            0,
            json.dumps(payload, ensure_ascii=True),
            now_iso(),
        ),
    )
    return candidate_id


def record_memory_write_audit(
    db: sqlite3.Connection,
    run_id: str,
    candidate: dict[str, Any],
    status: str,
) -> None:
    payload = {
        "candidate_id": candidate["candidate_id"],
        "target_layer": candidate["target_layer"],
        "kind": candidate["kind"],
        "accepted": False,
        "status": status,
        "reason": candidate.get("reason"),
        "review_required": candidate.get("review_required", True),
    }
    db.execute(
        """
        INSERT INTO memory_write_audit (
            audit_id, run_id, candidate_id, status, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            run_id,
            str(candidate["candidate_id"]),
            status,
            json.dumps(payload, ensure_ascii=True),
            now_iso(),
        ),
    )


def record_schema_failure(db: sqlite3.Connection, run_id: str, error: str) -> None:
    db.execute(
        """
        INSERT INTO reasoning_schema_failures (failure_id, run_id, error, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid4()), run_id, error, now_iso()),
    )


def record_repair_attempt(
    db: sqlite3.Connection,
    run_id: str,
    status: str,
    before_errors: list[str],
    after_errors: list[str],
) -> None:
    payload = {
        "status": status,
        "before_errors": before_errors,
        "after_errors": after_errors,
        "repair_policy": "fill_missing_structural_defaults_only",
    }
    db.execute(
        """
        INSERT INTO reasoning_schema_failures (failure_id, run_id, error, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid4()), run_id, json.dumps(payload, ensure_ascii=True), now_iso()),
    )


def record_action_proposal(
    db: sqlite3.Connection,
    run_id: str,
    action: dict[str, Any],
    status: str,
    reason: str,
) -> None:
    payload = {**action, "status": status, "policy_reason": reason, "executed": False}
    db.execute(
        """
        INSERT INTO action_audit (
            audit_id, run_id, action_id, status, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            run_id,
            action["action_id"],
            status,
            json.dumps(payload, ensure_ascii=True),
            now_iso(),
        ),
    )


def record_pending_action(
    db: sqlite3.Connection,
    run_id: str,
    action: dict[str, Any],
    reason: str,
) -> str:
    pending_id = str(uuid4())
    payload = {**action, "pending_reason": reason, "executed": False}
    db.execute(
        """
        INSERT INTO pending_actions (
            pending_id, run_id, action_id, status, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            pending_id,
            run_id,
            action["action_id"],
            "pending",
            json.dumps(payload, ensure_ascii=True),
            now_iso(),
        ),
    )
    return pending_id


def mark_run_schema_failed(
    db: sqlite3.Connection,
    run_id: str,
    validation_errors: list[str],
) -> None:
    db.execute(
        """
        UPDATE reasoning_runs
        SET status = ?, updated_at = ?, failure_summary = ?
        WHERE run_id = ?
        """,
        ("schema_failed", now_iso(), "; ".join(validation_errors), run_id),
    )


def mark_run_completed(db: sqlite3.Connection, run_id: str, reply_text: str) -> None:
    db.execute(
        """
        UPDATE reasoning_runs
        SET status = ?, updated_at = ?, reply_text = ?
        WHERE run_id = ?
        """,
        ("completed", now_iso(), reply_text, run_id),
    )
