from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .provider_client import ProviderCallError, extract_message_content, post_chat_completion
from .services.vision_config import (
    save_vision_config_candidate,
    validate_vision_config_candidate,
    vision_config,
    vision_config_payload as _vision_config_payload,
    vision_extraction_status_payload as _vision_extraction_status_payload,
)
from .services.vision_evidence import latest_extractable_visual_evidence, visual_evidence_by_id
from .services.vision_extraction_store import record_extraction_feature
from .services.vision_files import image_data_url, runtime_ref_to_path
from .services.vision_ocr import extract_with_local_ocr, local_ocr_available
from .services.local_vision_vlm import local_vlm_ready, recognize_visual_evidence


LOCAL_OCR_PROVIDERS = {"local_ocr", "local_rapidocr", "rapidocr", "ocr"}
LOCAL_VLM_PROVIDERS = {"local_vlm", "local_smolvlm", "smolvlm", "vlm"}


def _runtime_ref_to_path(raw_ref: str) -> Path:
    return runtime_ref_to_path(raw_ref)


def _image_data_url(path: Path, mime: str) -> str:
    return image_data_url(path, mime)


def _vision_config() -> dict[str, Any]:
    return vision_config()


def _local_ocr_available() -> bool:
    return local_ocr_available()


def _local_vlm_ready() -> bool:
    return local_vlm_ready()


def _extract_with_local_ocr(image_path: Path) -> dict[str, Any]:
    return extract_with_local_ocr(image_path)


def vision_config_payload() -> dict[str, Any]:
    return _vision_config_payload(local_ocr_available=_local_ocr_available())


def vision_extraction_status_payload() -> dict[str, Any]:
    return _vision_extraction_status_payload(
        config=_vision_config(),
        local_ocr_available=_local_ocr_available(),
    )


def _latest_visual_evidence() -> dict[str, Any] | None:
    return latest_extractable_visual_evidence()


def _visual_evidence_by_id(evidence_id: str) -> dict[str, Any] | None:
    return visual_evidence_by_id(evidence_id)


def _record_extraction_feature(evidence: dict[str, Any], extraction: dict[str, Any]) -> dict[str, Any]:
    return record_extraction_feature(evidence, extraction)


def extract_visual_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    secondary_confirmed = bool(payload.get("secondary_confirmed", False))
    if not secondary_confirmed:
        return {"ok": False, "called": False, "message": "secondary confirmation is required for vision extraction"}

    evidence_id = str(payload.get("evidence_id") or "").strip()
    evidence = _visual_evidence_by_id(evidence_id) if evidence_id else _latest_visual_evidence()
    if not evidence:
        return {"ok": False, "called": False, "message": "no visual evidence is available"}

    try:
        image_path = _runtime_ref_to_path(str(evidence["raw_ref"]))
    except ValueError as exc:
        return {"ok": False, "called": False, "message": str(exc)}
    if not image_path.exists():
        return {"ok": False, "called": False, "message": "raw image file is missing"}

    status = vision_extraction_status_payload()
    config = _vision_config()
    requested_provider = str(payload.get("provider") or "").strip().lower()
    if requested_provider in LOCAL_VLM_PROVIDERS:
        return recognize_visual_evidence(payload)

    use_local = requested_provider in LOCAL_OCR_PROVIDERS or not status["enabled"]
    if use_local:
        return _extract_with_local_reader(evidence, image_path, status)

    return _extract_with_provider(evidence, image_path, config, payload)


def _extract_with_local_reader(
    evidence: dict[str, Any],
    image_path: Path,
    status: dict[str, Any],
) -> dict[str, Any]:
    if not _local_ocr_available():
        return {
            "ok": False,
            "called": False,
            "blocked_reasons": [*status["blocked_reasons"], "local OCR dependency is not installed"],
            "api_key_returned": False,
            "raw_payload_returned": False,
        }
    try:
        extraction = _extract_with_local_ocr(image_path)
        refs = _record_extraction_feature(evidence, extraction)
        return {
            "ok": True,
            "called": True,
            "evidence_id": evidence["evidence_id"],
            "provider": "local_rapidocr",
            "model": "rapidocr_onnxruntime",
            "elapsed_ms": None,
            "extraction": {
                "description": extraction["description"],
                "visible_text": extraction["visible_text"],
                "objects": extraction["objects"],
                "uncertainty": extraction["uncertainty"],
            },
            **refs,
            "raw_payload_returned": False,
            "api_key_returned": False,
        }
    except Exception as exc:
        return {
            "ok": False,
            "called": True,
            "evidence_id": evidence["evidence_id"],
            "provider": "local_rapidocr",
            "model": "rapidocr_onnxruntime",
            "message": str(exc),
            "api_key_returned": False,
            "raw_payload_returned": False,
        }


def _extract_with_provider(
    evidence: dict[str, Any],
    image_path: Path,
    config: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or "").strip() or (
        "Describe the screen image for a multimodal assistant. Return JSON with keys: "
        "description, visible_text, objects, uncertainty."
    )
    messages = [
        {"role": "system", "content": "Return only a JSON object. No markdown."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": _image_data_url(image_path, str(evidence.get("mime") or ""))}},
            ],
        },
    ]
    try:
        response = post_chat_completion({**config, "cadence_scope": "vision_provider"}, messages, json_mode=True)
        content = extract_message_content(response["payload"])
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("vision provider returned non-object JSON")
        extraction = {
            **parsed,
            "provider": config["provider"],
            "model": config["model"],
            "raw_image_sent_to_configured_vision_provider": True,
            "raw_image_processed_locally": False,
            "raw_image_sent_to_deepseek": False,
            "image_generation_supported": False,
        }
        refs = _record_extraction_feature(evidence, extraction)
        return {
            "ok": True,
            "called": True,
            "evidence_id": evidence["evidence_id"],
            "provider": config["provider"],
            "model": config["model"],
            "elapsed_ms": response["elapsed_ms"],
            "extraction": parsed,
            **refs,
            "raw_payload_returned": False,
            "api_key_returned": False,
        }
    except (ProviderCallError, json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "called": True,
            "evidence_id": evidence["evidence_id"],
            "provider": config["provider"],
            "model": config["model"],
            "message": str(exc),
            "api_key_returned": False,
            "raw_payload_returned": False,
        }
