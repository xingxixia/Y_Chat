from __future__ import annotations

from typing import Any

from .audio_reader import audio_reader_status_payload
from .contracts import contracts_index_payload
from .data_status import data_status_payload
from .local_models import local_models_payload
from .memory import audio_status_payload, memory_status_payload, text_status_payload, vision_status_payload
from .model_provider import provider_readiness_payload, provider_status_payload
from .permissions import permission_status_payload
from .reasoning import reasoning_status_payload
from .screen_observation import screen_observation_status_payload
from .vision_reader import vision_reader_status_payload
from .vision_extractor import vision_extraction_status_payload
from .shared.contracts import SchemaVersion


def backend_status_payload() -> dict[str, Any]:
    provider = provider_status_payload()
    readiness = provider_readiness_payload()
    reasoning = reasoning_status_payload()
    memory = memory_status_payload()
    vision = vision_status_payload()
    extraction = vision_extraction_status_payload()
    data = data_status_payload()
    permissions = permission_status_payload()
    local_models = local_models_payload()
    vision_reader = vision_reader_status_payload()
    audio_reader = audio_reader_status_payload()
    screen = screen_observation_status_payload(active=False)
    return {
        "schema_version": SchemaVersion.BACKEND_STATUS,
        "app": "y_chat",
        "status": "ok",
        "contracts": contracts_index_payload(),
        "modules": {
            "provider": {
                "enabled": provider["enabled"],
                "real_model_calls": readiness["will_call_model_on_next_reasoning_run"],
                "readiness": readiness,
            },
            "reasoning": {
                "enabled": reasoning["enabled"],
                "provider_mode": reasoning["provider_mode"],
                "real_model_calls": reasoning["real_model_calls"],
                "runs_total": reasoning["runs_total"],
            },
            "memory": {
                "manual_enabled": memory["manual_enabled"],
                "automatic_writes_enabled": memory["automatic_writes_enabled"],
                "observations_count": memory["observations_count"],
                "visual_evidence_count": memory["visual_evidence_count"],
                "text_evidence_count": memory["text_evidence_count"],
                "audio_evidence_count": memory["audio_evidence_count"],
                "consolidation_buffer_count": memory["consolidation_buffer_count"],
            },
            "vision": {
                "metadata_status": vision,
                "extraction": extraction,
                "reader": vision_reader,
            },
            "text": text_status_payload(),
            "audio": {
                **audio_status_payload(),
                "reader": audio_reader,
            },
            "local_models": local_models,
            "screen_observation": screen,
            "permissions": {
                "enabled": permissions["enabled"],
                "disabled": permissions["disabled"],
            },
            "data": {
                "runtime_dir": data["runtime_dir"],
                "sqlite": data["runtime_files"]["sqlite"],
                "config": data["runtime_files"]["config"],
                "events": data["runtime_files"]["events"],
            },
        },
        "raw_payload_returned": False,
        "api_key_returned": False,
    }
