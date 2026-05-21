from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..memory import (
    add_memory_item,
    audio_status_payload,
    consolidation_buffer_payload,
    create_audio_evidence_record,
    create_text_evidence_record,
    create_visual_evidence_record,
    delete_memory_item,
    list_memory_audit_log,
    list_memory_items,
    list_memory_records,
    list_memory_review_queue,
    memory_contract_payload,
    memory_enabled,
    memory_shell_payload,
    memory_status_payload,
    text_status_payload,
)


router = APIRouter()


class MemoryCreateRequest(BaseModel):
    kind: str = "note"
    text: str


class VisualEvidenceRequest(BaseModel):
    source: str
    raw_ref: str
    sha256: str
    attachment_id: str | None = None
    source_event_id: str | None = None
    mime: str = "image/png"
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    source_display_width: int = 0
    source_display_height: int = 0
    thumbnail_max_width: int = 0
    raw_available: bool = True
    vision_reader_status: str = "metadata_only"


class TextEvidenceRequest(BaseModel):
    source: str = "user_command"
    text: str
    source_event_id: str | None = None
    language: str = "unknown"
    text_reader_status: str = "observed"


class AudioEvidenceRequest(BaseModel):
    source: str = "voice_clip"
    raw_ref: str
    sha256: str = ""
    attachment_id: str | None = None
    source_event_id: str | None = None
    mime: str = "audio/wav"
    duration_ms: int = 0
    size_bytes: int = 0
    raw_available: bool = True
    audio_reader_status: str = "metadata_only"
    transcript: str = ""


@router.get("/memory")
async def memory_list() -> dict:
    return {
        "enabled": memory_enabled(),
        "items": list_memory_items(),
    }


@router.get("/memory/status")
async def memory_status() -> dict:
    return memory_status_payload()


@router.get("/memory/contract")
async def memory_contract() -> dict:
    return memory_contract_payload()


@router.get("/memory/records")
async def memory_records() -> dict:
    return {
        "automatic_writes_enabled": False,
        "records": list_memory_records(),
    }


@router.get("/memory/review")
async def memory_review() -> dict:
    return {
        "automatic_writes_enabled": False,
        "review_queue": list_memory_review_queue(),
    }


@router.get("/memory/audit")
async def memory_audit() -> dict:
    return {
        "automatic_writes_enabled": False,
        "audit": list_memory_audit_log(),
    }


@router.get("/memory/shell")
async def memory_shell() -> dict:
    return memory_shell_payload()


@router.get("/memory/consolidation-buffer")
async def memory_consolidation_buffer() -> dict:
    return consolidation_buffer_payload()


@router.get("/text/status")
async def text_status() -> dict:
    return text_status_payload()


@router.get("/audio/status")
async def audio_status() -> dict:
    return audio_status_payload()


@router.post("/memory/visual-evidence")
async def memory_visual_evidence(request: VisualEvidenceRequest) -> dict:
    try:
        item = create_visual_evidence_record(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.post("/memory/text-evidence")
async def memory_text_evidence(request: TextEvidenceRequest) -> dict:
    try:
        item = create_text_evidence_record(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.post("/memory/audio-evidence")
async def memory_audio_evidence(request: AudioEvidenceRequest) -> dict:
    try:
        item = create_audio_evidence_record(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.post("/memory")
async def memory_create(request: MemoryCreateRequest) -> dict:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        item = add_memory_item(request.kind.strip() or "note", text)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"item": item}


@router.delete("/memory/{item_id}")
async def memory_delete(item_id: str) -> dict:
    return {"deleted": delete_memory_item(item_id)}
