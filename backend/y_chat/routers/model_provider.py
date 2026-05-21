from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..model_provider import (
    provider_config_audit_payload,
    provider_config_payload,
    provider_cadence_status_payload,
    provider_readiness_payload,
    provider_status_payload,
    run_model_provider_test_call,
    save_provider_config_candidate,
    validate_provider_config_candidate,
)


router = APIRouter()


class ProviderConfigValidateRequest(BaseModel):
    provider: str
    base_url: str
    model: str
    api_key: str = ""
    temperature: float | None = None
    stream: bool = False
    enabled_requested: bool = False
    secondary_confirmed: bool = False
    timeout_seconds: int = 45
    max_tokens: int = 1200
    thinking_type: str = "disabled"


class ProviderTestRequest(BaseModel):
    secondary_confirmed: bool = False
    prompt: str = "Return a tiny JSON object with ok true."


@router.get("/model/provider/status")
async def model_provider_status() -> dict:
    return provider_status_payload()


@router.get("/model/provider/config")
async def model_provider_config() -> dict:
    return provider_config_payload()


@router.post("/model/provider/config/validate")
async def model_provider_config_validate(request: ProviderConfigValidateRequest) -> dict:
    return validate_provider_config_candidate(request.model_dump())


@router.post("/model/provider/config/save")
async def model_provider_config_save(request: ProviderConfigValidateRequest) -> dict:
    return save_provider_config_candidate(request.model_dump())


@router.get("/model/provider/config/audit")
async def model_provider_config_audit() -> dict:
    return provider_config_audit_payload()


@router.get("/model/provider/readiness")
async def model_provider_readiness() -> dict:
    return provider_readiness_payload()


@router.get("/model/provider/cadence")
async def model_provider_cadence() -> dict:
    return provider_cadence_status_payload()


@router.post("/model/provider/test")
async def model_provider_test(request: ProviderTestRequest) -> dict:
    return run_model_provider_test_call(request.model_dump())
