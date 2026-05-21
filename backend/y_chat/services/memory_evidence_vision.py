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
from .memory_features import (
    create_visual_candidate_entity,
    recent_visual_signature_matches,
    visual_signature_from_raw_ref,
)

def create_visual_evidence_record(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_memory_db()
    source = str(payload.get("source") or "").strip()
    if source not in ATTACHMENT_REF_CONTRACT["supported_sources"]:
        raise ValueError("source must be manual_file, paste_image, or screen_frame")

    created_at = now_iso()
    attachment_id = str(payload.get("attachment_id") or uuid4())
    source_event_id = payload.get("source_event_id")
    raw_ref = str(payload.get("raw_ref") or payload.get("storage_ref") or "").strip()
    if not raw_ref:
        raise ValueError("raw_ref is required")
    mime = str(payload.get("mime") or "image/png").strip()
    sha256 = str(payload.get("sha256") or "").strip()
    if not sha256:
        raise ValueError("sha256 is required")
    width = int(payload.get("width") or 0)
    height = int(payload.get("height") or 0)
    size_bytes = int(payload.get("size_bytes") or 0)
    source_display_width = int(payload.get("source_display_width") or 0)
    source_display_height = int(payload.get("source_display_height") or 0)
    thumbnail_max_width = int(payload.get("thumbnail_max_width") or 0)
    raw_available = bool(payload.get("raw_available", True))
    status = str(payload.get("vision_reader_status") or "metadata_only").strip()
    if status not in VISION_READER_STATUS["supported_statuses"]:
        raise ValueError("vision_reader_status must be pending, metadata_only, extracted, or failed")

    backup_id = str(uuid4()) if raw_available else None
    observation_id = str(uuid4())
    feature_id = str(uuid4())
    signature_summary = visual_signature_from_raw_ref(raw_ref) if raw_available else None
    signature_feature_id = str(uuid4()) if signature_summary else None
    feature_ids = [feature_id] + ([signature_feature_id] if signature_feature_id else [])
    link_ids = [str(uuid4()), str(uuid4())]
    evidence_id = str(uuid4())
    buffer_id = str(uuid4())
    audit_id = str(uuid4())

    feature_summary = {
        "schema_version": "vision_feature.metadata.v1",
        "feature_kind": "metadata_only",
        "source": source,
        "sha256": sha256,
        "mime": mime,
        "width": width,
        "height": height,
        "source_display_width": source_display_width,
        "source_display_height": source_display_height,
        "thumbnail_max_width": thumbnail_max_width,
        "byte_size": size_bytes,
        "comparable_for_identity": bool(signature_summary),
        "comparable_signature_feature_ref": signature_feature_id,
        "pending_reason": (
            "local comparable visual signature created; VLM/OCR extraction still pending"
            if signature_summary
            else "no comparable visual feature available because raw image ref could not be resolved"
        ),
    }
    attachment_ref = {
        "attachment_id": attachment_id,
        "kind": "image",
        "source": source,
        "raw_ref": raw_ref,
        "mime": mime,
        "sha256": sha256,
        "width": width,
        "height": height,
        "source_display_width": source_display_width,
        "source_display_height": source_display_height,
        "thumbnail_max_width": thumbnail_max_width,
        "raw_available": raw_available,
        "vision_reader_status": status,
    }
    observation_summary = {
        "schema_version": "memory_observation.vision.v1",
        "attachment": attachment_ref,
        "extraction_status": status,
        "raw_payload_stored_in_event": False,
        "raw_payload_returned_in_debug": False,
        "feature_refs": feature_ids,
    }
    entity_candidate_refs: list[str] = []

    with sqlite3.connect(db_path()) as db:
        signature_matches = (
            recent_visual_signature_matches(db, str(signature_summary.get("average_hash")))
            if signature_summary
            else []
        )
        if backup_id:
            db.execute(
                """
                INSERT INTO raw_backups (
                    backup_id, modality, storage_ref, size_bytes, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (backup_id, "vision", raw_ref, size_bytes, None, created_at),
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
                "vision",
                source,
                _json_dumps(observation_summary),
                _json_dumps(feature_ids),
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
                "vision",
                "metadata_only",
                None,
                observation_id,
                f"feature://vision/metadata/{feature_id}",
                _json_dumps(feature_summary),
                created_at,
            ),
        )
        if signature_summary and signature_feature_id:
            signature_summary.update(
                {
                    "source": source,
                    "sha256": sha256,
                    "mime": mime,
                    "width": width,
                    "height": height,
                    "source_display_width": source_display_width,
                    "source_display_height": source_display_height,
                    "thumbnail_max_width": thumbnail_max_width,
                    "byte_size": size_bytes,
                    "raw_ref": raw_ref,
                    "raw_payload_stored_in_event": False,
                    "raw_payload_returned_in_debug": False,
                }
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
                    signature_feature_id,
                    "vision",
                    "visual_signature",
                    None,
                    observation_id,
                    f"feature://vision/signature/{signature_feature_id}",
                    _json_dumps(signature_summary),
                    created_at,
                ),
            )
            db.execute(
                """
                INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), signature_feature_id, observation_id, "feature-of", 1.0, created_at),
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
        if signature_summary and signature_feature_id:
            entity_candidate_refs.append(
                create_visual_candidate_entity(
                    db,
                    source=source,
                    observation_id=observation_id,
                    feature_refs=feature_ids,
                    signature_summary=signature_summary,
                    matches=signature_matches,
                    created_at=created_at,
                )
            )
        db.execute(
            """
            INSERT INTO memory_visual_evidence (
                evidence_id, source_event_id, attachment_id, source, raw_ref,
                backup_id, observation_id, feature_refs_json,
                entity_candidate_refs_json, mime, sha256, width, height,
                source_display_width, source_display_height, thumbnail_max_width,
                raw_available, vision_reader_status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                source_event_id,
                attachment_id,
                source,
                raw_ref,
                backup_id,
                observation_id,
                _json_dumps(feature_ids),
                _json_dumps(entity_candidate_refs),
                mime,
                sha256,
                width,
                height,
                source_display_width,
                source_display_height,
                thumbnail_max_width,
                1 if raw_available else 0,
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
                "consolidation_buffer",
                "visual_evidence",
                "pending",
                _json_dumps([source_event_id] if source_event_id else []),
                _json_dumps([evidence_id, observation_id]),
                _json_dumps(feature_ids),
                _json_dumps(entity_candidate_refs),
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
                "visual_evidence.created",
                _json_dumps(
                    {
                        "source": source,
                        "attachment_id": attachment_id,
                        "observation_id": observation_id,
                        "feature_ids": feature_ids,
                        "entity_candidate_refs": entity_candidate_refs,
                        "visual_signature_feature_id": signature_feature_id,
                        "visual_signature_match_count": len(signature_matches),
                        "backup_id": backup_id,
                        "source_display_width": source_display_width,
                        "source_display_height": source_display_height,
                        "thumbnail_max_width": thumbnail_max_width,
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
        "feature_refs": feature_ids,
        "entity_candidate_refs": entity_candidate_refs,
        "backup_id": backup_id,
        "source_display_width": source_display_width,
        "source_display_height": source_display_height,
        "thumbnail_max_width": thumbnail_max_width,
        "consolidation_buffer_id": buffer_id,
        "audit_id": audit_id,
        "raw_payload_returned": False,
    }
