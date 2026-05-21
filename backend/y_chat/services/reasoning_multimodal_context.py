from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from .redaction import REDACTED_MULTIMODAL, redact_text


MAX_CURRENT_EVENT_REFS = 12
LOCAL_PATH_REF = "[LOCAL_PATH_REF]"

VISION_REF_KEYS = {
    "image_ref",
    "image_refs",
    "screenshot_ref",
    "screenshot_refs",
    "frame_ref",
    "frame_refs",
    "crop_ref",
    "crop_refs",
    "visual_feature_ref",
    "visual_feature_refs",
    "vision_evidence_id",
    "visual_evidence_id",
}
AUDIO_REF_KEYS = {
    "audio_ref",
    "audio_refs",
    "voice_ref",
    "voice_refs",
    "audio_feature_ref",
    "audio_feature_refs",
    "audio_evidence_id",
    "voice_evidence_id",
}
ATTACHMENT_KEYS = {"attachment_ref", "attachment_refs", "attachments"}
SAFE_ATTACHMENT_FIELDS = {
    "attachment_id",
    "kind",
    "source",
    "raw_ref",
    "ref",
    "mime",
    "sha256",
    "width",
    "height",
    "duration_ms",
    "raw_available",
    "vision_reader_status",
    "audio_reader_status",
    "evidence_id",
    "feature_id",
    "observation_id",
}
LOCAL_PATH_RE = re.compile(r"(?i)^([a-z]:[\\/]|\\\\|/|file://)")


