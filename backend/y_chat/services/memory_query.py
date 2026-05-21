from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable

from .memory_contracts import (
    ATTACHMENT_REF_CONTRACT,
    AUDIO_READER_STATUS,
    MEMORY_LAYER_CONTRACTS,
    MEMORY_MODALITY_CONTRACTS,
    TEXT_READER_STATUS,
    VISION_READER_STATUS,
)
from .memory_store import db_path, ensure_memory_db, list_table_rows


def memory_status_payload(memory_enabled_fn: Callable[[], bool]) -> dict[str, Any]:
    ensure_memory_db()
    with sqlite3.connect(db_path()) as db:
        db.row_factory = sqlite3.Row
        manual_count = db.execute("SELECT COUNT(*) AS count FROM memory_items").fetchone()["count"]
        record_count = db.execute("SELECT COUNT(*) AS count FROM memory_records").fetchone()["count"]
        audit_count = db.execute("SELECT COUNT(*) AS count FROM memory_audit_log").fetchone()["count"]
        observations_count = db.execute("SELECT COUNT(*) AS count FROM memory_observations").fetchone()["count"]
        entities_count = db.execute("SELECT COUNT(*) AS count FROM memory_entities").fetchone()["count"]
        features_count = db.execute("SELECT COUNT(*) AS count FROM memory_features").fetchone()["count"]
        links_count = db.execute("SELECT COUNT(*) AS count FROM memory_links").fetchone()["count"]
        review_count = db.execute("SELECT COUNT(*) AS count FROM memory_review_queue").fetchone()["count"]
        consolidation_buffer_count = db.execute(
            "SELECT COUNT(*) AS count FROM memory_consolidation_buffer"
        ).fetchone()["count"]
        raw_backup_count = db.execute("SELECT COUNT(*) AS count FROM raw_backups").fetchone()["count"]
        visual_evidence_count = db.execute(
            "SELECT COUNT(*) AS count FROM memory_visual_evidence"
        ).fetchone()["count"]
        text_evidence_count = db.execute(
            "SELECT COUNT(*) AS count FROM memory_text_evidence"
        ).fetchone()["count"]
        audio_evidence_count = db.execute(
            "SELECT COUNT(*) AS count FROM memory_audio_evidence"
        ).fetchone()["count"]

    return {
        "manual_enabled": memory_enabled_fn(),
        "automatic_writes_enabled": False,
        "capture_enabled": {
            "vision": False,
            "audio": False,
            "screen": False,
            "voice": False,
        },
        "manual_items_count": manual_count,
        "records_count": record_count,
        "observations_count": observations_count,
        "entities_count": entities_count,
        "features_count": features_count,
        "links_count": links_count,
        "review_count": review_count,
        "consolidation_buffer_count": consolidation_buffer_count,
        "visual_evidence_count": visual_evidence_count,
        "text_evidence_count": text_evidence_count,
        "audio_evidence_count": audio_evidence_count,
        "raw_backup_count": raw_backup_count,
        "audit_count": audit_count,
        "formal_tables_ready": True,
        "multimodal_tables_ready": True,
        "visual_evidence_tables_ready": True,
        "text_evidence_tables_ready": True,
        "audio_evidence_tables_ready": True,
        "consolidation_buffer_ready": True,
        "manual_notes_legacy": True,
    }


def list_memory_records(limit: int = 100) -> list[dict[str, Any]]:
    ensure_memory_db()
    safe_limit = max(1, min(limit, 200))
    with sqlite3.connect(db_path()) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT record_id, kind, layer, status, version, content_json,
                   evidence_json, supersedes_record_id, created_at, updated_at
            FROM memory_records
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [
        {
            **dict(row),
            "content": json.loads(row["content_json"]),
            "evidence": json.loads(row["evidence_json"]),
            "content_json": None,
            "evidence_json": None,
        }
        for row in rows
    ]


def list_memory_review_queue(limit: int = 100) -> list[dict[str, Any]]:
    return list_table_rows("memory_review_queue", "created_at", limit)


def list_memory_audit_log(limit: int = 100) -> list[dict[str, Any]]:
    rows = list_table_rows("memory_audit_log", "created_at", limit)
    result: list[dict[str, Any]] = []
    for row in rows:
        payload_json = row.get("payload_json")
        payload: Any = {}
        if isinstance(payload_json, str) and payload_json:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {"unparsed_payload": payload_json}
        result.append({**row, "payload": payload, "payload_json": None})
    return result


def memory_shell_payload(
    *,
    list_consolidation_buffer_fn: Callable[[], list[dict[str, Any]]],
    list_visual_evidence_fn: Callable[[], list[dict[str, Any]]],
    list_text_evidence_fn: Callable[[], list[dict[str, Any]]],
    list_audio_evidence_fn: Callable[[], list[dict[str, Any]]],
    vision_status_payload_fn: Callable[[], dict[str, Any]],
    text_status_payload_fn: Callable[[], dict[str, Any]],
    audio_status_payload_fn: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    return {
        "automatic_writes_enabled": False,
        "capture_enabled": {
            "vision": False,
            "audio": False,
            "screen": False,
            "voice": False,
        },
        "observations": list_table_rows("memory_observations"),
        "entities": list_table_rows("memory_entities", "updated_at"),
        "features": list_table_rows("memory_features"),
        "links": list_table_rows("memory_links"),
        "review_queue": list_table_rows("memory_review_queue"),
        "consolidation_buffer": list_consolidation_buffer_fn(),
        "raw_backups": list_table_rows("raw_backups"),
        "visual_evidence": list_visual_evidence_fn(),
        "text_evidence": list_text_evidence_fn(),
        "audio_evidence": list_audio_evidence_fn(),
        "attachment_ref_contract": ATTACHMENT_REF_CONTRACT,
        "vision_reader": vision_status_payload_fn(),
        "text_reader": text_status_payload_fn(),
        "audio_reader": audio_status_payload_fn(),
    }


def memory_contract_payload() -> dict[str, Any]:
    return {
        "unified_memory": True,
        "scene_isolation_allowed": False,
        "automatic_writes_enabled": False,
        "real_capture_enabled": False,
        "text_only_identity_allowed": False,
        "deep_knowledge_default": False,
        "layers": MEMORY_LAYER_CONTRACTS,
        "modalities": MEMORY_MODALITY_CONTRACTS,
        "attachment_ref": ATTACHMENT_REF_CONTRACT,
        "vision_reader": VISION_READER_STATUS,
        "visual_evidence": {
            "schema_ready": True,
            "writes_enabled": False,
            "raw_bytes_returned": False,
            "sources": ["manual_file", "paste_image", "screen_frame"],
            "links_to": ["raw_backups", "memory_observations", "memory_features", "memory_entities"],
        },
        "text_evidence": {
            "schema_ready": True,
            "writes_enabled": True,
            "raw_bytes_returned": False,
            "sources": ["user_command", "ocr_text", "transcript", "manual_note"],
            "links_to": ["memory_observations", "memory_features", "memory_consolidation_buffer"],
        },
        "audio_evidence": {
            "schema_ready": True,
            "writes_enabled": False,
            "raw_bytes_returned": False,
            "sources": ["voice_clip", "audio_file"],
            "links_to": ["raw_backups", "memory_observations", "memory_features", "memory_consolidation_buffer"],
        },
        "consolidation_buffer": {
            "schema_ready": True,
            "writes_enabled": False,
            "sleep_consolidation_enabled": False,
            "purpose": "Inspect-only transition layer between short-term evidence and future sleep consolidation.",
        },
    }
