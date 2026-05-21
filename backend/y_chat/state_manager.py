from __future__ import annotations

from typing import Any


IMPLEMENTED_STATES = [
    {
        "name": "idle",
        "implemented": True,
        "source": "backend_or_electron_recovery",
        "detail": "Default resting state and bubble-clear recovery state.",
    },
    {
        "name": "thinking",
        "implemented": True,
        "source": "backend",
        "detail": "Emitted while Reasoning R1 is processing a command event.",
    },
    {
        "name": "talking",
        "implemented": True,
        "source": "backend",
        "detail": "Emitted when accepted output is shown through the bubble renderer.",
    },
    {
        "name": "dragging",
        "implemented": True,
        "source": "renderer_local_only",
        "detail": "Temporary renderer-local visual state; it does not overwrite backend semantic state.",
    },
]

RESERVED_STATES = [
    "reading",
    "error",
    "sleep",
    "listening",
    "observing",
    "interrupted",
    "speaking",
]


def state_contract_payload() -> dict[str, Any]:
    return {
        "schema_version": "state.contract.v1",
        "read_only": True,
        "event_type": "pet.state.changed",
        "payload_fields": [
            {
                "name": "state",
                "required": True,
                "detail": "Semantic pet state name.",
            },
            {
                "name": "previous_state",
                "required": False,
                "detail": "Best-effort previous semantic state for traceability.",
            },
        ],
        "implemented_states": IMPLEMENTED_STATES,
        "reserved_states": RESERVED_STATES,
        "state_sources": [
            "backend command/reasoning flow",
            "electron bubble-clear recovery",
            "renderer-local dragging overlay",
        ],
        "rules": [
            {
                "name": "semantic_state_only",
                "enabled": True,
                "detail": "State expresses current interaction semantics, not pet simulation meters.",
            },
            {
                "name": "event_driven",
                "enabled": True,
                "detail": "Backend semantic changes are emitted as pet.state.changed events.",
            },
            {
                "name": "dragging_is_local",
                "enabled": True,
                "detail": "Dragging is a temporary renderer-local overlay and returns to backend state when released.",
            },
            {
                "name": "no_sensitive_capture_side_effects",
                "enabled": True,
                "detail": "State changes do not enable screen, microphone, voice, external, process, input, or VR routes.",
            },
            {
                "name": "no_pet_simulation_systems",
                "enabled": True,
                "detail": "Hunger, shop, quests, currency, levels, feeding, and cleaning systems remain out of scope.",
            },
        ],
        "blocked_until_explicit_design": [
            "simulation meters",
            "sleep/listening/observing capture behavior",
            "voice speaking output",
            "screen observation",
            "external adapter output",
            "VR/OSC output",
            "final art-specific animation states",
        ],
    }
