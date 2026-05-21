from typing import Any

from .config import RUNTIME_DIR
from .services.redaction import DISPLAY_CLEANUP, REDACTED, REDACTION_PATTERNS, clean_text, redact_text


LOG_DIR = RUNTIME_DIR / "logs"


def clean_log_line(line: str) -> str:
    return clean_text(line)


def redact_log_line(line: str) -> tuple[str, bool]:
    return redact_text(line)


def log_status_payload() -> dict[str, Any]:
    logs: list[dict[str, Any]] = []
    if not LOG_DIR.exists():
        return {
            "redaction_enabled": True,
            "redaction_token": REDACTED,
            "redaction_patterns": REDACTION_PATTERNS,
            "display_cleanup": DISPLAY_CLEANUP,
            "logs": logs,
        }

    for path in sorted(LOG_DIR.glob("*.log"), key=lambda item: item.name.lower()):
        kind = "error" if ".err." in path.name else "output"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            redacted_count = 0
            tail = []
            for line in text.splitlines()[-8:]:
                redacted_line, was_redacted = redact_log_line(line)
                tail.append(redacted_line)
                if was_redacted:
                    redacted_count += 1
            stat = path.stat()
            logs.append(
                {
                    "name": path.name,
                    "kind": kind,
                    "bytes": stat.st_size,
                    "tail": tail,
                    "redacted_lines": redacted_count,
                    "display_cleaned": True,
                }
            )
        except OSError as exc:
            logs.append(
                {
                    "name": path.name,
                    "kind": kind,
                    "bytes": 0,
                    "tail": [f"failed to read log: {exc}"],
                    "redacted_lines": 0,
                    "display_cleaned": False,
                }
            )
    return {
        "redaction_enabled": True,
        "redaction_token": REDACTED,
        "redaction_patterns": REDACTION_PATTERNS,
        "display_cleanup": DISPLAY_CLEANUP,
        "logs": logs,
    }
