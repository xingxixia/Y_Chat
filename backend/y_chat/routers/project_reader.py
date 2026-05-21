from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..project_reader import (
    contract_payload as project_reader_contract_payload,
    list_root_files,
    status_payload as project_reader_status_payload,
)


router = APIRouter()


@router.get("/project-reader/status")
async def project_reader_status() -> dict:
    return project_reader_status_payload()


@router.get("/project-reader/contract")
async def project_reader_contract() -> dict:
    return project_reader_contract_payload()


@router.get("/project-reader/files")
async def project_reader_files(root_index: int = 0) -> dict:
    try:
        items = list_root_files(root_index)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": items}
