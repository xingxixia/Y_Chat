from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import RUNTIME_DIR, load_config
from .events import EventEnvelope, make_event


DB_PATH = RUNTIME_DIR / "test_atri.sqlite3"
PROVIDER_NAME = "deterministic_fallback"
SCHEMA_VERSION = "reasoning.v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reasoning_enabled() -> bool:
    config = load_config()
    return bool(config.get("reasoning", {}).get("enabled", True))


def ensure_reasoning_db() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS reasoning_runs (
                run_id TEXT PRIMARY KEY,
                source_event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                depth TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                reply_text TEXT,
                failure_summary TEXT
            )
            """
        )
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


def _connect() -> sqlite3.Connection:
    ensure_reasoning_db()
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def _insert_step(
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


def _insert_memory_candidate(
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


def _record_schema_failure(db: sqlite3.Connection, run_id: str, error: str) -> None:
    db.execute(
        """
        INSERT INTO reasoning_schema_failures (failure_id, run_id, error, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid4()), run_id, error, now_iso()),
    )


def build_deterministic_output(run_id: str, event: EventEnvelope) -> dict[str, Any]:
    text = str(event.payload.get("text", "")).strip()
    reply_text = (
        f"Received: {text}\n\n"
        "Reasoning R1 deterministic fallback handled this command."
    )
    candidate_id = str(uuid4())
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "reply": {
            "should_reply": True,
            "text": reply_text,
            "bubble_text": reply_text,
            "style": "normal",
            "final": True,
        },
        "state": {
            "pet_state": "talking",
            "emotion": "neutral",
            "animation": None,
        },
        "actions": [],
        "memory": {
            "write_candidates": [
                {
                    "candidate_id": candidate_id,
                    "target_layer": "short_term",
                    "kind": "task_state",
                    "content": {"text": text},
                    "related_entity_id": None,
                    "source_event_ids": [event.event_id],
                    "reason": "R1 fallback records command input for Debug inspection only.",
                    "confidence": 0.4,
                    "importance": 0.2,
                    "review_required": True,
                }
            ],
            "do_not_write_reason": None,
            "needs_consolidation": False,
        },
        "observations": [],
        "voice": {
            "speak": False,
            "text": None,
            "voice_style": None,
        },
        "debug": {
            "depth": "lightweight",
            "needs_deep_retrieval": False,
            "deep_retrieval_query": None,
            "trace": [],
        },
        "audit": {
            "safety_notes": ["deterministic fallback; real model not called"],
            "permission_requests": [],
        },
    }


def validate_reasoning_output(output: dict[str, Any], run_id: str) -> list[str]:
    errors: list[str] = []
    if output.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be reasoning.v1")
    if output.get("run_id") != run_id:
        errors.append("run_id mismatch")

    reply = output.get("reply")
    if not isinstance(reply, dict):
        errors.append("reply must be an object")
    else:
        if not isinstance(reply.get("should_reply"), bool):
            errors.append("reply.should_reply must be boolean")
        if reply.get("should_reply") and not isinstance(reply.get("text"), str):
            errors.append("reply.text must be string when should_reply is true")
        if reply.get("final") is not True:
            errors.append("reply.final must be true")

    if not isinstance(output.get("actions"), list):
        errors.append("actions must be a list")

    memory = output.get("memory")
    if not isinstance(memory, dict):
        errors.append("memory must be an object")
    elif not isinstance(memory.get("write_candidates"), list):
        errors.append("memory.write_candidates must be a list")
    else:
        for index, candidate in enumerate(memory["write_candidates"]):
            if not isinstance(candidate, dict):
                errors.append(f"memory.write_candidates[{index}] must be an object")
                continue
            for field in ("candidate_id", "target_layer", "kind", "content", "source_event_ids", "confidence"):
                if field not in candidate:
                    errors.append(f"memory.write_candidates[{index}].{field} is required")
            if "confidence" in candidate and not isinstance(candidate["confidence"], int | float):
                errors.append(f"memory.write_candidates[{index}].confidence must be numeric")

    return errors