def _parse_json(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return fallback
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _safe_text_ref(value: Any) -> tuple[str, bool]:
    text = str(value or "").strip()
    if not text:
        return "", False
    redacted, changed = redact_text(text)
    if redacted == REDACTED_MULTIMODAL or LOCAL_PATH_RE.match(redacted):
        if redacted == REDACTED_MULTIMODAL:
            return REDACTED_MULTIMODAL, True
        return LOCAL_PATH_REF, True
    return redacted, changed


def _safe_scalar(value: Any) -> tuple[Any, bool]:
    if isinstance(value, str):
        return _safe_text_ref(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value, False
    return str(type(value).__name__), True


def _normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _item_from_scalar(field: str, value: Any, *, index: int | None = None) -> tuple[dict[str, Any] | None, bool]:
    safe_value, changed = _safe_text_ref(value)
    if not safe_value:
        return None, changed
    item: dict[str, Any] = {"field": field, "ref": safe_value}
    if index is not None:
        item["index"] = index
    return item, changed


def _item_from_mapping(field: str, value: dict[str, Any], *, index: int | None = None) -> tuple[dict[str, Any] | None, bool]:
    item: dict[str, Any] = {"field": field}
    if index is not None:
        item["index"] = index
    changed = False
    for key in sorted(value.keys(), key=str):
        normalized = _normalize_key(key)
        if normalized not in SAFE_ATTACHMENT_FIELDS:
            continue
        safe_value, safe_changed = _safe_scalar(value[key])
        if safe_value == "":
            continue
        item[normalized] = safe_value
        changed = changed or safe_changed
    if len(item) <= (2 if index is not None else 1):
        return None, changed
    return item, changed


def _items_from_value(field: str, value: Any) -> tuple[list[dict[str, Any]], bool]:
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        changed = False
        for index, entry in enumerate(value[:MAX_CURRENT_EVENT_REFS]):
            if isinstance(entry, dict):
                item, item_changed = _item_from_mapping(field, entry, index=index)
            else:
                item, item_changed = _item_from_scalar(field, entry, index=index)
            if item:
                items.append(item)
            changed = changed or item_changed
        return items, changed or len(value) > MAX_CURRENT_EVENT_REFS
    if isinstance(value, dict):
        item, changed = _item_from_mapping(field, value)
        return ([item] if item else []), changed
    item, changed = _item_from_scalar(field, value)
    return ([item] if item else []), changed


def _attachment_modality(item: dict[str, Any]) -> str | None:
    kind = str(item.get("kind") or item.get("mime") or "").lower()
    if "audio" in kind or kind.startswith("voice"):
        return "audio"
    if "image" in kind or kind in {"vision", "visual", "screen_frame"}:
        return "vision"
    return None


def current_event_multimodal_refs(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    vision: list[dict[str, Any]] = []
    audio: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    redacted = False

    for key, value in payload.items():
        normalized = _normalize_key(key)
        if normalized in VISION_REF_KEYS:
            items, changed = _items_from_value(normalized, value)
            vision.extend(items)
            redacted = redacted or changed
        elif normalized in AUDIO_REF_KEYS:
            items, changed = _items_from_value(normalized, value)
            audio.extend(items)
            redacted = redacted or changed
        elif normalized in ATTACHMENT_KEYS:
            items, changed = _items_from_value(normalized, value)
            attachments.extend(items)
            redacted = redacted or changed
            for item in items:
                modality = _attachment_modality(item)
                if modality == "vision":
                    vision.append(item)
                elif modality == "audio":
                    audio.append(item)

    return {
        "schema_version": "current_event_multimodal_refs.v1",
        "vision": vision[:MAX_CURRENT_EVENT_REFS],
        "audio": audio[:MAX_CURRENT_EVENT_REFS],
        "attachments": attachments[:MAX_CURRENT_EVENT_REFS],
        "raw_payload_included": False,
        "absolute_local_paths_included": False,
        "ref_values_redacted": redacted,
    }


def empty_audio_context() -> dict[str, Any]:
    return {
        "schema_version": "reasoning_audio_context.v1",
        "recent_audio_evidence": [],
        "raw_audio_bytes_included": False,
        "absolute_local_paths_included": False,
        "provider_must_not_claim_unparsed_audio": True,
    }


def audio_feature_context(db: sqlite3.Connection, feature_refs: list[str]) -> list[dict[str, Any]]:
    refs = [str(ref) for ref in feature_refs if str(ref)]
    if not refs:
        return []
    placeholders = ",".join("?" for _ in refs)
    rows = db.execute(
        f"""
        SELECT feature_id, feature_kind, storage_ref, summary_json, created_at
        FROM memory_features
        WHERE feature_id IN ({placeholders})
        """,
        refs,
    ).fetchall()
    by_id = {row["feature_id"]: row for row in rows}
    features: list[dict[str, Any]] = []
    for ref in refs:
        row = by_id.get(ref)
        if not row:
            continue
        summary = _parse_json(row["summary_json"], {})
        item: dict[str, Any] = {
            "feature_id": row["feature_id"],
            "feature_kind": row["feature_kind"],
            "storage_ref": row["storage_ref"],
            "created_at": row["created_at"],
        }
        if row["feature_kind"] == "audio_metadata":
            item.update(
                {
                    "mime": summary.get("mime"),
                    "sha256": summary.get("sha256"),
                    "duration_ms": summary.get("duration_ms"),
                    "byte_size": summary.get("byte_size"),
                    "voiceprint_configured": bool(summary.get("voiceprint_configured", False)),
                    "asr_configured": bool(summary.get("asr_configured", False)),
                    "comparable_for_identity": bool(summary.get("comparable_for_identity", False)),
                    "pending_reason": summary.get("pending_reason"),
                }
            )
        elif row["feature_kind"] == "audio_asr_transcript":
            item.update(
                {
                    "provider": summary.get("provider"),
                    "model": summary.get("model"),
                    "language": summary.get("language"),
                    "duration_seconds": summary.get("duration_seconds"),
                    "transcript_hash": summary.get("transcript_hash"),
                    "transcript_chars": summary.get("transcript_chars"),
                    "auxiliary_text_evidence_id": summary.get("auxiliary_text_evidence_id"),
                    "text_auxiliary_only": bool(summary.get("text_auxiliary_only", True)),
                }
            )
        else:
            item["summary_kind"] = summary.get("feature_kind") or row["feature_kind"]
        features.append(item)
    return features


def transcript_observation_context(db: sqlite3.Connection, observation_id: str | None) -> dict[str, Any] | None:
    if not observation_id:
        return None
    row = db.execute(
        """
        SELECT observation_id, source, summary_json, created_at
        FROM memory_observations
        WHERE observation_id = ?
        """,
        (observation_id,),
    ).fetchone()
    if not row:
        return None
    summary = _parse_json(row["summary_json"], {})
    return {
        "observation_id": row["observation_id"],
        "source": row["source"],
        "text_chars": int(summary.get("text_chars") or 0),
        "text_hash": summary.get("text_hash"),
        "linked_audio_observation_id": summary.get("linked_audio_observation_id"),
        "created_at": row["created_at"],
        "raw_text_included": False,
    }


def recent_audio_reasoning_context(db: sqlite3.Connection, limit: int = 5) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 10))
    try:
        rows = db.execute(
            """
            SELECT evidence_id, source_event_id, attachment_id, source, raw_ref,
                   observation_id, feature_refs_json, transcript_observation_id,
                   mime, sha256, duration_ms, size_bytes, raw_available,
                   audio_reader_status, transcript_status, created_at
            FROM memory_audio_evidence
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
        audio_context: list[dict[str, Any]] = []
        any_redacted = False
        for row in rows:
            feature_refs = [str(item) for item in _parse_json(row["feature_refs_json"], [])]
            raw_ref, raw_ref_redacted = _safe_text_ref(row["raw_ref"])
            any_redacted = any_redacted or raw_ref_redacted
            audio_context.append(
                {
                    "evidence_id": row["evidence_id"],
                    "source_event_id": row["source_event_id"],
                    "attachment_id": row["attachment_id"],
                    "source": row["source"],
                    "raw_ref": raw_ref,
                    "observation_id": row["observation_id"],
                    "feature_refs": feature_refs,
                    "transcript_observation_id": row["transcript_observation_id"],
                    "transcript": transcript_observation_context(db, row["transcript_observation_id"]),
                    "mime": row["mime"],
                    "sha256": row["sha256"],
                    "duration_ms": row["duration_ms"],
                    "size_bytes": row["size_bytes"],
                    "raw_available": bool(row["raw_available"]),
                    "audio_reader_status": row["audio_reader_status"],
                    "transcript_status": row["transcript_status"],
                    "created_at": row["created_at"],
                    "features": audio_feature_context(db, feature_refs),
                }
            )
        return {
            "schema_version": "reasoning_audio_context.v1",
            "recent_audio_evidence": audio_context,
            "raw_audio_bytes_included": False,
            "absolute_local_paths_included": False,
            "provider_must_not_claim_unparsed_audio": True,
            "ref_values_redacted": any_redacted,
        }
    except sqlite3.Error:
        return empty_audio_context()
