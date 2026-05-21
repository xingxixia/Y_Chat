from __future__ import annotations

from typing import Any

from .config import CONFIG_PATH, load_config, save_config
from .provider_client import extract_message_content, post_chat_completion
from .services.model_provider_runtime import (
    ModelProviderConfig,
    active_provider_call_config as service_active_provider_call_config,
    get_model_provider_config as service_get_model_provider_config,
    provider_config_payload as service_provider_config_payload,
    provider_readiness_payload as service_provider_readiness_payload,
    provider_status_payload as service_provider_status_payload,
    run_model_provider_test_call as service_run_model_provider_test_call,
    save_provider_config_candidate as service_save_provider_config_candidate,
)
from .services.model_provider_cadence import provider_cadence_status_payload
from .services.provider_config import (
    provider_config_audit_payload,
    validate_provider_config_candidate,
)


def get_model_provider_config() -> ModelProviderConfig:
    return service_get_model_provider_config(load_config)


def provider_status_payload() -> dict[str, Any]:
    return service_provider_status_payload(load_config)


def provider_config_payload() -> dict[str, Any]:
    return service_provider_config_payload(load_config)


def provider_readiness_payload() -> dict[str, Any]:
    return service_provider_readiness_payload(provider_config_payload)


def save_provider_config_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return service_save_provider_config_candidate(
        candidate,
        load_config_fn=load_config,
        save_config_fn=save_config,
        config_path=CONFIG_PATH,
    )


def _active_provider_call_config() -> dict[str, Any]:
    return service_active_provider_call_config(load_config)


def run_model_provider_test_call(payload: dict[str, Any]) -> dict[str, Any]:
    return service_run_model_provider_test_call(
        payload,
        readiness_payload_fn=provider_readiness_payload,
        active_provider_call_config_fn=_active_provider_call_config,
        post_chat_completion_fn=post_chat_completion,
        extract_message_content_fn=extract_message_content,
    )
