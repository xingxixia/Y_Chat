from __future__ import annotations

import json
from typing import Any, Callable

from ..provider_client import ProviderCallError
from .provider_config import record_provider_config_audit


def run_model_provider_test_call(
    payload: dict[str, Any],
    *,
    readiness_payload_fn: Callable[[], dict[str, Any]],
    active_provider_call_config_fn: Callable[[], dict[str, Any]],
    post_chat_completion_fn: Callable[..., dict[str, Any]],
    extract_message_content_fn: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    secondary_confirmed = bool(payload.get("secondary_confirmed", False))
    if not secondary_confirmed:
        return {
            "ok": False,
            "called": False,
            "message": "secondary confirmation is required for a real provider test call",
            "api_key_returned": False,
        }

    readiness = readiness_payload_fn()
    if not readiness["ready"]:
        return {
            "ok": False,
            "called": False,
            "message": "provider is not ready for real calls",
            "blocked_reasons": readiness["blocked_reasons"],
            "api_key_returned": False,
        }

    config = active_provider_call_config_fn()
    config = {**config, "cadence_scope": "provider_test"}
    prompt = str(payload.get("prompt") or "Return a tiny JSON object with ok true.").strip()
    try:
        response = post_chat_completion_fn(
            config,
            [
                {"role": "system", "content": "Return only a JSON object. No markdown."},
                {"role": "user", "content": prompt},
            ],
            json_mode=True,
        )
        content = extract_message_content_fn(response["payload"])
        parsed: Any
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
        audit_id = record_provider_config_audit(
            "test_call_succeeded",
            {
                "action": "test_model_provider_call",
                "provider": config["provider"],
                "model": config["model"],
                "status_code": response["status_code"],
                "elapsed_ms": response["elapsed_ms"],
                "api_key_returned": False,
            },
        )
        return {
            "ok": True,
            "called": True,
            "provider": config["provider"],
            "model": config["model"],
            "status_code": response["status_code"],
            "elapsed_ms": response["elapsed_ms"],
            "content_chars": len(content),
            "json_object": parsed if isinstance(parsed, dict) else None,
            "audit_id": audit_id,
            "api_key_returned": False,
        }
    except ProviderCallError as exc:
        audit_id = record_provider_config_audit(
            "test_call_failed",
            {
                "action": "test_model_provider_call",
                "provider": config["provider"],
                "model": config["model"],
                "status_code": exc.status_code,
                "error_type": exc.error_type,
                "api_key_returned": False,
            },
        )
        return {
            "ok": False,
            "called": True,
            "provider": config["provider"],
            "model": config["model"],
            "status_code": exc.status_code,
            "error_type": exc.error_type,
            "message": str(exc),
            "audit_id": audit_id,
            "api_key_returned": False,
        }
