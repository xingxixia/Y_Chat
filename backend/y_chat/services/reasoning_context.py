from __future__ import annotations

from typing import Any

from ..events import EventEnvelope
from .reasoning_multimodal_context import (
    current_event_multimodal_refs,
    recent_audio_reasoning_context as service_recent_audio_reasoning_context,
)
from .reasoning_modalities import infer_event_modalities, primary_event_modality
from .reasoning_provider import PROVIDER_NAME, active_model_call_config
from .reasoning_visual_context import recent_visual_reasoning_context as service_recent_visual_reasoning_context


class ReasoningRequest(dict):
    pass


def source_event_summary(event: EventEnvelope) -> dict[str, Any]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    return {
        "event_id": event.event_id,
        "type": event.type,
        "source": event.source,
        "timestamp": event.timestamp,
        "correlation_id": event.correlation_id,
        "payload_keys": sorted(str(key) for key in payload.keys()),
    }


def build_context_snapshot(request: ReasoningRequest) -> dict[str, Any]:
    event = EventEnvelope.model_validate(request["source_event"])
    context = request.get("context", {})
    recent_summary = context.get("recent_summary", [])
    entity_refs = context.get("entity_refs", [])
    core_memory_summary = context.get("core_memory_summary", [])
    visual_context = context.get("visual_context", {})
    audio_context = context.get("audio_context", {})
    current_event_refs = context.get("current_event_refs", {})
    recent_visual_evidence = (
        visual_context.get("recent_visual_evidence", []) if isinstance(visual_context, dict) else []
    )
    recent_ocr_text = visual_context.get("recent_ocr_text", []) if isinstance(visual_context, dict) else []
    recent_audio_evidence = (
        audio_context.get("recent_audio_evidence", []) if isinstance(audio_context, dict) else []
    )
    recent_audio_transcripts = [
        item for item in recent_audio_evidence if isinstance(item, dict) and item.get("transcript")
    ] if isinstance(recent_audio_evidence, list) else []
    current_event_vision_refs = (
        current_event_refs.get("vision", []) if isinstance(current_event_refs, dict) else []
    )
    current_event_audio_refs = current_event_refs.get("audio", []) if isinstance(current_event_refs, dict) else []
    current_event_attachments = (
        current_event_refs.get("attachments", []) if isinstance(current_event_refs, dict) else []
    )
    current_event_text = str(context.get("current_event_text", ""))
    return {
        "schema_version": "reasoning_context_snapshot.v1",
        "run_id": request["run_id"],
        "input": request["input"],
        "source_event": source_event_summary(event),
        "context_summary": {
            "has_current_event_text": bool(current_event_text),
            "current_event_text_chars": len(current_event_text),
            "recent_summary_count": len(recent_summary) if isinstance(recent_summary, list) else 0,
            "entity_refs_count": len(entity_refs) if isinstance(entity_refs, list) else 0,
            "core_memory_summary_count": (
                len(core_memory_summary) if isinstance(core_memory_summary, list) else 0
            ),
            "recent_visual_evidence_count": (
                len(recent_visual_evidence) if isinstance(recent_visual_evidence, list) else 0
            ),
            "fresh_visual_evidence_count": int(visual_context.get("fresh_visual_evidence_count") or 0)
            if isinstance(visual_context, dict)
            else 0,
            "stale_visual_evidence_count": int(visual_context.get("stale_visual_evidence_count") or 0)
            if isinstance(visual_context, dict)
            else 0,
            "latest_visual_age_seconds": visual_context.get("latest_visual_age_seconds")
            if isinstance(visual_context, dict)
            else None,
            "current_screen_evidence_available": bool(visual_context.get("current_screen_evidence_available"))
            if isinstance(visual_context, dict)
            else False,
            "recent_ocr_text_count": len(recent_ocr_text) if isinstance(recent_ocr_text, list) else 0,
            "recent_audio_evidence_count": (
                len(recent_audio_evidence) if isinstance(recent_audio_evidence, list) else 0
            ),
            "recent_audio_transcript_count": len(recent_audio_transcripts),
            "current_event_ref_counts": {
                "vision": len(current_event_vision_refs) if isinstance(current_event_vision_refs, list) else 0,
                "audio": len(current_event_audio_refs) if isinstance(current_event_audio_refs, list) else 0,
                "attachments": len(current_event_attachments) if isinstance(current_event_attachments, list) else 0,
            },
            "modality_context": context.get("modality_context", {}),
        },
        "visual_context": visual_context,
        "audio_context": audio_context,
        "current_event_refs": current_event_refs,
        "provider": request["provider"],
        "depth": request["depth"],
        "real_model_calls": request["real_model_calls"],
        "raw_payload_stored": False,
    }


