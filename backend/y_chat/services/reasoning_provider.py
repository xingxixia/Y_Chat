from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from ..config import load_config
from ..provider_client import extract_message_content, post_chat_completion
from .redaction import redact_payload


PROVIDER_NAME = "deterministic_fallback"
REAL_PROVIDER_NAMES = {"deepseek", "openai_compatible"}
CJK_RE = r"[\u3400-\u9fff]"
OCR_FEATURE_PROVIDERS = {"local_rapidocr", "local_ocr", "rapidocr", "ocr"}
LOW_VALUE_VISUAL_DESCRIPTIONS = (
    "local image recognition",
    "not image generation",
)


def active_model_call_config() -> dict[str, Any]:
    config = load_config()
    llm_config = config.get("llm", {})
    permissions = config.get("permissions", {})
    if not isinstance(llm_config, dict):
        llm_config = {}
    if not isinstance(permissions, dict):
        permissions = {}
    active_provider = str(llm_config.get("active_provider", "")).strip()
    providers = llm_config.get("providers", {})
    provider_config = providers.get(active_provider, {}) if isinstance(providers, dict) else {}
    if not isinstance(provider_config, dict):
        provider_config = {}
    api_key = str(provider_config.get("api_key", "")).strip()
    base_url = str(provider_config.get("base_url", "")).strip().rstrip("/")
    model = str(provider_config.get("model", "")).strip()
    enabled = (
        bool(llm_config.get("enabled", False))
        and bool(permissions.get("model.call", False))
        and active_provider in REAL_PROVIDER_NAMES
        and bool(api_key)
        and bool(base_url)
        and bool(model)
    )
    return {
        "enabled": enabled,
        "provider": active_provider,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "temperature": provider_config.get("temperature", 0.7),
        "stream": bool(provider_config.get("stream", False)),
        "timeout_seconds": provider_config.get("timeout_seconds", 45),
        "max_tokens": provider_config.get("max_tokens", 1200),
        "thinking_type": provider_config.get("thinking_type", "disabled"),
        "reasoning_effort": provider_config.get("reasoning_effort", ""),
        "cadence_scope": "reasoning_foreground",
    }


