from __future__ import annotations

from typing import Any

from .services.model_cache import MODEL_CACHE_DIR, blocked_reasons, model_ready, model_state


AUDIO_LOCAL_MODEL_SPECS: dict[str, dict[str, Any]] = {
    "audio_asr": {
        "model_id": "Systran/faster-whisper-base",
        "local_dir": "Systran__faster-whisper-base",
        "purpose": "local ASR auxiliary transcript for audio evidence",
        "required_files": ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"],
        "required_packages": ["faster_whisper", "ctranslate2", "soundfile"],
        "modality": "audio",
        "text_auxiliary_only": True,
    },
}


def audio_reader_status_payload() -> dict[str, Any]:
    models = {name: model_state(name, spec) for name, spec in AUDIO_LOCAL_MODEL_SPECS.items()}
    asr_ready = model_ready(models["audio_asr"])
    return {
        "schema_version": "audio_reader.adapters.v1",
        "modality": "audio",
        "role": "independent speech/audio feature processing",
        "adapter_boundary": "independent_audio_reader",
        "api_swap_ready": True,
        "independent_from": ["text_reasoning_provider", "vision_reader"],
        "deepseek_role": "text_reasoning_api_only",
        "deepseek_receives_raw_audio": False,
        "scope": ["speech_to_text_auxiliary", "audio_feature_extraction"],
        "text_auxiliary_only": True,
        "cache_dir": str(MODEL_CACHE_DIR),
        "active_adapters": {
            "asr": "local_faster_whisper" if asr_ready else "not_ready",
            "speaker_features": "not_configured",
            "tts": "unsupported",
        },
        "ready": {
            "asr": asr_ready,
            "speaker_features": False,
            "api_asr": False,
        },
        "adapters": {
            "local_faster_whisper_asr": {
                "adapter_type": "local_model",
                "capability": "speech_to_text_auxiliary",
                "state": models["audio_asr"],
            },
            "api_audio_asr_future": {
                "adapter_type": "api",
                "capability": "speech_to_text_auxiliary",
                "configured": False,
                "swap_target": True,
                "raw_payload_returned": False,
                "api_key_returned": False,
            },
            "speaker_embedding_future": {
                "adapter_type": "local_or_api",
                "capability": "speaker_or_timbre_feature",
                "configured": False,
                "text_auxiliary_only": False,
            },
        },
        "blocked_reasons": blocked_reasons(models),
        "download_commands": [
            "conda run -n y_chat python scripts\\download_local_models.py audio_asr",
        ],
        "raw_payload_returned": False,
        "api_key_returned": False,
    }
