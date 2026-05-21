from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from uuid import uuid4

from ..config import RUNTIME_DIR
from ..shared.contracts import RUNTIME_REF_PREFIX

try:
    from PIL import Image
except ImportError:  # pragma: no cover - dependency is optional at import time
    Image = None  # type: ignore[assignment]


def stable_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def runtime_ref_to_path(raw_ref: str) -> Path | None:
    if not raw_ref.startswith(RUNTIME_REF_PREFIX):
        return None
    relative = unquote(raw_ref[len(RUNTIME_REF_PREFIX):]).replace("/", "\\")
    path = (RUNTIME_DIR / relative).resolve()
    runtime_root = RUNTIME_DIR.resolve()
    if runtime_root not in path.parents and path != runtime_root:
        return None
    return path


def visual_signature_from_raw_ref(raw_ref: str) -> dict[str, Any] | None:
    if Image is None:
        return None
    path = runtime_ref_to_path(raw_ref)
    if path is None or not path.exists():
        return None
    try:
        with Image.open(path) as image:
            return {
                "schema_version": "vision_feature.signature.v1",
                "feature_kind": "visual_signature",
                "signature_type": "average_hash_color_histogram",
                "average_hash": _average_hash_bits(image),
                "color_histogram": _histogram_signature(image),
                "comparable_for_identity": True,
                "identity_status": "candidate_only",
            }
    except Exception:
        return None


def recent_visual_signature_matches(
    db: sqlite3.Connection,
    average_hash: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        SELECT feature_id, summary_json, created_at
        FROM memory_features
        WHERE modality = ? AND feature_kind = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        ("vision", "visual_signature", limit),
    ).fetchall()
    matches: list[dict[str, Any]] = []
    for row in rows:
        try:
            summary = json.loads(row["summary_json"])
        except json.JSONDecodeError:
            continue
        other_hash = str(summary.get("average_hash", ""))
        distance = _hamming_distance(average_hash, other_hash)
        if distance <= 10:
            matches.append(
                {
                    "feature_id": row["feature_id"],
                    "distance": distance,
                    "created_at": row["created_at"],
                }
            )
    return sorted(matches, key=lambda item: item["distance"])[:5]


def create_visual_candidate_entity(
    db: sqlite3.Connection,
    *,
    source: str,
    observation_id: str,
    feature_refs: list[str],
    signature_summary: dict[str, Any],
    matches: list[dict[str, Any]],
    created_at: str,
) -> str:
    entity_id = str(uuid4())
    confidence = 0.55 if matches else 0.35
    summary = {
        "schema_version": "memory_entity.visual_candidate.v1",
        "kind": "visual_candidate",
        "source": source,
        "status": "candidate" if matches else "temporary",
        "candidate_only": True,
        "identity_confirmed": False,
        "match_basis": "average_hash_color_histogram",
        "matched_feature_refs": matches,
        "feature_refs": feature_refs,
        "average_hash": signature_summary.get("average_hash"),
        "color_histogram": signature_summary.get("color_histogram"),
        "warning": "comparable local signature only; not a confirmed object identity",
    }
    db.execute(
        """
        INSERT INTO memory_entities (
            entity_id, kind, label, status, confidence, summary_json,
            feature_refs_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            "visual_candidate",
            None,
            summary["status"],
            confidence,
            _json_dumps(summary),
            _json_dumps(feature_refs),
            created_at,
            created_at,
        ),
    )
    db.execute(
        """
        INSERT INTO memory_links (link_id, from_id, to_id, relation, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid4()), entity_id, observation_id, "candidate-from", confidence, created_at),
    )
    return entity_id


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _average_hash_bits(image: Any) -> str:
    grayscale = image.convert("L").resize((8, 8))
    pixels = list(grayscale.getdata())
    avg = sum(pixels) / len(pixels)
    return "".join("1" if value >= avg else "0" for value in pixels)


def _histogram_signature(image: Any) -> list[int]:
    quantized = image.convert("RGB").resize((32, 32))
    bins = [0] * 12
    for red, green, blue in quantized.getdata():
        bins[min(red // 64, 3)] += 1
        bins[4 + min(green // 64, 3)] += 1
        bins[8 + min(blue // 64, 3)] += 1
    total = max(1, sum(bins))
    return [round(value * 1000 / total) for value in bins]


def _hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        return max(len(left), len(right))
    return sum(1 for a, b in zip(left, right) if a != b)
