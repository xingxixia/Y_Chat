from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from .config import load_config, save_config
from .memory import db_path, ensure_memory_db, now_iso, _json_dumps


DEFAULT_INTERVAL_SECONDS = 3
MAX_ADAPTIVE_INTERVAL_SECONDS = 5
DEFAULT_QUEUE_PRESSURE_SECONDS = 30
EXTRACTION_MIN_INTERVAL_MS = 2500


def _screen_permission_enabled() -> bool:
    config = load_config()
    permissions = config.get("permissions", {})
    return bool(permissions.get("screen.observe", False)) if isinstance(permissions, dict) else False


def _screen_observation_config() -> dict[str, Any]:
    config = load_config()
    screen_config = config.get("screen_observation", {})
    return screen_config if isinstance(screen_config, dict) else {}


def _write_screen_audit(action: str, payload: dict[str, Any]) -> str:
    ensure_memory_db()
    audit_id = str(uuid4())
    with sqlite3.connect(db_path()) as db:
        db.execute(
            """
            INSERT INTO memory_audit_log (audit_id, record_id, action, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                None,
                action,
                _json_dumps(
                    {
                        **payload,
                        "raw_payload_stored_in_event": False,
                        "raw_payload_returned_in_debug": False,
                    }
                ),
                now_iso(),
            ),
        )
    return audit_id


def screen_observation_status_payload(
    active: bool = False,
    last_frame: dict[str, Any] | None = None,
    samples_captured: int = 0,
    samples_skipped: int = 0,
    last_capture_duration_ms: int | None = None,
    capture_avg_duration_ms: int | None = None,
    capture_max_duration_ms: int | None = None,
    capture_history_count: int = 0,
    adaptive_interval_seconds: int | None = None,
    adaptive_pressure_mode: bool = False,
    adaptive_reason: str = "steady",
    last_skip_reason: str | None = None,
    last_skip_at: str | None = None,
    last_error: str | None = None,
) -> dict[str, Any]:
    permission_enabled = _screen_permission_enabled()
    screen_config = _screen_observation_config()
    interval_seconds = int(screen_config.get("interval_seconds") or DEFAULT_INTERVAL_SECONDS)
    retain_raw = bool(screen_config.get("retain_raw", True))
    blocked_reasons: list[str] = []
    if not permission_enabled:
        blocked_reasons.append("permissions.screen.observe is disabled")
    if not active:
        blocked_reasons.append("screen observation is not active")
    if last_error:
        blocked_reasons.append(last_error)
    return {
        "schema_version": "screen_observation.status.v1",
        "enabled": active and permission_enabled,
        "active": active,
        "permission": "screen.observe",
        "permission_enabled": permission_enabled,
        "requires_secondary_confirmation": True,
        "display": "primary",
        "full_frame": True,
        "interval_seconds": interval_seconds,
        "base_interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "max_interval_seconds": MAX_ADAPTIVE_INTERVAL_SECONDS,
        "adaptive_interval_seconds": adaptive_interval_seconds or interval_seconds,
        "retain_raw": retain_raw,
        "pressure_mode": adaptive_pressure_mode,
        "queue_pressure_seconds": DEFAULT_QUEUE_PRESSURE_SECONDS,
        "samples_captured": samples_captured,
        "samples_skipped": samples_skipped,
        "samples_timed_out": 0,
        "samples_queued": 0,
        "samples_persisted": 0,
        "samples_dropped": 0,
        "samples_extraction_queued": 0,
        "samples_extracted": 0,
        "samples_extraction_failed": 0,
        "samples_extraction_dropped": 0,
        "last_capture_duration_ms": last_capture_duration_ms,
        "last_evidence_persist_duration_ms": None,
        "last_extraction_duration_ms": None,
        "capture_avg_duration_ms": capture_avg_duration_ms,
        "capture_max_duration_ms": capture_max_duration_ms,
        "capture_history_count": capture_history_count,
        "adaptive_pressure_mode": adaptive_pressure_mode,
        "adaptive_reason": adaptive_reason,
        "evidence_queue_length": 0,
        "evidence_queue_busy": False,
        "evidence_queue_limit": 2,
        "evidence_min_interval_ms": 1000,
        "extraction_queue_length": 0,
        "extraction_queue_busy": False,
        "extraction_queue_limit": 1,
        "extraction_min_interval_ms": EXTRACTION_MIN_INTERVAL_MS,
        "extraction_pressure_threshold_seconds": DEFAULT_QUEUE_PRESSURE_SECONDS,
        "extraction_pressure_mode": False,
        "extraction_pressure_state": "steady",
        "extraction_pressure_reason": "steady",
        "extraction_estimated_backlog_ms": 0,
        "extraction_oldest_queued_ms": None,
        "extraction_running_ms": None,
        "last_extraction_status": None,
        "last_extraction_provider": None,
        "last_extraction_model": None,
        "last_extraction_evidence_id": None,
        "extraction_current_evidence_id": None,
        "last_extraction_feature_id": None,
        "last_extraction_error": None,
        "last_extraction_queued_at": None,
        "last_extraction_started_at": None,
        "last_extraction_finished_at": None,
        "last_extraction_pressure_at": None,
        "last_extraction_recovered_at": None,
        "last_extraction_dropped_at": None,
        "last_skip_reason": last_skip_reason,
        "last_skip_at": last_skip_at,
        "last_timeout_at": None,
        "active_capture_requests": 0,
        "last_drop_reason": None,
        "last_drop_at": None,
        "last_frame": last_frame,
        "last_error": last_error,
        "blocked_reasons": blocked_reasons,
        "raw_payload_in_events": False,
        "raw_payload_in_provider_prompt": False,
        "raw_payload_returned_in_debug": False,
    }


def screen_observation_contract_payload() -> dict[str, Any]:
    return {
        "schema_version": "screen_observation.contract.v1",
        "read_only": False,
        "permission": "screen.observe",
        "requires_secondary_confirmation": True,
        "display": "primary",
        "full_frame": True,
        "interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "base_interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "max_interval_seconds": MAX_ADAPTIVE_INTERVAL_SECONDS,
        "sampling_cadence": "adaptive_fixed_tick",
        "overrun_policy": "average_duration_pressure_adjusts_interval",
        "max_active_capture_requests": 2,
        "adaptive_policy": {
            "history_frames": 8,
            "interval_step_seconds": 1,
            "default_interval_seconds": DEFAULT_INTERVAL_SECONDS,
            "max_interval_seconds": MAX_ADAPTIVE_INTERVAL_SECONDS,
            "pressure_inputs": ["capture_avg_duration_ms", "capture_max_duration_ms", "samples_skipped"],
        },
        "evidence_queue_policy": {
            "decoupled_from_capture_tick": True,
            "max_pending_frames": 2,
            "min_persist_interval_ms": 1000,
            "overflow": "drop_oldest",
        },
        "extraction_queue_policy": {
            "auto_extract_after_persist": True,
            "provider": "local_rapidocr",
            "max_pending_frames": 1,
            "min_extract_interval_ms": 2500,
            "overflow": "drop_oldest",
            "requires_raw_ref": True,
            "pressure_threshold_seconds": DEFAULT_QUEUE_PRESSURE_SECONDS,
            "pressure_state_values": ["steady", "busy", "pressure", "recovering", "failed"],
            "status_fields": [
                "extraction_pressure_mode",
                "extraction_pressure_state",
                "extraction_estimated_backlog_ms",
                "extraction_oldest_queued_ms",
                "extraction_running_ms",
                "last_extraction_pressure_at",
                "last_extraction_recovered_at",
            ],
        },
        "retain_raw_default": True,
        "raw_backup_path": "runtime/memory_blobs/vision/screenshots/",
        "preview_endpoint": "/screen/observation/preview?raw_ref=runtime://...",
        "event_payload_policy": "refs_and_metadata_only",
        "provider_prompt_policy": "refs_status_summaries_only",
        "pressure_threshold_seconds": 30,
        "rules": [
            "screen observation must be explicitly enabled",
            "persistent enablement requires secondary confirmation",
            "raw screenshots stay in local raw backup storage",
            "event history, Debug responses, and provider prompts must not carry raw image bytes",
            "Debug may render retained local screenshots through the explicit preview endpoint; JSON status still carries refs only",
            "sampled screen frames enter the same visual evidence pipeline as manual images",
            "visual evidence write and backend indexing are queued and rate-limited separately from the screen capture tick",
            "visual extraction is queued after evidence persistence and rate-limited separately from capture and evidence writes",
            "sampling starts at a 3-second cadence and may visibly adapt to 4 or 5 seconds when average capture duration or skipped ticks show pressure",
            "capture ticks do not wait for the previous frame, but concurrent in-flight capture requests are capped to avoid unbounded pressure",
        ],
    }


def request_screen_observation_start(payload: dict[str, Any]) -> dict[str, Any]:
    secondary_confirmed = bool(payload.get("secondary_confirmed", False))
    if not secondary_confirmed:
        return {
            "ok": False,
            "start_allowed": False,
            "saved": False,
            "message": "secondary confirmation is required for screen observation",
            "status": screen_observation_status_payload(active=False),
        }

    config = load_config()
    permissions = config.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        permissions = {}
        config["permissions"] = permissions
    permissions["screen.observe"] = True

    screen_config = config.setdefault("screen_observation", {})
    if not isinstance(screen_config, dict):
        screen_config = {}
        config["screen_observation"] = screen_config
    screen_config["enabled"] = True
    screen_config["display"] = "primary"
    screen_config["full_frame"] = True
    screen_config["interval_seconds"] = int(payload.get("interval_seconds") or DEFAULT_INTERVAL_SECONDS)
    screen_config["retain_raw"] = bool(payload.get("retain_raw", True))
    screen_config["queue_pressure_seconds"] = DEFAULT_QUEUE_PRESSURE_SECONDS

    save_config(config)
    audit_id = _write_screen_audit(
        "screen.observation.enabled",
        {
            "permission": "screen.observe",
            "secondary_confirmed": True,
            "display": "primary",
            "full_frame": True,
            "interval_seconds": screen_config["interval_seconds"],
            "retain_raw": screen_config["retain_raw"],
        },
    )
    return {
        "ok": True,
        "start_allowed": True,
        "saved": True,
        "audit_id": audit_id,
        "status": screen_observation_status_payload(active=False),
    }


def request_screen_observation_stop(payload: dict[str, Any]) -> dict[str, Any]:
    revoke_permission = bool(payload.get("revoke_permission", False))
    config = load_config()
    screen_config = config.setdefault("screen_observation", {})
    if not isinstance(screen_config, dict):
        screen_config = {}
        config["screen_observation"] = screen_config
    screen_config["enabled"] = False
    if revoke_permission:
        permissions = config.setdefault("permissions", {})
        if not isinstance(permissions, dict):
            permissions = {}
            config["permissions"] = permissions
        permissions["screen.observe"] = False
    save_config(config)
    audit_id = _write_screen_audit(
        "screen.observation.disabled",
        {
            "permission": "screen.observe",
            "revoke_permission": revoke_permission,
        },
    )
    return {
        "ok": True,
        "stopped": True,
        "saved": True,
        "audit_id": audit_id,
        "status": screen_observation_status_payload(active=False),
    }
