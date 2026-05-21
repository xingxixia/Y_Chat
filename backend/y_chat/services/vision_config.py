from __future__ import annotations

from typing import Any

from ..config import load_config, save_config
from .provider_config import mask_secret


SUPPORTED_VISION_PROVIDERS = {"deepseek", "openai_compatible"}


def vision_config() -> dict[str, Any]:
    config = load_config()
    vision = config.get("vision", {})
    permissions = config.get("permissions", {})
    if not isinstance(vision, dict):
        vision = {}
    if not isinstance(permissions, dict):
        permissions = {}
    provider = str(vision.get("provider", "")).strip() or str(config.get("llm", {}).get("active_provider", "")).strip()
    providers = vision.get("providers", {})
    provider_config = providers.get(provider, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider_config, dict):
        provider_config = {}
    enabled = bool(vision.get("enabled", False)) and bool(permissions.get("vision.extract", False))
    return {
        "enabled": enabled,
        "provider": provider,
        "base_url": str(provider_config.get("base_url", "")).strip().rstrip("/"),
        "model": str(provider_config.get("model", "")).strip(),
        "api_key": str(provider_config.get("api_key", "")).strip(),
        "temperature": provider_config.get("temperature", 0.0),
        "timeout_seconds": provider_config.get("timeout_seconds", 60),
        "max_tokens": provider_config.get("max_tokens", 800),
        "stream": False,
    }


def vision_config_payload(*, local_ocr_available: bool) -> dict[str, Any]:
    config = vision_config()
    provider_configured = bool(config["provider"] and config["base_url"] and config["model"] and config["api_key"])
    return {
        "schema_version": "vision.config.v1",
        "enabled": config["enabled"],
        "provider": config["provider"],
        "base_url": config["base_url"],
        "model": config["model"],
        "api_key_configured": bool(config["api_key"]),
        "api_key_masked": mask_secret(config["api_key"]),
        "temperature": config["temperature"],
        "timeout_seconds": config["timeout_seconds"],
        "max_tokens": config["max_tokens"],
        "provider_configured": provider_configured,
        "call_route": "openai_compatible_chat_completions_image_url",
        "local_ocr_available": local_ocr_available,
        "raw_payload_returned": False,
        "api_key_returned": False,
    }


def validate_vision_config_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    provider = str(candidate.get("provider") or "").strip()
    base_url = str(candidate.get("base_url") or "").strip().rstrip("/")
    model = str(candidate.get("model") or "").strip()
    api_key = str(candidate.get("api_key") or "")
    enabled_requested = bool(candidate.get("enabled_requested", False))
    temperature = candidate.get("temperature", 0.0)
    timeout_seconds = _safe_positive_int(candidate.get("timeout_seconds"), default=60, minimum=5, maximum=180)
    max_tokens = _safe_positive_int(candidate.get("max_tokens"), default=800, minimum=64, maximum=4096)
    errors: list[str] = []
    warnings: list[str] = []

    if provider not in SUPPORTED_VISION_PROVIDERS:
        errors.append("provider must be deepseek or openai_compatible")
    if not base_url.startswith(("http://", "https://")):
        errors.append("base_url must be an http or https URL")
    if not model:
        errors.append("model is required")
    if enabled_requested and not api_key.strip():
        errors.append("api_key is required when enabling vision extraction")
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.0
        errors.append("temperature must be numeric")
    if temperature < 0 or temperature > 2:
        errors.append("temperature must be between 0 and 2")

    return {
        "ok": not errors,
        "saved": False,
        "enabled_requested": enabled_requested,
        "requires_secondary_confirmation_for_save": True,
        "errors": errors,
        "warnings": warnings,
        "candidate": {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "api_key_configured": bool(api_key.strip()),
            "api_key_masked": mask_secret(api_key),
            "temperature": temperature,
            "timeout_seconds": timeout_seconds,
            "max_tokens": max_tokens,
        },
        "raw_payload_returned": False,
        "api_key_returned": False,
    }


def save_vision_config_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    validation = validate_vision_config_candidate(candidate)
    if not validation["ok"]:
        return {**validation, "saved": False, "message": "validation failed; vision config was not saved"}
    if not bool(candidate.get("secondary_confirmed", False)):
        return {
            **validation,
            "saved": False,
            "errors": [*validation["errors"], "secondary confirmation is required to save vision config"],
            "message": "secondary confirmation is required to save vision config",
        }

    api_key = str(candidate.get("api_key") or "").strip()
    sanitized = validation["candidate"]
    config = load_config()
    permissions = config.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        permissions = {}
        config["permissions"] = permissions
    vision_config_data = config.setdefault("vision", {})
    if not isinstance(vision_config_data, dict):
        vision_config_data = {}
        config["vision"] = vision_config_data
    providers = vision_config_data.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        vision_config_data["providers"] = providers
    provider_config = providers.setdefault(sanitized["provider"], {})
    if not isinstance(provider_config, dict):
        provider_config = {}
        providers[sanitized["provider"]] = provider_config

    provider_config.update(
        {
            "base_url": sanitized["base_url"],
            "api_key": api_key,
            "model": sanitized["model"],
            "temperature": sanitized["temperature"],
            "timeout_seconds": sanitized["timeout_seconds"],
            "max_tokens": sanitized["max_tokens"],
        }
    )
    enabled_requested = bool(candidate.get("enabled_requested", False))
    vision_config_data["provider"] = sanitized["provider"]
    vision_config_data["enabled"] = enabled_requested
    if enabled_requested:
        permissions["vision.extract"] = True
    save_config(config)
    return {
        **validation,
        "saved": True,
        "enabled": enabled_requested and bool(permissions.get("vision.extract", False)),
        "message": "vision config saved",
    }


def vision_extraction_status_payload(
    *,
    config: dict[str, Any],
    local_ocr_available: bool,
) -> dict[str, Any]:
    blocked_reasons: list[str] = []
    if not config["enabled"]:
        blocked_reasons.append("vision.enabled or permissions.vision.extract is disabled")
    if not config["provider"]:
        blocked_reasons.append("vision provider is not selected")
    if not config["base_url"]:
        blocked_reasons.append("vision provider base_url is not configured")
    if not config["model"]:
        blocked_reasons.append("vision provider model is not configured")
    if not config["api_key"]:
        blocked_reasons.append("vision provider API key is not configured")
    return {
        "schema_version": "vision_extraction.status.v1",
        "enabled": bool(config["enabled"] and not blocked_reasons[1:]),
        "provider": config["provider"],
        "model": config["model"],
        "call_route": "openai_compatible_chat_completions_image_url",
        "local_ocr_available": local_ocr_available,
        "local_ocr_provider": "local_rapidocr" if local_ocr_available else None,
        "blocked_reasons": blocked_reasons,
        "raw_payload_returned": False,
        "api_key_returned": False,
    }


def _safe_positive_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))
