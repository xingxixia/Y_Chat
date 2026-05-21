from __future__ import annotations

from typing import Any


MEMORY_LAYER_CONTRACTS: list[dict[str, Any]] = [
    {
        "name": "reasoning_scratch",
        "label": "Reasoning Scratch",
        "current_mode": "planned",
        "writes_enabled": False,
        "purpose": "Temporary low-weight reasoning trace and candidate conclusions.",
        "retention": "default TTL 5 minutes after summarization",
    },
    {
        "name": "working",
        "label": "Working Memory",
        "current_mode": "planned",
        "writes_enabled": False,
        "purpose": "Hot current task, conversation, state, and relevant recent entity observations.",
        "retention": "context-budget driven",
    },
    {
        "name": "short_term",
        "label": "Short-Term Memory",
        "current_mode": "planned",
        "writes_enabled": False,
        "purpose": "Recent conclusions that must survive scene and modality changes.",
        "retention": "heat based on importance, repetition, task activity, and entity relevance",
    },
    {
        "name": "long_term_core",
        "label": "Long-Term Core",
        "current_mode": "planned",
        "writes_enabled": False,
        "purpose": "Stable user preferences, project decisions, boundaries, and durable identity relationships.",
        "retention": "compact, editable, auditable",
    },
    {
        "name": "deep_knowledge",
        "label": "Deep Knowledge",
        "current_mode": "planned",
        "writes_enabled": False,
        "purpose": "Large documents, project history, detailed knowledge, and long-horizon experience.",
        "retention": "indexed and summarized; not scanned every ordinary turn",
    },
    {
        "name": "entity_identity",
        "label": "Entity Identity",
        "current_mode": "schema_ready",
        "writes_enabled": False,
        "purpose": "Continuity for people, objects, sounds, windows, places, files, and projects.",
        "retention": "temporary -> candidate -> confirmed -> archived",
    },
    {
        "name": "raw_backup",
        "label": "Raw Backup",
        "current_mode": "schema_ready",
        "writes_enabled": False,
        "purpose": "Original material for review and re-extraction, not the main memory body.",
        "retention": "planned rolling 20 GB / 30 days",
    },
    {
        "name": "audit_review",
        "label": "Audit And Review",
        "current_mode": "schema_ready",
        "writes_enabled": False,
        "purpose": "Trace automatic memory mutations and support undo/review later.",
        "retention": "audit remains after soft-delete",
    },
]

MEMORY_MODALITY_CONTRACTS: list[dict[str, Any]] = [
    {
        "modality": "text",
        "capture_enabled": False,
        "identity_body": "semantic conclusions and optional embeddings",
        "text_is_auxiliary": False,
        "required_feature_refs": ["semantic embedding", "facts", "preferences", "task state", "project decisions"],
        "raw_backup": "runtime/memory_blobs/text/",
        "current_mode": "manual notes only",
    },
    {
        "modality": "vision",
        "capture_enabled": False,
        "identity_body": "non-text visual features",
        "text_is_auxiliary": True,
        "required_feature_refs": [
            "image embedding",
            "perceptual hash",
            "local features",
            "color features",
            "shape features",
            "texture features",
            "object-region features",
        ],
        "raw_backup": "runtime/memory_blobs/vision/",
        "current_mode": "schema only; no capture",
    },
    {
        "modality": "audio",
        "capture_enabled": False,
        "identity_body": "non-text audio features",
        "text_is_auxiliary": True,
        "required_feature_refs": [
            "audio embedding",
            "voiceprint/timbre",
            "pitch/rhythm/spectrum",
            "sound-source cluster",
        ],
        "raw_backup": "runtime/memory_blobs/audio/",
        "current_mode": "schema only; no microphone or TTS route",
    },
    {
        "modality": "event_state_project",
        "capture_enabled": False,
        "identity_body": "event evidence and project/state conclusions",
        "text_is_auxiliary": False,
        "required_feature_refs": ["event ids", "state transitions", "project refs", "permission evidence"],
        "raw_backup": "runtime/events.jsonl and future memory_blobs/misc/",
        "current_mode": "event history and status only",
    },
]

ATTACHMENT_REF_CONTRACT: dict[str, Any] = {
    "schema_version": "attachment_ref.v1",
    "raw_payload_allowed": False,
    "supported_sources": ["manual_file", "paste_image", "screen_frame"],
    "required_fields": [
        "attachment_id",
        "kind",
        "source",
        "raw_ref",
        "mime",
        "sha256",
        "width",
        "height",
        "raw_available",
        "vision_reader_status",
    ],
    "rules": [
        "attachments carry opaque local refs and metadata only",
        "raw image bytes stay out of event history, context snapshots, Debug responses, and provider prompts",
        "manual files, pasted images, and screen frames share the same visual evidence shape",
    ],
}

VISION_READER_STATUS: dict[str, Any] = {
    "schema_version": "vision_reader.status.v1",
    "enabled": False,
    "mode": "metadata_only",
    "capture_enabled": False,
    "screen_observation_enabled": False,
    "auto_extract_manual_images": False,
    "auto_extract_screen_frames": False,
    "queue_pressure_seconds": 30,
    "pressure_mode": False,
    "model_configured": False,
    "embedding_model_configured": False,
    "local_signature_feature_enabled": True,
    "comparable_feature_kind": "average_hash_color_histogram",
    "model_download_enabled": False,
    "supported_statuses": ["pending", "metadata_only", "extracted", "failed"],
    "blocked_reasons": [
        "VLM/OCR extraction is disabled until a provider is configured",
        "no neural image embedding model is configured; local comparable visual signatures are available when raw refs resolve",
        "screen observation is disabled",
        "model downloads require explicit approval",
    ],
}

TEXT_READER_STATUS: dict[str, Any] = {
    "schema_version": "text_reader.status.v1",
    "enabled": True,
    "mode": "local_text_metadata",
    "auto_observe_command_text": True,
    "raw_payload_in_provider_prompt": False,
    "supported_statuses": ["observed", "summarized", "failed"],
    "blocked_reasons": [],
}

AUDIO_READER_STATUS: dict[str, Any] = {
    "schema_version": "audio_reader.status.v1",
    "enabled": False,
    "mode": "metadata_only",
    "capture_enabled": False,
    "microphone_enabled": False,
    "asr_configured": False,
    "speaker_embedding_configured": False,
    "model_download_enabled": False,
    "supported_statuses": ["pending", "metadata_only", "transcribed", "failed"],
    "blocked_reasons": [
        "microphone capture is disabled",
        "no ASR or speaker embedding model is configured",
        "model downloads require explicit approval",
    ],
}
