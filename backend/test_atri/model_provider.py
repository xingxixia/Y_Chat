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
