from __future__ import annotations

from typing import Any


TEXT_PAYLOAD_KEYS = {"text", "message", "prompt", "command", "transcript", "ocr_text"}
VISION_PAYLOAD_KEYS = {
    "image",
    "image_ref",
    "image_refs",
    "screenshot",
    "screenshot_ref",
    "frame_ref",
    "crop_ref",
    "ocr",
    "visual_features",
}
AUDIO_PAYLOAD_KEYS = {
    "audio",
    "audio_ref",
    "audio_refs",
    "voice",
    "voice_ref",
    "waveform",
    "speaker_id",
    "audio_features",
}
STATE_PAYLOAD_KEYS = {"state", "pet_state", "emotion", "animation"}
PROJECT_PAYLOAD_KEYS = {"path", "file", "files", "root", "project", "workspace"}
PRIMARY_MODALITIES = {
    "text",
    "vision",
    "audio",
    "state",
    "memory",
    "project",
    "interaction",
    "action",
    "debug",
    "system",
    "error",
    "external",
    "vr",
}


def _add_modality(modalities: list[str], modality: str) -> None:
    if modality not in modalities:
        modalities.append(modality)


def infer_event_modalities(event_type: str, payload: dict[str, Any] | None) -> list[str]:
    event_type = event_type.lower()
    payload = payload if isinstance(payload, dict) else {}
    keys = {str(key).lower() for key in payload.keys()}
    modalities: list[str] = []

    if event_type.startswith(("user.command.", "chat.", "text.")):
        _add_modality(modalities, "text")
    if event_type.startswith(("screen.", "vision.", "visual.", "camera.", "ocr.")):
        _add_modality(modalities, "vision")
    if event_type.startswith(("voice.", "audio.", "speech.", "microphone.")):
        _add_modality(modalities, "audio")
    if event_type.startswith("pet.state."):
        _add_modality(modalities, "state")
    if event_type.startswith("pet.model."):
        _add_modality(modalities, "interaction")
    if event_type.startswith("memory."):
        _add_modality(modalities, "memory")
    if event_type.startswith("project."):
        _add_modality(modalities, "project")
    if event_type.startswith("action."):
        _add_modality(modalities, "action")
    if event_type.startswith("debug."):
        _add_modality(modalities, "debug")
    if event_type.startswith("system."):
        _add_modality(modalities, "system")
    if event_type.startswith("error."):
        _add_modality(modalities, "error")
    if event_type.startswith("external."):
        _add_modality(modalities, "external")
    if event_type.startswith("vr."):
        _add_modality(modalities, "vr")

    if keys & TEXT_PAYLOAD_KEYS:
        _add_modality(modalities, "text")
    if keys & VISION_PAYLOAD_KEYS:
        _add_modality(modalities, "vision")
    if keys & AUDIO_PAYLOAD_KEYS:
        _add_modality(modalities, "audio")
    if keys & STATE_PAYLOAD_KEYS:
        _add_modality(modalities, "state")
    if keys & PROJECT_PAYLOAD_KEYS:
        _add_modality(modalities, "project")

    return modalities or ["event"]


def primary_event_modality(modalities: list[str]) -> str:
    for modality in modalities:
        if modality in PRIMARY_MODALITIES:
            return modality
    return "event"
