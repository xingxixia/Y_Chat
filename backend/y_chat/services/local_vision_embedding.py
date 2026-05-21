from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from ..config import runtime_sqlite_path
from ..memory import now_iso
from .memory_evidence_common import json_dumps
from .memory_evidence_query import parse_json_field
from .model_cache import MODEL_CACHE_DIR
from .runtime_refs import runtime_ref_to_path
from .vision_evidence import latest_extractable_visual_evidence, visual_evidence_by_id


MODEL_DIR = MODEL_CACHE_DIR / "openai__clip-vit-base-patch32"
_PROCESSOR: Any | None = None
_MODEL: Any | None = None
_CLIP_PROCESSOR_CLASS: Any | None = None
_CLIP_MODEL_CLASS: Any | None = None
_TORCH: Any | None = None


def clip_ready() -> bool:
    return (MODEL_DIR / "pytorch_model.bin").exists()


def embed_visual_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    secondary_confirmed = bool(payload.get("secondary_confirmed", False))
    if not secondary_confirmed:
        return {"ok": False, "called": False, "message": "secondary confirmation is required for local vision embedding"}
    if not clip_ready():
        return {
            "ok": False,
            "called": False,
            "message": "CLIP vision embedding model is not downloaded",
            "model_path": str(MODEL_DIR),
            "raw_payload_returned": False,
        }

    evidence_id = str(payload.get("evidence_id") or "").strip()
    evidence = visual_evidence_by_id(evidence_id) if evidence_id else latest_extractable_visual_evidence()
    if not evidence:
        return {"ok": False, "called": False, "message": "no extractable runtime:// visual evidence is available"}
    image_path = runtime_ref_to_path(str(evidence["raw_ref"]))
    if not image_path.exists():
        return {"ok": False, "called": False, "message": "raw image file is missing"}

    vector = _image_embedding(image_path)
    refs = _record_image_embedding(evidence, vector)
    return {
        "ok": True,
        "called": True,
        "evidence_id": evidence["evidence_id"],
        "provider": "local_clip",
        "model": "openai/clip-vit-base-patch32",
        "feature_kind": "image_embedding",
        "embedding_dimensions": len(vector),
        "embedding_hash": _vector_hash(vector),
        **refs,
        "raw_payload_returned": False,
        "api_key_returned": False,
    }


def _image_embedding(image_path: Path) -> list[float]:
    torch = _torch()
    processor, model = _clip()
    with Image.open(image_path) as image:
        inputs = processor(images=image.convert("RGB"), return_tensors="pt")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
    normalized = features / features.norm(dim=-1, keepdim=True)
    return [round(float(value), 8) for value in normalized[0].detach().cpu().tolist()]


def _clip() -> tuple[Any, Any]:
    global _PROCESSOR, _MODEL, _CLIP_MODEL_CLASS, _CLIP_PROCESSOR_CLASS
    if _CLIP_PROCESSOR_CLASS is None or _CLIP_MODEL_CLASS is None:
        from transformers import CLIPModel, CLIPProcessor

        _CLIP_PROCESSOR_CLASS = CLIPProcessor
        _CLIP_MODEL_CLASS = CLIPModel
    if _PROCESSOR is None:
        _PROCESSOR = _CLIP_PROCESSOR_CLASS.from_pretrained(str(MODEL_DIR), local_files_only=True)
    if _MODEL is None:
        _MODEL = _CLIP_MODEL_CLASS.from_pretrained(str(MODEL_DIR), local_files_only=True)
        _MODEL.eval()
    return _PROCESSOR, _MODEL


def _torch() -> Any:
    global _TORCH
    if _TORCH is None:
        import torch

        _TORCH = torch
    return _TORCH


def _record_image_embedding(evidence: dict[str, Any], vector: list[float]) -> dict[str, Any]:
    created_at = now_iso()
    feature_id = str(uuid4())
    audit_id = str(uuid4())
    feature_refs = _append_unique(parse_json_field(evidence.get("feature_refs_json"), []), feature_id)
    summary = {
        "schema_version": "vision_feature.embedding.v1",
        "feature_kind": "image_embedding",
        "provider": "local_clip",
        "model": "openai/clip-vit-base-patch32",
        "evidence_id": evidence["evidence_id"],
        "source_observation_id": evidence.get("observation_id"),
        "dimensions": len(vector),
        "embedding_hash": _vector_hash(vector),
        "comparable_for_identity": True,
        "identity_status": "candidate_only",
        "text_auxiliary_only": True,
        "raw_image_sent_to_deepseek": False,
        "image_generation_supported": False,
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
                "image_embedding",
                None,
                evidence.get("observation_id"),
                f"feature://vision/embedding/{feature_id}",
                json_dumps(summary),
                created_at,
            ),
        )
        db.execute(
            """
            UPDATE memory_visual_evidence
            SET feature_refs_json = ?, vision_reader_status = ?
            WHERE evidence_id = ?
            """,
            (json.dumps(feature_refs, ensure_ascii=True), "extracted", evidence["evidence_id"]),
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
            (str(uuid4()), feature_id, evidence["evidence_id"], "embedding-of", 1.0, created_at),
        )
        db.execute(
            """
            INSERT INTO memory_audit_log (audit_id, record_id, action, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                evidence["evidence_id"],
                "visual_evidence.image_embedded",
                json_dumps(
                    {
                        "feature_id": feature_id,
                        "feature_refs": feature_refs,
                        "model": "openai/clip-vit-base-patch32",
                        "embedding_hash": summary["embedding_hash"],
                        "raw_payload_returned": False,
                    }
                ),
                created_at,
            ),
        )
    return {"feature_id": feature_id, "feature_refs": feature_refs, "audit_id": audit_id}


def _append_unique(values: list[Any], extra: Any) -> list[str]:
    result = [str(value) for value in values if str(value)]
    extra_value = str(extra)
    if extra_value not in result:
        result.append(extra_value)
    return result


def _vector_hash(vector: list[float]) -> str:
    payload = ",".join(f"{value:.8f}" for value in vector)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
