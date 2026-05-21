from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..provider_client import chat_completions_url
from .model_provider_cadence import provider_cadence_status_payload
from .provider_config import RECOMMENDED_DEEPSEEK_MODELS, SUPPORTED_PROVIDER_NAMES, mask_secret


@dataclass(frozen=True)
class ModelProviderConfig:
    enabled: bool
    active_provider: str
    model: str
    configured: bool


ConfigLoader = Callable[[], dict[str, Any]]


def get_model_provider_config(load_config_fn: ConfigLoader) -> ModelProviderConfig:
    config = load_config_fn()
    llm_config = config.get("llm", {})
    permissions = config.get("permissions", {})

    active_provider = str(llm_config.get("active_provider", "")).strip()
    providers: dict[str, Any] = llm_config.get("providers", {})
    provider_config = providers.get(active_provider, {}) if active_provider else {}
    model = str(provider_config.get("model", "")).strip()
    api_key = str(provider_config.get("api_key", "")).strip()
    base_url = str(provider_config.get("base_url", "")).strip()

    enabled = bool(llm_config.get("enabled", False))
    allowed = bool(permissions.get("model.call", False))

    return ModelProviderConfig(
        enabled=enabled and allowed,
        active_provider=active_provider,
        model=model,
        configured=bool(active_provider and model and base_url and api_key),
    )


def provider_status_payload(load_config_fn: ConfigLoader) -> dict[str, Any]:
    provider = get_model_provider_config(load_config_fn)
    return {
        "enabled": provider.enabled,
        "active_provider": provider.active_provider,
        "model": provider.model,
        "configured": provider.configured,
    }


def provider_config_payload(load_config_fn: ConfigLoader) -> dict[str, Any]:
    config = load_config_fn()
    llm_config = config.get("llm", {})
    permissions = config.get("permissions", {})
    if not isinstance(llm_config, dict):
        llm_config = {}
    if not isinstance(permissions, dict):
        permissions = {}

    providers = llm_config.get("providers", {})
    if not isinstance(providers, dict):
        providers = {}

    provider_items: dict[str, dict[str, Any]] = {}
    for name, raw_provider in sorted(providers.items(), key=lambda item: str(item[0])):
        provider_config = raw_provider if isinstance(raw_provider, dict) else {}
        api_key = str(provider_config.get("api_key", ""))
        provider_items[str(name)] = {
            "base_url": str(provider_config.get("base_url", "")),
            "model": str(provider_config.get("model", "")),
            "temperature": provider_config.get("temperature"),
            "stream": bool(provider_config.get("stream", False)),
            "timeout_seconds": provider_config.get("timeout_seconds", 45),
            "max_tokens": provider_config.get("max_tokens", 1200),
            "thinking_type": str(provider_config.get("thinking_type", "disabled")),
            "api_key_configured": bool(api_key.strip()),
            "api_key_masked": mask_secret(api_key),
        }

    active_provider = str(llm_config.get("active_provider", "")).strip()
    enabled_requested = bool(llm_config.get("enabled", False))
    permission_allowed = bool(permissions.get("model.call", False))
    active_config = provider_items.get(active_provider, {})
    configured = bool(
        active_provider
        and active_provider in SUPPORTED_PROVIDER_NAMES
        and active_config.get("api_key_configured", False)
        and active_config.get("base_url")
        and active_config.get("model")
    )
    real_model_calls = enabled_requested and permission_allowed and configured
    blocked_reasons: list[str] = []
    if not enabled_requested:
        blocked_reasons.append("llm.enabled is false")
    if not permission_allowed:
        blocked_reasons.append("permissions.model.call is disabled")
    if not active_provider:
        blocked_reasons.append("active provider is not selected")
    elif active_provider not in SUPPORTED_PROVIDER_NAMES:
        blocked_reasons.append("active provider is not supported")
    if not active_config.get("base_url"):
        blocked_reasons.append("active provider base_url is not configured")
    if not active_config.get("model"):
        blocked_reasons.append("active provider model is not configured")
    if not active_config.get("api_key_configured", False):
        blocked_reasons.append("active provider API key is not configured")
    if active_provider == "deepseek" and active_config.get("model") == "deepseek-chat":
        blocked_reasons.append("deepseek-chat is legacy; prefer deepseek-v4-flash or deepseek-v4-pro")

    return {
        "enabled_requested": enabled_requested,
        "permission_allowed": permission_allowed,
        "effective_enabled": real_model_calls,
        "active_provider": active_provider,
        "providers": provider_items,
        "real_model_calls": real_model_calls,
        "read_only": False,
        "call_route": "openai_compatible_chat_completions",
        "call_url": chat_completions_url(str(active_config.get("base_url", ""))) if active_config.get("base_url") else "",
        "blocked_reasons": blocked_reasons,
        "next_requirements": [
            "confirm provider and model",
            "enter API key through Debug with secondary confirmation",
            "write redacted provider-config audit",
            "enable llm.enabled and permissions.model.call",
            "keep final output gated by complete reasoning.v1 JSON validation",
        ],
        "save_endpoint": "/model/provider/config/save",
        "recommended_models": {
            "deepseek": RECOMMENDED_DEEPSEEK_MODELS,
            "openai_compatible": [],
        },
        "real_call_test_endpoint": "/model/provider/test",
        "cadence": provider_cadence_status_payload(),
    }


def provider_readiness_payload(config_payload_fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    config = config_payload_fn()
    return {
        "ready": bool(config["real_model_calls"]),
        "will_call_model_on_next_reasoning_run": bool(config["real_model_calls"]),
        "call_route": config["call_route"],
        "active_provider": config["active_provider"],
        "blocked_reasons": config["blocked_reasons"],
        "cadence": provider_cadence_status_payload(),
        "redacted": True,
        "dry_run_only": True,
        "api_key_returned": False,
    }


def active_provider_call_config(load_config_fn: ConfigLoader) -> dict[str, Any]:
    config = load_config_fn()
    llm_config = config.get("llm", {})
    permissions = config.get("permissions", {})
    if not isinstance(llm_config, dict):
        llm_config = {}
    if not isinstance(permissions, dict):
        permissions = {}
    active_provider = str(llm_config.get("active_provider", "")).strip()
    providers = llm_config.get("providers", {})
    provider_config = providers.get(active_provider, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider_config, dict):
        provider_config = {}
    return {
        "enabled": bool(llm_config.get("enabled", False)) and bool(permissions.get("model.call", False)),
        "provider": active_provider,
        "base_url": str(provider_config.get("base_url", "")).strip().rstrip("/"),
        "model": str(provider_config.get("model", "")).strip(),
        "api_key": str(provider_config.get("api_key", "")).strip(),
        "temperature": provider_config.get("temperature", 0.0),
        "stream": False,
        "timeout_seconds": provider_config.get("timeout_seconds", 45),
        "max_tokens": provider_config.get("max_tokens", 512),
        "thinking_type": provider_config.get("thinking_type", "disabled"),
        "cadence_scope": "reasoning_foreground",
    }
