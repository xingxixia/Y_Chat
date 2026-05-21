from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..local_models import local_models_payload
from ..services.local_audio_asr import transcribe_audio_evidence
from ..services.local_vision_embedding import embed_visual_evidence


router = APIRouter()


class VisionEmbedRequest(BaseModel):
    secondary_confirmed: bool = False
    evidence_id: str = ""


class AudioTranscribeRequest(BaseModel):
    secondary_confirmed: bool = False
    evidence_id: str = ""


@router.get("/local-models/status")
async def local_models_status() -> dict:
    return local_models_payload()


@router.post("/local-models/vision/embed")
async def local_models_vision_embed(request: VisionEmbedRequest) -> dict:
    result = embed_visual_evidence(request.model_dump())
    return {
        **result,
        "canonical_endpoint": "/vision/reader/embed",
        "compatibility_endpoint": "/local-models/vision/embed",
    }


@router.post("/local-models/audio/transcribe")
async def local_models_audio_transcribe(request: AudioTranscribeRequest) -> dict:
    result = transcribe_audio_evidence(request.model_dump())
    return {
        **result,
        "canonical_endpoint": "/audio/reader/transcribe",
        "compatibility_endpoint": "/local-models/audio/transcribe",
    }