def run_deterministic_reasoning(event: EventEnvelope) -> dict[str, Any]:
    ensure_reasoning_db()

    run_id = str(uuid4())
    created_at = now_iso()
    output = build_deterministic_output(run_id, event)
    validation_errors = validate_reasoning_output(output, run_id)
    reply = output.get("reply") if isinstance(output.get("reply"), dict) else {}
    reply_text = str(reply.get("bubble_text") or reply.get("text") or "")

    with _connect() as db:
        db.execute(
            """
            INSERT INTO reasoning_runs (
                run_id, source_event_id, event_type, status, depth, provider,
                created_at, updated_at, reply_text, failure_summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                event.event_id,
                event.type,
                "created",
                "lightweight",
                PROVIDER_NAME,
                created_at,
                created_at,
                None,
                None,
            ),
        )
        context_step_id = _insert_step(
            db,
            run_id,
            1,
            "context_check",
            "completed",
            "R1 built a minimal context packet from the source event.",
        )
        output_step_id = _insert_step(
            db,
            run_id,
            2,
            "deterministic_fallback",
            "completed",
            "R1 produced a safe deterministic fallback reasoning.v1 output.",
        )
        schema_step_id = _insert_step(
            db,
            run_id,
            3,
            "schema_validating",
            "completed" if not validation_errors else "failed",
            "R1 validated deterministic fallback output against reasoning.v1.",
        )
        if validation_errors:
            for error in validation_errors:
                _record_schema_failure(db, run_id, error)
            db.execute(
                """
                UPDATE reasoning_runs
                SET status = ?, updated_at = ?, failure_summary = ?
                WHERE run_id = ?
                """,
                ("schema_failed", now_iso(), "; ".join(validation_errors), run_id),
            )
            return {
                "run_id": run_id,
                "events": [
                    make_event(
                        "reasoning.started",
                        "backend",
                        {
                            "run_id": run_id,
                            "depth": "lightweight",
                            "provider": PROVIDER_NAME,
                            "source_event_id": event.event_id,
                        },
                        correlation_id=event.event_id,
                    ).model_dump(),
                    make_event(
                        "reasoning.schema.invalid",
                        "backend",
                        {"run_id": run_id, "errors": validation_errors},
                        correlation_id=event.event_id,
                    ).model_dump(),
                    make_event(
                        "reasoning.failed",
                        "backend",
                        {"run_id": run_id, "reason": "schema_failed"},
                        correlation_id=event.event_id,
                    ).model_dump(),
                ],
            }

        candidate_ids = [
            _insert_memory_candidate(db, run_id, candidate)
            for candidate in output["memory"]["write_candidates"]
        ]
        updated_at = now_iso()
        db.execute(
            """
            UPDATE reasoning_runs
            SET status = ?, updated_at = ?, reply_text = ?
            WHERE run_id = ?
            """,
            ("completed", updated_at, reply_text, run_id),
        )

    events = [
        make_event(
            "reasoning.started",
            "backend",
            {
                "run_id": run_id,
                "depth": "lightweight",
                "provider": PROVIDER_NAME,
                "source_event_id": event.event_id,
            },
            correlation_id=event.event_id,
        ),
        make_event(
            "pet.state.changed",
            "backend",
            {
                "state": "thinking",
                "previous_state": "idle",
                "run_id": run_id,
            },
            correlation_id=event.event_id,
        ),
        make_event(
            "reasoning.step.completed",
            "backend",
            {
                "run_id": run_id,
                "step_id": context_step_id,
                "step_type": "context_check",
                "status": "completed",
            },
            correlation_id=event.event_id,
        ),
        make_event(
            "reasoning.step.completed",
            "backend",
            {
                "run_id": run_id,
                "step_id": output_step_id,
                "step_type": "deterministic_fallback",
                "status": "completed",
            },
            correlation_id=event.event_id,
        ),
        make_event(
            "reasoning.step.completed",
            "backend",
            {
                "run_id": run_id,
                "step_id": schema_step_id,
                "step_type": "schema_validating",
                "status": "completed",
            },
            correlation_id=event.event_id,
        ),
        make_event(
            "reasoning.output.produced",
            "backend",
            {
                "run_id": run_id,
                "schema_version": SCHEMA_VERSION,
                "provider": PROVIDER_NAME,
                "memory_candidate_ids": candidate_ids,
            },
            correlation_id=event.event_id,
        ),
        make_event(
            "pet.bubble.show",
            "backend",
            {"text": reply_text, "run_id": run_id},
            correlation_id=event.event_id,
        ),
        make_event(
            "pet.state.changed",
            "backend",
            {
                "state": "talking",
                "previous_state": "thinking",
                "run_id": run_id,
            },
            correlation_id=event.event_id,
        ),
    ]

    return {
        "run_id": run_id,
        "events": [event.model_dump() for event in events],
    }


def reasoning_status_payload() -> dict[str, Any]:
    ensure_reasoning_db()
    with _connect() as db:
        row = db.execute(
            """
            SELECT run_id, status, depth, provider, updated_at, failure_summary
            FROM reasoning_runs
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
        total = db.execute("SELECT COUNT(*) AS count FROM reasoning_runs").fetchone()["count"]

    return {
        "enabled": reasoning_enabled(),
        "provider": PROVIDER_NAME,
        "real_model_calls": False,
        "queue": {"foreground_active": False, "background_pending": 0},
        "runs_total": total,
        "current_run": dict(row) if row else None,
    }


def list_reasoning_runs(limit: int = 50) -> list[dict[str, Any]]:
    ensure_reasoning_db()
    safe_limit = max(1, min(limit, 100))
    with _connect() as db:
        rows = db.execute(
            """
            SELECT run_id, source_event_id, event_type, status, depth, provider,
                   created_at, updated_at, reply_text, failure_summary
            FROM reasoning_runs
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_reasoning_run(run_id: str) -> dict[str, Any] | None:
    ensure_reasoning_db()
    with _connect() as db:
        run = db.execute(
            """
            SELECT run_id, source_event_id, event_type, status, depth, provider,
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

    return {
        "run": dict(run),
        "steps": [dict(row) for row in steps],
        "schema_failures": [dict(row) for row in schema_failures],
        "memory_candidates": [
            {
                **dict(row),
                "payload": json.loads(row["payload_json"]),
                "payload_json": None,
            }
            for row in candidates
        ],
        "actions": [],
        "pending_actions": [],
        "audit": [],
    }
