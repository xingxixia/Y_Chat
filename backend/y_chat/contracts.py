from __future__ import annotations

from typing import Any

from .shared.contracts import SchemaVersion


def contracts_index_payload() -> dict[str, Any]:
    return {
        "schema_version": SchemaVersion.CONTRACTS_INDEX,
        "read_only": True,
        "mutation_enabled": False,
        "entries": [
            {
                "name": "reasoning output",
                "endpoint": "/reasoning/contract",
                "status": "active",
                "risk_scope": "model output validation, replies, actions, memory candidates",
            },
            {
                "name": "memory",
                "endpoint": "/memory/contract",
                "status": "active",
                "risk_scope": "unified multimodal memory, automatic writes disabled",
            },
            {
                "name": "vision status",
                "endpoint": "/vision/status",
                "status": "active",
                "risk_scope": "VisionReader status, local OCR fallback, optional gated OpenAI-compatible VLM extraction",
            },
            {
                "name": "vision reader adapters",
                "endpoint": "/vision/reader/status",
                "status": "active",
                "risk_scope": "independent image recognition and feature adapters; image generation unsupported",
            },
            {
                "name": "text status",
                "endpoint": "/text/status",
                "status": "active",
                "risk_scope": "local text evidence observation and refs-only memory writes",
            },
            {
                "name": "audio status",
                "endpoint": "/audio/status",
                "status": "active",
                "risk_scope": "metadata-only audio evidence status, microphone and ASR disabled",
            },
            {
                "name": "audio reader adapters",
                "endpoint": "/audio/reader/status",
                "status": "active",
                "risk_scope": "independent ASR and audio feature adapters, swappable separately from vision",
            },
            {
                "name": "screen observation",
                "endpoint": "/screen/observation/status",
                "status": "gated",
                "risk_scope": "primary display sampling, local screenshot refs, visual evidence ingestion, secondary confirmation required",
            },
            {
                "name": "project reader",
                "endpoint": "/project-reader/contract",
                "status": "active",
                "risk_scope": "project roots, path safety, content reads disabled",
            },
            {
                "name": "permissions",
                "endpoint": "/permissions/contract",
                "status": "active",
                "risk_scope": "capability gates, secondary confirmation, audit requirements",
            },
            {
                "name": "events",
                "endpoint": "/events/contract",
                "status": "active",
                "risk_scope": "local internal event ingress, external adapters blocked",
            },
            {
                "name": "state manager",
                "endpoint": "/state/contract",
                "status": "active",
                "risk_scope": "semantic pet state, no capture or simulation side effects",
            },
        ],
        "status_endpoints": [
            "/health",
            "/backend/status",
            "/data/status",
            "/model/provider/status",
            "/model/provider/config",
            "/model/provider/readiness",
            "/permissions/status",
            "/logs/status",
            "/reasoning/status",
            "/memory/status",
            "/vision/status",
            "/vision/reader/status",
            "/vision/reader/recognize",
            "/vision/config",
            "/vision/extraction/status",
            "/text/status",
            "/audio/status",
            "/audio/reader/status",
            "/screen/observation/status",
            "/project-reader/status",
        ],
        "blocked_until_explicit_user_selection": [
            "API key saving",
            "real model calls",
            "project file content reads",
            "physical camera capture",
            "microphone listening",
            "voice output",
            "external/LAN/OSC adapters",
            "file writes outside accepted memory/debug behavior",
            "process execution",
            "desktop input control",
            "VR output",
        ],
    }
