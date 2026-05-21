from __future__ import annotations

import json
import sqlite3
from typing import Any
from uuid import uuid4

from ..config import runtime_sqlite_path
from ..memory import create_text_evidence_record, now_iso


def record_extraction_feature(evidence: dict[str, Any], extraction: dict[str, Any]) -> dict[str, Any]:
    created_at = now_iso()
    feature_id = str(uuid4())
    buffer_id = str(uuid4())
    audit_id = str(uuid4())
    extracted_text = str(extraction.get("description") or extraction.get("text") or "").strip()
    visible_text = normalize_visible_text(extraction.get("visible_text", []))
    text_refs: dict[str, Any] | None = None
    if visible_text:
        text_refs = create_text_evidence_record(
            {
                "source": "ocr_text",
                "source_event_id": evidence.get("source_event_id"),
                "text": "\n".join(visible_text),
                "language": str(extraction.get("language") or "unknown"),
                "text_reader_status": "observed",
            }
        )
    existing_feature_refs = parse_json_list(evidence.get("feature_refs_json"))
    feature_refs = append_unique(existing_feature_refs, feature_id)
    entity_candidate_refs = parse_json_list(evidence.get("entity_candidate_refs_json"))
    summary = {
        "schema_version": "vision_feature.extracted.v1",
        "feature_kind": "vlm_extracted_text",
        "source": evidence["source"],
        "evidence_id": evidence["evidence_id"],
        "source_observation_id": evidence.get("observation_id"),
        "provider": extraction.get("provider"),
        "model": extraction.get("model"),
        "description": extracted_text,
        "objects": extraction.get("objects", []),
        "visible_text": visible_text,
        "auxiliary_text_evidence_id": text_refs.get("evidence_id") if text_refs else None,
        "auxiliary_text_observation_id": text_refs.get("observation_id") if text_refs else None,
        "auxiliary_text_feature_refs": text_refs.get("feature_refs") if text_refs else [],
        "raw_image_sent_to_configured_vision_provider": bool(
            extraction.get("raw_image_sent_to_configured_vision_provider", False)
        ),
        "raw_image_processed_locally": bool(extraction.get("raw_image_processed_locally", False)),
        "raw_image_sent_to_deepseek": bool(extraction.get("raw_image_sent_to_deepseek", False)),
        "image_generation_supported": bool(extraction.get("image_generation_supported", False)),
        "raw_payload_returned": False,
    }
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.execute(
            """
            INSERT INTO memory_features (
                feature_id, modality, feature_kind, owner_entity_id,
                source_observation_id, storage_ref, summary_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feature_id,
                "vision",
                "vlm_extracted_text",
                None,
                evidence.get("observation_id"),
                f"feature://vision/extracted/{feature_id}",
                json.dumps(summary, ensure_ascii=True),
                created_at,
            ),
        )
        db.execute(
            """
            INSERT INTO memory_consolidation_buffer (
                buffer_id, target_layer, kind, status, source_refs_json,
                evidence_refs_json, feature_refs_json, entity_candidate_refs_json,
                confidence, importance, review_required, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                buffer_id,
                "consolidation_buffer",
                "visual_extraction",
                "pending",
                json.dumps([evidence.get("source_event_id")] if evidence.get("source_event_id") else [], ensure_ascii=True),
                json.dumps(
                    [
                        value
                        for value in [
                            evidence["evidence_id"],
                            evidence.get("observation_id"),
                            text_refs.get("evidence_id") if text_refs else None,
                        ]
                        if value
                    ],
                    ensure_ascii=True,
                ),
                json.dumps(feature_refs, ensure_ascii=True),
                json.dumps(entity_candidate_refs, ensure_ascii=True),
                0.7,
                0.6,
                0,
                created_at,
                created_at,
            ),
        )
        db.execute(
            """
            UPDATE memory_visual_evidence
            SET vision_reader_status = ?, feature_refs_json = ?
            WHERE evidence_id = ?
            """,
            ("extracted", json.dumps(feature_refs, ensure_ascii=True), evidence["evidence_id"]),
        )
        if evidence.get("observation_id"):
            db.execute(
                """
                UPDATE memory_observations
                SET feature_refs_json = ?
                WHERE observation_id = ?
                """,
                (json.dumps(feature_refs, ensure_ascii=True), evidence["observation_id"]),
            )
            db.execute(
                """
                INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), feature_id, evidence["observation_id"], "feature-of", 1.0, created_at),
            )
        db.execute(
            """
            INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid4()), feature_id, evidence["evidence_id"], "extracted-from", 1.0, created_at),
        )
        if text_refs:
            db.execute(
                """
                INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), text_refs["observation_id"], evidence["observation_id"], "ocr-text-of", 0.8, created_at),
            )
        db.execute(
            """
            INSERT INTO memory_audit_log (audit_id, record_id, action, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                evidence["evidence_id"],
                "visual_evidence.extracted",
                json.dumps(
                    {
                        "feature_id": feature_id,
                        "buffer_id": buffer_id,
                        "feature_refs": feature_refs,
                        "entity_candidate_refs": entity_candidate_refs,
                        "auxiliary_text_evidence_id": text_refs.get("evidence_id") if text_refs else None,
                        "provider": extraction.get("provider"),
                        "model": extraction.get("model"),
                        "raw_payload_returned": False,
                    },
                    ensure_ascii=True,
                ),
                created_at,
            ),
        )
    return {
        "feature_id": feature_id,
        "feature_refs": feature_refs,
        "entity_candidate_refs": entity_candidate_refs,
        "auxiliary_text_evidence_id": text_refs.get("evidence_id") if text_refs else None,
        "auxiliary_text_observation_id": text_refs.get("observation_id") if text_refs else None,
        "auxiliary_text_feature_refs": text_refs.get("feature_refs") if text_refs else [],
        "consolidation_buffer_id": buffer_id,
        "audit_id": audit_id,
    }


def parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def append_unique(values: list[Any], extra: Any) -> list[Any]:
    result = [str(value) for value in values if str(value)]
    extra_value = str(extra)
    if extra_value and extra_value not in result:
        result.append(extra_value)
    return result


def normalize_visible_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "").strip()
            else:
                text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    return []
