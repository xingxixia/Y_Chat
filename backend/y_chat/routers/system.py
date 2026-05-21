from __future__ import annotations

from fastapi import APIRouter

from ..backend_status import backend_status_payload
from ..contracts import contracts_index_payload
from ..data_status import data_status_payload
from ..events import event_contract_payload
from ..logs import log_status_payload
from ..permissions import permission_contract_payload, permission_status_payload
from ..state_manager import state_contract_payload


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "y_chat"}


@router.get("/backend/status")
async def backend_status() -> dict:
    return backend_status_payload()


@router.get("/data/status")
async def data_status() -> dict:
    return data_status_payload()


@router.get("/contracts")
async def contracts_index() -> dict:
    return contracts_index_payload()


@router.get("/permissions/status")
async def permissions_status() -> dict:
    return permission_status_payload()


@router.get("/permissions/contract")
async def permissions_contract() -> dict:
    return permission_contract_payload()


@router.get("/events/contract")
async def events_contract() -> dict:
    return event_contract_payload()


@router.get("/state/contract")
async def state_contract() -> dict:
    return state_contract_payload()


@router.get("/logs/status")
async def logs_status() -> dict:
    return log_status_payload()
