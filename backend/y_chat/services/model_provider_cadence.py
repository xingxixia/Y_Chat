from __future__ import annotations

import time
from threading import Lock
from typing import Any


DEFAULT_SCOPE = "provider_api"

CADENCE_POLICIES: dict[str, dict[str, Any]] = {
    "reasoning_foreground": {
        "min_interval_seconds": 1.0,
        "purpose": "user-turn text reasoning",
        "high_frequency_allowed": False,
    },
    "provider_test": {
        "min_interval_seconds": 5.0,
        "purpose": "explicit Debug API probe",
        "high_frequency_allowed": False,
    },
    "vision_provider": {
        "min_interval_seconds": 8.0,
        "purpose": "future external vision adapter call",
        "high_frequency_allowed": False,
    },
    "background": {
        "min_interval_seconds": 30.0,
        "purpose": "future proactive/background reasoning",
        "high_frequency_allowed": False,
    },
    DEFAULT_SCOPE: {
        "min_interval_seconds": 2.0,
        "purpose": "generic OpenAI-compatible API call",
        "high_frequency_allowed": False,
    },
}

_LOCK = Lock()
_STATE: dict[str, dict[str, Any]] = {}


def provider_cadence_policy() -> dict[str, Any]:
    return {
        "schema_version": "model_provider.cadence_policy.v1",
        "role": "DeepSeek/API text reasoning cadence guard",
        "deepseek_role": "text_reasoning_api_only",
        "high_frequency_inputs": "local_adapters_only",
        "provider_receives": "sanitized multimodal summaries, refs, and feature descriptions",
        "provider_must_not_receive": ["raw_image_bytes", "raw_audio_bytes", "per_frame_events", "per_audio_fragment_events"],
        "coalescing_required_before_api": True,
        "scopes": CADENCE_POLICIES,
    }


def provider_cadence_status_payload() -> dict[str, Any]:
    now = time.monotonic()
    with _LOCK:
        scopes = {
            name: _scope_status(name, policy, _STATE.get(name, {}), now)
            for name, policy in CADENCE_POLICIES.items()
        }
    return {
        "schema_version": "model_provider.cadence_status.v1",
        "policy": provider_cadence_policy(),
        "scopes": scopes,
        "api_key_returned": False,
        "raw_payload_returned": False,
    }


def begin_provider_call(config: dict[str, Any]) -> dict[str, Any]:
    scope = _safe_scope(config.get("cadence_scope"))
    policy = CADENCE_POLICIES[scope]
    now = time.monotonic()
    with _LOCK:
        state = _STATE.setdefault(scope, {})
        if state.get("active"):
            retry_after = 1.0
            _record_blocked(state, now, retry_after, "call already active")
            return _blocked_result(scope, policy, retry_after, "provider API call is already active")

        last_started = state.get("last_started_monotonic")
        if isinstance(last_started, (int, float)):
            elapsed = now - float(last_started)
            min_interval = float(policy["min_interval_seconds"])
            if elapsed < min_interval:
                retry_after = round(min_interval - elapsed, 3)
                _record_blocked(state, now, retry_after, "min interval")
                return _blocked_result(
                    scope,
                    policy,
                    retry_after,
                    f"provider API cadence guard blocked this call; retry after {retry_after:.1f}s",
                )

        state["active"] = True
        state["last_started_monotonic"] = now
        state["last_started_at_ms"] = int(time.time() * 1000)
        state["last_provider"] = str(config.get("provider") or "")
        state["last_model"] = str(config.get("model") or "")
        state["started_count"] = int(state.get("started_count", 0)) + 1
        return {
            "allowed": True,
            "scope": scope,
            "started_monotonic": now,
            "min_interval_seconds": policy["min_interval_seconds"],
        }


def finish_provider_call(token: dict[str, Any], *, ok: bool, elapsed_ms: int | None = None, error_type: str | None = None) -> None:
    scope = _safe_scope(token.get("scope"))
    with _LOCK:
        state = _STATE.setdefault(scope, {})
        state["active"] = False
        state["last_finished_at_ms"] = int(time.time() * 1000)
        state["last_ok"] = bool(ok)
        state["last_elapsed_ms"] = elapsed_ms
        state["last_error_type"] = error_type


def reset_provider_cadence_state() -> None:
    with _LOCK:
        _STATE.clear()


def _safe_scope(value: Any) -> str:
    scope = str(value or DEFAULT_SCOPE).strip()
    return scope if scope in CADENCE_POLICIES else DEFAULT_SCOPE


def _record_blocked(state: dict[str, Any], now: float, retry_after: float, reason: str) -> None:
    state["last_blocked_monotonic"] = now
    state["last_blocked_at_ms"] = int(time.time() * 1000)
    state["last_blocked_retry_after_seconds"] = retry_after
    state["last_blocked_reason"] = reason
    state["blocked_count"] = int(state.get("blocked_count", 0)) + 1


def _blocked_result(scope: str, policy: dict[str, Any], retry_after: float, message: str) -> dict[str, Any]:
    return {
        "allowed": False,
        "scope": scope,
        "retry_after_seconds": retry_after,
        "min_interval_seconds": policy["min_interval_seconds"],
        "message": message,
    }


def _scope_status(name: str, policy: dict[str, Any], state: dict[str, Any], now: float) -> dict[str, Any]:
    last_started = state.get("last_started_monotonic")
    min_interval = float(policy["min_interval_seconds"])
    if isinstance(last_started, (int, float)):
        seconds_since_start = max(0.0, now - float(last_started))
        retry_after = max(0.0, min_interval - seconds_since_start)
    else:
        seconds_since_start = None
        retry_after = 0.0
    return {
        "scope": name,
        **policy,
        "active": bool(state.get("active", False)),
        "allowed_now": not state.get("active", False) and retry_after <= 0,
        "retry_after_seconds": round(retry_after, 3),
        "seconds_since_last_start": round(seconds_since_start, 3) if seconds_since_start is not None else None,
        "started_count": int(state.get("started_count", 0)),
        "blocked_count": int(state.get("blocked_count", 0)),
        "last_provider": state.get("last_provider"),
        "last_model": state.get("last_model"),
        "last_ok": state.get("last_ok"),
        "last_elapsed_ms": state.get("last_elapsed_ms"),
        "last_error_type": state.get("last_error_type"),
        "last_blocked_reason": state.get("last_blocked_reason"),
        "last_blocked_retry_after_seconds": state.get("last_blocked_retry_after_seconds"),
    }
