from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:  # pragma: no cover - optional local OCR dependency
    RapidOCR = None  # type: ignore[assignment]

_LOCAL_OCR_ENGINE: Any | None = None


def local_ocr_available() -> bool:
    return RapidOCR is not None


def local_ocr_engine() -> Any:
    global _LOCAL_OCR_ENGINE
    if RapidOCR is None:
        raise RuntimeError("rapidocr_onnxruntime is not installed")
    if _LOCAL_OCR_ENGINE is None:
        _LOCAL_OCR_ENGINE = RapidOCR()
    return _LOCAL_OCR_ENGINE


def extract_with_local_ocr(image_path: Path) -> dict[str, Any]:
    engine = local_ocr_engine()
    result, elapsed = engine(image_path)
    visible_text: list[str] = []
    objects: list[dict[str, Any]] = []
    for item in result or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        box = item[0]
        text = str(item[1] or "").strip()
        score = float(item[2]) if len(item) >= 3 else None
        if not text:
            continue
        visible_text.append(text)
        objects.append({"kind": "text_region", "text": text, "confidence": score, "box": box})
    return {
        "description": "Local OCR extracted visible text from the image." if visible_text else "Local OCR found no readable text.",
        "visible_text": visible_text,
        "objects": objects,
        "uncertainty": "medium" if visible_text else "high",
        "provider": "local_rapidocr",
        "model": "rapidocr_onnxruntime",
        "local_elapsed": elapsed,
    }
