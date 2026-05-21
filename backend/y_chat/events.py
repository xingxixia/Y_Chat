from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .services.redaction import redact_payload, redaction_policy_payload
from .shared.contracts import EventType, PermissionName, SchemaVersion


EVENT_ENVELOPE_FIELDS = [
    {"name": "event_id", "required": False, "detail": "Generated when omitted; used for traceability."},
    {"name": "type", "required": True, "detail": f"Stable event type such as {EventType.USER_COMMAND_SUBMITTED}."},
    {"name": "source", "required": True, "detail": "Local source name such as frontend, backend, or electron."},
    {"name": "timestamp", "required": False, "detail": "Generated in UTC when omitted."},
    {"name": "correlation_id", "required": False, "detail": "Optional link to the triggering event."},
    {"name": "payload", "required": False, "detail": "JSON object; payload content is module-specific."},
]

EVENT_SAFETY_RULES = [
    {
        "name": "internal_only",
        "enabled": True,
        "detail": "The current event HTTP route is local/internal and is not an external adapter.",
    },
    {
        "name": "external_network_adapters",
        "enabled": False,
        "detail": "No external HTTP, WebSocket, LAN, plugin, CLI, OSC, or VR adapter is active.",
    },
    {
        "name": "event_envelope_required",
        "enabled": True,
        "detail": "Events must validate as EventEnvelope before backend handling.",
    },
    {
        "name": "reasoning_route_for_commands",
        "enabled": True,
        "detail": f"{EventType.USER_COMMAND_SUBMITTED} is routed through Reasoning R1 deterministic fallback.",
    },
    {
        "name": "raw_capture_payloads",
        "enabled": False,
        "detail": "Screen, microphone, and raw multimodal capture payloads are not accepted by active capture paths.",
    },
    {
        "name": "diagnostic_payload_redaction",
        "enabled": True,
        "detail": "Debug/event-history views redact secrets and raw multimodal payload fields while preserving refs and metadata.",
    },
]


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    source: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def make_event(
    event_type: str,
    source: str,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        type=event_type,
        source=source,
        payload=payload or {},
        correlation_id=correlation_id,
    )


def sanitize_event_for_debug(event: EventEnvelope | dict[str, Any]) -> dict[str, Any]:
    event_dict = event.model_dump() if isinstance(event, EventEnvelope) else dict(event)
    payload = event_dict.get("payload")
    redacted_payload, changed = redact_payload(payload if isinstance(payload, dict) else {})
    event_dict["payload"] = redacted_payload
    event_dict["payload_redacted"] = bool(changed)
    event_dict["raw_payload_stored_in_event"] = False
    return event_dict


def event_contract_payload() -> dict[str, Any]:
    redaction_policy = redaction_policy_payload()
    return {
        "schema_version": SchemaVersion.EVENTS_CONTRACT,
        "read_only": True,
        "diagnostic_payload_redaction": redaction_policy,
        "envelope": EVENT_ENVELOPE_FIELDS,
        "accepted_sources": ["frontend", "backend", "electron", "smoke", "debug"],
        "active_ingress": [
            {
                "route": "POST /events/internal",
                "scope": "local_internal",
                "external": False,
                "accepts_raw_capture": False,
            },
            {
                "route": "WS /ws/internal",
                "scope": "local_internal",
                "external": False,
                "accepts_raw_capture": False,
            },
        ],
        "active_event_types": [
            EventType.USER_COMMAND_SUBMITTED,
            EventType.REASONING_STARTED,
            EventType.REASONING_STEP_COMPLETED,
            EventType.REASONING_OUTPUT_PRODUCED,
            EventType.REASONING_SCHEMA_INVALID,
            EventType.REASONING_REPAIR_REQUESTED,
            EventType.REASONING_FAILED,
            "action.proposed",
            "action.pending_authorization",
            EventType.PET_STATE_CHANGED,
            EventType.PET_BUBBLE_SHOW,
            EventType.PET_BUBBLE_CLEAR,
            "debug.log",
            "error.reported",
            EventType.SYSTEM_HELLO,
        ],
        "inactive_adapters": [
            "external.http",
            "external.websocket",
            "external.lan",
            "external.osc",
            PermissionName.VOICE_LISTEN,
            PermissionName.SCREEN_OBSERVE,
            PermissionName.VR_OUTPUT,
            PermissionName.PROCESS_RUN,
            PermissionName.INPUT_CONTROL,
        ],
        "blocked_until_enabled": [
            "external network ingress",
            "LAN adapters",
            "microphone capture events",
            "screen capture events",
            "raw audio/video payloads",
            "VR/OSC output events",
            "process or input-control actions",
        ],
        "safety_rules": EVENT_SAFETY_RULES,
    }
