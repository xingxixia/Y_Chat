from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from .memory_evidence_common import (
    ATTACHMENT_REF_CONTRACT,
    AUDIO_READER_STATUS,
    TEXT_READER_STATUS,
    VISION_READER_STATUS,
    db_path,
    ensure_memory_db,
    json_dumps as _json_dumps,
    now_iso,
)
from .memory_features import stable_text_hash

def create_text_evidence_record(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_memory_db()
    source = str(payload.get("source") or "user_command").strip()
    if source not in {"user_command", "ocr_text", "transcript", "manual_note"}:
        raise ValueError("source must be user_command, ocr_text, transcript, or manual_note")
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("text is required")

    created_at = now_iso()
    source_event_id = payload.get("source_event_id")
    language = str(payload.get("language") or "unknown").strip()
    status = str(payload.get("text_reader_status") or "observed").strip()
    if status not in TEXT_READER_STATUS["supported_statuses"]:
        raise ValueError("text_reader_status must be observed, summarized, or failed")

    evidence_id = str(uuid4())
    observation_id = str(uuid4())
    feature_id = str(uuid4())
    link_id = str(uuid4())
    buffer_id = str(uuid4())
    audit_id = str(uuid4())
    text_hash = stable_text_hash(text)
    summary = {
        "schema_version": "memory_observation.text.v1",
        "source": source,
        "text": text,
        "text_chars": len(text),
        "text_hash": text_hash,
        "language": language,
        "text_reader_status": status,
        "raw_payload_returned_in_debug": False,
    }
    feature_summary = {
        "schema_version": "text_feature.lexical.v1",
        "feature_kind": "text_metadata",
        "text_hash": text_hash,
        "text_chars": len(text),
        "language": language,
        "embedding_configured": False,
        "comparable_for_semantic_search": False,
        "pending_reason": "text embedding/retrieval is not configured in this slice",
    }

    with sqlite3.connect(db_path()) as db:
        db.execute(
            """
            INSERT INTO memory_observations (
                observation_id, source_event_id, modality, source, summary_json,
                feature_refs_json, raw_ref, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                source_event_id,
                "text",
                source,
                _json_dumps(summary),
                _json_dumps([feature_id]),
                None,
                1.0,
                created_at,
            ),
        )
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
                "text",
                "text_metadata",
                None,
                observation_id,
                f"feature://text/metadata/{feature_id}",
                _json_dumps(feature_summary),
                created_at,
            ),
        )
        db.execute(
            """
            INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (link_id, feature_id, observation_id, "feature-of", 1.0, created_at),
        )
        db.execute(
            """
            INSERT INTO memory_text_evidence (
                evidence_id, source_event_id, source, observation_id,
                feature_refs_json, text_chars, text_hash, language,
                text_reader_status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                source_event_id,
                source,
                observation_id,
                _json_dumps([feature_id]),
                len(text),
                text_hash,
                language,
                status,
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
                "short_term",
                "text_evidence",
                "pending",
                _json_dumps([source_event_id] if source_event_id else []),
                _json_dumps([evidence_id, observation_id]),
                _json_dumps([feature_id]),
                _json_dumps([]),
                0.7,
                0.5,
                0,
                created_at,
                created_at,
            ),
        )
        db.execute(
            """
            INSERT INTO memory_audit_log (audit_id, record_id, action, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                evidence_id,
                "text_evidence.created",
                _json_dumps(
                    {
                        "source": source,
                        "observation_id": observation_id,
                        "feature_ids": [feature_id],
                        "text_hash": text_hash,
                        "text_chars": len(text),
                        "raw_payload_returned_in_debug": False,
                    }
                ),
                created_at,
            ),
        )

    return {
        "evidence_id": evidence_id,
        "observation_id": observation_id,
        "feature_refs": [feature_id],
        "consolidation_buffer_id": buffer_id,
        "audit_id": audit_id,
        "text_hash": text_hash,
        "text_chars": len(text),
        "raw_payload_returned": False,
    }
