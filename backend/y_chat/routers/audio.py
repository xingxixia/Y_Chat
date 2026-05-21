from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..audio_reader import audio_reader_status_payload
from ..services.local_audio_asr import transcribe_audio_evidence


router = APIRouter()


class AudioTranscribeRequest(BaseModel):
    secondary_confirmed: bool = False
    evidence_id: str = ""


@router.get("/audio/reader/status")
async def audio_reader_status() -> dict:
    return audio_reader_status_payload()


@router.post("/audio/reader/transcribe")
async def audio_reader_transcribe(request: AudioTranscribeRequest) -> dict:
    return transcribe_audio_evidence(request.model_dump())
