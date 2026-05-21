from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..reasoning import (
    get_reasoning_run,
    list_reasoning_runs,
    reasoning_contract_payload,
    reasoning_status_payload,
)


router = APIRouter()


@router.get("/reasoning/status")
async def reasoning_status() -> dict:
    return reasoning_status_payload()


@router.get("/reasoning/contract")
async def reasoning_contract() -> dict:
    return reasoning_contract_payload()


@router.get("/reasoning/runs")
async def reasoning_runs() -> dict:
    return {"runs": list_reasoning_runs()}


@router.get("/reasoning/runs/{run_id}")
async def reasoning_run_detail(run_id: str) -> dict:
    run = get_reasoning_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="reasoning run not found")
    return run
