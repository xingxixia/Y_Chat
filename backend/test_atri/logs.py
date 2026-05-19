from __future__ import annotations

import re
from typing import Any

from .config import RUNTIME_DIR


LOG_DIR = RUNTIME_DIR / "logs"

REDACTED = "[REDACTED]"

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
    r"(?i)([\"']?\b(api[_-]?key|x-api-key|token|access[_-]?token|refresh[_-]?token|secret|password)\b[\"']?)"
    r"(\s*[:=]\s*)"
    r"([\"']?)([^\"'\s,;}]+)([\"']?)"
)
AUTH_HEADER_RE = re.compile(r"(?i)\b(authorization)(\s*[:=]\s*)([^\s,;]+(?:\s+[^\s,;]+)?)")
BEARER_TOKEN_RE = re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]{8,})")


def clean_log_line(line: str) -> str:
    cleaned = line.lstrip("\ufeff")
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


def redact_log_line(line: str) -> str:
    cleaned = clean_log_line(line)
    redacted = AUTH_HEADER_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", cleaned)
    redacted = BEARER_TOKEN_RE.sub(lambda match: f"{match.group(1)} {REDACTED}", redacted)
    return SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(3)}{match.group(4)}{REDACTED}{match.group(6)}",
        redacted,
    )


def log_status_payload() -> dict[str, Any]:
    logs: list[dict[str, Any]] = []
    if not LOG_DIR.exists():
        return {"logs": logs}

    for path in sorted(LOG_DIR.glob("*.log"), key=lambda item: item.name.lower()):
        kind = "error" if ".err." in path.name else "output"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tail = [redact_log_line(line) for line in text.splitlines()[-8:]]
            stat = path.stat()
            logs.append(
                {
                    "name": path.name,
                    "kind": kind,
                    "bytes": stat.st_size,
                    "tail": tail,
                }
            )
        except OSError as exc:
            logs.append(
                {
                    "name": path.name,
                    "kind": kind,
                    "bytes": 0,
                    "tail": [f"failed to read log: {exc}"],
                }
            )
    return {"logs": logs}
