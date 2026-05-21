from __future__ import annotations

import json
import sqlite3
from typing import Any
from uuid import uuid4

from .config import load_config
from .events import EventEnvelope, make_event
from .provider_client import ProviderCallError
from .services.reasoning_actions import (
    classify_action as action_classify_action,
    normalize_action as action_normalize_action,
)
from .services.reasoning_context import (
    ReasoningRequest,
    build_context_snapshot as context_build_context_snapshot,
    build_reasoning_request as context_build_reasoning_request,
    recent_audio_reasoning_context as context_recent_audio_reasoning_context,
    recent_visual_reasoning_context as context_recent_visual_reasoning_context,
    source_event_summary as context_source_event_summary,
)
from .services.reasoning_fallback import (
    build_deterministic_output as fallback_build_deterministic_output,
)
from .services.reasoning_modalities import (
    infer_event_modalities as modal_infer_event_modalities,
    primary_event_modality as modal_primary_event_modality,
)
from .services.reasoning_provider import (
    PROVIDER_NAME,
    active_model_call_config as provider_active_model_call_config,
    build_provider_prompt as provider_build_provider_prompt,
    call_openai_compatible_chat as provider_call_openai_compatible_chat,
    extract_json_object as provider_extract_json_object,
    multimodal_context_summary as provider_multimodal_context_summary,
    strip_secrets_from_request as provider_strip_secrets_from_request,
)
from .services.reasoning_query import (
    decorate_run_row as query_decorate_run_row,
    get_latest_run_summary as query_get_latest_run_summary,
    get_reasoning_run as query_get_reasoning_run,
    list_reasoning_runs as query_list_reasoning_runs,
)
from .services.reasoning_schema import (
    SCHEMA_VERSION,
    reasoning_contract_payload as schema_reasoning_contract_payload,
    repair_reasoning_output as schema_repair_reasoning_output,
    validate_reasoning_output as schema_validate_reasoning_output,
)
from .services.reasoning_store import (
    connect as store_connect,
    ensure_reasoning_db as store_ensure_reasoning_db,
    insert_memory_candidate as store_insert_memory_candidate,
    insert_run as store_insert_run,
    insert_step as store_insert_step,
    mark_run_completed as store_mark_run_completed,
    mark_run_schema_failed as store_mark_run_schema_failed,
    now_iso,
    record_action_proposal as store_record_action_proposal,
    record_context_snapshot as store_record_context_snapshot,
    record_memory_write_audit as store_record_memory_write_audit,
    record_pending_action as store_record_pending_action,
    record_repair_attempt as store_record_repair_attempt,
    record_schema_failure as store_record_schema_failure,
)
from .services.reasoning_visual_enrichment import (
    ensure_visual_recognition_for_reasoning as visual_enrichment_ensure_visual_recognition_for_reasoning,
)


class ReasoningResponse(dict):
    pass


def reasoning_enabled() -> bool:
    config = load_config()
    return bool(config.get("reasoning", {}).get("enabled", True))


def configured_permissions() -> dict[str, bool]:
    permissions = load_config().get("permissions", {})
    if not isinstance(permissions, dict):
        return {}
    return {str(name): bool(value) for name, value in permissions.items()}


