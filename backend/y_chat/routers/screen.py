from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.responses import FileResponse

from ..config import RUNTIME_DIR
from ..screen_observation import (
    request_screen_observation_start,
    request_screen_observation_stop,
    screen_observation_contract_payload,
    screen_observation_status_payload,
)
from ..shared.contracts import RUNTIME_REF_PREFIX


router = APIRouter()


class ScreenObservationStartRequest(BaseModel):
    secondary_confirmed: bool = False
    interval_seconds: int = 3
    retain_raw: bool = True


class ScreenObservationStopRequest(BaseModel):
    revoke_permission: bool = False


def _runtime_preview_path(raw_ref: str) -> Path:
    prefix = RUNTIME_REF_PREFIX
    if not raw_ref.startswith(prefix):
        raise HTTPException(status_code=400, detail=f"raw_ref must use {RUNTIME_REF_PREFIX}")
    relative = unquote(raw_ref[len(prefix):]).replace("/", "\\")
    path = (RUNTIME_DIR / relative).resolve()
    runtime_root = RUNTIME_DIR.resolve()
    screenshot_root = (RUNTIME_DIR / "memory_blobs" / "vision" / "screenshots").resolve()
    if runtime_root not in path.parents and path != runtime_root:
        raise HTTPException(status_code=400, detail="raw_ref escapes runtime")
    if screenshot_root not in path.parents and path != screenshot_root:
        raise HTTPException(status_code=403, detail="preview is limited to retained screen images")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="raw image not found")
    return path


@router.get("/screen/observation/status")
async def screen_observation_status() -> dict:
    return screen_observation_status_payload(active=False)


@router.get("/screen/observation/contract")
async def screen_observation_contract() -> dict:
    return screen_observation_contract_payload()


@router.get("/screen/observation/preview")
async def screen_observation_preview(raw_ref: str) -> FileResponse:
    path = _runtime_preview_path(raw_ref)
    media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/screen/observation/start")
async def screen_observation_start(request: ScreenObservationStartRequest) -> dict:
    return request_screen_observation_start(request.model_dump())


@router.post("/screen/observation/stop")
async def screen_observation_stop(request: ScreenObservationStopRequest) -> dict:
    return request_screen_observation_stop(request.model_dump())
