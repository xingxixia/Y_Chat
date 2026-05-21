from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .redaction import REDACTED_MULTIMODAL, redact_text
from .visual_freshness import CURRENT_SCREEN_MAX_AGE_SECONDS, visual_freshness_status


LOCAL_PATH_REF = "[LOCAL_PATH_REF]"
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


def _truncate_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...[truncated]"


def _safe_ref(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    redacted, _ = redact_text(text)
    if redacted == REDACTED_MULTIMODAL:
        return REDACTED_MULTIMODAL
    if LOCAL_PATH_RE.match(redacted):
        return LOCAL_PATH_REF
    return redacted


def _bounded_visible_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_truncate_text(value)]
    if isinstance(value, list):
        result: list[str] = []
        for item in value[:10]:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
            else:
                text = item
            normalized = _truncate_text(text, 200)
            if normalized:
                result.append(normalized)
        return result
    return []


def _empty_context() -> dict[str, Any]:
    return {
        "schema_version": "reasoning_visual_context.v1",
        "recent_visual_evidence": [],
        "recent_ocr_text": [],
        "fresh_visual_evidence_count": 0,
        "stale_visual_evidence_count": 0,
        "fresh_ocr_text_count": 0,
        "stale_ocr_text_count": 0,
        "latest_visual_age_seconds": None,
        "current_screen_evidence_available": False,
        "freshness_policy": {
            "current_screen_max_age_seconds": CURRENT_SCREEN_MAX_AGE_SECONDS,
        },
        "raw_image_bytes_included": False,
        "absolute_local_paths_included": False,
        "provider_must_not_claim_unparsed_images": True,
    }


def visual_feature_context(db: sqlite3.Connection, feature_refs: list[str]) -> list[dict[str, Any]]:
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
        if row["feature_kind"] == "visual_signature":
            item.update(
                {
                    "signature_type": summary.get("signature_type"),
                    "comparable_for_identity": bool(summary.get("comparable_for_identity")),
                    "identity_status": summary.get("identity_status"),
                }
            )
        elif row["feature_kind"] == "vlm_extracted_text":
            item.update(
                {
                    "provider": summary.get("provider"),
                    "model": summary.get("model"),
                    "description": _truncate_text(summary.get("description"), 500),
                    "visible_text": _bounded_visible_text(summary.get("visible_text")),
                    "object_count": len(summary.get("objects", [])) if isinstance(summary.get("objects"), list) else 0,
                    "auxiliary_text_evidence_id": summary.get("auxiliary_text_evidence_id"),
                }
            )
        elif row["feature_kind"] == "image_embedding":
            item.update(
                {
                    "provider": summary.get("provider"),
                    "model": summary.get("model"),
                    "dimensions": summary.get("dimensions"),
                    "embedding_hash": summary.get("embedding_hash"),
                    "comparable_for_identity": bool(summary.get("comparable_for_identity")),
                    "identity_status": summary.get("identity_status"),
                }
            )
        else:
            item["summary_kind"] = summary.get("feature_kind") or row["feature_kind"]
        features.append(item)
    return features


def visual_candidate_context(db: sqlite3.Connection, entity_refs: list[str]) -> list[dict[str, Any]]:
    refs = [str(ref) for ref in entity_refs if str(ref)]
    if not refs:
        return []
    placeholders = ",".join("?" for _ in refs)
    rows = db.execute(
        f"""
        SELECT entity_id, kind, status, confidence, summary_json, updated_at
        FROM memory_entities
        WHERE entity_id IN ({placeholders})
        """,
        refs,
    ).fetchall()
    by_id = {row["entity_id"]: row for row in rows}
    candidates: list[dict[str, Any]] = []
    for ref in refs:
        row = by_id.get(ref)
        if not row:
            continue
        summary = _parse_json(row["summary_json"], {})
        candidates.append(
            {
                "entity_id": row["entity_id"],
                "kind": row["kind"],
                "status": row["status"],
                "confidence": row["confidence"],
                "candidate_only": bool(summary.get("candidate_only", True)),
                "identity_confirmed": bool(summary.get("identity_confirmed", False)),
                "match_basis": summary.get("match_basis"),
                "updated_at": row["updated_at"],
            }
        )
    return candidates


