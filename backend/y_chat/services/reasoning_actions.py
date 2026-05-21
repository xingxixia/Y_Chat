from __future__ import annotations

from typing import Any
from uuid import uuid4


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


def normalize_action(action: dict[str, Any]) -> dict[str, Any]:
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


def classify_action(action: dict[str, Any], permissions: dict[str, bool]) -> tuple[str, str]:
    capability = str(action["capability"])
    risk = str(action["risk"])
    if risk == "high" or capability in HIGH_RISK_ACTIONS or action["requires_confirmation"]:
        return "pending_authorization", "requires_secondary_confirmation"
    if not permissions.get(capability, False):
        return "pending_authorization", "permission_disabled"
    return "approved_low_risk_not_executed", "r1_does_not_execute_actions"
