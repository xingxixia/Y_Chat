from __future__ import annotations

import sqlite3
from typing import Any

from ..config import runtime_sqlite_path
from .vision_files import runtime_ref_to_path


def latest_visual_evidence() -> dict[str, Any] | None:
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            """
            SELECT evidence_id, attachment_id, raw_ref, mime, sha256, width, height,
                   source, source_event_id, observation_id, feature_refs_json,
                   entity_candidate_refs_json, vision_reader_status, created_at
            FROM memory_visual_evidence
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def latest_extractable_visual_evidence() -> dict[str, Any] | None:
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT evidence_id, attachment_id, raw_ref, mime, sha256, width, height,
                   source, source_event_id, observation_id, feature_refs_json,
                   entity_candidate_refs_json, vision_reader_status, created_at
            FROM memory_visual_evidence
            WHERE raw_available = 1
            ORDER BY created_at DESC
            LIMIT 50
            """
        ).fetchall()
    for row in rows:
        item = dict(row)
        raw_ref = str(item.get("raw_ref") or "")
        if not raw_ref.startswith("runtime://"):
            continue
        try:
            path = runtime_ref_to_path(raw_ref)
        except ValueError:
            continue
        if path.exists():
            return item
    return None


def visual_evidence_by_id(evidence_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            """
            SELECT evidence_id, attachment_id, raw_ref, mime, sha256, width, height,
                   source, source_event_id, observation_id, feature_refs_json,
                   entity_candidate_refs_json, vision_reader_status, created_at
            FROM memory_visual_evidence
            WHERE evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()
    return dict(row) if row else None
