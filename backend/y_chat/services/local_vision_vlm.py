from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from .model_cache import MODEL_CACHE_DIR
from .runtime_refs import runtime_ref_to_path
from .vision_evidence import latest_extractable_visual_evidence, visual_evidence_by_id
from .vision_extraction_store import record_extraction_feature


MODEL_ID = "HuggingFaceTB/SmolVLM-256M-Instruct"
MODEL_DIR = MODEL_CACHE_DIR / "HuggingFaceTB__SmolVLM-256M-Instruct"
DEFAULT_PROMPT = (
    "Describe this image for a multimodal assistant in one concise paragraph. "
    "Mention the main subjects, colors, layout, actions, and any readable text. "
    "Do not describe image generation."
)

_MODEL_CLASS: Any | None = None
_PROCESSOR_CLASS: Any | None = None
_MODEL: Any | None = None
_PROCESSOR: Any | None = None
_TORCH: Any | None = None


def local_vlm_ready() -> bool:
    required = [
        "config.json",
        "processor_config.json",
        "tokenizer.json",
        "model.safetensors",
    ]
    return MODEL_DIR.exists() and all((MODEL_DIR / filename).exists() for filename in required)


def recognize_visual_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    secondary_confirmed = bool(payload.get("secondary_confirmed", False))
    if not secondary_confirmed:
        return {"ok": False, "called": False, "message": "secondary confirmation is required for local vision recognition"}
    if not local_vlm_ready():
        return {
            "ok": False,
            "called": False,
            "not_ready": True,
            "provider": "local_smolvlm",
            "model": MODEL_ID,
            "message": "local VLM recognition model is not downloaded",
            "model_path": str(MODEL_DIR),
            "download_command": "conda run -n y_chat python scripts\\download_local_models.py vision_vlm",
            "image_generation_supported": False,
            "raw_payload_returned": False,
            "api_key_returned": False,
        }

    evidence_id = str(payload.get("evidence_id") or "").strip()
    evidence = visual_evidence_by_id(evidence_id) if evidence_id else latest_extractable_visual_evidence()
    if not evidence:
        return {"ok": False, "called": False, "message": "no extractable runtime:// visual evidence is available"}
    image_path = runtime_ref_to_path(str(evidence["raw_ref"]))
    if not image_path.exists():
        return {"ok": False, "called": False, "message": "raw image file is missing"}

    prompt = str(payload.get("prompt") or "").strip() or DEFAULT_PROMPT
    extraction = _recognize_image(image_path, prompt)
    refs = record_extraction_feature(evidence, extraction)
    return {
        "ok": True,
        "called": True,
        "evidence_id": evidence["evidence_id"],
        "provider": "local_smolvlm",
        "model": MODEL_ID,
        "extraction": {
            "description": extraction["description"],
            "visible_text": extraction["visible_text"],
            "objects": extraction["objects"],
            "uncertainty": extraction["uncertainty"],
        },
        **refs,
        "image_generation_supported": False,
        "raw_payload_returned": False,
        "api_key_returned": False,
    }


def _recognize_image(image_path: Path, prompt: str) -> dict[str, Any]:
    torch = _torch()
    processor, model = _vlm()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    with Image.open(image_path) as image:
        inputs = processor(text=[text], images=[image.convert("RGB")], return_tensors="pt")
    device = getattr(model, "device", None)
    if device is not None:
        inputs = {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    input_length = inputs["input_ids"].shape[1]
    generated = generated_ids[:, input_length:]
    content = processor.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    parsed = _parse_recognition_json(content)
    return {
        "description": str(parsed.get("description") or content).strip(),
        "visible_text": _normalize_string_list(parsed.get("visible_text", [])),
        "objects": _normalize_objects(parsed.get("objects", [])),
        "uncertainty": str(parsed.get("uncertainty") or "medium"),
        "provider": "local_smolvlm",
        "model": MODEL_ID,
        "raw_image_sent_to_configured_vision_provider": False,
        "raw_image_processed_locally": True,
        "raw_image_sent_to_deepseek": False,
        "image_generation_supported": False,
    }


def _vlm() -> tuple[Any, Any]:
    global _MODEL, _MODEL_CLASS, _PROCESSOR, _PROCESSOR_CLASS
    if _MODEL_CLASS is None or _PROCESSOR_CLASS is None:
        from transformers import AutoModelForImageTextToText, AutoProcessor

        _MODEL_CLASS = AutoModelForImageTextToText
        _PROCESSOR_CLASS = AutoProcessor
    if _PROCESSOR is None:
        _PROCESSOR = _PROCESSOR_CLASS.from_pretrained(str(MODEL_DIR), local_files_only=True)
    if _MODEL is None:
        torch = _torch()
        kwargs: dict[str, Any] = {"local_files_only": True, "device_map": "auto"}
        if torch.cuda.is_available():
            kwargs["torch_dtype"] = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            kwargs["torch_dtype"] = torch.float32
            kwargs["device_map"] = "cpu"
        _MODEL = _MODEL_CLASS.from_pretrained(str(MODEL_DIR), **kwargs)
        _MODEL.eval()
    return _PROCESSOR, _MODEL


def _torch() -> Any:
    global _TORCH
    if _TORCH is None:
        import torch

        _TORCH = torch
    return _TORCH


def _parse_recognition_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {"description": text, "visible_text": [], "objects": [], "uncertainty": "medium"}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"description": text, "visible_text": [], "objects": [], "uncertainty": "medium"}
    return parsed if isinstance(parsed, dict) else {"description": text, "visible_text": [], "objects": [], "uncertainty": "medium"}


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item.get("text") if isinstance(item, dict) else item).strip()
        if text:
            result.append(text)
    return result


def _normalize_objects(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:50]
