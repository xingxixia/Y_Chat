from __future__ import annotations

import sqlite3
from typing import Any

from .memory_evidence_common import (
    ATTACHMENT_REF_CONTRACT,
    AUDIO_READER_STATUS,
    TEXT_READER_STATUS,
    VISION_READER_STATUS,
    db_path,
    ensure_memory_db,
    list_table_rows,
    parse_json_field,
)


def list_visual_evidence(limit: int = 100) -> list[dict[str, Any]]:
    rows = list_table_rows("memory_visual_evidence", "created_at", limit)
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                **row,
                "raw_available": bool(row.get("raw_available")),
                "feature_refs": parse_json_field(row.get("feature_refs_json"), []),
                "entity_candidate_refs": parse_json_field(row.get("entity_candidate_refs_json"), []),
                "feature_refs_json": None,
                "entity_candidate_refs_json": None,
            }
        )
    return result


def list_text_evidence(limit: int = 100) -> list[dict[str, Any]]:
    rows = list_table_rows("memory_text_evidence", "created_at", limit)
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                **row,
                "feature_refs": parse_json_field(row.get("feature_refs_json"), []),
                "feature_refs_json": None,
            }
        )
    return result


def list_audio_evidence(limit: int = 100) -> list[dict[str, Any]]:
    rows = list_table_rows("memory_audio_evidence", "created_at", limit)
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                **row,
                "raw_available": bool(row.get("raw_available")),
                "feature_refs": parse_json_field(row.get("feature_refs_json"), []),
                "feature_refs_json": None,
            }
        )
    return result


def list_consolidation_buffer(limit: int = 100) -> list[dict[str, Any]]:
    rows = list_table_rows("memory_consolidation_buffer", "updated_at", limit)
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                **row,
                "review_required": bool(row.get("review_required")),
                "source_refs": parse_json_field(row.get("source_refs_json"), []),
                "evidence_refs": parse_json_field(row.get("evidence_refs_json"), []),
                "feature_refs": parse_json_field(row.get("feature_refs_json"), []),
                "entity_candidate_refs": parse_json_field(row.get("entity_candidate_refs_json"), []),
                "source_refs_json": None,
                "evidence_refs_json": None,
                "feature_refs_json": None,
                "entity_candidate_refs_json": None,
            }
        )
    return result


def consolidation_buffer_payload() -> dict[str, Any]:
    return {
        "automatic_writes_enabled": False,
        "sleep_consolidation_enabled": False,
        "schema_ready": True,
        "buffer": list_consolidation_buffer(),
    }


def vision_status_payload() -> dict[str, Any]:
    ensure_memory_db()
    with sqlite3.connect(db_path()) as db:
        db.row_factory = sqlite3.Row
        visual_evidence_count = db.execute(
            "SELECT COUNT(*) AS count FROM memory_visual_evidence"
        ).fetchone()["count"]
        pending_count = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_visual_evidence
            WHERE vision_reader_status = 'pending'
            """
        ).fetchone()["count"]
    return {
        **VISION_READER_STATUS,
        "visual_evidence_count": visual_evidence_count,
        "pending_extractions": pending_count,
        "attachment_ref_contract": ATTACHMENT_REF_CONTRACT,
    }


def text_status_payload() -> dict[str, Any]:
    ensure_memory_db()
    with sqlite3.connect(db_path()) as db:
        db.row_factory = sqlite3.Row
        text_evidence_count = db.execute(
            "SELECT COUNT(*) AS count FROM memory_text_evidence"
        ).fetchone()["count"]
    return {
        **TEXT_READER_STATUS,
        "text_evidence_count": text_evidence_count,
    }


def audio_status_payload() -> dict[str, Any]:
    ensure_memory_db()
    with sqlite3.connect(db_path()) as db:
        db.row_factory = sqlite3.Row
        audio_evidence_count = db.execute(
            "SELECT COUNT(*) AS count FROM memory_audio_evidence"
        ).fetchone()["count"]
        pending_transcripts = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_audio_evidence
            WHERE transcript_status = 'pending'
            """
        ).fetchone()["count"]
    return {
        **AUDIO_READER_STATUS,
        "audio_evidence_count": audio_evidence_count,
        "pending_transcripts": pending_transcripts,
    }
