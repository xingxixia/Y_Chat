from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..events import EventEnvelope
from .reasoning_modalities import infer_event_modalities, primary_event_modality
from .reasoning_schema import SCHEMA_VERSION


def build_deterministic_output(run_id: str, event: EventEnvelope) -> dict[str, Any]:
    text = str(event.payload.get("text", "")).strip()
    modalities = infer_event_modalities(event.type, event.payload if isinstance(event.payload, dict) else {})
    primary_modality = primary_event_modality(modalities)
    reply_text = (
        f"Received {primary_modality} event: {text or event.type}\n\n"
        "Reasoning R1 deterministic fallback handled this command."
    )
    candidate_id = str(uuid4())
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "reply": {
            "should_reply": True,
            "text": reply_text,
            "bubble_text": reply_text,
            "style": "normal",
            "final": True,
        },
        "state": {
            "pet_state": "talking",
            "emotion": "neutral",
            "animation": None,
        },
        "actions": [],
        "memory": {
            "write_candidates": [
                {
                    "candidate_id": candidate_id,
                    "target_layer": "short_term",
                    "kind": "task_state",
                    "content": {
                        "text": text,
                        "event_type": event.type,
                        "source": event.source,
                        "primary_modality": primary_modality,
                        "modalities": modalities,
                    },
                    "related_entity_id": None,
                    "source_event_ids": [event.event_id],
                    "reason": "R1 fallback records command input for Debug inspection only.",
                    "confidence": 0.4,
                    "importance": 0.2,
                    "review_required": True,
                }
            ],
            "do_not_write_reason": None,
            "needs_consolidation": False,
        },
        "observations": [],
        "voice": {
            "speak": False,
            "text": None,
            "voice_style": None,
        },
        "debug": {
            "depth": "lightweight",
            "needs_deep_retrieval": False,
            "deep_retrieval_query": None,
            "trace": [],
        },
        "audit": {
            "safety_notes": ["deterministic fallback; real model not called"],
            "permission_requests": [],
        },
    }
