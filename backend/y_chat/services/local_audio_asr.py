from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import runtime_sqlite_path
from ..memory import create_text_evidence_record, now_iso
from .memory_evidence_common import json_dumps
from .memory_evidence_query import parse_json_field
from .model_cache import MODEL_CACHE_DIR
from .runtime_refs import runtime_ref_to_path


MODEL_DIR = MODEL_CACHE_DIR / "Systran__faster-whisper-base"
_WHISPER_MODEL_CLASS: Any | None = None
_MODEL: Any | None = None


def asr_ready() -> bool:
    return (MODEL_DIR / "config.json").exists() and (MODEL_DIR / "model.bin").exists()


def transcribe_audio_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    secondary_confirmed = bool(payload.get("secondary_confirmed", False))
    if not secondary_confirmed:
        return {"ok": False, "called": False, "message": "secondary confirmation is required for local audio ASR"}
    if not asr_ready():
        return {
            "ok": False,
            "called": False,
            "message": "faster-whisper base model is not downloaded",
            "model_path": str(MODEL_DIR),
            "raw_payload_returned": False,
            "api_key_returned": False,
        }

    evidence_id = str(payload.get("evidence_id") or "").strip()
    evidence = audio_evidence_by_id(evidence_id) if evidence_id else latest_extractable_audio_evidence()
    if not evidence:
        return {"ok": False, "called": False, "message": "no extractable runtime:// audio evidence is available"}
    audio_path = runtime_ref_to_path(str(evidence["raw_ref"]))
    if not audio_path.exists():
        return {"ok": False, "called": False, "message": "raw audio file is missing"}

    transcript, language, duration = _transcribe(audio_path)
    refs = _record_audio_transcript(evidence, transcript, language, duration)
    return {
        "ok": True,
        "called": True,
        "evidence_id": evidence["evidence_id"],
        "provider": "local_faster_whisper",
        "model": "Systran/faster-whisper-base",
        "transcript_chars": len(transcript),
        "transcript_hash": _text_hash(transcript),
        "language": language,
        "duration_seconds": duration,
        **refs,
        "raw_payload_returned": False,
        "api_key_returned": False,
    }


def latest_extractable_audio_evidence() -> dict[str, Any] | None:
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT evidence_id, source_event_id, attachment_id, source, raw_ref,
                   observation_id, feature_refs_json, transcript_observation_id,
                   mime, sha256, duration_ms, size_bytes, raw_available,
                   audio_reader_status, transcript_status
            FROM memory_audio_evidence
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


def audio_evidence_by_id(evidence_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(runtime_sqlite_path()) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            """
            SELECT evidence_id, source_event_id, attachment_id, source, raw_ref,
                   observation_id, feature_refs_json, transcript_observation_id,
                   mime, sha256, duration_ms, size_bytes, raw_available,
                   audio_reader_status, transcript_status
            FROM memory_audio_evidence
            WHERE evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()
    return dict(row) if row else None


def _transcribe(audio_path: Path) -> tuple[str, str, float]:
    model = _asr_model()
    segments, info = model.transcribe(str(audio_path), beam_size=1)
    texts = [segment.text.strip() for segment in segments if segment.text.strip()]
    return " ".join(texts).strip(), str(getattr(info, "language", "unknown") or "unknown"), float(
        getattr(info, "duration", 0.0) or 0.0
    )


def _asr_model() -> Any:
    global _MODEL, _WHISPER_MODEL_CLASS
    if _WHISPER_MODEL_CLASS is None:
        from faster_whisper import WhisperModel

        _WHISPER_MODEL_CLASS = WhisperModel
    if _MODEL is None:
        _MODEL = _WHISPER_MODEL_CLASS(str(MODEL_DIR), device="cpu", compute_type="int8", local_files_only=True)
    return _MODEL


def _record_audio_transcript(evidence: dict[str, Any], transcript: str, language: str, duration_seconds: float) -> dict[str, Any]:
    created_at = now_iso()
    feature_id = str(uuid4())
    audit_id = str(uuid4())
    feature_refs = _append_unique(parse_json_field(evidence.get("feature_refs_json"), []), feature_id)
    text_refs = None
    if transcript:
        text_refs = create_text_evidence_record(
            {
                "source": "transcript",
                "source_event_id": evidence.get("source_event_id"),
                "text": transcript,
                "language": language,
                "text_reader_status": "observed",
            }
        )
    summary = {
        "schema_version": "audio_feature.asr.v1",
        "feature_kind": "audio_asr_transcript",
        "provider": "local_faster_whisper",
        "model": "Systran/faster-whisper-base",
        "evidence_id": evidence["evidence_id"],
        "source_observation_id": evidence.get("observation_id"),
        "language": language,
        "duration_seconds": duration_seconds,
        "transcript_hash": _text_hash(transcript),
        "transcript_chars": len(transcript),
        "auxiliary_text_evidence_id": text_refs.get("evidence_id") if text_refs else None,
        "text_auxiliary_only": True,
        "raw_audio_sent_to_deepseek": False,
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
            (feature_id, "audio", "audio_asr_transcript", None, evidence.get("observation_id"), f"feature://audio/asr/{feature_id}", json_dumps(summary), created_at),
        )
        db.execute(
            """
            UPDATE memory_audio_evidence
            SET feature_refs_json = ?, audio_reader_status = ?, transcript_status = ?,
                transcript_observation_id = ?
            WHERE evidence_id = ?
            """,
            (
                json.dumps(feature_refs, ensure_ascii=True),
                "transcribed" if transcript else "failed",
                "provided" if transcript else "failed",
                text_refs.get("observation_id") if text_refs else evidence.get("transcript_observation_id"),
                evidence["evidence_id"],
            ),
        )
        if evidence.get("observation_id"):
            db.execute(
                "UPDATE memory_observations SET feature_refs_json = ? WHERE observation_id = ?",
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
            (str(uuid4()), feature_id, evidence["evidence_id"], "transcript-of", 0.8, created_at),
        )
        if text_refs and evidence.get("observation_id"):
            db.execute(
                """
                INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), text_refs["observation_id"], evidence["observation_id"], "transcript-of", 0.8, created_at),
            )
        db.execute(
            """
            INSERT INTO memory_audit_log (audit_id, record_id, action, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                evidence["evidence_id"],
                "audio_evidence.transcribed",
                json_dumps(
                    {
                        "feature_id": feature_id,
                        "feature_refs": feature_refs,
                        "model": "Systran/faster-whisper-base",
                        "transcript_hash": summary["transcript_hash"],
                        "transcript_chars": len(transcript),
                        "raw_payload_returned": False,
                    }
                ),
                created_at,
            ),
        )
    return {
        "feature_id": feature_id,
        "feature_refs": feature_refs,
        "auxiliary_text_evidence_id": text_refs.get("evidence_id") if text_refs else None,
        "auxiliary_text_observation_id": text_refs.get("observation_id") if text_refs else None,
        "audit_id": audit_id,
    }


def _append_unique(values: list[Any], extra: Any) -> list[str]:
    result = [str(value) for value in values if str(value)]
    extra_value = str(extra)
    if extra_value not in result:
        result.append(extra_value)
    return result


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
