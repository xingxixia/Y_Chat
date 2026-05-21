from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .provider_config import record_provider_config_audit, validate_provider_config_candidate


ConfigLoader = Callable[[], dict[str, Any]]
ConfigSaver = Callable[[dict[str, Any]], None]


def save_provider_config_candidate(
    candidate: dict[str, Any],
    *,
    load_config_fn: ConfigLoader,
    save_config_fn: ConfigSaver,
    config_path: Path,
) -> dict[str, Any]:
    validation = validate_provider_config_candidate(candidate)
    if not validation["ok"]:
        return {
            **validation,
            "saved": False,
            "enabled": False,
            "message": "validation failed; config was not saved",
        }

    provider = str(candidate.get("provider") or candidate.get("active_provider") or "").strip()
    api_key = str(candidate.get("api_key") or "").strip()
    secondary_confirmed = bool(candidate.get("secondary_confirmed", False))
    enabled_requested = bool(candidate.get("enabled_requested", False))
    if not secondary_confirmed:
        return {
            **validation,
            "saved": False,
            "enabled": False,
            "errors": [*validation["errors"], "secondary confirmation is required to save provider config"],
            "message": "secondary confirmation is required to save provider config",
        }

    config = load_config_fn()
    llm_config = config.setdefault("llm", {})
    if not isinstance(llm_config, dict):
        llm_config = {}
        config["llm"] = llm_config
    providers = llm_config.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        llm_config["providers"] = providers
    provider_config = providers.setdefault(provider, {})
    if not isinstance(provider_config, dict):
        provider_config = {}
        providers[provider] = provider_config
    existing_api_key = str(provider_config.get("api_key", "")).strip()
    effective_api_key = api_key or existing_api_key
    if not effective_api_key:
        return {
            **validation,
            "saved": False,
            "enabled": False,
            "errors": [*validation["errors"], "api_key is required to save provider config"],
            "message": "api_key is required to save provider config",
        }

    sanitized = validation["candidate"]
    provider_config["base_url"] = sanitized["base_url"]
    provider_config["api_key"] = effective_api_key
    provider_config["model"] = sanitized["model"]
    provider_config["temperature"] = sanitized["temperature"]
    provider_config["stream"] = sanitized["stream"]
    provider_config["timeout_seconds"] = sanitized["timeout_seconds"]
    provider_config["max_tokens"] = sanitized["max_tokens"]
    provider_config["thinking_type"] = sanitized["thinking_type"]
    llm_config["active_provider"] = provider
    llm_config["enabled"] = enabled_requested

    permissions = config.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        permissions = {}
        config["permissions"] = permissions
    if enabled_requested:
        permissions["model.call"] = True

    if bool(candidate.get("use_for_vision", False)):
        vision_config = config.setdefault("vision", {})
        if not isinstance(vision_config, dict):
            vision_config = {}
            config["vision"] = vision_config
        vision_providers = vision_config.setdefault("providers", {})
        if not isinstance(vision_providers, dict):
            vision_providers = {}
            vision_config["providers"] = vision_providers
        vision_provider_config = vision_providers.setdefault(provider, {})
        if not isinstance(vision_provider_config, dict):
            vision_provider_config = {}
            vision_providers[provider] = vision_provider_config
        vision_provider_config.update(
            {
                "base_url": sanitized["base_url"],
                "api_key": api_key,
                "model": sanitized["model"],
                "temperature": sanitized["temperature"],
                "timeout_seconds": sanitized["timeout_seconds"],
                "max_tokens": sanitized["max_tokens"],
            }
        )
        vision_config["provider"] = provider
        vision_config["enabled"] = True
        permissions["vision.extract"] = True

    save_config_fn(config)
    audit_payload = {
        "action": "save_provider_config_candidate",
        "saved": True,
        "enabled_requested": enabled_requested,
        "secondary_confirmed": secondary_confirmed,
        "permission_model_call": bool(permissions.get("model.call", False)),
        "candidate": sanitized,
        "config_path": str(config_path),
        "clear_api_key_in_audit": False,
    }
    audit_id = record_provider_config_audit("saved", audit_payload)
    return {
        "ok": True,
        "saved": True,
        "enabled": bool(llm_config.get("enabled", False)) and bool(permissions.get("model.call", False)),
        "real_model_calls": bool(llm_config.get("enabled", False)) and bool(permissions.get("model.call", False)),
        "requires_secondary_confirmation_for_save": True,
        "audit_id": audit_id,
        "candidate": sanitized,
        "errors": [],
        "warnings": validation["warnings"],
        "message": "provider config saved locally; real calls are available only through the reasoning route",
    }