def infer_event_modalities(event: EventEnvelope) -> list[str]:
    """Classify an event without reducing multimodal input to text only."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    return modal_infer_event_modalities(event.type, payload)


def primary_event_modality(event: EventEnvelope) -> str:
    return modal_primary_event_modality(infer_event_modalities(event))


def _run_modality_payload(event_type: str) -> dict[str, Any]:
    event = EventEnvelope(type=event_type, source="stored_run", payload={})
    modalities = infer_event_modalities(event)
    return {
        "primary_modality": primary_event_modality(event),
        "modalities": modalities,
    }


def ensure_reasoning_db() -> None:
    store_ensure_reasoning_db()


def _connect() -> sqlite3.Connection:
    return store_connect()


def _insert_step(
    db: sqlite3.Connection,
    run_id: str,
    step_index: int,
    step_type: str,
    status: str,
    summary: str,
) -> str:
    return store_insert_step(db, run_id, step_index, step_type, status, summary)


def _source_event_summary(event: EventEnvelope) -> dict[str, Any]:
    return context_source_event_summary(event)


def build_context_snapshot(request: ReasoningRequest) -> dict[str, Any]:
    return context_build_context_snapshot(request)


def _record_context_snapshot(
    db: sqlite3.Connection,
    run_id: str,
    request: ReasoningRequest,
) -> str:
    snapshot = build_context_snapshot(request)
    return store_record_context_snapshot(db, run_id, snapshot)


def _insert_memory_candidate(
    db: sqlite3.Connection,
    run_id: str,
    candidate: dict[str, Any],
) -> str:
    return store_insert_memory_candidate(db, run_id, candidate)


def _record_memory_write_audit(
    db: sqlite3.Connection,
    run_id: str,
    candidate: dict[str, Any],
    status: str,
) -> None:
    store_record_memory_write_audit(db, run_id, candidate, status)


def _record_schema_failure(db: sqlite3.Connection, run_id: str, error: str) -> None:
    store_record_schema_failure(db, run_id, error)


def _record_repair_attempt(
    db: sqlite3.Connection,
    run_id: str,
    status: str,
    before_errors: list[str],
    after_errors: list[str],
) -> None:
    store_record_repair_attempt(db, run_id, status, before_errors, after_errors)


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    return action_normalize_action(action)


def _classify_action(action: dict[str, Any], permissions: dict[str, bool]) -> tuple[str, str]:
    return action_classify_action(action, permissions)


def _record_action_proposal(
    db: sqlite3.Connection,
    run_id: str,
    action: dict[str, Any],
    status: str,
    reason: str,
) -> None:
    store_record_action_proposal(db, run_id, action, status, reason)


def _record_pending_action(
    db: sqlite3.Connection,
    run_id: str,
    action: dict[str, Any],
    reason: str,
) -> str:
    return store_record_pending_action(db, run_id, action, reason)


def recent_visual_reasoning_context(limit: int = 5) -> dict[str, Any]:
    with _connect() as db:
        return context_recent_visual_reasoning_context(db, limit)


def recent_audio_reasoning_context(limit: int = 5) -> dict[str, Any]:
    with _connect() as db:
        return context_recent_audio_reasoning_context(db, limit)


def build_deterministic_output(run_id: str, event: EventEnvelope) -> dict[str, Any]:
    return fallback_build_deterministic_output(run_id, event)


def build_reasoning_request(run_id: str, event: EventEnvelope) -> ReasoningRequest:
    with _connect() as db:
        visual_context = context_recent_visual_reasoning_context(db)
        audio_context = context_recent_audio_reasoning_context(db)
    return context_build_reasoning_request(run_id, event, visual_context, audio_context, active_model_call_config())


def ensure_visual_recognition_for_reasoning(event: EventEnvelope) -> dict[str, Any]:
    return visual_enrichment_ensure_visual_recognition_for_reasoning(event)


def _should_report_visual_enrichment(result: dict[str, Any]) -> bool:
    return bool(result.get("called")) or result.get("reason") != "visual understanding was not requested"


def active_model_call_config() -> dict[str, Any]:
    return provider_active_model_call_config()


def strip_secrets_from_request(request: ReasoningRequest) -> dict[str, Any]:
    return provider_strip_secrets_from_request(request)


def build_provider_prompt(request: ReasoningRequest) -> str:
    return provider_build_provider_prompt(request)


def multimodal_context_summary(request: ReasoningRequest) -> dict[str, Any]:
    return provider_multimodal_context_summary(request)


def extract_json_object(text: str) -> dict[str, Any]:
    return provider_extract_json_object(text)


def call_openai_compatible_chat(request: ReasoningRequest, config: dict[str, Any]) -> dict[str, Any]:
    return provider_call_openai_compatible_chat(request, config)


def generate_reasoning(request: ReasoningRequest) -> ReasoningResponse:
    model_config = active_model_call_config()
    if model_config["enabled"]:
        try:
            output = call_openai_compatible_chat(request, model_config)
            return ReasoningResponse(
                {
                    "provider": model_config["provider"],
                    "real_model_call": True,
                    "output": output,
                }
            )
        except (ProviderCallError, KeyError, ValueError, json.JSONDecodeError) as exc:
            event = EventEnvelope.model_validate(request["source_event"])
            fallback_output = build_deterministic_output(str(request["run_id"]), event)
            fallback_output["audit"]["safety_notes"].append(f"real provider failed; deterministic fallback used: {type(exc).__name__}")
            return ReasoningResponse(
                {
                    "provider": model_config["provider"],
                    "real_model_call": True,
                    "provider_error": type(exc).__name__,
                    "output": fallback_output,
                }
            )
    event = EventEnvelope.model_validate(request["source_event"])
    output = build_deterministic_output(str(request["run_id"]), event)
    return ReasoningResponse(
        {
            "provider": PROVIDER_NAME,
            "real_model_call": False,
            "output": output,
        }
    )


def reasoning_contract_payload() -> dict[str, Any]:
    return schema_reasoning_contract_payload()


def repair_reasoning_output(
    output: dict[str, Any],
    run_id: str,
    event: EventEnvelope,
) -> dict[str, Any]:
    return schema_repair_reasoning_output(output, run_id)


def validate_reasoning_output(output: dict[str, Any], run_id: str) -> list[str]:
    return schema_validate_reasoning_output(output, run_id)


def run_deterministic_reasoning(event: EventEnvelope) -> dict[str, Any]:
    ensure_reasoning_db()

    run_id = str(uuid4())
    created_at = now_iso()
    visual_enrichment = ensure_visual_recognition_for_reasoning(event)
    request = build_reasoning_request(run_id, event)
    response = generate_reasoning(request)
    response_provider = str(response.get("provider") or PROVIDER_NAME)
    real_model_call = bool(response.get("real_model_call", False))
    output = response["output"]
    input_modalities = request["input"]["modalities"]
    primary_modality = request["input"]["primary_modality"]
    validation_errors = validate_reasoning_output(output, run_id)
    repaired = False
    repair_errors: list[str] = []
    if validation_errors:
        repaired_output = repair_reasoning_output(output, run_id, event)
        repair_errors = validate_reasoning_output(repaired_output, run_id)
        if not repair_errors:
            output = repaired_output
            repaired = True
    repair_step_id: str | None = None
    report_visual_enrichment = _should_report_visual_enrichment(visual_enrichment)
    reply = output.get("reply") if isinstance(output.get("reply"), dict) else {}
    reply_text = str(reply.get("bubble_text") or reply.get("text") or "")

    with _connect() as db:
        store_insert_run(
            db,
            run_id=run_id,
            source_event_id=event.event_id,
            event_type=event.type,
            depth="lightweight",
            provider=response_provider,
            primary_modality=primary_modality,
            modalities=input_modalities,
            created_at=created_at,
        )
        context_snapshot_id = _record_context_snapshot(db, run_id, request)
        context_step_id = _insert_step(
            db,
            run_id,
            1,
            "context_check",
            "completed",
            "R1 built and stored a sanitized multimodal context snapshot from the source event.",
        )
        step_index = 2
        visual_enrichment_step_id: str | None = None
        if report_visual_enrichment:
            visual_enrichment_step_id = _insert_step(
                db,
                run_id,
                step_index,
                "visual_context_enrichment",
                "completed" if visual_enrichment.get("ok") else "skipped",
                (
                    "R1 ensured local VLM visual recognition for an explicit visual request."
                    if visual_enrichment.get("called")
                    else f"R1 visual enrichment not run: {visual_enrichment.get('reason') or 'not needed'}."
                ),
            )
            step_index += 1
        output_step_id = _insert_step(
            db,
            run_id,
            step_index,
            "provider_running",
            "completed",
            f"R1 called generate_reasoning through the {response_provider} provider route.",
        )
        step_index += 1
        schema_step_id = _insert_step(
            db,
            run_id,
            step_index,
            "schema_validating",
            "completed" if not validation_errors or repaired else "failed",
            "R1 validated deterministic fallback output against reasoning.v1.",
        )
        step_index += 1
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
                step_index,
                "schema_repair",
                "completed" if repaired else "failed",
                "R1 attempted one structural schema repair without adding actions or memory.",
            )

        if validation_errors and not repaired:
            for error in validation_errors:
                _record_schema_failure(db, run_id, error)
            store_mark_run_schema_failed(db, run_id, validation_errors)
            return {
                "run_id": run_id,
            "events": [
                make_event(
                        "reasoning.started",
                        "backend",
                        {
                            "run_id": run_id,
                            "depth": "lightweight",
                            "provider": response_provider,
                            "real_model_call": real_model_call,
                            "source_event_id": event.event_id,
                            "primary_modality": primary_modality,
                            "modalities": input_modalities,
                            "context_snapshot_id": context_snapshot_id,
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

        store_mark_run_completed(db, run_id, reply_text)

    events = [
        make_event(
            "reasoning.started",
            "backend",
            {
                "run_id": run_id,
                "depth": "lightweight",
                "provider": response_provider,
                "real_model_call": real_model_call,
                "source_event_id": event.event_id,
                "primary_modality": primary_modality,
                "modalities": input_modalities,
                "context_snapshot_id": context_snapshot_id,
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
                "provider": response_provider,
                "real_model_call": real_model_call,
                "memory_candidate_ids": candidate_ids,
                "action_ids": [record["action_id"] for record in action_records],
                "primary_modality": primary_modality,
                "modalities": input_modalities,
            },
            correlation_id=event.event_id,
        ),
    ]
    if visual_enrichment_step_id:
        events.insert(
            3,
            make_event(
                "reasoning.step.completed",
                "backend",
                {
                    "run_id": run_id,
                    "step_id": visual_enrichment_step_id,
                    "step_type": "visual_context_enrichment",
                    "status": "completed" if visual_enrichment.get("ok") else "skipped",
                    "called": bool(visual_enrichment.get("called")),
                    "provider": visual_enrichment.get("provider"),
                },
                correlation_id=event.event_id,
            ),
        )
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
    model_config = active_model_call_config()
    with _connect() as db:
        current_run, total = query_get_latest_run_summary(db, _run_modality_payload)

    return {
        "enabled": reasoning_enabled(),
        "provider": model_config["provider"] if model_config["enabled"] else PROVIDER_NAME,
        "real_model_calls": model_config["enabled"],
        "provider_mode": model_config["provider"] if model_config["enabled"] else "deterministic_fallback",
        "model_blocked_reasons": [] if model_config["enabled"] else [
            "real model calls are disabled until llm.enabled, permissions.model.call, provider, model, base_url, and API key are all configured",
        ],
        "supported_input_modalities": [
            "text",
            "vision",
            "audio",
            "state",
            "memory",
            "project",
            "interaction",
            "action",
            "external",
            "vr",
        ],
        "capture_enabled": {"vision": True, "audio": False, "screen": True, "voice": False},
        "capture_blocked_reasons": {
            "vision": "physical camera capture and neural image embeddings are not implemented; screen frames can enter visual evidence when screen.observe is enabled",
            "audio": "microphone capture is not implemented and voice.listen is disabled",
            "screen": "screen observation is gated by screen.observe and secondary confirmation; capture is not active from the backend process itself",
            "voice": "ASR/TTS route is not selected",
        },
        "write_paths": {
            "memory_candidates": "inspect_only",
            "formal_memory": "disabled",
            "actions": "proposal_only",
        },
        "queue": {"foreground_active": False, "background_pending": 0},
        "runs_total": total,
        "current_run": current_run,
    }


def _decorate_run_row(row: dict[str, Any]) -> dict[str, Any]:
    return query_decorate_run_row(row, _run_modality_payload)


def list_reasoning_runs(limit: int = 50) -> list[dict[str, Any]]:
    ensure_reasoning_db()
    with _connect() as db:
        return query_list_reasoning_runs(db, _run_modality_payload, limit)


def get_reasoning_run(run_id: str) -> dict[str, Any] | None:
    ensure_reasoning_db()
    with _connect() as db:
        return query_get_reasoning_run(db, run_id, _run_modality_payload)
