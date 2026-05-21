from __future__ import annotations

from pathlib import Path

from ..config import RUNTIME_DIR
from ..shared.contracts import RUNTIME_REF_PREFIX


def runtime_ref_to_path(raw_ref: str) -> Path:
    if not raw_ref.startswith(RUNTIME_REF_PREFIX):
        raise ValueError("only runtime:// raw refs can be extracted")
    relative = raw_ref[len(RUNTIME_REF_PREFIX):].replace("/", "\\")
    path = (RUNTIME_DIR / relative).resolve()
    runtime_root = RUNTIME_DIR.resolve()
    if runtime_root not in path.parents and path != runtime_root:
        raise ValueError("raw ref escapes runtime directory")
    return path