def build_reasoning_request(
    run_id: str,
    event: EventEnvelope,
    visual_context: dict[str, Any],
    audio_context: dict[str, Any] | None = None,
    model_config: dict[str, Any] | None = None,
) -> ReasoningRequest:
    payload = event.payload if isinstance(event.payload, dict) else {}
    text = str(payload.get("text", "")).strip()
    modalities = infer_event_modalities(event.type, payload)
    primary_modality = primary_event_modality(modalities)
    model_config = model_config or active_model_call_config()
    audio_context = audio_context or {
        "schema_version": "reasoning_audio_context.v1",
        "recent_audio_evidence": [],
        "raw_audio_bytes_included": False,
        "absolute_local_paths_included": False,
        "provider_must_not_claim_unparsed_audio": True,
    }
    current_event_refs = current_event_multimodal_refs(payload)
    recent_visual_evidence = visual_context.get("recent_visual_evidence", [])
    recent_ocr_text = visual_context.get("recent_ocr_text", [])
    recent_audio_evidence = audio_context.get("recent_audio_evidence", [])
    current_event_vision_refs = current_event_refs.get("vision", [])
    current_event_audio_refs = current_event_refs.get("audio", [])
    return ReasoningRequest(
        {
            "schema_version": "reasoning_request.v1",
            "run_id": run_id,
            "source_event": event.model_dump(),
            "input": {
                "event_type": event.type,
                "source": event.source,
                "primary_modality": primary_modality,
                "modalities": modalities,
            },
            "depth": "lightweight",
            "provider": model_config["provider"] if model_config["enabled"] else PROVIDER_NAME,
            "context": {
                "current_event_text": text,
                "recent_summary": [],
                "entity_refs": [],
                "core_memory_summary": [],
                "visual_context": visual_context,
                "audio_context": audio_context,
                "current_event_refs": current_event_refs,
                "modality_context": {
                    "text": {"available": "text" in modalities},
                    "vision": {
                        "available": "vision" in modalities or bool(recent_visual_evidence),
                        "capture_enabled": True,
                        "recent_visual_evidence_count": len(recent_visual_evidence),
                        "fresh_visual_evidence_count": int(visual_context.get("fresh_visual_evidence_count") or 0),
                        "stale_visual_evidence_count": int(visual_context.get("stale_visual_evidence_count") or 0),
                        "current_screen_evidence_available": bool(
                            visual_context.get("current_screen_evidence_available")
                        ),
                        "recent_ocr_text_count": len(recent_ocr_text),
                        "current_event_ref_count": len(current_event_vision_refs),
                    },
                    "audio": {
                        "available": "audio" in modalities or bool(recent_audio_evidence),
                        "capture_enabled": False,
                        "asr_enabled": False,
                        "recent_audio_evidence_count": len(recent_audio_evidence),
                        "recent_transcript_count": len(
                            [item for item in recent_audio_evidence if isinstance(item, dict) and item.get("transcript")]
                        ),
                        "current_event_ref_count": len(current_event_audio_refs),
                    },
                    "state": {"available": "state" in modalities},
                    "project": {"available": "project" in modalities},
                },
            },
            "real_model_calls": model_config["enabled"],
        }
    )


def recent_visual_reasoning_context(db, limit: int = 5) -> dict[str, Any]:
    return service_recent_visual_reasoning_context(db, limit)


def recent_audio_reasoning_context(db, limit: int = 5) -> dict[str, Any]:
    return service_recent_audio_reasoning_context(db, limit)
