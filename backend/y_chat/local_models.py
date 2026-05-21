from __future__ import annotations

from typing import Any

from .audio_reader import AUDIO_LOCAL_MODEL_SPECS, audio_reader_status_payload
from .services.model_cache import MODEL_CACHE_DIR, blocked_reasons, model_state
from .vision_reader import VISION_LOCAL_MODEL_SPECS, vision_reader_status_payload


LOCAL_MODEL_SPECS: dict[str, dict[str, Any]] = {
    **VISION_LOCAL_MODEL_SPECS,
    **AUDIO_LOCAL_MODEL_SPECS,
}


def local_models_payload() -> dict[str, Any]:
    models = {name: model_state(name, spec) for name, spec in LOCAL_MODEL_SPECS.items()}
    vision_embedding_ready = models["vision_embedding"]["downloaded"] and models["vision_embedding"]["packages_ready"]
    vision_vlm_ready = models["vision_vlm"]["downloaded"] and models["vision_vlm"]["packages_ready"]
    vision_vlm_qwen_ready = models["vision_vlm_qwen"]["downloaded"] and models["vision_vlm_qwen"]["packages_ready"]
    audio_asr_ready = models["audio_asr"]["downloaded"] and models["audio_asr"]["packages_ready"]
    vision_reader = vision_reader_status_payload()
    audio_reader = audio_reader_status_payload()
    return {
        "schema_version": "local_models.status.v1",
        "cache_dir": str(MODEL_CACHE_DIR),
        "download_enabled": False,
        "download_requires_explicit_user_action": True,
        "deepseek_role": "text_reasoning_api_only",
        "vision_role": "independent image recognition / local VLM / embeddings; OCR is auxiliary text only; current first-run VLM is small and swappable",
        "audio_role": "local ASR / audio features; transcript text is auxiliary only",
        "adapter_boundary": "aggregate_status_only",
        "independent_readers": {
            "vision": "/vision/reader/status",
            "audio": "/audio/reader/status",
        },
        "vision_reader": vision_reader,
        "audio_reader": audio_reader,
        "image_generation_supported": False,
        "image_generation_configured": False,
        "models": models,
        "ready": {
            "vision_embedding": vision_embedding_ready,
            "vision_vlm": vision_vlm_ready,
            "vision_vlm_qwen": vision_vlm_qwen_ready,
            "audio_asr": audio_asr_ready,
        },
        "blocked_reasons": blocked_reasons(models),
        "download_commands": [
            "conda run -n y_chat python scripts\\download_local_models.py vision_embedding",
            "conda run -n y_chat python scripts\\download_local_models.py audio_asr",
            "conda run -n y_chat python scripts\\download_local_models.py vision_vlm",
            "conda run -n y_chat python scripts\\download_local_models.py vision_vlm_qwen",
        ],
        "raw_payload_returned": False,
        "api_key_returned": False,
    }
