from __future__ import annotations

from typing import Any

from .config import RUNTIME_DIR


LOG_DIR = RUNTIME_DIR / "logs"


def log_status_payload() -> dict[str, Any]:
    logs: list[dict[str, Any]] = []
    if not LOG_DIR.exists():
        return {"logs": logs}

    for path in sorted(LOG_DIR.glob("*.log"), key=lambda item: item.name.lower()):
        kind = "error" if ".err." in path.name else "output"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tail = text.splitlines()[-8:]
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
