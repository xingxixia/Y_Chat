from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..config import runtime_sqlite_path
from ..events import EventEnvelope
from .local_vision_vlm import MODEL_ID, local_vlm_ready, recognize_visual_evidence
from .visual_freshness import visual_freshness_status
from .vision_evidence import latest_extractable_visual_evidence, visual_evidence_by_id
from .vision_extraction_store import parse_json_list


VISUAL_REQUEST_TERMS = (
    "\u56fe\u50cf",
    "\u56fe\u7247",
    "\u89c6\u89c9",
    "\u5c4f\u5e55",
    "\u622a\u56fe",
    "\u753b\u9762",
    "\u8bc6\u522b",
    "\u770b\u89c1",
    "\u770b\u5230",
    "\u770b\u4e00\u4e0b",
    "\u770b\u4e0b",
    "vlm",
    "image",
    "picture",
    "visual",
    "screen",
    "screenshot",
    "recognize",
    "describe",
    "what do you see",
    "look at",
)


def user_requests_visual_understanding(event: EventEnvelope) -> bool:
    if event.type != "user.command.submitted":
        return False
    payload = event.payload if isinstance(event.payload, dict) else {}
    text = str(payload.get("text") or "").strip().lower()
    if not text:
        return False
    if any(term in text for term in VISUAL_REQUEST_TERMS):
        return True
    return bool(payload.get("image_ref") or payload.get("screenshot_ref") or payload.get("frame_ref"))


def ensure_visual_recognition_for_reasoning(event: EventEnvelope) -> dict[str, Any]:
    """Run the local VLM once when the user explicitly asks about visual content."""
    if not user_requests_visual_understanding(event):
        return {"ok": True, "called": False, "reason": "visual understanding was not requested"}
    if not local_vlm_ready():
        return {
            "ok": False,
            "called": False,
            "not_ready": True,
            "provider": "local_smolvlm",
            "model": MODEL_ID,
            "reason": "local VLM is not ready",
        }

    evidence = _requested_visual_evidence(event) or latest_extractable_visual_evidence()
    if not evidence:
        return {"ok": False, "called": False, "reason": "no extractable visual evidence is available"}
    freshness = visual_freshness_status(evidence.get("created_at"))
    if freshness["stale_for_current_screen"]:
        return {
            "ok": False,
            "called": False,
            "provider": "local_smolvlm",
            "model": MODEL_ID,
            "evidence_id": evidence["evidence_id"],
            "reason": "latest visual evidence is stale for current screen",
            **freshness,
        }
    if _has_local_vlm_feature(evidence):
        return {
            "ok": True,
            "called": False,
            "provider": "local_smolvlm",
            "model": MODEL_ID,
            "evidence_id": evidence["evidence_id"],
            "reason": "latest visual evidence already has local VLM recognition",
        }

    return recognize_visual_evidence(
        {
            "secondary_confirmed": True,
            "evidence_id": evidence["evidence_id"],
            "provider": "local_smolvlm",
            "prompt": (
                "What is visible in this screen image? Describe the UI layout, windows, text areas, "
                "visible objects, and any readable text. Answer with concrete visual details only."
            ),
        }
    )


def _has_local_vlm_feature(evidence: dict[str, Any]) -> bool:
    feature_refs = [str(ref) for ref in parse_json_list(evidence.get("feature_refs_json")) if str(ref)]
    if not feature_refs:
        return False
    placeholders = ",".join("?" for _ in feature_refs)
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            f"""
            SELECT feature_kind, summary_json
            FROM memory_features
            WHERE feature_id IN ({placeholders})
            """,
            feature_refs,
        ).fetchall()
    for row in rows:
        if row["feature_kind"] != "vlm_extracted_text":
            continue
        summary = _parse_summary(row["summary_json"])
        provider = str(summary.get("provider") or "").lower()
        description = str(summary.get("description") or "").strip().lower()
        if "local image recognition" in description and "not image generation" in description:
            continue
        if provider in {"local_smolvlm", "local_vlm", "smolvlm"}:
            return True
        if bool(summary.get("raw_image_processed_locally")) and provider != "local_rapidocr":
            return True
    return False


def _requested_visual_evidence(event: EventEnvelope) -> dict[str, Any] | None:
    payload = event.payload if isinstance(event.payload, dict) else {}
    for key in ("visual_evidence_id", "vision_evidence_id"):
        evidence_id = str(payload.get(key) or "").strip()
        if not evidence_id:
            continue
        evidence = visual_evidence_by_id(evidence_id)
        if evidence and bool(evidence.get("raw_ref")):
            return evidence
    return None


def _parse_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
