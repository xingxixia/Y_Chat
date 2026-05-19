from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import load_config


@dataclass(frozen=True)
class ModelProviderConfig:
    enabled: bool
    active_provider: str
    model: str
    configured: bool


def mask_secret(value: str) -> str:
    secret = value.strip()
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:3]}...{secret[-4:]}"


def get_model_provider_config() -> ModelProviderConfig:
    config = load_config()
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


def provider_status_payload() -> dict[str, Any]:
    provider = get_model_provider_config()
    return {
        "enabled": provider.enabled,
        "active_provider": provider.active_provider,
        "model": provider.model,
        "configured": provider.configured,
    }


def provider_config_payload() -> dict[str, Any]:
    config = load_config()
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
            "api_key_configured": bool(api_key.strip()),
            "api_key_masked": mask_secret(api_key),
        }

    active_provider = str(llm_config.get("active_provider", "")).strip()
    enabled_requested = bool(llm_config.get("enabled", False))
    permission_allowed = bool(permissions.get("model.call", False))

    return {
        "enabled_requested": enabled_requested,
        "permission_allowed": permission_allowed,
        "effective_enabled": enabled_requested and permission_allowed,
        "active_provider": active_provider,
        "providers": provider_items,
        "real_model_calls": False,
        "read_only": True,
    }