def strip_secrets_from_request(request: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(dict(request))
    source_event = snapshot.get("source_event")
    if isinstance(source_event, dict):
        payload = source_event.get("payload")
        if isinstance(payload, dict):
            redacted_payload, _ = redact_payload(payload)
            source_event["payload"] = redacted_payload
    return snapshot


def multimodal_context_summary(request: dict[str, Any]) -> dict[str, Any]:
    context = request.get("context", {})
    visual_context = context.get("visual_context", {}) if isinstance(context, dict) else {}
    audio_context = context.get("audio_context", {}) if isinstance(context, dict) else {}
    current_event_refs = context.get("current_event_refs", {}) if isinstance(context, dict) else {}
    visual_evidence = (
        visual_context.get("recent_visual_evidence", []) if isinstance(visual_context, dict) else []
    )
    recent_ocr_text = visual_context.get("recent_ocr_text", []) if isinstance(visual_context, dict) else []
    audio_evidence = audio_context.get("recent_audio_evidence", []) if isinstance(audio_context, dict) else []
    current_vision_refs = current_event_refs.get("vision", []) if isinstance(current_event_refs, dict) else []
    current_audio_refs = current_event_refs.get("audio", []) if isinstance(current_event_refs, dict) else []
    current_attachments = current_event_refs.get("attachments", []) if isinstance(current_event_refs, dict) else []

    visual_description_count = 0
    fresh_visual_description_count = 0
    visual_embedding_count = 0
    fresh_visual_embedding_count = 0
    ocr_feature_description_count = 0
    if isinstance(visual_evidence, list):
        for evidence in visual_evidence:
            features = evidence.get("features", []) if isinstance(evidence, dict) else []
            fresh_evidence = bool(evidence.get("fresh_for_current_screen")) if isinstance(evidence, dict) else False
            if not isinstance(features, list):
                continue
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                kind = str(feature.get("feature_kind") or "")
                provider = str(feature.get("provider") or "").lower()
                model = str(feature.get("model") or "").lower()
                is_ocr_feature = provider in OCR_FEATURE_PROVIDERS or "rapidocr" in model
                description = str(feature.get("description") or "").strip()
                low_value_description = any(marker in description.lower() for marker in LOW_VALUE_VISUAL_DESCRIPTIONS)
                if kind == "vlm_extracted_text" and description and not low_value_description:
                    if is_ocr_feature:
                        ocr_feature_description_count += 1
                    else:
                        visual_description_count += 1
                        if fresh_evidence:
                            fresh_visual_description_count += 1
                if kind == "image_embedding":
                    visual_embedding_count += 1
                    if fresh_evidence:
                        fresh_visual_embedding_count += 1

    audio_transcript_metadata_count = 0
    if isinstance(audio_evidence, list):
        for evidence in audio_evidence:
            transcript = evidence.get("transcript") if isinstance(evidence, dict) else None
            if isinstance(transcript, dict):
                audio_transcript_metadata_count += 1

    return {
        "schema_version": "reasoning_multimodal_context_summary.v1",
        "recent_visual_evidence_count": len(visual_evidence) if isinstance(visual_evidence, list) else 0,
        "fresh_visual_evidence_count": int(visual_context.get("fresh_visual_evidence_count") or 0)
        if isinstance(visual_context, dict)
        else 0,
        "stale_visual_evidence_count": int(visual_context.get("stale_visual_evidence_count") or 0)
        if isinstance(visual_context, dict)
        else 0,
        "latest_visual_age_seconds": visual_context.get("latest_visual_age_seconds")
        if isinstance(visual_context, dict)
        else None,
        "current_screen_evidence_available": bool(visual_context.get("current_screen_evidence_available"))
        if isinstance(visual_context, dict)
        else False,
        "recent_visual_description_count": visual_description_count,
        "fresh_visual_description_count": fresh_visual_description_count,
        "recent_visual_embedding_count": visual_embedding_count,
        "fresh_visual_embedding_count": fresh_visual_embedding_count,
        "recent_ocr_feature_description_count": ocr_feature_description_count,
        "recent_ocr_text_count": len(recent_ocr_text) if isinstance(recent_ocr_text, list) else 0,
        "fresh_ocr_text_count": int(visual_context.get("fresh_ocr_text_count") or 0)
        if isinstance(visual_context, dict)
        else 0,
        "stale_ocr_text_count": int(visual_context.get("stale_ocr_text_count") or 0)
        if isinstance(visual_context, dict)
        else 0,
        "recent_audio_evidence_count": len(audio_evidence) if isinstance(audio_evidence, list) else 0,
        "recent_audio_transcript_metadata_count": audio_transcript_metadata_count,
        "current_event_ref_counts": {
            "vision": len(current_vision_refs) if isinstance(current_vision_refs, list) else 0,
            "audio": len(current_audio_refs) if isinstance(current_audio_refs, list) else 0,
            "attachments": len(current_attachments) if isinstance(current_attachments, list) else 0,
        },
        "raw_image_bytes_included": False,
        "raw_audio_bytes_included": False,
    }


def preferred_reply_language(text: str) -> str:
    import re

    return "Chinese" if re.search(CJK_RE, text) else "same_as_user"


def build_provider_prompt(request: dict[str, Any]) -> str:
    text = str(request["context"].get("current_event_text", "")).strip()
    modalities = ", ".join(request["input"].get("modalities", []))
    reply_language = preferred_reply_language(text)
    visual_context = request["context"].get("visual_context", {})
    audio_context = request["context"].get("audio_context", {})
    current_event_refs = request["context"].get("current_event_refs", {})
    multimodal_summary = multimodal_context_summary(request)
    multimodal_summary_text = json.dumps(multimodal_summary, ensure_ascii=True)
    visual_context_text = json.dumps(visual_context, ensure_ascii=True)
    audio_context_text = json.dumps(audio_context, ensure_ascii=True)
    current_event_refs_text = json.dumps(current_event_refs, ensure_ascii=True)
    return (
        "You are the reasoning engine for Y_Chat. Return only valid JSON matching reasoning.v1. "
        "Do not include markdown fences. Keep actions empty unless a capability is explicitly safe and necessary. "
        "Memory write candidates are optional and should be high-confidence only. "
        "Answer the user's latest request directly and in the user's language. "
        "If user_text contains Chinese, reply.text and reply.bubble_text must be Chinese. "
        "When the user asks whether multimodal context is present, answer from multimodal_context_summary_json "
        "and the visual/audio context instead of asking for clarification. "
        "If the user asks what is currently on screen or what you can see now, and "
        "current_screen_evidence_available is false with no current vision refs, say there is no fresh current "
        "screen evidence and suggest starting screen observation or sampling once. Do not summarize stale visual "
        "memory in that answer unless the user explicitly asks for historical visual memory. "
        "Stale visual evidence may only be described as historical memory when requested. "
        "Image refs are local evidence references, not raw images. Do not claim you saw image pixels unless "
        "the visual context contains an extracted description, OCR text, or visual feature summary. "
        "Features from local_rapidocr/rapidocr are OCR-only auxiliary visible-text evidence, not image semantic recognition. "
        "Audio refs are local evidence references, not raw audio. Do not claim you heard audio unless the audio "
        "context contains transcript metadata or audio feature summaries, and treat transcripts as auxiliary text.\n\n"
        f"run_id: {request['run_id']}\n"
        f"event_type: {request['input'].get('event_type')}\n"
        f"primary_modality: {request['input'].get('primary_modality')}\n"
        f"modalities: {modalities}\n"
        f"preferred_reply_language: {reply_language}\n"
        f"user_text: {text}\n"
        f"multimodal_context_summary_json: {multimodal_summary_text}\n"
        f"current_event_refs_json: {current_event_refs_text}\n"
        f"visual_context_json: {visual_context_text}\n"
        f"audio_context_json: {audio_context_text}\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "schema_version": "reasoning.v1",\n'
        f'  "run_id": "{request["run_id"]}",\n'
        '  "reply": {"should_reply": true, "text": "...", "bubble_text": "...", "style": "normal", "final": true},\n'
        '  "state": {"pet_state": "talking", "emotion": "neutral", "animation": null},\n'
        '  "actions": [],\n'
        '  "memory": {"write_candidates": [], "do_not_write_reason": null, "needs_consolidation": false},\n'
        '  "observations": [],\n'
        '  "voice": {"speak": false, "text": null, "voice_style": null},\n'
        '  "debug": {"depth": "lightweight", "needs_deep_retrieval": false, "deep_retrieval_query": null, "trace": []},\n'
        '  "audit": {"safety_notes": [], "permission_requests": []}\n'
        "}"
    )


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        loaded = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        loaded = json.loads(stripped[start : end + 1])
    if not isinstance(loaded, dict):
        raise ValueError("provider output must be a JSON object")
    return loaded


def call_openai_compatible_chat(request: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    response = post_chat_completion(
        config,
        [
            {
                "role": "system",
                "content": "Return only complete JSON. No markdown. No extra prose. The JSON object must match reasoning.v1.",
            },
            {"role": "user", "content": build_provider_prompt(request)},
        ],
        json_mode=True,
    )
    content = extract_message_content(response["payload"])
    return extract_json_object(str(content))
