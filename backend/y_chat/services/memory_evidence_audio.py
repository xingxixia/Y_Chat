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

def create_audio_evidence_record(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_memory_db()
    source = str(payload.get("source") or "voice_clip").strip()
    if source not in {"voice_clip", "audio_file"}:
        raise ValueError("source must be voice_clip or audio_file")
    raw_ref = str(payload.get("raw_ref") or "").strip()
    if not raw_ref:
        raise ValueError("raw_ref is required")
    status = str(payload.get("audio_reader_status") or "metadata_only").strip()
    if status not in AUDIO_READER_STATUS["supported_statuses"]:
        raise ValueError("audio_reader_status must be pending, metadata_only, transcribed, or failed")

    created_at = now_iso()
    attachment_id = str(payload.get("attachment_id") or uuid4())
    source_event_id = payload.get("source_event_id")
    mime = str(payload.get("mime") or "audio/wav").strip()
    sha256 = str(payload.get("sha256") or "").strip()
    duration_ms = int(payload.get("duration_ms") or 0)
    size_bytes = int(payload.get("size_bytes") or 0)
    raw_available = bool(payload.get("raw_available", True))
    transcript = str(payload.get("transcript") or "").strip()
    transcript_status = "provided" if transcript else "pending"

    backup_id = str(uuid4()) if raw_available else None
    evidence_id = str(uuid4())
    observation_id = str(uuid4())
    feature_id = str(uuid4())
    transcript_observation_id = str(uuid4()) if transcript else None
    buffer_id = str(uuid4())
    audit_id = str(uuid4())
    link_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
    attachment_ref = {
        "attachment_id": attachment_id,
        "kind": "audio",
        "source": source,
        "raw_ref": raw_ref,
        "mime": mime,
        "sha256": sha256,
        "duration_ms": duration_ms,
        "raw_available": raw_available,
        "audio_reader_status": status,
        "transcript_status": transcript_status,
    }
    summary = {
        "schema_version": "memory_observation.audio.v1",
        "attachment": attachment_ref,
        "raw_payload_stored_in_event": False,
        "raw_payload_returned_in_debug": False,
    }
    feature_summary = {
        "schema_version": "audio_feature.metadata.v1",
        "feature_kind": "audio_metadata",
        "mime": mime,
        "sha256": sha256,
        "duration_ms": duration_ms,
        "byte_size": size_bytes,
        "voiceprint_configured": False,
        "asr_configured": False,
        "comparable_for_identity": False,
        "pending_reason": "ASR and speaker embeddings are not configured in this slice",
    }

    with sqlite3.connect(db_path()) as db:
        if backup_id:
            db.execute(
                """
                INSERT INTO raw_backups (
                    backup_id, modality, storage_ref, size_bytes, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (backup_id, "audio", raw_ref, size_bytes, None, created_at),
            )
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
                "audio",
                source,
                _json_dumps(summary),
                _json_dumps([feature_id]),
                raw_ref,
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
                "audio",
                "audio_metadata",
                None,
                observation_id,
                f"feature://audio/metadata/{feature_id}",
                _json_dumps(feature_summary),
                created_at,
            ),
        )
        if transcript and transcript_observation_id:
            transcript_summary = {
                "schema_version": "memory_observation.text.v1",
                "source": "transcript",
                "text": transcript,
                "text_chars": len(transcript),
                "text_hash": stable_text_hash(transcript),
                "linked_audio_observation_id": observation_id,
            }
            db.execute(
                """
                INSERT INTO memory_observations (
                    observation_id, source_event_id, modality, source, summary_json,
                    feature_refs_json, raw_ref, confidence, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transcript_observation_id,
                    source_event_id,
                    "text",
                    "transcript",
                    _json_dumps(transcript_summary),
                    _json_dumps([]),
                    None,
                    0.8,
                    created_at,
                ),
            )
            db.execute(
                """
                INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (link_ids[2], transcript_observation_id, observation_id, "summary-of", 0.8, created_at),
            )
        if backup_id:
            db.execute(
                """
                INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (link_ids[0], observation_id, backup_id, "evidence-of", 1.0, created_at),
            )
        db.execute(
            """
            INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (link_ids[1], feature_id, observation_id, "feature-of", 1.0, created_at),
        )
        db.execute(
            """
            INSERT INTO memory_audio_evidence (
                evidence_id, source_event_id, attachment_id, source, raw_ref,
                backup_id, observation_id, feature_refs_json,
                transcript_observation_id, mime, sha256, duration_ms,
                size_bytes, raw_available, audio_reader_status,
                transcript_status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                source_event_id,
                attachment_id,
                source,
                raw_ref,
                backup_id,
                observation_id,
                _json_dumps([feature_id]),
                transcript_observation_id,
                mime,
                sha256,
                duration_ms,
                size_bytes,
                1 if raw_available else 0,
                status,
                transcript_status,
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
                "audio_evidence",
                "pending",
                _json_dumps([source_event_id] if source_event_id else []),
                _json_dumps([evidence_id, observation_id]),
                _json_dumps([feature_id]),
                _json_dumps([]),
                0.5,
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
                "audio_evidence.created",
                _json_dumps(
                    {
                        "source": source,
                        "attachment_id": attachment_id,
                        "observation_id": observation_id,
                        "feature_ids": [feature_id],
                        "backup_id": backup_id,
                        "transcript_status": transcript_status,
                        "raw_payload_stored_in_event": False,
                        "raw_payload_returned_in_debug": False,
                    }
                ),
                created_at,
            ),
        )

    return {
        "evidence_id": evidence_id,
        "attachment_ref": attachment_ref,
        "observation_id": observation_id,
        "feature_refs": [feature_id],
        "backup_id": backup_id,
        "transcript_observation_id": transcript_observation_id,
        "consolidation_buffer_id": buffer_id,
        "audit_id": audit_id,
        "raw_payload_returned": False,
    }
