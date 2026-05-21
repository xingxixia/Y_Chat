from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "reasoning.v1"

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

REASONING_OUTPUT_CONTRACT: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "transport_may_stream": True,
    "execution_requires_complete_json": True,
    "repair_attempts": 1,
    "repair_policy": "fill_missing_structural_defaults_only",
    "real_model_calls": False,
    "provider_mode": "deterministic_fallback",
    "top_level_required": [
        "schema_version",
        "run_id",
        "reply",
        "state",
        "actions",
        "memory",
        "observations",
        "voice",
        "debug",
        "audit",
    ],
    "top_level_sections": [
        {
            "name": "reply",
            "required": ["should_reply", "text", "bubble_text", "style", "final"],
            "acceptance_rules": [
                "reply must be an object",
                "reply.should_reply must be boolean",
                "reply.text must be string when should_reply is true",
                "reply.final must be true",
            ],
        },
        {
            "name": "state",
            "required": ["pet_state", "emotion", "animation"],
            "acceptance_rules": ["state proposes events; backend/event layer emits actual pet.state.changed"],
        },
        {
            "name": "actions",
            "required": ["capability", "name", "params", "reason", "risk"],
            "acceptance_rules": [
                "actions must be a list",
                "action params must be an object",
                "risk must be low, medium, or high",
                "action_id values must not duplicate inside one run",
                "R1 stores proposals only and never executes actions",
            ],
        },
        {
            "name": "memory",
            "required": ["write_candidates", "do_not_write_reason", "needs_consolidation"],
            "acceptance_rules": [
                "memory must be an object",
                "memory.write_candidates must be a list",
                "candidate_id, target_layer, kind, content, source_event_ids, and confidence are required for candidates",
                "R1 stores candidates for inspection only and never writes formal memory",
            ],
        },
        {
            "name": "debug",
            "required": ["depth", "needs_deep_retrieval", "deep_retrieval_query", "trace"],
            "acceptance_rules": ["debug trace is diagnostic data, not normal UI text"],
        },
        {
            "name": "audit",
            "required": ["safety_notes", "permission_requests"],
            "acceptance_rules": ["audit must not expose API keys or authorization tokens"],
        },
    ],
    "blocked_until_valid": [
        "final reply bubble",
        "formal memory writes",
        "action execution",
        "voice output",
        "external adapters",
        "VR/OSC output",
    ],
    "failure_events": [
        "reasoning.schema.invalid",
        "reasoning.repair.requested",
        "reasoning.failed",
    ],
}


def reasoning_contract_payload() -> dict[str, Any]:
    return REASONING_OUTPUT_CONTRACT


def repair_reasoning_output(output: dict[str, Any], run_id: str) -> dict[str, Any]:
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
