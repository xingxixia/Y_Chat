from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import RUNTIME_DIR, load_config, runtime_sqlite_path
from .events import EventEnvelope, make_event


PROVIDER_NAME = "deterministic_fallback"
SCHEMA_VERSION = "reasoning.v1"
HIGH_RISK_ACTIONS = {
    "external.http",
    "external.lan",
    "external.osc",
    "file.write",
    "input.control",
    "process.run",
    "screen.observe.long",
    "voice.listen.long",
    "vr.output",
}
REPAIRABLE_TOP_LEVEL_DEFAULTS: dict[str, Any] = {
    "actions": [],
    "observations": [],
    "voice": {"speak": False, "text": None, "voice_style": None},
    "debug": {
        "depth": "lightweight",
        "needs_deep_retrieval": False,
        "deep_retrieval_query": None,
        "trace": [],
    },
    "audit": {"safety_notes": [], "permission_requests": []},
}


class ReasoningRequest(dict):
    pass


class ReasoningResponse(dict):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reasoning_enabled() -> bool:
    config = load_config()
    return bool(config.get("reasoning", {}).get("enabled", True))


def configured_permissions() -> dict[str, bool]:
    permissions = load_config().get("permissions", {})
    if not isinstance(permissions, dict):
        return {}
    return {str(name): bool(value) for name, value in permissions.items()}


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
    db = sqlite3.connect(runtime_sqlite_path())
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


