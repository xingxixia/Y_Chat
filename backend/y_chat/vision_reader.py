from __future__ import annotations

from typing import Any

from .services.model_cache import MODEL_CACHE_DIR, blocked_reasons, model_ready, model_state
from .services.local_vision_vlm import local_vlm_ready
from .vision_extractor import vision_extraction_status_payload
from .services.vision_ocr import local_ocr_available


VISION_LOCAL_MODEL_SPECS: dict[str, dict[str, Any]] = {
    "vision_embedding": {
        "model_id": "openai/clip-vit-base-patch32",
        "local_dir": "openai__clip-vit-base-patch32",
        "purpose": "local image embedding / visual feature refs",
        "required_files": ["config.json", "preprocessor_config.json", "pytorch_model.bin"],
        "required_packages": ["transformers", "torch", "PIL"],
        "modality": "vision",
        "text_auxiliary_only": True,
    },
    "vision_vlm": {
        "model_id": "HuggingFaceTB/SmolVLM-256M-Instruct",
        "local_dir": "HuggingFaceTB__SmolVLM-256M-Instruct",
        "purpose": "local VisionReader recognition / image understanding (small VLM first-run adapter)",
        "required_files": [
            "config.json",
            "processor_config.json",
            "tokenizer.json",
            "model.safetensors",
        ],
        "required_packages": ["transformers", "torch", "PIL"],
        "modality": "vision",
        "text_auxiliary_only": True,
    },
    "vision_vlm_qwen": {
        "model_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "local_dir": "Qwen__Qwen2.5-VL-3B-Instruct",
        "purpose": "larger local VisionReader recognition upgrade candidate",
        "required_files": [
            "config.json",
            "generation_config.json",
            "merges.txt",
            "model.safetensors.index.json",
            "preprocessor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
            "model-00001-of-00002.safetensors",
            "model-00002-of-00002.safetensors",
        ],
        "required_packages": ["transformers", "torch", "PIL"],
        "modality": "vision",
        "text_auxiliary_only": True,
    },
}


def vision_reader_status_payload() -> dict[str, Any]:
    models = {name: model_state(name, spec) for name, spec in VISION_LOCAL_MODEL_SPECS.items()}
    embedding_ready = model_ready(models["vision_embedding"])
    qwen_ready = model_ready(models["vision_vlm_qwen"])
    local_vlm_is_ready = local_vlm_ready()
    extraction = vision_extraction_status_payload()
    api_recognition_ready = bool(extraction["enabled"])
    ocr_available = local_ocr_available()
    return {
        "schema_version": "vision_reader.adapters.v1",
        "modality": "vision",
        "role": "independent image recognition / understanding / feature extraction",
        "adapter_boundary": "independent_vision_reader",
        "api_swap_ready": True,
        "independent_from": ["text_reasoning_provider", "audio_reader"],
        "deepseek_role": "text_reasoning_api_only",
        "deepseek_receives_raw_images": False,
        "scope": ["image_recognition", "image_understanding", "feature_extraction", "screen_frame_understanding"],
        "text_auxiliary_only": True,
        "image_generation_supported": False,
        "image_generation_configured": False,
        "excluded_capabilities": ["image_generation", "image_editing"],
        "cache_dir": str(MODEL_CACHE_DIR),
        "active_adapters": {
            "embedding": "local_clip" if embedding_ready else "not_ready",
            "recognition": _active_recognition_adapter(
                local_vlm_ready=local_vlm_is_ready,
                api_recognition_ready=api_recognition_ready,
                local_ocr_available=ocr_available,
            ),
            "generation": "unsupported",
        },
        "action_endpoints": {
            "embedding": "/vision/reader/embed",
            "recognition": "/vision/reader/recognize",
            "compatibility_extract": "/vision/extract",
        },
        "ready": {
            "embedding": embedding_ready,
            "local_recognition": local_vlm_is_ready,
            "local_qwen_recognition": qwen_ready,
            "api_recognition": api_recognition_ready,
            "any_recognition": local_vlm_is_ready or api_recognition_ready or ocr_available,
        },
        "adapters": {
            "local_clip_embedding": {
                "adapter_type": "local_model",
                "capability": "image_embedding",
                "state": models["vision_embedding"],
            },
            "local_vlm_recognition": {
                "adapter_type": "local_model",
                "capability": "image_recognition",
                "state": models["vision_vlm"],
                "upgrade_candidate": "Qwen/Qwen2.5-VL-3B-Instruct",
            },
            "local_qwen_recognition": {
                "adapter_type": "local_model",
                "capability": "image_recognition_upgrade_candidate",
                "state": models["vision_vlm_qwen"],
                "ready": qwen_ready,
                "active": False,
                "activation_note": (
                    "downloaded and runtime-smoked candidate; keep SmolVLM active until provider selection, "
                    "caching, and low-frequency gating are wired"
                ),
            },
            "api_vision_recognition": {
                "adapter_type": "api",
                "capability": "image_recognition",
                "configured": api_recognition_ready,
                "provider": extraction["provider"],
                "model": extraction["model"],
                "call_route": extraction["call_route"],
                "raw_payload_returned": False,
                "api_key_returned": False,
            },
            "local_ocr_auxiliary": {
                "adapter_type": "local_library",
                "capability": "visible_text_auxiliary",
                "available": ocr_available,
                "identity_body": False,
                "text_auxiliary_only": True,
            },
        },
        "blocked_reasons": [
            *blocked_reasons(models),
            *extraction["blocked_reasons"],
        ],
        "download_commands": [
            "conda run -n y_chat python scripts\\download_local_models.py vision_embedding",
            "conda run -n y_chat python scripts\\download_local_models.py vision_vlm",
            "conda run -n y_chat python scripts\\download_local_models.py vision_vlm_qwen",
        ],
        "raw_payload_returned": False,
        "api_key_returned": False,
    }


def _active_recognition_adapter(
    *,
    local_vlm_ready: bool,
    api_recognition_ready: bool,
    local_ocr_available: bool,
) -> str:
    if local_vlm_ready:
        return "local_vlm"
    if api_recognition_ready:
        return "api_vision"
    if local_ocr_available:
        return "local_ocr_auxiliary_only"
    return "not_ready"
