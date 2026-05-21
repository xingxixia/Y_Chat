from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..memory import vision_status_payload
from ..services.local_vision_embedding import embed_visual_evidence
from ..services.local_vision_vlm import recognize_visual_evidence
from ..vision_reader import vision_reader_status_payload
from ..vision_extractor import (
    extract_visual_evidence,
    save_vision_config_candidate,
    validate_vision_config_candidate,
    vision_config_payload,
    vision_extraction_status_payload,
)


router = APIRouter()


class VisionExtractRequest(BaseModel):
    secondary_confirmed: bool = False
    evidence_id: str = ""
    provider: str = ""
    prompt: str = ""


class VisionConfigRequest(BaseModel):
    provider: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float | None = 0.0
    enabled_requested: bool = False
    secondary_confirmed: bool = False
    timeout_seconds: int = 60
    max_tokens: int = 800


class VisionEmbedRequest(BaseModel):
    secondary_confirmed: bool = False
    evidence_id: str = ""


@router.get("/vision/status")
async def vision_status() -> dict:
    status = vision_status_payload()
    return {**status, "extraction": vision_extraction_status_payload()}


@router.get("/vision/reader/status")
async def vision_reader_status() -> dict:
    return vision_reader_status_payload()


@router.post("/vision/reader/embed")
async def vision_reader_embed(request: VisionEmbedRequest) -> dict:
    return embed_visual_evidence(request.model_dump())


@router.post("/vision/reader/recognize")
async def vision_reader_recognize(request: VisionExtractRequest) -> dict:
    return recognize_visual_evidence(request.model_dump())


@router.get("/vision/extraction/status")
async def vision_extraction_status() -> dict:
    return vision_extraction_status_payload()


@router.get("/vision/config")
async def vision_config() -> dict:
    return vision_config_payload()


@router.post("/vision/config/validate")
async def vision_config_validate(request: VisionConfigRequest) -> dict:
    return validate_vision_config_candidate(request.model_dump())


@router.post("/vision/config/save")
async def vision_config_save(request: VisionConfigRequest) -> dict:
    return save_vision_config_candidate(request.model_dump())


@router.post("/vision/extract")
async def vision_extract(request: VisionExtractRequest) -> dict:
    return extract_visual_evidence(request.model_dump())
