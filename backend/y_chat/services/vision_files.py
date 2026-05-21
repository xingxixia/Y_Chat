from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from .runtime_refs import runtime_ref_to_path


def image_data_url(path: Path, mime: str) -> str:
    media_type = mime or mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{data}"
