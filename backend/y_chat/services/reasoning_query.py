from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable


def decorate_run_row(
    row: dict[str, Any],
    infer_modality_payload: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    modalities_json = row.pop("modalities_json", None)
    modalities = None
    if isinstance(modalities_json, str) and modalities_json:
        try:
            parsed = json.loads(modalities_json)
            if isinstance(parsed, list):
                modalities = [str(item) for item in parsed]
        except json.JSONDecodeError:
            modalities = None
    if not modalities:
        inferred = infer_modality_payload(str(row.get("event_type", "")))
        modalities = inferred["modalities"]
    primary_modality = row.get("primary_modality") or next(iter(modalities), "event")
    return {**row, "primary_modality": primary_modality, "modalities": modalities}


def get_latest_run_summary(
    db: sqlite3.Connection,
    infer_modality_payload: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, Any] | None, int]:
    row = db.execute(
        """
        SELECT run_id, event_type, status, depth, provider, primary_modality,
               modalities_json, updated_at, failure_summary
        FROM reasoning_runs
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).fetchone()
    total = db.execute("SELECT COUNT(*) AS count FROM reasoning_runs").fetchone()["count"]
    current_run = decorate_run_row(dict(row), infer_modality_payload) if row else None
    return current_run, int(total)


def list_reasoning_runs(
    db: sqlite3.Connection,
    infer_modality_payload: Callable[[str], dict[str, Any]],
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))
    rows = db.execute(
        """
        SELECT run_id, source_event_id, event_type, status, depth, provider,
               primary_modality, modalities_json,
               created_at, updated_at, reply_text, failure_summary
        FROM reasoning_runs
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (safe_limit,),
    ).fetchall()
    return [decorate_run_row(dict(row), infer_modality_payload) for row in rows]


def get_reasoning_run(
    db: sqlite3.Connection,
    run_id: str,
    infer_modality_payload: Callable[[str], dict[str, Any]],
) -> dict[str, Any] | None:
    run = db.execute(
        """
        SELECT run_id, source_event_id, event_type, status, depth, provider,
               primary_modality, modalities_json,
               created_at, updated_at, reply_text, failure_summary
        FROM reasoning_runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if run is None:
        return None

    steps = db.execute(
        """
        SELECT step_id, run_id, step_index, step_type, status, summary, created_at
        FROM reasoning_steps
        WHERE run_id = ?
        ORDER BY step_index ASC
        """,
        (run_id,),
    ).fetchall()
    candidates = db.execute(
        """
        SELECT candidate_id, run_id, target_layer, kind, confidence, accepted,
               payload_json, created_at
        FROM memory_write_candidates
        WHERE run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()
    schema_failures = db.execute(
        """
        SELECT failure_id, run_id, error, created_at
        FROM reasoning_schema_failures
        WHERE run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()
    context_snapshots = db.execute(
        """
        SELECT snapshot_id, run_id, schema_version, payload_json, created_at
        FROM reasoning_context_snapshots
        WHERE run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()
    action_audit = db.execute(
        """
        SELECT audit_id, run_id, action_id, status, payload_json, created_at
        FROM action_audit
        WHERE run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()
    pending_actions = db.execute(
        """
        SELECT pending_id, run_id, action_id, status, payload_json, created_at
        FROM pending_actions
        WHERE run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()
    memory_audit = db.execute(
        """
        SELECT audit_id, run_id, candidate_id, status, payload_json, created_at
        FROM memory_write_audit
        WHERE run_id = ?
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()

    return {
        "run": decorate_run_row(dict(run), infer_modality_payload),
        "steps": [dict(row) for row in steps],
        "context_snapshots": [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in context_snapshots
        ],
        "schema_failures": [dict(row) for row in schema_failures],
        "memory_candidates": [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in candidates
        ],
        "actions": [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in action_audit
        ],
        "pending_actions": [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in pending_actions
        ],
        "audit": [
            {
                "kind": "action",
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in action_audit
        ]
        + [
            {
                "kind": "memory_write",
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in memory_audit
        ],
    }