def recent_visual_reasoning_context(db: sqlite3.Connection, limit: int = 5) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 10))
    try:
        visual_rows = db.execute(
            """
            SELECT evidence_id, source_event_id, attachment_id, source, raw_ref,
                   observation_id, feature_refs_json, entity_candidate_refs_json,
                   mime, sha256, width, height, raw_available,
                   vision_reader_status, created_at
            FROM memory_visual_evidence
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
        ocr_rows = db.execute(
            """
            SELECT evidence.evidence_id, evidence.source_event_id, evidence.observation_id,
                   evidence.text_chars, evidence.language, evidence.text_reader_status,
                   evidence.created_at, observation.summary_json
            FROM memory_text_evidence AS evidence
            LEFT JOIN memory_observations AS observation
              ON observation.observation_id = evidence.observation_id
            WHERE evidence.source = ?
            ORDER BY evidence.created_at DESC
            LIMIT ?
            """,
            ("ocr_text", safe_limit),
        ).fetchall()
        now = datetime.now(timezone.utc)
        visual_context: list[dict[str, Any]] = []
        for row in visual_rows:
            feature_refs = [str(item) for item in _parse_json(row["feature_refs_json"], [])]
            entity_refs = [str(item) for item in _parse_json(row["entity_candidate_refs_json"], [])]
            freshness = visual_freshness_status(row["created_at"], now=now)
            visual_context.append(
                {
                    "evidence_id": row["evidence_id"],
                    "source_event_id": row["source_event_id"],
                    "attachment_id": row["attachment_id"],
                    "source": row["source"],
                    "raw_ref": _safe_ref(row["raw_ref"]),
                    "observation_id": row["observation_id"],
                    "feature_refs": feature_refs,
                    "entity_candidate_refs": entity_refs,
                    "mime": row["mime"],
                    "sha256": row["sha256"],
                    "width": row["width"],
                    "height": row["height"],
                    "raw_available": bool(row["raw_available"]),
                    "vision_reader_status": row["vision_reader_status"],
                    "created_at": row["created_at"],
                    **freshness,
                    "features": visual_feature_context(db, feature_refs),
                    "candidate_entities": visual_candidate_context(db, entity_refs),
                }
            )
        ocr_context: list[dict[str, Any]] = []
        for row in ocr_rows:
            summary = _parse_json(row["summary_json"], {})
            freshness = visual_freshness_status(row["created_at"], now=now)
            ocr_context.append(
                {
                    "evidence_id": row["evidence_id"],
                    "source_event_id": row["source_event_id"],
                    "observation_id": row["observation_id"],
                    "text": _truncate_text(summary.get("text"), 500),
                    "text_chars": row["text_chars"],
                    "language": row["language"],
                    "text_reader_status": row["text_reader_status"],
                    "created_at": row["created_at"],
                    **freshness,
                }
            )
        fresh_visual_count = sum(1 for item in visual_context if item.get("fresh_for_current_screen"))
        fresh_ocr_count = sum(1 for item in ocr_context if item.get("fresh_for_current_screen"))
        return {
            "schema_version": "reasoning_visual_context.v1",
            "recent_visual_evidence": visual_context,
            "recent_ocr_text": ocr_context,
            "fresh_visual_evidence_count": fresh_visual_count,
            "stale_visual_evidence_count": max(0, len(visual_context) - fresh_visual_count),
            "fresh_ocr_text_count": fresh_ocr_count,
            "stale_ocr_text_count": max(0, len(ocr_context) - fresh_ocr_count),
            "latest_visual_age_seconds": visual_context[0].get("age_seconds") if visual_context else None,
            "current_screen_evidence_available": bool(fresh_visual_count),
            "freshness_policy": {
                "current_screen_max_age_seconds": CURRENT_SCREEN_MAX_AGE_SECONDS,
            },
            "raw_image_bytes_included": False,
            "absolute_local_paths_included": False,
            "provider_must_not_claim_unparsed_images": True,
        }
    except sqlite3.Error:
        return _empty_context()