def _record_memory_write_audit(
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


def _record_schema_failure(db: sqlite3.Connection, run_id: str, error: str) -> None:
    db.execute(
        """
        INSERT INTO reasoning_schema_failures (failure_id, run_id, error, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(uuid4()), run_id, error, now_iso()),
    )


def _record_repair_attempt(
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


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    risk = str(action.get("risk", "low")).lower()
    if risk not in {"low", "medium", "high"}:
        risk = "medium"
    return {
        "action_id": str(action.get("action_id") or uuid4()),
        "capability": str(action["capability"]),
        "name": str(action["name"]),
        "params": action.get("params") if isinstance(action.get("params"), dict) else {},
        "reason": str(action.get("reason", "")),
        "risk": risk,
        "requires_confirmation": bool(action.get("requires_confirmation", False)),
        "retryable": bool(action.get("retryable", False)),
    }


def _classify_action(action: dict[str, Any], permissions: dict[str, bool]) -> tuple[str, str]:
    capability = str(action["capability"])
    risk = str(action["risk"])
    if risk == "high" or capability in HIGH_RISK_ACTIONS or action["requires_confirmation"]:
        return "pending_authorization", "requires_secondary_confirmation"
    if not permissions.get(capability, False):
        return "pending_authorization", "permission_disabled"
    return "approved_low_risk_not_executed", "r1_does_not_execute_actions"


def _record_action_proposal(
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


def _record_pending_action(
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


def build_reasoning_request(run_id: str, event: EventEnvelope) -> ReasoningRequest:
    text = str(event.payload.get("text", "")).strip()
    return ReasoningRequest(
        {
            "schema_version": "reasoning_request.v1",
            "run_id": run_id,
            "source_event": event.model_dump(),
            "depth": "lightweight",
            "provider": PROVIDER_NAME,
            "context": {
                "current_event_text": text,
                "recent_summary": [],
                "entity_refs": [],
                "core_memory_summary": [],
            },
            "real_model_calls": False,
        }
    )


def generate_reasoning(request: ReasoningRequest) -> ReasoningResponse:
    event = EventEnvelope.model_validate(request["source_event"])
    output = build_deterministic_output(str(request["run_id"]), event)
    return ReasoningResponse(
        {
            "provider": PROVIDER_NAME,
            "real_model_call": False,
            "output": output,
        }
    )


def repair_reasoning_output(
    output: dict[str, Any],
    run_id: str,
    event: EventEnvelope,
) -> dict[str, Any]:
    repaired = dict(output)
    repaired.setdefault("schema_version", SCHEMA_VERSION)
    repaired.setdefault("run_id", run_id)
    for key, value in REPAIRABLE_TOP_LEVEL_DEFAULTS.items():
        if key not in repaired:
            repaired[key] = value.copy() if isinstance(value, dict) else list(value)

    if "reply" not in repaired:
        repaired["reply"] = {
            "should_reply": False,
            "text": "",
            "bubble_text": "",
            "style": "normal",
            "final": True,
        }
    elif isinstance(repaired["reply"], dict):
        repaired["reply"].setdefault("should_reply", False)
        repaired["reply"].setdefault("text", "")
        repaired["reply"].setdefault("bubble_text", repaired["reply"].get("text", ""))
        repaired["reply"].setdefault("style", "normal")
        repaired["reply"].setdefault("final", True)

    if "state" not in repaired:
        repaired["state"] = {
            "pet_state": "idle",
            "emotion": "neutral",
            "animation": None,
        }

    if "memory" not in repaired:
        repaired["memory"] = {
            "write_candidates": [],
            "do_not_write_reason": "schema_repair_added_empty_memory_section",
            "needs_consolidation": False,
        }
    elif isinstance(repaired["memory"], dict):
        repaired["memory"].setdefault("write_candidates", [])
        repaired["memory"].setdefault("do_not_write_reason", "schema_repair")
        repaired["memory"].setdefault("needs_consolidation", False)

    return repaired


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
    else:
        seen_action_ids: set[str] = set()
        for index, action in enumerate(output["actions"]):
            if not isinstance(action, dict):
                errors.append(f"actions[{index}] must be an object")
                continue
            for field in ("capability", "name", "params", "reason", "risk"):
                if field not in action:
                    errors.append(f"actions[{index}].{field} is required")
            if "action_id" in action:
                action_id = str(action["action_id"])
                if action_id in seen_action_ids:
                    errors.append(f"actions[{index}].action_id is duplicated")
                seen_action_ids.add(action_id)
            if "params" in action and not isinstance(action["params"], dict):
                errors.append(f"actions[{index}].params must be an object")
            if "risk" in action and str(action["risk"]).lower() not in {"low", "medium", "high"}:
                errors.append(f"actions[{index}].risk must be low, medium, or high")

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
    request = build_reasoning_request(run_id, event)
    response = generate_reasoning(request)
    output = response["output"]
    validation_errors = validate_reasoning_output(output, run_id)
    repaired = False
    repair_errors: list[str] = []
    if validation_errors:
        repaired_output = repair_reasoning_output(output, run_id, event)
        repair_errors = validate_reasoning_output(repaired_output, run_id)
        if not repair_errors:
            output = repaired_output
            repaired = True
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
            "provider_running",
            "completed",
            "R1 called generate_reasoning through the deterministic fallback provider route.",
        )
        schema_step_id = _insert_step(
            db,
            run_id,
            3,
            "schema_validating",
            "completed" if not validation_errors or repaired else "failed",
            "R1 validated deterministic fallback output against reasoning.v1.",
        )
        if validation_errors:
            _record_repair_attempt(
                db,
                run_id,
                "succeeded" if repaired else "failed",
                validation_errors,
                repair_errors,
            )
            repair_step_id = _insert_step(
                db,
                run_id,
                4,
                "schema_repair",
                "completed" if repaired else "failed",
                "R1 attempted one structural schema repair without adding actions or memory.",
            )

        if validation_errors and not repaired:
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
                        "reasoning.repair.requested",
                        "backend",
                        {
                            "run_id": run_id,
                            "step_id": repair_step_id,
                            "status": "failed",
                            "errors": repair_errors,
                        },
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

        candidate_ids = []
        for candidate in output["memory"]["write_candidates"]:
            candidate_id = _insert_memory_candidate(db, run_id, candidate)
            _record_memory_write_audit(db, run_id, candidate, "candidate_recorded")
            candidate_ids.append(candidate_id)

        permissions = configured_permissions()
        action_records = []
        pending_records = []
        for raw_action in output["actions"]:
            action = _normalize_action(raw_action)
            status, policy_reason = _classify_action(action, permissions)
            _record_action_proposal(db, run_id, action, status, policy_reason)
            if status == "pending_authorization":
                pending_id = _record_pending_action(db, run_id, action, policy_reason)
                pending_records.append(
                    {
                        "pending_id": pending_id,
                        "action_id": action["action_id"],
                        "capability": action["capability"],
                        "risk": action["risk"],
                        "reason": policy_reason,
                    }
                )
            action_records.append(
                {
                    "action_id": action["action_id"],
                    "capability": action["capability"],
                    "name": action["name"],
                    "risk": action["risk"],
                    "status": status,
                    "reason": policy_reason,
                }
            )

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
                "step_type": "provider_running",
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
                "action_ids": [record["action_id"] for record in action_records],
            },
            correlation_id=event.event_id,
        ),
    ]
    if repaired:
        events.append(
            make_event(
                "reasoning.repair.requested",
                "backend",
                {
                    "run_id": run_id,
                    "step_id": repair_step_id,
                    "status": "completed",
                    "errors": validation_errors,
                },
                correlation_id=event.event_id,
            )
        )
    for record in action_records:
        events.append(
            make_event(
                "action.proposed",
                "backend",
                {
                    "run_id": run_id,
                    "action_id": record["action_id"],
                    "capability": record["capability"],
                    "name": record["name"],
                    "risk": record["risk"],
                    "status": record["status"],
                    "reason": record["reason"],
                    "executed": False,
                },
                correlation_id=event.event_id,
            )
        )
    for record in pending_records:
        events.append(
            make_event(
                "action.pending_authorization",
                "backend",
                {
                    "run_id": run_id,
                    "pending_id": record["pending_id"],
                    "action_id": record["action_id"],
                    "capability": record["capability"],
                    "risk": record["risk"],
                    "reason": record["reason"],
                    "executed": False,
                },
                correlation_id=event.event_id,
            )
        )
    events.extend(
        [
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
    )

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
