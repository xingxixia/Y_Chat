from __future__ import annotations

import re
from typing import Any


REDACTED = "[REDACTED]"
REDACTED_MULTIMODAL = "[REDACTED_MULTIMODAL_PAYLOAD]"
MAX_REDACTION_DEPTH = 8

REDACTION_PATTERNS = [
    "api_key assignments",
    "x-api-key assignments",
    "authorization headers",
    "bearer tokens",
    "token assignments",
    "secret assignments",
    "password assignments",
    "cookie headers",
    "raw multimodal payload fields",
    "data URI multimodal payloads",
]
DISPLAY_CLEANUP = [
    "UTF-8 BOM",
    "ANSI color escapes",
    "stray ANSI fragments",
    "common UTF-8 mojibake",
    "control characters",
]

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_FRAGMENT_RE = re.compile(r"^\[[0-?]*[ -/]*[@-~]\s*")
ANSI_START_RE = re.compile(r"\x1b.*$")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2", "\u00ef\u00bb\u00bf")
COMMON_DISPLAY_FIXES = {
    "\u00e2\u009e\u009c": "\u279c",
    "\u9253?": "\u279c",
    "\ufffd": "",
}

SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)([\"']?\b(api[_-]?key|x-api-key|token|access[_-]?token|refresh[_-]?token|secret|password|credential)\b[\"']?)"
    r"(\s*[:=]\s*)"
    r"([\"']?)([^\"'\s,;}]+)([\"']?)"
)
AUTH_HEADER_RE = re.compile(r"(?i)\b(authorization)(\s*[:=]\s*)([^\s,;]+(?:\s+[^\s,;]+)?)")
COOKIE_HEADER_RE = re.compile(r"(?i)\b(cookie|set-cookie)(\s*[:=]\s*)([^\r\n]+)")
BEARER_TOKEN_RE = re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]{8,})")
DATA_URI_RE = re.compile(r"(?i)^data:(image|audio|video)/")

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "x-api-key",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
)
RAW_MULTIMODAL_KEYS = {
    "image",
    "images",
    "audio",
    "video",
    "waveform",
    "screenshot",
    "frame",
    "crop",
    "bytes",
    "blob",
    "base64",
    "raw_payload",
    "raw_bytes",
    "image_bytes",
    "audio_bytes",
    "video_bytes",
}


def normalize_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def key_is_sensitive(key: Any) -> bool:
    normalized = normalize_key(key)
    return any(part.replace("-", "_") in normalized for part in SENSITIVE_KEY_PARTS)


def key_is_raw_multimodal(key: Any) -> bool:
    return normalize_key(key) in RAW_MULTIMODAL_KEYS


def clean_text(value: str) -> str:
    cleaned = value.lstrip("\ufeff")
    cleaned = ANSI_ESCAPE_RE.sub("", cleaned)
    cleaned = ANSI_START_RE.sub("", cleaned)
    cleaned = ANSI_FRAGMENT_RE.sub("", cleaned)

    try:
        if any(marker in cleaned for marker in MOJIBAKE_MARKERS):
            cleaned = cleaned.encode("latin1").decode("utf-8").lstrip("\ufeff")
    except UnicodeError:
        pass

    for bad, fixed in COMMON_DISPLAY_FIXES.items():
        cleaned = cleaned.replace(bad, fixed)

    cleaned = ANSI_ESCAPE_RE.sub("", cleaned)
    cleaned = ANSI_START_RE.sub("", cleaned)
    cleaned = ANSI_FRAGMENT_RE.sub("", cleaned)
    for bad, fixed in COMMON_DISPLAY_FIXES.items():
        cleaned = cleaned.replace(bad, fixed)

    return CONTROL_CHAR_RE.sub("", cleaned)


def redact_text(value: str) -> tuple[str, bool]:
    cleaned = clean_text(value)
    redacted = AUTH_HEADER_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", cleaned)
    redacted = COOKIE_HEADER_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", redacted)
    redacted = BEARER_TOKEN_RE.sub(lambda match: f"{match.group(1)} {REDACTED}", redacted)
    redacted = SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(3)}{match.group(4)}{REDACTED}{match.group(6)}",
        redacted,
    )
    if DATA_URI_RE.match(redacted):
        return REDACTED_MULTIMODAL, True
    return redacted, redacted != cleaned


def redact_payload(value: Any, *, _depth: int = 0) -> tuple[Any, bool]:
    if _depth >= MAX_REDACTION_DEPTH:
        return "[REDACTED_MAX_DEPTH]", True

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        changed = False
        for key, item in value.items():
            key_text = str(key)
            if key_is_sensitive(key_text):
                redacted[key_text] = REDACTED
                changed = True
            elif key_is_raw_multimodal(key_text):
                redacted[key_text] = REDACTED_MULTIMODAL
                changed = True
            else:
                next_value, next_changed = redact_payload(item, _depth=_depth + 1)
                redacted[key_text] = next_value
                changed = changed or next_changed
        return redacted, changed

    if isinstance(value, list):
        items = []
        changed = False
        for item in value:
            next_value, next_changed = redact_payload(item, _depth=_depth + 1)
            items.append(next_value)
            changed = changed or next_changed
        return items, changed

    if isinstance(value, str):
        return redact_text(value)

    return value, False


def redaction_policy_payload() -> dict[str, Any]:
    return {
        "enabled": True,
        "token": REDACTED,
        "multimodal_token": REDACTED_MULTIMODAL,
        "patterns": REDACTION_PATTERNS,
        "display_cleanup": DISPLAY_CLEANUP,
        "safe_ref_fields_preserved": [
            "raw_ref",
            "image_ref",
            "audio_ref",
            "video_ref",
            "screenshot_ref",
            "frame_ref",
            "attachment_ref",
            "feature_id",
            "evidence_id",
            "sha256",
        ],
    }
